"""Discord OAuth2 authentication and authorization middleware."""

from __future__ import annotations

import hmac
import re
import secrets
from functools import wraps

import requests
from flask import g, jsonify, redirect, request, session

import config

DISCORD_API = "https://discord.com/api/v10"
DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"

_OAUTH_STATE_KEY = "oauth_state"

# Opening the collection-room workflow must not implicitly open server-side
# generation if FEATURE_GENERATION is enabled in some later deployment.
# Approved hosts/admins retain those routes; public room hosts do not.
_APPROVED_HOST_ROOM_ENDPOINTS = frozenset({
    "rooms.room_test_generate",
    "rooms.room_generate",
    "rooms.room_generation_latest",
    "rooms.room_generation_status",
    "rooms.room_launch",
    "rooms.room_stop",
    "rooms.room_spoiler",
    "rooms.room_download",
    "rooms.room_patches",
    "rooms.room_patch_download",
})

# These blueprints contain only resources owned by the signed-in account.
# They require an authenticated user, but never legacy beta approval. Keeping
# this boundary at the blueprint level avoids accidentally opening a future
# unrelated endpoint merely because its URL happens to start with /api/my.
_SIGNED_IN_PERSONAL_BLUEPRINTS = frozenset({
    "account",
    "room_templates",
    "user_yamls",
})


# Discord bot service token. The bot presents `X-AP-Bot-Token` plus the acting
# member's `X-Discord-User-Id` and acts as the existing AP-Pie user with that
# discord_id. It is accepted ONLY on the (endpoint, method) pairs below; every
# other protected route answers 403 and the token grants nothing there. Value
# is the ownership rule: "any" = any registered member (the room is created in
# their name), "owner" = the acting member must be the room's host, "member" =
# any registered member may add a YAML to a room they can name (the YAML is
# attributed to them, not to the host).
BOT_TOKEN_HEADER = "X-AP-Bot-Token"
BOT_USER_HEADER = "X-Discord-User-Id"
BOT_ROUTES = {
    ("rooms.rooms_create", "POST"): "any",
    ("rooms.rooms_update", "PUT"): "owner",
    ("rooms.room_close", "POST"): "owner",
    ("rooms.yaml_upload", "POST"): "member",
    ("rooms.generated_room_preview", "POST"): "owner",
    ("rooms.generated_room_confirm", "PUT"): "owner",
    ("rooms.room_tracker", "GET"): "owner",
    ("rooms.room_activity_stream", "GET"): "owner",
}
_DISCORD_ID_RE = re.compile(r"^[0-9]{15,25}$")


def via_discord() -> bool:
    """True when this request was authenticated by the bot service token."""
    return bool(getattr(g, "via_discord", False))


def bot_route_rule(endpoint: str | None, method: str) -> str | None:
    return BOT_ROUTES.get((endpoint or "", method))


def _bot_token_ok(presented: str) -> bool:
    """Constant-time check; fails closed on an unset or too-short secret."""
    expected = getattr(config, "DISCORD_BOT_TOKEN", "") or ""
    if len(expected) < getattr(config, "DISCORD_BOT_TOKEN_MIN_LEN", 32):
        return False
    return hmac.compare_digest(
        presented.strip().encode("utf-8"), expected.encode("utf-8"),
    )


def _bot_authenticate():
    """Resolve a bot-token request to (user, error_response).

    Never creates a user: an unknown Discord id is refused. The acting user is
    never an admin through this path, so a bot call cannot reach admin powers
    or other members' rooms even when the member is a site admin.
    """
    if not _bot_token_ok(request.headers.get(BOT_TOKEN_HEADER, "")):
        return None, (jsonify({
            "error": "Invalid bot token", "code": "bot_token_invalid",
        }), 401)
    discord_id = request.headers.get(BOT_USER_HEADER, "").strip()
    if not _DISCORD_ID_RE.match(discord_id):
        return None, (jsonify({
            "error": f"{BOT_USER_HEADER} must be a Discord user id",
            "code": "discord_user_required",
        }), 400)
    from db import get_user_by_discord_id
    user = get_user_by_discord_id(discord_id)
    if not user:
        return None, (jsonify({
            "error": "This Discord account has no AP-Pie account yet. Log in to AP-Pie once with Discord first.",
            "code": "discord_user_not_registered",
        }), 403)
    if user.get("deletion_due_at"):
        return None, (jsonify({
            "error": "Account deletion is pending",
            "code": "account_pending_deletion",
        }), 401)
    return {**user, "is_admin": False}, None


def generate_oauth_state() -> str:
    """Generate and store a fresh OAuth state token in the session."""
    state = secrets.token_urlsafe(32)
    session[_OAUTH_STATE_KEY] = state
    return state


def consume_oauth_state(received: str | None) -> bool:
    """Pop the expected state from the session and compare it to the callback's.

    Always clears the session value, whether the comparison succeeds or not,
    so a single state token cannot be reused.
    """
    expected = session.pop(_OAUTH_STATE_KEY, None)
    if not expected or not received:
        return False
    return secrets.compare_digest(expected, received)


def discord_login_url(state: str) -> str:
    """Build the Discord OAuth2 authorization URL, embedding the CSRF state."""
    params = {
        "client_id": config.DISCORD_CLIENT_ID,
        "redirect_uri": config.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "state": state,
    }
    qs = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return f"{DISCORD_AUTH_URL}?{qs}"


def exchange_code(code: str) -> dict | None:
    """Exchange an authorization code for an access token."""
    resp = requests.post(
        DISCORD_TOKEN_URL,
        data={
            "client_id": config.DISCORD_CLIENT_ID,
            "client_secret": config.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.DISCORD_REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    return resp.json()


def get_discord_user(access_token: str) -> dict | None:
    """Fetch the authenticated user's Discord profile."""
    resp = requests.get(
        f"{DISCORD_API}/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    return resp.json()


def requires_auth(f):
    """Decorator that requires a valid session with a logged-in user."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401

        from db import get_user
        user = get_user(user_id)
        if not user:
            session.clear()
            return jsonify({"error": "Authentication required"}), 401
        if user.get("deletion_due_at"):
            session.clear()
            return jsonify({
                "error": "Account deletion is pending",
                "code": "account_pending_deletion",
            }), 401

        g.user = user
        return f(*args, **kwargs)
    return wrapper


def _auth_configured() -> bool:
    """Check if Discord OAuth credentials are set."""
    return bool(config.DISCORD_CLIENT_ID and config.DISCORD_CLIENT_SECRET)


def requires_admin(f):
    """Decorator that requires the current user to be an admin."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401

        from db import get_user
        user = get_user(user_id)
        if not user or user.get("deletion_due_at") or not user.get("is_admin"):
            if user and user.get("deletion_due_at"):
                session.clear()
            return jsonify({"error": "Admin access required"}), 403

        g.user = user
        return f(*args, **kwargs)
    return wrapper


def _record_403(kind: str, user: dict) -> None:
    """FEAT-31: record a middleware refusal.

    The blocked path is already stored as the event's `path`, so no props are
    needed. Import is local to keep auth.py free of an import-time dependency
    on the analytics module.
    """
    try:
        import analytics

        analytics.record_event(kind, user_id=user.get("id"), req=request)
    except Exception:
        pass


def apply_auth_to_app(app):
    """Register a before_request hook that protects non-public routes.

    If Discord OAuth is not configured, all routes are accessible without auth.
    Authenticated but unapproved users can only access public endpoints.
    """
    public_prefixes = (
        "/api/market",
        "/api/auth",
        "/api/trackers",
        "/api/templates",
        "/api/health",
        "/api/connect",
        "/api/submit",
        "/api/public",
        "/api/features",
        "/api/deployment",
        # FEAT-39: the APWorld index browser is public. IMPORTANT: skipping
        # the middleware also means g.user is NEVER set on these routes, so
        # any /api/apworlds/* route that wants the current user must read
        # the session itself (apworld_requests._current_user does this via
        # a session fallback since the 2026-07-22 branch audit; @requires_admin
        # always did). Every mutating route keeps its own gate: install/
        # remove/refresh are @requires_admin, /installed is behind the
        # generation flag, maintainer routes resolve the session in-body.
        # The room-less builder-schema route (FEAT-38, ruling 2026-07-22)
        # is intentionally public: anonymous visitors build + download a
        # YAML from the index; it serves sha256-cached metadata behind a
        # size cap and a cold-derivation concurrency cap. Any FUTURE
        # sensitive route under this prefix must add its own in-body check.
        "/api/apworlds",
        # FEAT-31: the browser event intake is public by necessity - it
        # records what anonymous visitors do. It accepts only allowlisted
        # kinds, always answers 204, and reads the session itself when one
        # happens to be present (same in-body pattern as /api/apworlds).
        # The admin read surface lives at /api/admin/events, which does not
        # start with this prefix and so stays behind the is_admin check.
        "/api/events",
        # FEAT-42: browsing presets and recording that one was applied are
        # public, because building a YAML is. Every mutating route in that
        # blueprint carries @requires_auth itself, and the admin routes live
        # under /api/admin where the middleware still gates them.
        "/api/presets",
        # CTR track registry: public reads; every write route carries
        # @requires_auth itself and the review routes sit under /api/admin.
        # The whole blueprint 404s while the ctr_registry flag is off.
        "/api/ctr/",
    )

    @app.before_request
    def check_auth():
        # If OAuth not configured, skip auth entirely
        if not _auth_configured():
            return None

        # A scheduled deletion invalidates every extant signed cookie, including
        # requests to otherwise-public APIs. Recovery gets a separate, narrowly
        # scoped session marker only after a fresh Discord OAuth round-trip.
        session_user_id = session.get("user_id")
        if session_user_id:
            from db import get_user
            session_user = get_user(session_user_id)
            if session_user and session_user.get("deletion_due_at"):
                session.clear()

        # Static files and SPA - always public
        if not request.path.startswith("/api/"):
            return None

        # Flask has already routed an otherwise-unmatched /api/* request to
        # the final frontend catch-all. Let that endpoint return its
        # API-shaped 404 instead of turning a nonexistent protected route
        # into a misleading authentication challenge.
        if request.endpoint == "serve_frontend":
            return None

        # Discord bot service token. Handled before the public-prefix pass so a
        # bot request on a listed route never falls through to session auth,
        # and a bot token on any other protected route is refused outright.
        if request.headers.get(BOT_TOKEN_HEADER) is not None:
            rule = bot_route_rule(request.endpoint, request.method)
            if rule is not None:
                user, error = _bot_authenticate()
                if error:
                    return error
                g.user = user
                g.via_discord = True
                g.bot_rule = rule
                return None
            if not any(request.path.startswith(p) for p in public_prefixes):
                return jsonify({
                    "error": "The bot token is not accepted on this route",
                    "code": "bot_route_not_allowed",
                }), 403

        # Public API endpoints - accessible to everyone
        for prefix in public_prefixes:
            if request.path.startswith(prefix):
                return None

        # All other API endpoints require auth
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401

        from db import get_user
        user = get_user(user_id)
        if not user:
            session.clear()
            return jsonify({"error": "Authentication required"}), 401
        if user.get("deletion_due_at"):
            session.clear()
            return jsonify({
                "error": "Account deletion is pending",
                "code": "account_pending_deletion",
            }), 401

        g.user = user

        # Audit-2026-05-04 #3: enforce is_admin in the middleware itself for
        # /api/admin/* paths, on top of the per-route @requires_admin
        # decorators. Defense-in-depth: a future contributor adding a new
        # admin route without the decorator still gets blocked here.
        if request.path.startswith("/api/admin"):
            if not user.get("is_admin"):
                _record_403("admin_403", user)
                return jsonify({"error": "Admin access required"}), 403
            return None

        if request.blueprint in _SIGNED_IN_PERSONAL_BLUEPRINTS:
            return None

        # Open room creation is narrower than global approval. Any signed-in
        # Discord user may use their own room collector and room templates,
        # while unrelated protected/admin/generation surfaces retain their
        # existing role gates. Ownership is enforced inside the room APIs.
        if config.FEATURES.get("open_room_creation", False):
            room_collector_path = (
                (request.path == "/api/rooms" or request.path.startswith("/api/rooms/"))
                and request.endpoint not in _APPROVED_HOST_ROOM_ENDPOINTS
            )
            if room_collector_path:
                return None

        # Non-admin protected routes require approval
        if not user.get("is_approved") and not user.get("is_admin"):
            _record_403("auth_403", user)
            return jsonify({"error": "Account not yet approved"}), 403

        return None
