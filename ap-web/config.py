import os


def _bool_env(name: str, default: bool) -> bool:
    """Parse a boolean env var. Accepts 1/true/yes/on (case-insensitive) as True."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


# ── Feature flags ────────────────────────────────────────────────
# Each flag gates a coherent surface (UI + endpoints). Defaults are ON for
# backward compat - Atlas (and any other deploy that doesn't set the env)
# keeps the full feature set. New deploys can set FEATURE_<NAME>=false in
# their .env to ship a scoped-down build (the YAML-collector MVP for ap-pie.com).
#
# To add a new flag:
#   1. Append to this dict with a default
#   2. Pass through in docker-compose.yml ap-web environment section
#   3. Apply @requires_feature("name") to the relevant route handlers
#   4. Read via useFeature("name") in the frontend to hide UI surfaces
FEATURES: dict[str, bool] = {
    # Local Archipelago server-side generation, AP server launch/stop, and
    # APWorld install/management. Turn OFF to ship as a YAML collector only:
    # hosts collect YAMLs, then download the bundle and run generation
    # themselves off-server.
    "generation": _bool_env("FEATURE_GENERATION", True),
}


OUTPUT_DIR = os.environ.get("AP_OUTPUT_DIR", r"C:\ProgramData\Archipelago\output")
SERVER_EXE = os.environ.get("AP_SERVER_EXE", r"C:\ProgramData\Archipelago\ArchipelagoServer.exe")
DEBUG = os.environ.get("AP_DEBUG", "0") == "1"
HOST = os.environ.get("AP_HOST", "localhost")
PORT_RANGE_START = int(os.environ.get("AP_PORT_RANGE_START", "38281"))
PORT_RANGE_END = int(os.environ.get("AP_PORT_RANGE_END", "38380"))
CORS_ORIGINS = os.environ.get("AP_CORS_ORIGINS", "")
MAX_UPLOAD_MB = int(os.environ.get("AP_MAX_UPLOAD_MB", "50"))
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://archipelago:archipelago@localhost:5432/archipelago")
WORLDS_DIR = os.environ.get("AP_WORLDS_DIR", r"C:\ProgramData\Archipelago\custom_worlds")
INDEX_REPO = os.environ.get("AP_INDEX_REPO", "https://github.com/dowlle/Archipelago-index.git")
GENERATOR_EXE = os.environ.get("AP_GENERATOR_EXE", r"C:\ProgramData\Archipelago\ArchipelagoGenerate.exe")
GENERATION_TIMEOUT = int(os.environ.get("AP_GENERATION_TIMEOUT", "300"))

# Discord OAuth
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "")
OWNER_DISCORD_ID = os.environ.get("AP_OWNER_DISCORD_ID", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

# Tracker
TRACKER_CACHE_TTL = int(os.environ.get("AP_TRACKER_CACHE_TTL", "30"))
# FEAT-14 follow-up 2026-05-02: per-slot detail (items / locations / hints)
# changes less often than the rolling per-room grid that users see
# auto-refreshing, so it tolerates a longer TTL with negligible UX impact
# and meaningful traffic reduction. Manual Refresh button in the
# SlotDetailModal is the user's escape hatch.
TRACKER_SLOT_CACHE_TTL = int(os.environ.get("AP_TRACKER_SLOT_CACHE_TTL", "60"))
# Hard cap on the in-memory tracker cache (per-room + per-slot share one
# OrderedDict). LRU eviction at the cap. 2000 covers a long tail of
# active rooms × slots without unbounded growth.
TRACKER_CACHE_MAX = int(os.environ.get("AP_TRACKER_CACHE_MAX", "2000"))

# FEAT-17: real-time WebSocket tracker (tracker_ws.py). Background asyncio
# thread that maintains one persistent connection per active room.
# - WS_MAX: hard cap on simultaneous connections; rooms past the cap fall
#   back to HTML scrape silently. Archipelago Pie won't see this many for a long
#   time; sanity ceiling, not capacity planning.
# - WS_IDLE_MINUTES: a connection with no incoming packets for this long
#   gets cancelled. Reconnect happens lazily on the next API read.
# - WS_ENABLED: kill-switch (off by default in V0 so the existing scrape
#   path keeps serving production until V1 wires the cache into the API).
TRACKER_WS_ENABLED = _bool_env("AP_TRACKER_WS_ENABLED", False)
TRACKER_WS_MAX = int(os.environ.get("AP_TRACKER_WS_MAX", "200"))
TRACKER_WS_IDLE_MINUTES = int(os.environ.get("AP_TRACKER_WS_IDLE_MINUTES", "60"))

# Templates
from pathlib import Path as _Path
TEMPLATES_DIR = os.environ.get("AP_TEMPLATES_DIR",
    str(_Path(GENERATOR_EXE).parent / "Players" / "Templates"))
