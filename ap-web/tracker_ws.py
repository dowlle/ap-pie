"""FEAT-17: real-time AP MultiServer WebSocket tracker.

V0 (this commit) - infrastructure only. Spawns one persistent WebSocket
connection per active room, populates an in-memory TrackerState, exposes
state via TrackerManager.get_state(room_id). Does NOT yet feed the
`room_tracker` API endpoints - those still use the HTML scrape. Wiring
happens in V1 once V0 has soaked.

Design (full plan at vault `Product/2026-05-02 - FEAT-17 Real-Time
Tracker Architecture.md`):

- One background thread owns an asyncio event loop. Spawned in
  `app.create_app()` after DB init.
- One `TrackerConnection` per room with `tracker_url IS NOT NULL` and
  `status = 'open'`. Lifecycle managed by `TrackerManager`.
- Connection uses `wss://` first (TLS-fronted on archipelago.gg), falls
  back to `ws://` on InvalidMessage. Mirrors CommonClient.py:server_loop.
- Connect packet: `tags=["Tracker"]`, `game=""`, `items_handling=0`.
  Server bypasses per-slot game-version check for tagged tracker
  connections (MultiServer.py:1874).
- Slot name for connection: prefer the host's own slot (match
  `room_yamls.submitter_user_id == room.host_user_id`); fall back to
  scraping one slot name from the tracker page.
- Idle disconnect: any connection with no incoming packets for
  AP_TRACKER_IDLE_MINUTES (default 60) gets cancelled. Reconnect lazily
  on the next API read for that room.
- Connection cap: AP_TRACKER_WS_MAX (default 200). Cap-exceeded rooms
  silently fall back to HTML scrape.

Thread safety: TrackerState fields are mutated only on the asyncio loop.
Cross-thread reads acquire a per-state RLock briefly. Outer manager dicts
use a separate RLock.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import ssl
import threading
import time
import urllib.request
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

import websockets

import config
import datapackage_cache

logger = logging.getLogger("tracker_ws")
# Python's default logging config has no handlers attached to user loggers,
# so logger.info() goes nowhere - invisible in `docker logs`. Attach a
# StreamHandler unless something upstream already configured the root.
if not logger.handlers and not logging.getLogger().handlers:
    _stream_handler = logging.StreamHandler()
    _stream_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(name)s %(levelname)s: %(message)s"
    ))
    logger.addHandler(_stream_handler)
logger.setLevel(logging.INFO)


# AP MultiServer client status codes (NetUtils.ClientStatus)
_STATUS_LABELS = {
    0: "unknown",
    5: "ready",
    10: "playing",
    20: "connected",
    30: "goal",
}

# Version we report in the Connect packet. Must be >= the server's
# minimum_client_versions floor; 0.5.0 is well above the long tail.
_CLIENT_VERSION = {"major": 0, "minor": 5, "build": 0, "class": "Version"}


# ── State ────────────────────────────────────────────────────────────


@dataclass
class TrackerState:
    """In-memory tracker state for one room. Mutated only on the asyncio
    loop; cross-thread reads acquire `lock` briefly."""
    room_id: str
    tracker_url: str
    host: str
    port: int
    slot_name: str
    own_slot: int = 0
    own_team: int = 0
    seed_name: str = ""
    server_version: tuple = (0, 0, 0)
    games: list[str] = field(default_factory=list)
    # slot -> {"name": str, "game": str, "type": int, "group_members": list[int]}
    slot_info: dict[int, dict[str, Any]] = field(default_factory=dict)
    # slot -> {"team": int, "alias": str, "name": str}
    players: dict[int, dict[str, Any]] = field(default_factory=dict)
    # slot -> set of checked location IDs
    checked_locations: dict[int, set[int]] = field(default_factory=dict)
    # OUR slot only (server only sends missing for the connected slot)
    own_missing_locations: set[int] = field(default_factory=set)
    # slot -> int (ClientStatus from _read_client_status_<team>_<slot>)
    client_status: dict[int, int] = field(default_factory=dict)
    # slot -> int (cumulative locations count, derived from RoomInfo or
    # observed via slot_info). For slots other than ours we don't know
    # the exact total without explicit data - left empty in V0; V1 will
    # populate via DataPackage or LocationScouts as needed.
    locations_total: dict[int, int] = field(default_factory=dict)
    # V1.1: game name -> checksum from RoomInfo. Used to look the game up
    # in datapackage_cache when resolving item / location IDs to names.
    datapackage_checksums: dict[str, str] = field(default_factory=dict)
    # V1.2: slot -> list of Hint dicts (from `_read_hints_<team>_<slot>`)
    hints: dict[int, list[dict]] = field(default_factory=dict)
    # V1.5: bounded ring buffer of recent PrintJSON events. Capped at 200
    # - enough to surface a meaningful activity panel, small enough to
    # not balloon memory across hundreds of rooms. JSON-serialisable.
    activity: deque = field(default_factory=lambda: deque(maxlen=200))
    last_packet_at: float = 0.0
    connected_at: float = 0.0
    state: str = "init"  # init -> connecting -> connected -> closed -> error
    last_error: Optional[str] = None
    packet_counts: dict[str, int] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def snapshot(self) -> dict[str, Any]:
        """Render a thread-safe JSON-serialisable summary. Used by the
        debug endpoint and (V1) by the room_tracker API."""
        with self.lock:
            return {
                "room_id": self.room_id,
                "host": self.host,
                "port": self.port,
                "slot_name": self.slot_name,
                "own_slot": self.own_slot,
                "own_team": self.own_team,
                "seed_name": self.seed_name,
                "server_version": list(self.server_version),
                "state": self.state,
                "last_error": self.last_error,
                "connected_at": self.connected_at,
                "last_packet_at": self.last_packet_at,
                "seconds_since_packet": (time.time() - self.last_packet_at) if self.last_packet_at else None,
                "games_count": len(self.games),
                "slot_count": len(self.slot_info),
                "players_count": len(self.players),
                "slots_with_checks": sum(1 for s in self.checked_locations.values() if s),
                "total_checks_observed": sum(len(s) for s in self.checked_locations.values()),
                "own_missing_count": len(self.own_missing_locations),
                "packet_counts": dict(self.packet_counts),
                # V1.1: how much of the room's DataPackage we've already cached.
                # `cached_count` walks the disk cache so it stays correct even
                # after a worker restart picked up a pre-warmed `.state/`.
                "datapackage_games_total": len(self.datapackage_checksums),
                "datapackage_games_cached": datapackage_cache.cached_count(self.datapackage_checksums),
                # V1.2: hints-by-slot total (across all subscribed slots)
                "hints_count": sum(len(h) for h in self.hints.values()),
                "slots_with_hints": sum(1 for h in self.hints.values() if h),
                # V1.5: activity buffer depth (capped at 200 by the deque)
                "activity_count": len(self.activity),
            }


# ── Connection ───────────────────────────────────────────────────────


class TrackerConnection:
    """One persistent connection to one AP server room.

    Owns its TrackerState. Run via `await connection.run()` on the asyncio
    loop. Reconnects with exponential backoff up to MAX_BACKOFF on
    transient failure. Stops cleanly when `stop()` is called.
    """

    INITIAL_BACKOFF = 5.0
    MAX_BACKOFF = 300.0  # 5 min cap so dead rooms don't hammer

    def __init__(
        self,
        room_id: str,
        tracker_url: str,
        host: str,
        port: int,
        slot_name: str,
    ) -> None:
        self.state = TrackerState(
            room_id=room_id,
            tracker_url=tracker_url,
            host=host,
            port=port,
            slot_name=slot_name,
        )
        self._stop_event = asyncio.Event()
        self._socket: Optional[websockets.WebSocketClientProtocol] = None
        self._backoff = self.INITIAL_BACKOFF
        # Stable UUID per (room_id, slot_name) so reconnects show as the
        # same client in the activity log instead of a new join each time.
        self._uuid = str(uuid.uuid5(
            uuid.NAMESPACE_URL, f"ap-pie:{room_id}:{slot_name}",
        ))

    def stop(self) -> None:
        self._stop_event.set()
        # Closing the socket from outside the loop is intentional -
        # asyncio.run_coroutine_threadsafe would be cleaner but stop() is
        # called from the asyncio loop itself or after it shuts down.

    async def run(self) -> None:
        """Connect-loop forever (until stop). Each iteration is one
        connection attempt + handler loop. Reconnect with backoff on
        failure. Backoff resets on successful connect."""
        while not self._stop_event.is_set():
            try:
                await self._connect_and_run()
                self._backoff = self.INITIAL_BACKOFF
            except asyncio.CancelledError:
                logger.info(f"FEAT-17 [{self.state.room_id}] cancelled")
                raise
            except Exception as e:
                logger.warning(
                    f"FEAT-17 [{self.state.room_id}] connection error: "
                    f"{type(e).__name__}: {e}"
                )
                with self.state.lock:
                    self.state.state = "error"
                    self.state.last_error = f"{type(e).__name__}: {e}"
            if self._stop_event.is_set():
                break
            wait = min(self._backoff, self.MAX_BACKOFF)
            logger.info(
                f"FEAT-17 [{self.state.room_id}] reconnecting in {wait:.0f}s"
            )
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=wait)
                break  # stop signalled
            except asyncio.TimeoutError:
                pass
            self._backoff = min(self._backoff * 2, self.MAX_BACKOFF)
        with self.state.lock:
            self.state.state = "closed"

    async def _connect_and_run(self) -> None:
        with self.state.lock:
            self.state.state = "connecting"
            self.state.last_error = None
        # wss-first then ws fallback (game ports are TLS-fronted on
        # archipelago.gg; CommonClient.py uses the same fallback shape).
        for scheme in ("wss", "ws"):
            address = f"{scheme}://{self.state.host}:{self.state.port}"
            try:
                ssl_ctx = ssl.create_default_context() if scheme == "wss" else None
                self._socket = await websockets.connect(
                    address,
                    ping_timeout=None,
                    ping_interval=None,
                    ssl=ssl_ctx,
                    max_size=2**24,  # 16 MB; the Connected packet is ~200 KB for big rooms
                )
                logger.info(
                    f"FEAT-17 [{self.state.room_id}] connected via {scheme}://"
                )
                break
            except (websockets.InvalidMessage, ssl.SSLError, OSError) as e:
                logger.debug(
                    f"FEAT-17 [{self.state.room_id}] {scheme}:// failed: "
                    f"{type(e).__name__}: {e}"
                )
                self._socket = None
                continue
        if self._socket is None:
            raise RuntimeError(
                f"all schemes failed for {self.state.host}:{self.state.port}"
            )
        try:
            with self.state.lock:
                self.state.state = "connected"
                self.state.connected_at = time.time()
            await self._loop()
        finally:
            try:
                await self._socket.close()
            except Exception:
                pass
            self._socket = None

    async def _loop(self) -> None:
        async for raw in self._socket:
            now = time.time()
            try:
                msgs = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"FEAT-17 [{self.state.room_id}] bad packet: {e}"
                )
                continue
            for msg in msgs:
                cmd = msg.get("cmd", "?")
                with self.state.lock:
                    self.state.last_packet_at = now
                    self.state.packet_counts[cmd] = (
                        self.state.packet_counts.get(cmd, 0) + 1
                    )
                await self._handle(cmd, msg)
            if self._stop_event.is_set():
                break

    async def _handle(self, cmd: str, msg: dict) -> None:
        if cmd == "RoomInfo":
            await self._on_room_info(msg)
        elif cmd == "Connected":
            await self._on_connected(msg)
        elif cmd == "ConnectionRefused":
            errors = msg.get("errors", [])
            logger.warning(
                f"FEAT-17 [{self.state.room_id}] connection refused: {errors}"
            )
            with self.state.lock:
                self.state.last_error = f"refused: {errors}"
            # Don't infinite-retry on hard auth errors
            if any(e in errors for e in ("InvalidSlot", "InvalidGame", "IncompatibleVersion")):
                self._stop_event.set()
        elif cmd == "RoomUpdate":
            self._on_room_update(msg)
        elif cmd == "Retrieved":
            self._on_retrieved(msg)
        elif cmd == "SetReply":
            # V1.2: pushes for keys we subscribed to via SetNotify. Same
            # shape as one entry of Retrieved.keys (key + value), so reuse
            # the parser.
            self._on_set_reply(msg)
        elif cmd == "PrintJSON":
            # V1.3 + V1.5: parse for ItemSend attribution + activity stream
            self._on_print_json(msg)
        elif cmd == "ReceivedItems":
            # V0/V1: items received for OUR slot only - server only sends
            # this to the slot's own connections. Other slots' items remain
            # invisible from a single Tracker connection (Design C in arch
            # doc keeps the HTML scrape fallback for that surface).
            pass
        elif cmd == "DataPackage":
            # V1.1: cache by (game, checksum) for runtime name resolution.
            self._on_data_package(msg)
        # Other packet types (LocationInfo, Bounced, InvalidPacket, Print)
        # get counted in packet_counts but otherwise ignored.

    async def _on_room_info(self, msg: dict) -> None:
        with self.state.lock:
            v = msg.get("version") or {}
            self.state.server_version = (
                int(v.get("major", 0)),
                int(v.get("minor", 0)),
                int(v.get("build", 0)),
            )
            self.state.seed_name = msg.get("seed_name", "")
            self.state.games = list(msg.get("games", []))
            # V1.1: capture per-game checksums so we can ask the server
            # for the games we don't have cached, and so PrintJSON parsing
            # can resolve item / location IDs to names later.
            self.state.datapackage_checksums = dict(
                msg.get("datapackage_checksums") or {}
            )

        # V1.1: GetDataPackage for any games whose (name, checksum) pair
        # isn't already on disk. The May Async (~150 games) might fetch a
        # 2-3 MB DataPackage on first connect - paid once, reused forever.
        missing = datapackage_cache.missing_games(self.state.datapackage_checksums)
        if missing:
            logger.info(
                f"FEAT-17 [{self.state.room_id}] GetDataPackage for "
                f"{len(missing)} game(s) not cached"
            )
            await self._send([{"cmd": "GetDataPackage", "games": missing}])
        else:
            logger.info(
                f"FEAT-17 [{self.state.room_id}] DataPackage fully cached "
                f"({len(self.state.datapackage_checksums)} game(s))"
            )

        # Send Connect immediately
        connect = {
            "cmd": "Connect",
            "password": "",
            "name": self.state.slot_name,
            "version": _CLIENT_VERSION,
            "tags": ["Tracker"],
            "items_handling": 0,
            "uuid": self._uuid,
            "game": "",
            "slot_data": False,
        }
        logger.info(
            f"FEAT-17 [{self.state.room_id}] sending Connect (slot='{self.state.slot_name}')"
        )
        await self._send([connect])

    async def _on_connected(self, msg: dict) -> None:
        with self.state.lock:
            self.state.own_team = int(msg.get("team", 0))
            self.state.own_slot = int(msg.get("slot", 0))
            # players is a list of NetworkPlayer dicts
            for p in msg.get("players", []):
                slot_id = int(p.get("slot", 0))
                self.state.players[slot_id] = {
                    "team": int(p.get("team", 0)),
                    "alias": p.get("alias", ""),
                    "name": p.get("name", ""),
                }
            # slot_info is dict[str_slot, NetworkSlot]
            for sid_str, info in msg.get("slot_info", {}).items():
                try:
                    sid = int(sid_str)
                except (TypeError, ValueError):
                    continue
                self.state.slot_info[sid] = {
                    "name": info.get("name", ""),
                    "game": info.get("game", ""),
                    "type": int(info.get("type", 1)),
                    "group_members": list(info.get("group_members", [])),
                }
            # Our slot's missing/checked locations
            self.state.own_missing_locations = set(msg.get("missing_locations", []))
            for loc in msg.get("checked_locations", []):
                self.state.checked_locations.setdefault(self.state.own_slot, set()).add(int(loc))
        logger.info(
            f"FEAT-17 [{self.state.room_id}] Connected: own_slot={self.state.own_slot}, "
            f"slot_count={len(self.state.slot_info)}, "
            f"own_missing={len(self.state.own_missing_locations)}"
        )

        # V1.2: subscribe to per-slot hints + client_status. Single base
        # connection + Get/SetNotify lets us track ALL slots' hints +
        # status from ONE WebSocket - see arch doc 2026-05-02 Phase 1
        # spike findings.
        #
        # Skip group/itemlink slots (type 2): they have no client_status
        # and their hints flow through the player slots that own them.
        team = self.state.own_team
        keys: list[str] = []
        with self.state.lock:
            for slot_id, info in self.state.slot_info.items():
                if info.get("type") == 2:
                    continue
                keys.append(f"_read_hints_{team}_{slot_id}")
                keys.append(f"_read_client_status_{team}_{slot_id}")
        if keys:
            # Get prefills the cache with current values; SetNotify makes
            # the server push SetReply on every subsequent change. Two
            # separate packets so a partial Get failure doesn't take down
            # the subscription.
            await self._send([{"cmd": "Get", "keys": keys}])
            await self._send([{"cmd": "SetNotify", "keys": keys}])
            logger.info(
                f"FEAT-17 [{self.state.room_id}] subscribed to "
                f"{len(keys)} keys ({len(keys) // 2} slots × 2)"
            )

    def _on_room_update(self, msg: dict) -> None:
        with self.state.lock:
            # V1.3 fix: RoomUpdate `checked_locations` is sent ONLY to the
            # connected slot's clients (MultiServer.update_checked_locations
            # broadcasts to ctx.clients[team][slot] - see lines 1085-1087).
            # So this list is OUR own slot's checked locations, not global.
            # V0 lumped these into slot 0 - fixed: attribute to own_slot.
            # Other slots' check attribution flows in via PrintJSON ItemSend
            # (see _on_print_json).
            for loc in msg.get("checked_locations", []):
                self.state.checked_locations.setdefault(
                    self.state.own_slot, set()
                ).add(int(loc))
            # hint_points roll-up per the connected slot
            if "hint_points" in msg:
                self.state.client_status[self.state.own_slot] = self.state.client_status.get(
                    self.state.own_slot, 0
                )

    def _on_retrieved(self, msg: dict) -> None:
        """V1.2: handle the bulk Get response - populates hints + status
        for all subscribed slots in one shot."""
        keys = msg.get("keys") or {}
        for key, value in keys.items():
            self._apply_read_key(key, value)

    def _on_set_reply(self, msg: dict) -> None:
        """V1.2: handle a single SetNotify push. SetReply shape mirrors
        a single key/value pair from Retrieved.keys - same handler."""
        self._apply_read_key(msg.get("key", ""), msg.get("value"))

    def _apply_read_key(self, key: str, value: Any) -> None:
        """Dispatch a `_read_*` key/value to the right field on TrackerState.
        Handles the keys we subscribed to in _on_connected:
          - `_read_hints_<team>_<slot>` → list of Hint dicts
          - `_read_client_status_<team>_<slot>` → int (ClientStatus 0..30)
        Other `_read_*` keys are ignored (we don't subscribe to them yet).
        """
        if not key:
            return
        with self.state.lock:
            if key.startswith("_read_hints_"):
                tail = key[len("_read_hints_"):]
                slot_id = _parse_slot_from_tail(tail)
                if slot_id is not None:
                    self.state.hints[slot_id] = list(value or [])
            elif key.startswith("_read_client_status_"):
                tail = key[len("_read_client_status_"):]
                slot_id = _parse_slot_from_tail(tail)
                if slot_id is not None:
                    try:
                        self.state.client_status[slot_id] = int(value or 0)
                    except (ValueError, TypeError):
                        pass

    def _on_data_package(self, msg: dict) -> None:
        """V1.1: receive the GetDataPackage response and persist each
        game's name maps to the disk cache so future runtime resolves are
        free."""
        games = (msg.get("data") or {}).get("games") or {}
        if not games:
            return
        cached = 0
        with self.state.lock:
            for game_name, game_data in games.items():
                # Prefer the checksum from RoomInfo (canonical for THIS
                # server); fall back to whatever's in the packet body.
                checksum = (
                    self.state.datapackage_checksums.get(game_name)
                    or (game_data or {}).get("checksum")
                    or ""
                )
                if not checksum:
                    continue
                datapackage_cache.store(game_name, checksum, game_data)
                cached += 1
        logger.info(
            f"FEAT-17 [{self.state.room_id}] cached DataPackage for "
            f"{cached}/{len(games)} game(s)"
        )

    def _on_print_json(self, msg: dict) -> None:
        """V1.3 + V1.5: parse PrintJSON for ItemSend attribution and the
        activity ring buffer.

        ItemSend events carry the structured `item: NetworkItem` field -
        `item.player` is the slot that found the location, `item.location`
        is the location id. That's the canonical per-slot check
        attribution path (server only sends RoomUpdate.checked_locations
        to the slot itself, so we can't get other slots' check sets any
        other way from a single base connection).

        Activity buffer renders a human-readable summary string by walking
        `data: list[JSONMessagePart]` and resolving item / location / player
        IDs via the DataPackage cache.
        """
        type_ = msg.get("type") or "Unknown"

        # V1.3: per-slot location attribution via ItemSend.item.player.
        # Only ItemSend carries item/location attribution; other PrintJSON
        # types (Chat, Join, Goal, etc.) don't.
        if type_ == "ItemSend":
            item = msg.get("item") or {}
            try:
                finder_slot = int(item.get("player", 0))
                location_id = int(item.get("location", -1))
            except (TypeError, ValueError):
                finder_slot, location_id = 0, -1
            if finder_slot > 0 and location_id >= 0:
                with self.state.lock:
                    self.state.checked_locations.setdefault(
                        finder_slot, set()
                    ).add(location_id)

        # V1.5: render both a flat human-readable text AND a typed-parts
        # array, append to the activity buffer. Frontend uses `parts` for
        # Archipelago-style colour coding (progression/useful/filler/trap
        # for items, green for locations, yellow for players); `text`
        # stays as a fallback / for filter substring matching. Resolution
        # uses the DataPackage cache; falls back to "Item #N" / etc. if
        # unresolved (cache cold or unknown game).
        text, parts = self._render_print_json(msg.get("data") or [])
        event = {
            "ts": time.time(),
            "type": type_,
            "text": text,
            "parts": parts,
            "tags": list(msg.get("tags") or []),
            "team": msg.get("team"),
            "slot": msg.get("slot"),
            "receiving": msg.get("receiving"),
            "item": msg.get("item"),  # finder slot / location / flags / item_id
            "found": msg.get("found"),  # for Hint events
        }
        with self.state.lock:
            self.state.activity.append(event)

    def _render_print_json(self, parts: list) -> tuple[str, list[dict]]:
        """Walk JSONMessageParts, resolve typed parts via DataPackage cache.

        Returns `(flat_text, structured_parts)`:
          - `flat_text`: concatenated resolved string. Used for substring
            filter matching and as a fallback render.
          - `structured_parts`: list of `{kind, text, ...}` dicts. The
            frontend uses these to apply Archipelago-standard colours per
            segment type (item flags, location, player, etc.). `kind` is
            our normalised name, distinct from the wire `type` so future
            renames don't break clients.

        Part kinds emitted:
          - {"kind": "text", "text": "..."}                    plain run
          - {"kind": "item", "text": "...", "flags": int}      resolved item
          - {"kind": "location", "text": "..."}                resolved location
          - {"kind": "player", "text": "...", "slot": int}     resolved player
          - {"kind": "entrance", "text": "..."}                entrance label
        """
        flat: list[str] = []
        structured: list[dict] = []

        def emit(kind: str, text: str, **extra) -> None:
            text = str(text)
            flat.append(text)
            part = {"kind": kind, "text": text}
            part.update(extra)
            structured.append(part)

        for p in parts:
            if not isinstance(p, dict):
                emit("text", p)
                continue
            ptype = p.get("type", "text")
            text = p.get("text", "")
            if ptype == "item_id":
                # text is the item id as a string. `player` is the slot that
                # OWNS this item (i.e. the slot whose game we resolve against).
                try:
                    item_id = int(text)
                    owner_slot = int(p.get("player", 0))
                except (TypeError, ValueError):
                    emit("text", text)
                    continue
                game = self._slot_game(owner_slot)
                checksum = self.state.datapackage_checksums.get(game, "")
                resolved = datapackage_cache.resolve_item(game, checksum, item_id)
                # Flags arrive on the part itself (per JSONMessagePart spec)
                # OR on the parent ItemSend's `item` field. Preserve here so
                # the frontend can colour per-progression / useful / filler /
                # trap classification.
                try:
                    flags = int(p.get("flags", 0) or 0)
                except (TypeError, ValueError):
                    flags = 0
                emit("item", resolved, flags=flags)
            elif ptype == "item_name":
                # Already resolved item name. Flags may still be present.
                try:
                    flags = int(p.get("flags", 0) or 0)
                except (TypeError, ValueError):
                    flags = 0
                emit("item", text, flags=flags)
            elif ptype == "location_id":
                try:
                    loc_id = int(text)
                    owner_slot = int(p.get("player", 0))
                except (TypeError, ValueError):
                    emit("text", text)
                    continue
                game = self._slot_game(owner_slot)
                checksum = self.state.datapackage_checksums.get(game, "")
                emit("location", datapackage_cache.resolve_location(game, checksum, loc_id))
            elif ptype == "location_name":
                emit("location", text)
            elif ptype == "player_id":
                try:
                    slot_id = int(text)
                except (TypeError, ValueError):
                    emit("text", text)
                    continue
                player = self.state.players.get(slot_id) or {}
                resolved = (
                    player.get("alias") or player.get("name") or f"Slot {slot_id}"
                )
                emit("player", resolved, slot=slot_id)
            elif ptype == "player_name":
                emit("player", text)
            elif ptype == "entrance_name":
                emit("entrance", text)
            elif ptype == "color":
                # Drop the colour wrapping, keep the text content
                emit("text", text)
            else:
                emit("text", text)

        return "".join(flat), structured

    def _slot_game(self, slot_id: int) -> str:
        info = self.state.slot_info.get(slot_id) or {}
        return info.get("game", "")

    async def _send(self, msgs: list[dict]) -> None:
        if self._socket is None:
            return
        await self._socket.send(json.dumps(msgs))


def _parse_slot_from_tail(tail: str) -> Optional[int]:
    """Pull the slot int from the tail of a `_read_*_<team>_<slot>` key.
    Tail looks like `<team>_<slot>` - split on `_`, last segment is slot."""
    parts = tail.split("_")
    if len(parts) < 2:
        return None
    try:
        return int(parts[-1])
    except (TypeError, ValueError):
        return None


# ── Manager ──────────────────────────────────────────────────────────


class TrackerManager:
    """Owns the asyncio loop + all TrackerConnections. Thread-safe API.

    Lifecycle: `start()` spawns the background thread. `stop()` cancels
    everything and joins. `schedule(...)` from any thread queues a new
    connection. `get_state(room_id)` returns the live TrackerState (or
    None if no connection exists for this room) - read-only access; the
    state's `.lock` should be acquired for multi-field reads but
    `.snapshot()` handles that internally.
    """

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._connections: dict[str, TrackerConnection] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = threading.RLock()
        self._started = threading.Event()
        self._max = max(1, getattr(config, "TRACKER_WS_MAX", 200))
        self._idle_minutes = max(
            5, getattr(config, "TRACKER_WS_IDLE_MINUTES", 60)
        )

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run_loop, name="tracker-ws", daemon=True,
        )
        self._thread.start()
        # Block briefly until the loop is up so callers can immediately
        # schedule connections.
        self._started.wait(timeout=5)
        logger.info(
            f"FEAT-17 TrackerManager started (max={self._max}, idle={self._idle_minutes}min)"
        )

    def stop(self) -> None:
        if self._loop is None:
            return
        loop = self._loop
        loop.call_soon_threadsafe(loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        self._loop = None

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        # Periodic idle sweep
        self._loop.create_task(self._idle_sweep())
        self._started.set()
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    async def _idle_sweep(self) -> None:
        while True:
            await asyncio.sleep(60)
            cutoff = time.time() - self._idle_minutes * 60
            to_close: list[str] = []
            with self._lock:
                for rid, conn in self._connections.items():
                    last = conn.state.last_packet_at
                    if last and last < cutoff:
                        to_close.append(rid)
            for rid in to_close:
                logger.info(
                    f"FEAT-17 [{rid}] idle > {self._idle_minutes}min, closing"
                )
                self._cancel(rid)

    def schedule(
        self,
        room_id: str,
        tracker_url: str,
        host: str,
        port: int,
        slot_name: str,
    ) -> bool:
        """Thread-safe: queue a connection on the asyncio loop. Returns
        True if scheduled, False if already running or capped."""
        if self._loop is None:
            logger.warning("FEAT-17 schedule called before start()")
            return False
        with self._lock:
            if room_id in self._connections:
                return False
            if len(self._connections) >= self._max:
                logger.warning(
                    f"FEAT-17 [{room_id}] cap {self._max} reached, declining"
                )
                return False
        self._loop.call_soon_threadsafe(
            self._do_schedule, room_id, tracker_url, host, port, slot_name,
        )
        return True

    def _do_schedule(
        self, room_id: str, tracker_url: str, host: str, port: int, slot_name: str,
    ) -> None:
        """Runs on the asyncio loop."""
        if room_id in self._connections:
            return
        conn = TrackerConnection(room_id, tracker_url, host, port, slot_name)
        task = asyncio.create_task(conn.run(), name=f"tracker-{room_id}")
        with self._lock:
            self._connections[room_id] = conn
            self._tasks[room_id] = task
        task.add_done_callback(lambda t, rid=room_id: self._on_done(rid))

    def _on_done(self, room_id: str) -> None:
        with self._lock:
            self._connections.pop(room_id, None)
            self._tasks.pop(room_id, None)

    def cancel(self, room_id: str) -> None:
        """Thread-safe: cancel a connection."""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._cancel, room_id)

    def reschedule(
        self,
        room_id: str,
        tracker_url: str,
        host: str,
        port: int,
        slot_name: str,
    ) -> bool:
        """Thread-safe: cancel any existing connection for room_id, wait
        for cleanup, then schedule a fresh one with the new params.

        Used when room settings change (slot override, tracker URL, host,
        port) - we want the in-memory connection to reflect the new
        config without an app restart."""
        if self._loop is None:
            return False
        asyncio.run_coroutine_threadsafe(
            self._reschedule_async(room_id, tracker_url, host, port, slot_name),
            self._loop,
        )
        return True

    async def _reschedule_async(
        self,
        room_id: str,
        tracker_url: str,
        host: str,
        port: int,
        slot_name: str,
    ) -> None:
        with self._lock:
            old_task = self._tasks.get(room_id)
            old_conn = self._connections.get(room_id)
        if old_conn is not None:
            old_conn.stop()
        if old_task is not None and not old_task.done():
            old_task.cancel()
            try:
                await old_task
            except (asyncio.CancelledError, Exception):
                pass
        # _on_done callback should have removed the entry by now, but
        # double-check defensively before scheduling fresh.
        with self._lock:
            self._connections.pop(room_id, None)
            self._tasks.pop(room_id, None)
        self._do_schedule(room_id, tracker_url, host, port, slot_name)

    def _cancel(self, room_id: str) -> None:
        with self._lock:
            conn = self._connections.get(room_id)
            task = self._tasks.get(room_id)
        if conn:
            conn.stop()
        if task and not task.done():
            task.cancel()

    def get_state(self, room_id: str) -> Optional[TrackerState]:
        with self._lock:
            conn = self._connections.get(room_id)
        return conn.state if conn else None

    def list_states(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            conns = list(self._connections.items())
        return {rid: c.state.snapshot() for rid, c in conns}


# Module-level singleton - wired up in app.create_app()
manager = TrackerManager()


# ── Bootstrap helpers ────────────────────────────────────────────────


def discover_slot_name(
    room_id: str,
    host_user_id: Optional[int],
    explicit_override: Optional[str] = None,
) -> Optional[str]:
    """Pick a slot name to connect as.

    Precedence:
    1. `explicit_override` (rooms.tracker_slot_name) - host's deliberate
       choice, always wins. Stripped + nulled if blank.
    2. Host's own slot via room_yamls.submitter_user_id == host_user_id
       (first-uploaded match).
    3. (caller falls back to scraping the first slot from the tracker page)
    """
    if explicit_override and explicit_override.strip():
        return explicit_override.strip()
    from db import get_yamls
    if host_user_id is not None:
        try:
            yamls = get_yamls(room_id)
            for y in yamls:
                if y.get("submitter_user_id") == host_user_id:
                    return y.get("player_name")
        except Exception as e:
            logger.warning(
                f"FEAT-17 [{room_id}] host-slot lookup failed: {e}"
            )
    return None


def scrape_first_slot_name(tracker_url: str) -> Optional[str]:
    """Scrape the first slot name from the tracker landing page. Used as
    fallback when we can't match the host's slot via room_yamls.

    SEC: validates the URL scheme/host before fetching. urllib honours
    `file://` natively, so without this guard a tracker_url of
    `file:///etc/passwd` would be read off disk before parsing failed.
    Reported by Eijebong 2026-05-04.
    """
    from tracker import is_safe_tracker_url
    if not is_safe_tracker_url(tracker_url):
        logger.warning(
            f"FEAT-17 slot scrape rejected unsafe tracker_url: "
            f"{tracker_url[:80]!r}"
        )
        return None
    try:
        with urllib.request.urlopen(tracker_url, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        start = html.find('id="checks-table"')
        if start < 0:
            return None
        end = html.find("</table>", start)
        table = html[start:end] if end > 0 else html[start:]
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL)
        import html as _html
        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
            if len(cells) < 2:
                continue
            name = _html.unescape(re.sub(r"<[^>]+>", "", cells[1]).strip())
            if name:
                return name
    except Exception as e:
        logger.warning(f"FEAT-17 slot scrape failed: {e}")
    return None


def bootstrap_from_db() -> int:
    """Scan rooms with a tracker_url + an external host:port + status=open,
    schedule a TrackerConnection for each. Called at app startup.

    Returns the count of rooms scheduled."""
    from db import _db_url, _get_conn, _dictrow
    if _db_url is None:
        logger.info("FEAT-17 bootstrap skipped: no DB")
        return 0
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            # Status filter intentionally LOOSE - Archipelago Pie's `status` tracks
            # the submission lifecycle (open/closed/generated/playing/...);
            # the AP server keeps running long after submissions close,
            # which is exactly when the live tracker is most valuable.
            # The idle-sweep handles dead servers via packet timeout, so
            # we can safely include all non-deleted rooms.
            cur.execute(
                """SELECT id, tracker_url, external_host, external_port,
                          host_user_id, status, tracker_slot_name
                   FROM rooms
                   WHERE tracker_url IS NOT NULL
                     AND external_host IS NOT NULL
                     AND external_port IS NOT NULL
                     AND COALESCE(status, '') != 'deleted'"""
            )
            rooms = _dictrow(cur)
    except Exception as e:
        logger.warning(f"FEAT-17 bootstrap query failed: {e}")
        return 0

    scheduled = 0
    for r in rooms:
        room_id = r["id"]
        slot_name = discover_slot_name(
            room_id, r.get("host_user_id"), r.get("tracker_slot_name"),
        )
        if not slot_name:
            slot_name = scrape_first_slot_name(r["tracker_url"])
        if not slot_name:
            logger.warning(
                f"FEAT-17 [{room_id}] no usable slot name, skipping bootstrap"
            )
            continue
        ok = manager.schedule(
            room_id=room_id,
            tracker_url=r["tracker_url"],
            host=r["external_host"],
            port=int(r["external_port"]),
            slot_name=slot_name,
        )
        if ok:
            scheduled += 1
    logger.info(f"FEAT-17 bootstrap: scheduled {scheduled} connection(s)")
    return scheduled


# ── V1.4: endpoint augmentation helpers ─────────────────────────────
#
# These let api/rooms.py + api/public.py merge live WebSocket data into
# the HTML-scrape-shaped responses without reorganising the data flow.
# The HTML scrape stays as the source of truth for per-slot totals
# (checks_total, full locations list, items_received) - Design C from the
# arch doc - and WS data overlays the parts where it has a real edge:
# real-time client_status and (for the slot detail) richer hints.


# Map AP `client_status` ints → label string + goal-completed flag, mirror
# the same shape `_status_label_from_int` builds in api/rooms.py for HTML
# scrape data so the frontend sees a consistent vocabulary regardless of
# which source filled the field.
def _ws_status_label(status: int, has_checks: bool) -> tuple[str, bool]:
    """Map AP `client_status` ints to one of four labels matching the
    archipelago.gg tracker page vocabulary: connected / playing /
    disconnected / goal_completed. AP's CLIENT_READY (10) folds into
    "playing" and CLIENT_UNKNOWN (0) renders as "connected" when we've
    seen check activity, otherwise "disconnected"."""
    if status >= 30:
        return "goal_completed", True   # CLIENT_GOAL
    if status >= 20:
        return "playing", False         # CLIENT_PLAYING
    if status >= 10:
        return "playing", False         # CLIENT_READY folds into Playing
    if status >= 5:
        return "connected", False       # CLIENT_CONNECTED
    return ("connected", False) if has_checks else ("disconnected", False)


def grid_overrides(room_id: str) -> Optional[dict[int, dict]]:
    """Return per-slot overrides for the LiveTracker grid endpoint.

    Shape: `{slot_id: {"client_status": int, "status_label": str,
    "goal_completed": bool, "ws_observed_checks": int}}`. Caller merges
    these on top of the HTML-scrape-derived player records to surface
    fresh status without waiting on the next 30s scrape window.

    Returns None when no WS connection exists or it's not yet connected
    - in that case the caller should just return the HTML scrape as-is.
    """
    state = manager.get_state(room_id)
    if state is None or state.state != "connected":
        return None
    out: dict[int, dict] = {}
    with state.lock:
        for slot_id in state.slot_info:
            status = int(state.client_status.get(slot_id, 0))
            checked = state.checked_locations.get(slot_id) or set()
            label, goal = _ws_status_label(status, bool(checked))
            out[slot_id] = {
                "client_status": status,
                "status_label": label,
                "goal_completed": goal,
                # `ws_observed_checks` is a partial counter - for non-own
                # slots it's only what we've seen via PrintJSON since
                # connect, NOT the absolute total. Caller decides whether
                # to surface it. The grid uses HTML's checks_done as the
                # canonical figure to keep the % display honest.
                "ws_observed_checks": len(checked),
            }
    return out


def _convert_ws_hint(state: "TrackerState", hint: dict) -> dict:
    """Render one `_read_hints_*` Hint dict into the SlotHint shape the
    frontend SlotDetailModal already understands (identical to the HTML
    `hints-table` row format).

    Item names resolve in the receiver's game (items live in receiver's
    game space). Location names resolve in the finder's game. Player
    aliases come from `state.players` (alias falls back to name)."""
    finding = int(hint.get("finding_player", 0))
    receiving = int(hint.get("receiving_player", 0))
    try:
        item_id = int(hint.get("item", 0))
        location_id = int(hint.get("location", 0))
    except (TypeError, ValueError):
        item_id, location_id = 0, 0
    found = bool(hint.get("found"))
    entrance = hint.get("entrance") or ""

    finder_player = state.players.get(finding) or {}
    finder_name = (
        finder_player.get("alias") or finder_player.get("name")
        or f"Slot {finding}"
    )
    receiver_player = state.players.get(receiving) or {}
    receiver_name = (
        receiver_player.get("alias") or receiver_player.get("name")
        or f"Slot {receiving}"
    )

    receiver_game = (state.slot_info.get(receiving) or {}).get("game", "")
    item_checksum = state.datapackage_checksums.get(receiver_game, "")
    item_name = datapackage_cache.resolve_item(receiver_game, item_checksum, item_id)

    finder_game = (state.slot_info.get(finding) or {}).get("game", "")
    loc_checksum = state.datapackage_checksums.get(finder_game, "")
    location_name = datapackage_cache.resolve_location(finder_game, loc_checksum, location_id)

    return {
        "finder": finder_name,
        "receiver": receiver_name,
        "item": item_name,
        "location": location_name,
        # Match the HTML `hints-table` "Game" column = finder's game.
        "game": finder_game,
        "entrance": entrance,
        "found": found,
    }


def slot_overrides(room_id: str, slot: int) -> Optional[dict]:
    """Return WS-derived augmentations for the per-slot detail endpoint.

    Shape: `{"hints": [SlotHint], "client_status": int, "status_label": str,
    "goal_completed": bool}`. Caller merges these on top of the HTML
    fetch_slot_data result so the modal renders real-time hints + status
    while keeping the HTML-scraped items_received and locations.

    Returns None if no WS state is available (caller falls through to the
    pure HTML response). Returns a dict with empty `hints` when WS is
    connected but hasn't yet received hints for this slot - that's still
    useful as "no hints exist for this slot" beats stale HTML.
    """
    state = manager.get_state(room_id)
    if state is None or state.state != "connected":
        return None
    with state.lock:
        # Hints from the slot's perspective: server stores hints under
        # the slot's _read_hints_T_S key when the slot is the FINDER OR
        # the RECEIVER - both directions are visible to the slot's view.
        # We just hand back what the server gave us.
        ws_hints = list(state.hints.get(slot, []) or [])
        status = int(state.client_status.get(slot, 0))
        checked = state.checked_locations.get(slot) or set()
        # Build hint dicts BEFORE we drop the lock; resolution uses the
        # state's slot_info / players / datapackage_checksums.
        rendered_hints = [_convert_ws_hint(state, h) for h in ws_hints]
    label, goal = _ws_status_label(status, bool(checked))
    return {
        "hints": rendered_hints,
        "client_status": status,
        "status_label": label,
        "goal_completed": goal,
    }


def read_activity(room_id: str, since: Optional[float] = None,
                  limit: int = 200) -> Optional[dict]:
    """V1.5: read the in-game activity ring buffer for a room.

    `since` filters to events newer than the given timestamp (use the
    `now` returned in the previous call to chain polls). `limit` caps
    the number of events returned (most-recent-N). Returns None when
    no WS connection exists for the room.
    """
    state = manager.get_state(room_id)
    if state is None:
        return None
    with state.lock:
        events = list(state.activity)
    if since is not None:
        events = [e for e in events if e.get("ts", 0) > since]
    if limit > 0 and len(events) > limit:
        events = events[-limit:]
    return {
        "status": "ok" if state.state == "connected" else state.state,
        "now": time.time(),
        "events": events,
    }
