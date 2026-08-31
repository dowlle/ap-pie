import os


def _bool_env(name: str, default: bool) -> bool:
    """Parse a boolean env var. Accepts 1/true/yes/on (case-insensitive) as True."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


# ── Feature flags ────────────────────────────────────────────────
# Each flag gates a coherent surface (UI + endpoints). Defaults are ON for
# backward compat - older deploys that don't set the env keep the full
# feature set. New deploys can set FEATURE_<NAME>=false in their .env to
# ship a scoped-down build (the YAML-collector MVP for ap-pie.com).
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
    # Let any signed-in Discord user create and manage collection rooms.
    # Keep this opt-in so code can reach beta before the public switch and so
    # operators retain a one-variable rollback without reverting a release.
    "open_room_creation": _bool_env("FEATURE_OPEN_ROOM_CREATION", False),
}

# Open-room abuse ceilings. When FEATURE_OPEN_ROOM_CREATION is enabled, every
# non-admin host uses these limits. Deleting an old room frees quota.
ROOM_CREATION_PER_HOUR = int(os.environ.get("AP_ROOM_CREATION_PER_HOUR", "5"))
ROOM_CREATION_MAX_ACTIVE = int(os.environ.get("AP_ROOM_CREATION_MAX_ACTIVE", "10"))
ROOM_CREATION_MAX_TOTAL = int(os.environ.get("AP_ROOM_CREATION_MAX_TOTAL", "50"))

# Account deletion is deliberately two-stage. Scheduling locks the account but
# keeps its data intact for this many days so an accidental deletion can be
# cancelled through a fresh Discord login. The irreversible purge runs only
# after the deadline. Erasure receipts live outside Postgres so they survive a
# database restore long enough to replay deletions against a restored dump.
ACCOUNT_DELETION_GRACE_DAYS = int(os.environ.get("AP_ACCOUNT_DELETION_GRACE_DAYS", "7"))
ACCOUNT_ERASURE_RECEIPT_DAYS = int(os.environ.get("AP_ACCOUNT_ERASURE_RECEIPT_DAYS", "16"))
ACCOUNT_ERASURE_LEDGER = os.environ.get(
    "AP_ACCOUNT_ERASURE_LEDGER",
    os.path.join(os.path.dirname(__file__), ".state", "account-erasure-receipts.jsonl"),
)


OUTPUT_DIR = os.environ.get("AP_OUTPUT_DIR", r"C:\ProgramData\Archipelago\output")
SERVER_EXE = os.environ.get("AP_SERVER_EXE", r"C:\ProgramData\Archipelago\ArchipelagoServer.exe")
DEBUG = os.environ.get("AP_DEBUG", "0") == "1"
HOST = os.environ.get("AP_HOST", "localhost")
PORT_RANGE_START = int(os.environ.get("AP_PORT_RANGE_START", "38281"))
PORT_RANGE_END = int(os.environ.get("AP_PORT_RANGE_END", "38380"))
CORS_ORIGINS = os.environ.get("AP_CORS_ORIGINS", "")

# OPS-07 beta env: a non-empty label drives a visible banner above the
# NavBar (and PublicLayout header) so testers can never confuse a beta
# deployment with prod. Empty string = prod / unlabelled, no banner.
# Value is exposed verbatim via /api/deployment for the frontend.
DEPLOYMENT_LABEL = os.environ.get("AP_DEPLOYMENT_LABEL", "")

# FEAT-39: public origin used to build absolute canonical/OG URLs and the
# sitemap for the server-rendered guide pages. Always the production origin,
# even on beta: beta is served with X-Robots-Tag: noindex at the proxy, so
# its canonical links should still point at prod to avoid duplicate-content
# signals. Override with AP_PUBLIC_BASE_URL only if the prod origin changes.
PUBLIC_BASE_URL = os.environ.get("AP_PUBLIC_BASE_URL", "https://ap-pie.com").rstrip("/")
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
# A room-creation block must not disappear when its user row is erased. This
# keyed value pseudonymises Discord ids in the separate abuse-prevention table;
# it is still personal data and is described as such in the privacy notice.
ABUSE_HMAC_KEY = os.environ.get("AP_ABUSE_HMAC_KEY", SECRET_KEY)

# APIE-1 (ap-pie-wide SSO): the session cookie defaults to host-only with
# Flask's default name "session". To make one Discord login work across all
# ap-pie.com subdomains (ap-pie.com, digipelago.ap-pie.com, future
# pokepelago.*), an ecosystem deploy sets:
#   - SESSION_COOKIE_DOMAIN=.ap-pie.com  -> the cookie is shared across subdomains
#   - SESSION_COOKIE_NAME=apie_session   -> a distinct ecosystem cookie name
# Every ecosystem product also shares the SAME SECRET_KEY so a session minted
# on any subdomain validates on all of them (Flask sessions are signed cookies,
# not server state). Each product keeps its OWN database keyed by discord_id;
# the cookie only carries identity.
#
# Both default to empty/unset so existing single-host deploys are unchanged.
# The distinct NAME matters for the beta stack: beta.ap-pie.com has its own
# SECRET_KEY and its own users table, so it must NOT share the prod cookie.
# Beta sets a different SESSION_COOKIE_NAME (and no domain) to stay isolated;
# without the name split, a beta login would clobber the shared prod cookie
# (same name + Domain=.ap-pie.com) and vice versa.
SESSION_COOKIE_DOMAIN = os.environ.get("SESSION_COOKIE_DOMAIN", "")
SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "")

# OPS-21: machine access to POST /api/apworlds/refresh, so the index-merge
# pipeline can refresh the in-container clone itself instead of a human
# remembering the manual step after every merge.
#
# The endpoint still accepts an admin session (the Refresh button is
# unchanged); this token is a second, narrower door for one caller. It grants
# exactly one action - re-sync a public read-only git mirror and drop a cache
# - so a leak is a nuisance, not an escalation. It is NOT an admin credential
# and must never be accepted by any other route.
#
# Unset (the default) disables token auth entirely, so every deploy that
# doesn't opt in keeps admin-session-only behaviour. A value shorter than 32
# characters is refused at request time rather than silently accepted, so a
# placeholder can't become a live credential.
INDEX_REFRESH_TOKEN = os.environ.get("AP_INDEX_REFRESH_TOKEN", "")
INDEX_REFRESH_TOKEN_MIN_LEN = 32

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

# ── FEAT-31: cookieless analytics ────────────────────────────────
# ANALYTICS_ENABLED is the master switch: off means nothing is recorded
# anywhere and POST /api/events returns 204 without touching the database.
# ANALYTICS_VISIT_ID disables the in-memory per-page-load visit id on its
# own, which downgrades anonymous funnels to plain counts while leaving
# every other event intact. Neither flag stores anything on a visitor's
# device in any configuration - there is no cookie and no web storage.
ANALYTICS_ENABLED = _bool_env("AP_ANALYTICS_ENABLED", True)
ANALYTICS_VISIT_ID = _bool_env("AP_ANALYTICS_VISIT_ID", True)
# Storage limitation (GDPR Art. 5(1)(e)). Raw rows are deleted past this
# horizon; the events_daily rollup keeps counts-only history after that.
ANALYTICS_RETENTION_DAYS = int(os.environ.get("AP_ANALYTICS_RETENTION_DAYS", "180"))
# Per-IP ceiling for the public POST /api/events endpoint, per hour. The IP
# is used transiently for this bucket and is never persisted with an event.
ANALYTICS_EVENTS_PER_IP_PER_HOUR = int(
    os.environ.get("AP_ANALYTICS_EVENTS_PER_IP_PER_HOUR", "600")
)
ANALYTICS_EVENTS_GLOBAL_PER_MINUTE = int(
    os.environ.get("AP_ANALYTICS_EVENTS_GLOBAL_PER_MINUTE", "600")
)

# SEC-41: safe default. Enable only after Caddy requires Cloudflare
# Authenticated Origin Pulls and overwrites X-AP-Origin-Verified upstream.
TRUST_CLOUDFLARE_HEADERS = _bool_env("AP_TRUST_CLOUDFLARE_HEADERS", False)

# Templates
from pathlib import Path as _Path
TEMPLATES_DIR = os.environ.get("AP_TEMPLATES_DIR",
    str(_Path(GENERATOR_EXE).parent / "Players" / "Templates"))
