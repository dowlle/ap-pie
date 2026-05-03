"""FEAT-17 V1: per-(game, checksum) DataPackage cache for the WebSocket
tracker.

Distinct from the existing `datapackage.py` module - that one is keyed by
local-room seed and serves the host-only ItemTracker for Archipelago Pie-generated
games. This module is keyed by `(game_name, checksum)` so we can dedupe
across rooms (hundreds of external rooms share the same SM64 0.1.2
DataPackage; we should fetch + store it once).

Disk layout:
    ap-web/.state/datapackage_v2/<safe_game>/<checksum>.json

Each file is a single JSON dict with `item_id_to_name` and
`location_id_to_name` (plus the `game` and `checksum` for reverse
lookup). Memory cache layered in front so repeated resolves don't re-read
disk on every PrintJSON event.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger("tracker_ws.dp_cache")
if not logger.handlers and not logging.getLogger().handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "[%(asctime)s] %(name)s %(levelname)s: %(message)s"
    ))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)

STATE_DIR = Path(__file__).parent / ".state" / "datapackage_v2"

_lock = threading.RLock()
_mem_cache: dict[tuple[str, str], dict] = {}


def _safe_name(s: str) -> str:
    """Filesystem-safe rendering of an AP game name. Restrictive but
    one-way: we never need to recover the original from the path. Reads
    use `(game, checksum)` keys directly, not filename parsing."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s)[:120] or "_"


def _disk_path(game: str, checksum: str) -> Path:
    return STATE_DIR / _safe_name(game) / f"{checksum}.json"


def _read_disk(game: str, checksum: str) -> Optional[dict]:
    p = _disk_path(game, checksum)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"corrupt datapackage cache at {p}: {e}")
        return None


def get(game: str, checksum: str) -> Optional[dict]:
    """Return cached game payload or None. Memory-first, disk fallback."""
    if not game or not checksum:
        return None
    key = (game, checksum)
    with _lock:
        cached = _mem_cache.get(key)
    if cached is not None:
        return cached
    on_disk = _read_disk(game, checksum)
    if on_disk is not None:
        with _lock:
            _mem_cache[key] = on_disk
    return on_disk


def store(game: str, checksum: str, game_data: dict) -> None:
    """Persist one game's DataPackage. `game_data` is the raw dict from
    the AP `DataPackage` packet (`item_name_to_id`, `location_name_to_id`).
    We invert to `id_to_name` because the runtime use is always
    "resolve this id to a name" not the other way around."""
    if not game or not checksum:
        return
    item_n2i = game_data.get("item_name_to_id") or {}
    loc_n2i = game_data.get("location_name_to_id") or {}
    payload = {
        "game": game,
        "checksum": checksum,
        "item_id_to_name": {str(v): k for k, v in item_n2i.items()},
        "location_id_to_name": {str(v): k for k, v in loc_n2i.items()},
    }
    key = (game, checksum)
    with _lock:
        _mem_cache[key] = payload
    p = _disk_path(game, checksum)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload), encoding="utf-8")
    except Exception as e:
        logger.warning(f"failed to write datapackage cache {p}: {e}")


def resolve_item(game: str, checksum: str, item_id: int) -> str:
    pkg = get(game, checksum)
    if not pkg:
        return f"Item #{item_id}"
    return pkg["item_id_to_name"].get(str(item_id), f"Item #{item_id}")


def resolve_location(game: str, checksum: str, location_id: int) -> str:
    pkg = get(game, checksum)
    if not pkg:
        return f"Location #{location_id}"
    return pkg["location_id_to_name"].get(str(location_id), f"Location #{location_id}")


def location_count(game: str, checksum: str) -> int:
    """Total number of locations defined for a (game, checksum). Used as
    an upper-bound denominator when building per-slot completion fractions
    for slots other than our own connected slot."""
    pkg = get(game, checksum)
    if not pkg:
        return 0
    return len(pkg.get("location_id_to_name") or {})


def missing_games(checksums: dict[str, str]) -> list[str]:
    """Given the `datapackage_checksums` from RoomInfo, return the games
    we don't have a fresh cache for. Used by tracker_ws.TrackerConnection
    to construct the GetDataPackage request after RoomInfo arrives."""
    out: list[str] = []
    for game, checksum in checksums.items():
        if not game or not checksum:
            continue
        if get(game, checksum) is None:
            out.append(game)
    return out


def cached_count(checksums: dict[str, str]) -> int:
    """How many of the given (game, checksum) pairs are already in cache.
    Used by snapshot() to surface progress in the admin endpoint."""
    n = 0
    for game, checksum in checksums.items():
        if get(game, checksum) is not None:
            n += 1
    return n
