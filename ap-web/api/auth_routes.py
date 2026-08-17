"""Discord OAuth2 login/callback/logout/me endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, request, session

from auth import (
    consume_oauth_state,
    discord_login_url,
    exchange_code,
    generate_oauth_state,
    get_discord_user,
)
from db import create_or_update_user, get_user

import analytics

bp = Blueprint("auth", __name__)


def _record_callback_failed(reason: str) -> None:
    """FEAT-31: one canonical short code per OAuth failure mode. Never the
    provider's error text, which can echo request parameters."""
    analytics.record_event("oauth_callback_failed", props={"reason": reason}, req=request)


def _safe_next(value: str | None) -> str | None:
    """Accept only relative paths so we can never be coerced into an open redirect."""
    if not value:
        return None
    if not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        return None
    return value


@bp.route("/api/auth/login")
def login():
    """Redirect the user to Discord's OAuth2 authorization page.

    Generates a per-session CSRF state token and stores it in the session
    so the callback can verify the response came from our initiated flow.
    Optional ?next= query parameter (relative path only) is stashed in the
    session so the callback can land the user back where they started -
    used by RoomPublic when a require-Discord-login room redirects to OAuth.
    """
    state = generate_oauth_state()
    next_url = _safe_next(request.args.get("next"))
    if next_url:
        session["post_login_next"] = next_url
    elif "post_login_next" in session:
        # Don't carry a stale next-redirect across unrelated logins
        session.pop("post_login_next", None)
    # FEAT-31: top of the auth funnel. next_path is a site-relative path
    # already validated by _safe_next, so it carries no third-party URL.
    analytics.record_event(
        "oauth_login_started", props={"next_path": next_url or "/"}, req=request
    )
    return redirect(discord_login_url(state))


@bp.route("/api/auth/callback")
def callback():
    """Handle the OAuth2 callback from Discord."""
    if not consume_oauth_state(request.args.get("state")):
        _record_callback_failed("state_mismatch")
        return jsonify({"error": "Invalid or missing OAuth state"}), 400

    code = request.args.get("code")
    if not code:
        _record_callback_failed("missing_code")
        return jsonify({"error": "Missing authorization code"}), 400

    token_data = exchange_code(code)
    if not token_data or "access_token" not in token_data:
        _record_callback_failed("token_exchange")
        return jsonify({"error": "Failed to exchange authorization code"}), 400

    discord_user = get_discord_user(token_data["access_token"])
    if not discord_user or "id" not in discord_user:
        _record_callback_failed("profile_fetch")
        return jsonify({"error": "Failed to get Discord user info"}), 400

    # Prefer the Discord display name (`global_name`) over the unique handle
    # (`username`). The handle is the lowercase ".appie"-style identifier;
    # the display name is what Discord shows in the UI ("Appie") and what a
    # user expects to see as themselves.
    display_name = (
        discord_user.get("global_name")
        or discord_user.get("username")
        or discord_user["id"]
    )

    user = create_or_update_user(
        discord_id=discord_user["id"],
        discord_username=display_name,
    )

    session["user_id"] = user["id"]
    session["discord_username"] = user["discord_username"]

    # FEAT-31: bottom of the auth funnel. The Discord id and display name are
    # deliberately not recorded - user_id is the same identity the rest of the
    # events log uses.
    analytics.record_event(
        "oauth_callback_succeeded",
        user_id=user["id"],
        props={"first_login": bool(user.get("is_new_user"))},
        req=request,
    )

    # Redirect to the post-login next URL when set (validated as relative
    # path on /api/auth/login), otherwise the frontend root.
    next_url = _safe_next(session.pop("post_login_next", None)) or "/"
    return redirect(next_url)


@bp.route("/api/auth/me")
def me():
    """Return the current authenticated user, or 401.

    Augments the stored user row with a derived `is_owner` flag so the
    frontend can gate the owner-only "view as" toggle (DEVEX-02). Owner
    is whoever's Discord ID matches `AP_OWNER_DISCORD_ID`; this is not
    persisted as a column because `OWNER_DISCORD_ID` is env-driven and
    could change without re-bootstrapping the row. is_admin is still the
    canonical authorization flag everywhere else.
    """
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    user = get_user(user_id)
    if not user:
        session.clear()
        return jsonify({"error": "Not authenticated"}), 401

    import config
    is_owner = bool(
        config.OWNER_DISCORD_ID
        and user.get("discord_id") == config.OWNER_DISCORD_ID
    )
    return jsonify({**user, "is_owner": is_owner})


@bp.route("/api/auth/logout", methods=["POST"])
def logout():
    """Clear the user's session."""
    session.clear()
    return jsonify({"status": "ok"})
