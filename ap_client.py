"""
Game-agnostic Archipelago client for sending location checks.
Connects to a slot, fetches location names from the server's DataPackage,
shows missing locations, and lets you pick which to send.
"""

import asyncio
import json
import time
import uuid
import sys

import websockets


# ── Server interaction state ──
location_names: dict[int, str] = {}  # populated from DataPackage
item_names: dict[int, str] = {}      # populated from DataPackage
missing_locations: list[int] = []
checked_locations: list[int] = []
ws_connection = None
connected_event = asyncio.Event()
slot_number = None
slot_game = None
players_info = {}
queued_sends: list[dict] = []  # {"task": asyncio.Task, "ids": list[int], "delay": float, "queued_at": float}
_next_queue_id = 1


def name_for(loc_id: int) -> str:
    return location_names.get(loc_id, f"Unknown Location {loc_id}")


def item_name_for(item_id: int) -> str:
    return item_names.get(item_id, f"Unknown Item {item_id}")


def categorize_locations(loc_ids: list[int]) -> dict[str, list[tuple[int, str]]]:
    """Group locations by common prefix."""
    categories: dict[str, list[tuple[int, str]]] = {}
    for loc_id in sorted(loc_ids):
        name = name_for(loc_id)
        cat = "General"
        for sep in (":", " - "):
            if sep in name:
                cat = name.split(sep, 1)[0].strip()
                break
        categories.setdefault(cat, []).append((loc_id, name))
    return categories


def auto_group_locations(loc_ids: list[int]) -> dict[str, list[tuple[int, str]]]:
    """Group locations by fine-grained prefix (the part before the last separator).

    Strips the trailing varying part of each name so that e.g.
    'Hub 7-2, item 1' through 'Hub 7-2, item 8' all share the key 'Hub 7-2'.
    Falls back to the full name if no recognizable separator is found.
    """
    groups: dict[str, list[tuple[int, str]]] = {}
    for loc_id in sorted(loc_ids):
        name = name_for(loc_id)
        if ", " in name:
            key = name.rsplit(", ", 1)[0]
        elif ":" in name:
            key = name.rsplit(":", 1)[0].strip()
        elif " - " in name:
            key = name.rsplit(" - ", 1)[0].strip()
        else:
            key = name
        groups.setdefault(key, []).append((loc_id, name))
    return groups


def parse_index_set(arg: str, max_idx: int) -> list[int]:
    """Parse '1-5,7' or 'all' into a sorted list of valid 1-based indices."""
    arg = arg.strip()
    if arg.lower() == "all":
        return list(range(1, max_idx + 1))
    indices: set[int] = set()
    for part in arg.replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                for i in range(int(a), int(b) + 1):
                    indices.add(i)
            except ValueError:
                print(f"  Invalid range: {part}")
        else:
            try:
                indices.add(int(part))
            except ValueError:
                print(f"  Invalid number: {part}")
    valid = sorted(i for i in indices if 1 <= i <= max_idx)
    out_of_range = sorted(i for i in indices if not (1 <= i <= max_idx))
    if out_of_range:
        print(f"  Out-of-range indices ignored: {out_of_range}")
    return valid


async def get_connection_info() -> tuple[str, str, str | None]:
    """Interactive dialog to get server, slot name, and password."""
    loop = asyncio.get_event_loop()

    print("=" * 60)
    print("  Archipelago Location Check Client")
    print("=" * 60)
    print()

    server = await loop.run_in_executor(
        None, lambda: input("Server address (e.g. localhost:38281): ").strip()
    )
    if not server:
        server = "localhost:38281"

    if not server.startswith("ws://") and not server.startswith("wss://"):
        # Try wss first, fall back to ws
        server_wss = "wss://" + server
        server_ws = "ws://" + server
    else:
        server_wss = server if server.startswith("wss://") else None
        server_ws = server if server.startswith("ws://") else None

    # Connect to get RoomInfo with slot list
    ws = None
    for attempt in ([server_wss, server_ws] if server_wss and server_ws else [server_wss or server_ws]):
        print(f"\n  Connecting to {attempt}...")
        try:
            ws = await websockets.connect(attempt, ping_interval=30, ping_timeout=60)
            server = attempt
            break
        except Exception as e:
            print(f"  Failed ({e}), trying next...")

    try:
        if not ws:
            raise Exception("Could not connect via wss or ws")
    except Exception as e:
        print(f"  Could not connect: {e}")
        sys.exit(1)

    raw = await ws.recv()
    msgs = json.loads(raw)

    room_games = []
    room_slot_info = {}  # slot_num -> {name, game}

    for msg in msgs:
        if msg["cmd"] == "RoomInfo":
            version = msg.get("version", {})
            room_games = msg.get("games", [])
            # slot_info maps slot number -> {name, game, type, group_members}
            for s, info in msg.get("slot_info", {}).items():
                slot_type = info.get("type", 0)
                if slot_type == 1:  # player slots only (not spectator/group)
                    room_slot_info[int(s)] = {
                        "name": info.get("name", ""),
                        "game": info.get("game", ""),
                    }
            print(f"  Room version: {version}")
            print(f"  Games: {', '.join(room_games)}")

    # Show available slots
    if room_slot_info:
        print(f"\n  Available slots:")
        for s in sorted(room_slot_info):
            info = room_slot_info[s]
            print(f"    [{s}] {info['name']} ({info['game']})")
    print()

    slot_name = await loop.run_in_executor(
        None, lambda: input("Slot name: ").strip()
    )
    if not slot_name:
        print("  No slot name provided. Exiting.")
        await ws.close()
        sys.exit(1)

    # Look up the game for this slot name
    game_name = None
    for s, info in room_slot_info.items():
        if info["name"] == slot_name:
            game_name = info["game"]
            break

    if not game_name:
        print(f"  Warning: Slot '{slot_name}' not found in room info.")
        game_name = await loop.run_in_executor(
            None, lambda: input("  Enter game name manually: ").strip()
        )
        if not game_name:
            await ws.close()
            sys.exit(1)

    password_input = await loop.run_in_executor(
        None, lambda: input("Password (leave blank if none): ").strip()
    )
    password = password_input if password_input else None

    await ws.close()
    return server, slot_name, game_name, password


async def connect_and_listen(server: str, slot_name: str, game_name: str, password: str | None):
    global ws_connection, missing_locations, checked_locations
    global slot_number, slot_game, players_info, location_names, item_names

    print(f"\n  Connecting to {server} as '{slot_name}' ({game_name})...")

    try:
        async with websockets.connect(server, ping_interval=30, ping_timeout=60) as ws:
            ws_connection = ws

            # Wait for RoomInfo (again, since we reconnected)
            raw = await ws.recv()
            msgs = json.loads(raw)
            room_games = []
            for msg in msgs:
                if msg["cmd"] == "RoomInfo":
                    room_games = msg.get("games", [])

            # Request DataPackage
            print("  Requesting DataPackage...")
            await ws.send(json.dumps([{"cmd": "GetDataPackage", "games": room_games}]))

            raw = await ws.recv()
            msgs = json.loads(raw)
            for msg in msgs:
                if msg["cmd"] == "DataPackage":
                    data = msg.get("data", {})
                    games_data = data.get("games", {})
                    for gname, game_data in games_data.items():
                        for iname, iid in game_data.get("item_name_to_id", {}).items():
                            item_names[iid] = iname
                        for lname, lid in game_data.get("location_name_to_id", {}).items():
                            location_names[lid] = lname
                    print(f"  DataPackage loaded: {len(location_names)} locations, {len(item_names)} items")

            # Send Connect with the correct game
            connect_packet = [{
                "cmd": "Connect",
                "password": password or "",
                "name": slot_name,
                "version": {"major": 0, "minor": 6, "build": 7, "class": "Version"},
                "tags": [],
                "items_handling": 0b001,
                "uuid": str(uuid.uuid4()),
                "game": game_name,
                "slot_data": False,
            }]
            await ws.send(json.dumps(connect_packet))

            # Process responses
            async for raw in ws:
                msgs = json.loads(raw)
                for msg in msgs:
                    cmd = msg["cmd"]

                    if cmd == "Connected":
                        slot_number = msg["slot"]
                        slot_game = game_name
                        missing_locations = list(msg.get("missing_locations", []))
                        checked_locations = list(msg.get("checked_locations", []))

                        for p in msg.get("players", []):
                            players_info[p["slot"]] = {
                                "name": p.get("name", ""),
                                "alias": p.get("alias", ""),
                            }
                        slot_info = msg.get("slot_info", {})
                        for s, info in slot_info.items():
                            s_int = int(s)
                            if s_int not in players_info:
                                players_info[s_int] = {"name": info.get("name", ""), "alias": ""}
                            players_info[s_int]["game"] = info.get("game", "")

                        print(f"\n  Connected! Slot #{slot_number}, Game: {slot_game}")
                        print(f"  Missing locations: {len(missing_locations)}")
                        print(f"  Already checked:   {len(checked_locations)}")
                        connected_event.set()

                    elif cmd == "ConnectionRefused":
                        errors = msg.get("errors", [])
                        print(f"\n  Connection REFUSED: {errors}")
                        connected_event.set()
                        return

                    elif cmd == "RoomUpdate":
                        if "checked_locations" in msg:
                            newly_checked = set(msg["checked_locations"])
                            checked_locations.extend(newly_checked - set(checked_locations))
                            missing_locations = [l for l in missing_locations if l not in newly_checked]

                    elif cmd == "PrintJSON":
                        parts = msg.get("data", [])
                        text = "".join(p.get("text", "") for p in parts)
                        if text.strip():
                            print(f"  [Server] {text.strip()}")

                    elif cmd == "ReceivedItems":
                        items = msg.get("items", [])
                        for item in items:
                            iname = item_name_for(item.get("item", 0))
                            print(f"  [Received] {iname} from slot {item.get('player')}")

    except Exception as e:
        print(f"Connection error: {e}")
        connected_event.set()


def parse_indices(arg: str, listed: list[int]) -> list[int]:
    """Parse '1-8,10,15-17' into location IDs from the listed locations."""
    indices: set[int] = set()
    for part in arg.replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                for i in range(int(a), int(b) + 1):
                    indices.add(i)
            except ValueError:
                print(f"  Invalid range: {part}")
        else:
            try:
                indices.add(int(part))
            except ValueError:
                print(f"  Invalid number: {part}")

    ids = []
    for idx in sorted(indices):
        if 1 <= idx <= len(listed):
            ids.append(listed[idx - 1])
        else:
            print(f"  Index {idx} out of range (1-{len(listed)})")
    return ids


async def delayed_send(queue_entry: dict):
    """Wait then send locations."""
    delay = queue_entry["delay"]
    ids = queue_entry["ids"]
    qid = queue_entry["id"]
    label = queue_entry.get("label", "")
    label_str = f" [{label}]" if label else ""
    try:
        await asyncio.sleep(delay)
        print(f"\n  [Queue #{qid}]{label_str} Sending {len(ids)} checks now...")
        await send_locations(ids)
        print(f"  [Queue #{qid}]{label_str} Done!")
        if queue_entry in queued_sends:
            queued_sends.remove(queue_entry)
    except asyncio.CancelledError:
        print(f"\n  [Queue #{qid}]{label_str} Cancelled.")
        if queue_entry in queued_sends:
            queued_sends.remove(queue_entry)


async def send_locations(loc_ids: list[int]):
    """Send LocationChecks to the server."""
    global ws_connection, missing_locations, checked_locations
    if not ws_connection:
        print("Not connected!")
        return

    packet = [{"cmd": "LocationChecks", "locations": loc_ids}]
    await ws_connection.send(json.dumps(packet))

    sent_set = set(loc_ids)
    missing_locations = [l for l in missing_locations if l not in sent_set]
    checked_locations.extend(loc_ids)

    print(f"  Sent {len(loc_ids)} location check(s).")


async def interactive_loop():
    """Interactive menu for picking and sending locations."""
    await connected_event.wait()

    if not ws_connection or slot_number is None:
        print("Failed to connect. Exiting.")
        return

    _listed_locations: list[int] = []
    _listed_groups: list[tuple[str, list[int]]] = []

    while True:
        print("\n" + "=" * 60)
        print(f"Missing locations: {len(missing_locations)} | Checked: {len(checked_locations)}")
        print("=" * 60)
        print("Commands:")
        print("  list [filter]      - Show missing locations (optional text filter)")
        print("  categories         - Show category summary")
        print("  search <text>      - Search location names")
        print("  send <numbers>     - Send locations by list # (e.g. 'send 1,2,3' or 'send 1-10')")
        print("  sendin <sec> <#>   - Queue a send after <sec> seconds (e.g. 'sendin 300 1-8,10')")
        print("  sendcat <cat>      - Send all locations in a category")
        print("  groups [filter]    - Show auto-detected sub-groups (e.g. 'Hub 7-2' batches)")
        print("  release <#|all>    - Send all locations in selected groups immediately")
        print("  slowrelease <sec> <#|all> - Send selected groups one batch at a time, <sec> apart")
        print("  queue              - Show pending queued sends")
        print("  cancel <id>        - Cancel a queued send")
        print("  cancelall          - Cancel all queued sends")
        print("  quit               - Disconnect and exit")
        print()

        try:
            cmd = await asyncio.get_event_loop().run_in_executor(None, lambda: input("> ").strip())
        except EOFError:
            print("No interactive input available. Connection stays open. Press Ctrl+C to quit.")
            try:
                while True:
                    await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            break
        except KeyboardInterrupt:
            break

        if not cmd:
            continue

        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if action == "quit":
            print("Disconnecting...")
            await ws_connection.close()
            break

        elif action == "categories":
            cats = categorize_locations(missing_locations)
            for cat_name, locs in cats.items():
                print(f"  {cat_name}: {len(locs)} locations")

        elif action == "list":
            cats = categorize_locations(missing_locations)
            filter_text = arg.lower().strip() if arg else None

            idx = 1
            _listed_locations.clear()

            for cat_name, locs in cats.items():
                filtered = locs
                if filter_text:
                    filtered = [(lid, ln) for lid, ln in locs
                                if filter_text in ln.lower() or filter_text in cat_name.lower()]
                if not filtered:
                    continue
                print(f"\n--- {cat_name} ({len(filtered)}) ---")
                for loc_id, loc_name in filtered:
                    print(f"  [{idx:3d}] {loc_name}  (ID: {loc_id})")
                    _listed_locations.append(loc_id)
                    idx += 1

            if not _listed_locations:
                print("  No locations match that filter.")

        elif action == "search":
            if not arg:
                print("  Usage: search <text>")
                continue
            search = arg.lower()
            idx = 1
            _listed_locations.clear()
            for loc_id in sorted(missing_locations):
                name = name_for(loc_id)
                if search in name.lower():
                    print(f"  [{idx:3d}] {name}  (ID: {loc_id})")
                    _listed_locations.append(loc_id)
                    idx += 1
            if not _listed_locations:
                print("  No locations match that search.")

        elif action == "send":
            if not arg:
                print("  Usage: send 1,2,3 or send 1-10")
                continue
            if not _listed_locations:
                print("  Run 'list' or 'search' first to populate the location list.")
                continue

            to_send_ids = parse_indices(arg, _listed_locations)
            if to_send_ids:
                print(f"\n  About to send {len(to_send_ids)} checks:")
                for lid in to_send_ids:
                    print(f"    - {name_for(lid)}")
                confirm = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("  Confirm? (y/n): ").strip().lower()
                )
                if confirm in ("y", "yes"):
                    await send_locations(to_send_ids)
                else:
                    print("  Cancelled.")

        elif action == "sendin":
            # sendin <seconds> <indices>
            sendin_parts = arg.split(maxsplit=1)
            if len(sendin_parts) < 2:
                print("  Usage: sendin <seconds> <numbers>  (e.g. 'sendin 300 1-8,10')")
                continue
            try:
                delay = float(sendin_parts[0])
            except ValueError:
                print(f"  Invalid delay: {sendin_parts[0]}")
                continue
            if not _listed_locations:
                print("  Run 'list' or 'search' first to populate the location list.")
                continue

            to_send_ids = parse_indices(sendin_parts[1], _listed_locations)
            if to_send_ids:
                mins, secs = divmod(int(delay), 60)
                time_str = f"{mins}m{secs}s" if mins else f"{secs}s"
                print(f"\n  Queuing {len(to_send_ids)} checks to send in {time_str}:")
                for lid in to_send_ids:
                    print(f"    - {name_for(lid)}")
                confirm = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("  Confirm? (y/n): ").strip().lower()
                )
                if confirm in ("y", "yes"):
                    global _next_queue_id
                    entry = {
                        "id": _next_queue_id,
                        "ids": to_send_ids,
                        "delay": delay,
                        "queued_at": time.time(),
                    }
                    _next_queue_id += 1
                    entry["task"] = asyncio.create_task(delayed_send(entry))
                    queued_sends.append(entry)
                    print(f"  Queued as #{entry['id']} - will send in {time_str}.")
                else:
                    print("  Cancelled.")

        elif action == "queue":
            if not queued_sends:
                print("  No pending queued sends.")
            else:
                now = time.time()
                for entry in sorted(queued_sends, key=lambda e: e["queued_at"] + e["delay"]):
                    elapsed = now - entry["queued_at"]
                    remaining = max(0, entry["delay"] - elapsed)
                    mins, secs = divmod(int(remaining), 60)
                    time_str = f"{mins}m{secs}s" if mins else f"{secs}s"
                    label = entry.get("label", "")
                    label_str = f" [{label}]" if label else ""
                    print(f"  #{entry['id']}:{label_str} {len(entry['ids'])} checks, sends in {time_str}")
                    if not label:
                        for lid in entry["ids"]:
                            print(f"      - {name_for(lid)}")

        elif action == "cancel":
            if not arg:
                print("  Usage: cancel <queue id>")
                continue
            try:
                cancel_id = int(arg)
            except ValueError:
                print(f"  Invalid queue id: {arg}")
                continue
            found = None
            for entry in queued_sends:
                if entry["id"] == cancel_id:
                    found = entry
                    break
            if found:
                found["task"].cancel()
            else:
                print(f"  No queued send with id #{cancel_id}")

        elif action == "cancelall":
            if not queued_sends:
                print("  No pending queued sends.")
            else:
                count = len(queued_sends)
                for entry in list(queued_sends):
                    entry["task"].cancel()
                print(f"  Cancelled {count} queued send(s).")

        elif action == "groups":
            filter_text = arg.lower().strip() if arg else None
            grps = auto_group_locations(missing_locations)
            if filter_text:
                grps = {k: v for k, v in grps.items()
                        if filter_text in k.lower()
                        or any(filter_text in n.lower() for _, n in v)}
            if not grps:
                print("  No groups match that filter.")
                continue

            _listed_groups.clear()
            idx = 1
            for gname, locs in grps.items():
                print(f"  [{idx:3d}] {gname}  ({len(locs)} locations)")
                _listed_groups.append((gname, [lid for lid, _ in locs]))
                idx += 1
            print(f"\n  {len(_listed_groups)} group(s), {sum(len(g[1]) for g in _listed_groups)} total locations.")

        elif action == "release":
            if not arg:
                print("  Usage: release <group numbers|all>  (run 'groups' first)")
                continue
            if not _listed_groups:
                print("  Run 'groups' first to populate the group list.")
                continue

            selected = parse_index_set(arg, len(_listed_groups))
            if not selected:
                print("  No valid groups selected.")
                continue

            all_ids: list[int] = []
            print(f"\n  About to release {len(selected)} group(s):")
            for idx in selected:
                gname, ids = _listed_groups[idx - 1]
                print(f"    [{idx}] {gname} - {len(ids)} locations")
                all_ids.extend(ids)
            print(f"  Total: {len(all_ids)} location checks")
            confirm = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("  Confirm full release? (y/n): ").strip().lower()
            )
            if confirm in ("y", "yes"):
                await send_locations(all_ids)
            else:
                print("  Cancelled.")

        elif action == "slowrelease":
            sr_parts = arg.split(maxsplit=1)
            if len(sr_parts) < 2:
                print("  Usage: slowrelease <seconds> <group numbers|all>")
                print("    e.g. 'slowrelease 300 1-5'  (group 1 in 5m, group 2 in 10m, ...)")
                continue
            try:
                delay = float(sr_parts[0])
            except ValueError:
                print(f"  Invalid delay: {sr_parts[0]}")
                continue
            if delay <= 0:
                print("  Delay must be greater than 0.")
                continue
            if not _listed_groups:
                print("  Run 'groups' first to populate the group list.")
                continue

            selected = parse_index_set(sr_parts[1], len(_listed_groups))
            if not selected:
                print("  No valid groups selected.")
                continue

            print(f"\n  About to slow-release {len(selected)} group(s) at {delay:g}s intervals:")
            for i, idx in enumerate(selected, start=1):
                gname, ids = _listed_groups[idx - 1]
                eta = delay * i
                mins, secs = divmod(int(eta), 60)
                eta_str = f"{mins}m{secs}s" if mins else f"{secs}s"
                print(f"    [+{eta_str}] {gname} - {len(ids)} locations")
            confirm = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("  Confirm slow release? (y/n): ").strip().lower()
            )
            if confirm in ("y", "yes"):
                now = time.time()
                for i, idx in enumerate(selected, start=1):
                    gname, ids = _listed_groups[idx - 1]
                    entry = {
                        "id": _next_queue_id,
                        "ids": ids,
                        "delay": delay * i,
                        "queued_at": now,
                        "label": gname,
                    }
                    _next_queue_id += 1
                    entry["task"] = asyncio.create_task(delayed_send(entry))
                    queued_sends.append(entry)
                print(f"  Queued {len(selected)} batch(es). Use 'queue' to inspect, 'cancelall' to abort.")
            else:
                print("  Cancelled.")

        elif action == "sendcat":
            if not arg:
                print("  Usage: sendcat <category name>")
                continue
            cats = categorize_locations(missing_locations)
            matched = [(name, locs) for name, locs in cats.items() if arg.lower() in name.lower()]
            if not matched:
                print(f"  No category matching '{arg}'")
                continue
            for cat_name, locs in matched:
                ids = [l[0] for l in locs]
                print(f"\n  About to send ALL {len(ids)} checks in '{cat_name}':")
                for lid, lname in locs:
                    print(f"    - {lname}")
                confirm = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("  Confirm? (y/n): ").strip().lower()
                )
                if confirm in ("y", "yes"):
                    await send_locations(ids)
                else:
                    print("  Cancelled.")

        else:
            print(f"  Unknown command: {action}")


async def main():
    # Interactive startup dialog
    server, slot_name, game_name, password = await get_connection_info()

    listener = asyncio.create_task(connect_and_listen(server, slot_name, game_name, password))
    menu = asyncio.create_task(interactive_loop())

    done, pending = await asyncio.wait(
        [listener, menu], return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    if ws_connection and not ws_connection.closed:
        await ws_connection.close()


if __name__ == "__main__":
    asyncio.run(main())
