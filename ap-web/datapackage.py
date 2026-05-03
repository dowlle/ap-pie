"""Fetch and cache Archipelago DataPackage (item/location name mappings) via WebSocket."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_DIR = Path(__file__).parent / ".state"


def _cache_path(seed: str) -> Path:
    return STATE_DIR / f"datapackage_{seed}.json"


def fetch_datapackage(port: int) -> dict:
    """Connect to AP server on localhost:{port} and fetch the DataPackage.

    Returns {"games": {"GameName": {"item_id_to_name": {id: name}, "location_id_to_name": {id: name}}}}.
    """
    from websockets.sync.client import connect

    uri = f"ws://localhost:{port}"
    with connect(uri, open_timeout=5, close_timeout=5) as ws:
        # Receive RoomInfo
        raw = ws.recv(timeout=5)
        room_info = json.loads(raw)
        if isinstance(room_info, list):
            room_info = room_info[0]

        checksums = room_info.get("datapackage_checksums", {})
        games = list(checksums.keys())
        if not games:
            return {"games": {}}

        # Request DataPackage
        ws.send(json.dumps([{"cmd": "GetDataPackage", "games": games}]))
        raw = ws.recv(timeout=10)
        dp = json.loads(raw)
        if isinstance(dp, list):
            dp = dp[0]

    result: dict[str, dict] = {}
    for game_name, game_data in dp.get("data", {}).get("games", {}).items():
        item_name_to_id = game_data.get("item_name_to_id", {})
        location_name_to_id = game_data.get("location_name_to_id", {})
        result[game_name] = {
            "item_id_to_name": {str(v): k for k, v in item_name_to_id.items()},
            "location_id_to_name": {str(v): k for k, v in location_name_to_id.items()},
        }

    return {"games": result}


def get_datapackage(seed: str, port: int | None) -> dict | None:
    """Get DataPackage for a seed, using disk cache or fetching from server.

    Returns None if unavailable (no cache, server not running).
    """
    cache = _cache_path(seed)
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except Exception:
            pass

    if port is None:
        return None

    try:
        dp = fetch_datapackage(port)
    except Exception as e:
        logger.warning("Failed to fetch DataPackage from port %d: %s", port, e)
        return None

    # Cache to disk
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(dp))
    except Exception as e:
        logger.warning("Failed to cache DataPackage: %s", e)

    return dp
