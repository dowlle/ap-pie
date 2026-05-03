from __future__ import annotations

import io
import pickle
import re
import zipfile
import zlib
from datetime import datetime
from pathlib import Path

from ap_lib.models import GameRecord, Hint, NetworkItem, NetworkSlot, PlayerInfo

DEFAULT_OUTPUT_DIR = r"C:\ProgramData\Archipelago\output"
DEFAULT_SERVER_EXE = r"C:\ProgramData\Archipelago\ArchipelagoServer.exe"


class _APUnpickler(pickle.Unpickler):
    """Unpickler that substitutes stub types for Archipelago modules.

    SEC: classes are resolved against a hardcoded allowlist. Anything not
    on the allowlist is replaced with an inert stub - we never fall back
    to pickle's default `__import__`-based resolution. Without this, a
    `.archipelago` payload could pickle e.g. `os.system` as a reduce
    target and achieve RCE during `pickle.loads`. Reported by Eijebong
    2026-05-04.
    """

    _CLASS_MAP: dict[str, type] = {
        "NetUtils.NetworkSlot": NetworkSlot,
        "NetUtils.SlotType": int,
        "NetUtils.NetworkItem": NetworkItem,
        "NetUtils.Hint": Hint,
        "NetUtils.HintStatus": int,
    }

    # Modules + class names that the legitimate `.archipelago` and
    # `.apsave` formats actually need. Anything else is treated as
    # untrusted input and replaced with a no-op stub.
    _SAFE_BY_MODULE: dict[str, frozenset[str]] = {
        "builtins": frozenset({
            "object", "dict", "list", "tuple", "set", "frozenset",
            "str", "int", "float", "bool", "bytes", "bytearray",
            "complex", "type", "slice", "range", "NoneType",
        }),
        "copyreg": frozenset({"_reconstructor", "__newobj__"}),
        "collections": frozenset({
            "OrderedDict", "defaultdict", "deque", "Counter",
        }),
        "datetime": frozenset({
            "datetime", "date", "time", "timedelta", "timezone",
        }),
        "_codecs": frozenset({"encode"}),
    }

    def find_class(self, module: str, name: str) -> type:
        key = f"{module}.{name}"
        if key in self._CLASS_MAP:
            return self._CLASS_MAP[key]
        if name in self._SAFE_BY_MODULE.get(module, frozenset()):
            return super().find_class(module, name)
        return type(name, (), {"__init__": lambda self, *a, **kw: None})


def _unpickle(data: bytes) -> dict:
    return _APUnpickler(io.BytesIO(data)).load()


def parse_multidata(zip_path: Path) -> GameRecord | None:
    """Parse an AP output zip and return a GameRecord."""
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError):
        return None

    arch_files = [n for n in zf.namelist() if n.endswith(".archipelago")]
    if not arch_files:
        return None

    try:
        raw = zf.read(arch_files[0])
        obj = _unpickle(zlib.decompress(raw[1:]))
    except Exception:
        return None

    players: list[PlayerInfo] = []
    slot_info: dict = obj.get("slot_info", {})
    for slot_id, info in sorted(slot_info.items()):
        if isinstance(info, tuple) and hasattr(info, "name"):
            if info.type in (0, 1):
                players.append(PlayerInfo(slot=slot_id, name=info.name, game=info.game))

    patch_files = [
        n
        for n in zf.namelist()
        if not n.endswith(".archipelago") and not n.endswith("_Spoiler.txt")
    ]

    spoiler = any(n.endswith("_Spoiler.txt") for n in zf.namelist())

    creation_time = None
    try:
        first_entry = zf.infolist()[0]
        creation_time = datetime(*first_entry.date_time)
    except (IndexError, ValueError):
        pass

    server_opts = obj.get("server_options", {})

    version = obj.get("version", (0, 0, 0))
    if not isinstance(version, tuple):
        version = (0, 0, 0)

    locations = obj.get("locations", {})
    for p in players:
        p.checks_total = len(locations.get(p.slot, {}))

    # Try to extract per-game world versions from patch filenames
    game_versions = _extract_game_versions(zf, patch_files)

    return GameRecord(
        seed=obj.get("seed_name", "unknown"),
        ap_version=version,
        creation_time=creation_time,
        players=players,
        zip_path=zip_path,
        patch_files=patch_files,
        race_mode=obj.get("race_mode", 0),
        hint_cost=server_opts.get("hint_cost"),
        release_mode=server_opts.get("release_mode"),
        collect_mode=server_opts.get("collect_mode"),
        spoiler=spoiler,
        game_versions=game_versions,
    )


def _extract_game_versions(zf: zipfile.ZipFile, patch_files: list[str]) -> dict[str, str]:
    """Try to extract game world versions from available sources."""
    versions: dict[str, str] = {}

    # Method 1: Parse patch filenames - format like "AP-SEED-P2-Factorio_0.6.5.zip"
    # The version suffix after the game name (after last underscore) is the AP version, not world version
    # This isn't reliable for world versions, skip.

    # Method 2: Nothing else available in the zip itself.
    # World versions come from the generation log (stored in room.generation_log).
    return versions


def parse_generation_log(log: str) -> dict[str, str]:
    """Parse world versions from a generation log.

    The log contains lines like:
        Pokemon Emerald                         : v2.4.1  | Items:  291 | Locations:  1338
    """
    versions: dict[str, str] = {}
    for line in log.split("\n"):
        m = re.match(r"\s+(.+?)\s*:\s*v(\S+)\s*\|", line)
        if m:
            game_name = m.group(1).strip()
            version = m.group(2)
            versions[game_name] = version
    return versions


def parse_save(save_path: Path, record: GameRecord) -> None:
    """Parse an .apsave file and enrich the GameRecord with completion data."""
    try:
        raw = save_path.read_bytes()
        obj = _unpickle(zlib.decompress(raw))
    except Exception:
        return

    slot_players = {p.slot: p for p in record.players}

    location_checks: dict = obj.get("location_checks", {})
    for key, checked in location_checks.items():
        if isinstance(key, tuple) and len(key) == 2:
            _, slot_id = key
            if slot_id in slot_players:
                slot_players[slot_id].checks_done = len(checked) if hasattr(checked, "__len__") else 0

    client_state: dict = obj.get("client_game_state", {})
    for key, state in client_state.items():
        if isinstance(key, tuple) and len(key) == 2:
            _, slot_id = key
            if slot_id in slot_players:
                slot_players[slot_id].client_status = int(state) if isinstance(state, int) else 0

    all_times: list[float] = []
    for entry in obj.get("client_activity_timers", ()):
        if isinstance(entry, tuple) and len(entry) == 2:
            all_times.append(entry[1])
    for entry in obj.get("client_connection_timers", ()):
        if isinstance(entry, tuple) and len(entry) == 2:
            all_times.append(entry[1])
    try:
        all_times.append(save_path.stat().st_mtime)
    except OSError:
        pass

    if all_times:
        record.last_activity = datetime.fromtimestamp(max(all_times))


def extract_received_items(save_path: Path) -> dict[int, list[dict]]:
    """Extract per-slot received items from an .apsave file.

    Returns {slot_id: [{"item": int, "location": int, "player": int, "flags": int}, ...]}.
    """
    try:
        raw = save_path.read_bytes()
        obj = _unpickle(zlib.decompress(raw))
    except Exception:
        return {}

    result: dict[int, list[dict]] = {}
    for key, items in obj.get("received_items", {}).items():
        if isinstance(key, tuple) and len(key) >= 2:
            slot_id = key[1]
            item_list = []
            for ni in items:
                if isinstance(ni, tuple) and hasattr(ni, "item"):
                    item_list.append({
                        "item": ni.item,
                        "location": ni.location,
                        "player": ni.player,
                        "flags": ni.flags,
                    })
            if slot_id in result:
                result[slot_id].extend(item_list)
            else:
                result[slot_id] = item_list
    return result


def extract_slot_info(zip_path: Path) -> dict[int, dict]:
    """Extract slot_info from multidata: {slot_id: {"name": str, "game": str}}."""
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError):
        return {}

    arch_files = [n for n in zf.namelist() if n.endswith(".archipelago")]
    if not arch_files:
        return {}

    try:
        raw = zf.read(arch_files[0])
        obj = _unpickle(zlib.decompress(raw[1:]))
    except Exception:
        return {}

    result: dict[int, dict] = {}
    for slot_id, info in obj.get("slot_info", {}).items():
        if isinstance(info, tuple) and hasattr(info, "name"):
            result[slot_id] = {"name": info.name, "game": info.game}
    return result


def scan_output_dir(output_dir: Path) -> list[GameRecord]:
    """Scan the output directory and return all parsed game records."""
    records: list[GameRecord] = []
    saves: set[str] = set()

    for f in output_dir.iterdir():
        if f.suffix == ".apsave":
            saves.add(f.stem)

    for f in sorted(output_dir.iterdir()):
        if f.suffix != ".zip" or not f.name.startswith("AP_"):
            continue
        record = parse_multidata(f)
        if record is None:
            continue
        if f.stem in saves:
            record.has_save = True
            record.save_path = f.with_suffix(".apsave")
            parse_save(record.save_path, record)
        # Load game versions from sidecar file if present
        versions_file = f.with_suffix(".versions.json")
        if versions_file.exists():
            try:
                import json
                record.game_versions = json.loads(versions_file.read_text())
            except Exception:
                pass
        records.append(record)

    return records
