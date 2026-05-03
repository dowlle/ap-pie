"""Discord OAuth2 authentication and authorization middleware."""

from __future__ import annotations

import secrets
from functools import wraps

import requests
from flask import g, jsonify, redirect, request, session

import config

DISCORD_API = "https://discord.com/api/v10"
DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"

_OAUTH_STATE_KEY = "oauth_state"


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
        if not user or not user.get("is_admin"):
            return jsonify({"error": "Admin access required"}), 403

        g.user = user
        return f(*args, **kwargs)
    return wrapper


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
    )

    @app.before_request
    def check_auth():
        # If OAuth not configured, skip auth entirely
        if not _auth_configured():
            return None

        # Static files and SPA - always public
        if not request.path.startswith("/api/"):
            return None

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

        g.user = user

        # Admin endpoints have their own check
        if request.path.startswith("/api/admin"):
            return None

        # Non-admin protected routes require approval
        if not user.get("is_approved") and not user.get("is_admin"):
            return jsonify({"error": "Account not yet approved"}), 403

        return None
