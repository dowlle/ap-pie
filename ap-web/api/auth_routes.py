"""Discord OAuth2 login/callback/logout/me endpoints."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, redirect, request, session

from auth import (
    consume_oauth_state,
    discord_login_url,
    exchange_code,
    generate_oauth_state,
    get_discord_user,
    requires_auth,
)
from db import (
    cancel_account_deletion,
    consume_account_deletion_reauth_limit,
    create_account_deletion_token,
    create_or_update_user,
    get_user,
)

import analytics
import config

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
    session.pop("oauth_purpose", None)
    session.pop("oauth_reauth_user_id", None)
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


@bp.route("/api/auth/account-delete-reauth")
@requires_auth
def account_delete_reauth():
    """Start a dedicated OAuth round-trip for the destructive account flow."""
    if config.OWNER_DISCORD_ID and g.user.get("discord_id") == config.OWNER_DISCORD_ID:
        return jsonify({
            "error": "The owner account requires the manual verified deletion process."
        }), 403
    allowed, retry_after = consume_account_deletion_reauth_limit(g.user["id"])
    if not allowed:
        response = jsonify({
            "error": "Too many deletion reauthentication attempts. Try again shortly."
        })
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response
    state = generate_oauth_state()
    session["oauth_purpose"] = "account_delete"
    session["oauth_reauth_user_id"] = g.user["id"]
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

    purpose = session.pop("oauth_purpose", None)
    if purpose == "account_delete":
        original_user_id = session.pop("oauth_reauth_user_id", None)
        original = get_user(original_user_id) if isinstance(original_user_id, int) else {}
        if (
            not original
            or original.get("deletion_due_at")
            or original.get("discord_id") != discord_user["id"]
        ):
            session.clear()
            _record_callback_failed("reauth_identity_mismatch")
            return jsonify({
                "error": "Discord reauthentication did not match the signed-in account."
            }), 403
        raw_token = secrets.token_urlsafe(32)
        create_account_deletion_token(
            original["id"], hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        )
        session["user_id"] = original["id"]
        session["discord_username"] = original["discord_username"]
        session["account_deletion_token"] = raw_token
        return redirect("/my/account?delete=ready")

    user = create_or_update_user(
        discord_id=discord_user["id"],
        discord_username=display_name,
    )
    expired_account_recreated = False

    if user.get("deletion_due_at"):
        due_at = datetime.fromisoformat(user["deletion_due_at"])
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        if due_at <= datetime.now(timezone.utc):
            # Do not leave an expired account in a five-minute limbo. The
            # fresh Discord sign-in may trigger its now-due hard deletion,
            # after which this identity can start again with an empty account.
            from account_erasure import process_due_account

            process_due_account(
                user["id"], manager=current_app.config.get("server_manager")
            )
            user = create_or_update_user(
                discord_id=discord_user["id"],
                discord_username=display_name,
            )
            expired_account_recreated = True

    if user.get("deletion_due_at"):
        # This fresh OAuth proves control of the same Discord identity, but it
        # does not silently restore anything. The recovery page shows the exact
        # deadline and asks for an explicit cancellation.
        session.clear()
        session["account_recovery_user_id"] = user["id"]
        return redirect("/account-recovery")

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
    if expired_account_recreated:
        next_url = "/my/account?deletion=completed"
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
    if user.get("deletion_due_at"):
        session.clear()
        return jsonify({
            "error": "Account deletion is pending",
            "code": "account_pending_deletion",
        }), 401

    import config
    is_owner = bool(
        config.OWNER_DISCORD_ID
        and user.get("discord_id") == config.OWNER_DISCORD_ID
    )
    return jsonify({**user, "is_owner": is_owner})


@bp.route("/api/auth/account-recovery")
def account_recovery_status():
    user_id = session.get("account_recovery_user_id")
    user = get_user(user_id) if isinstance(user_id, int) else {}
    if not user or not user.get("deletion_due_at"):
        session.pop("account_recovery_user_id", None)
        return jsonify({"error": "Fresh Discord sign-in required for recovery."}), 401
    return jsonify({
        "discord_username": user["discord_username"],
        "deletion_requested_at": user["deletion_requested_at"],
        "deletion_due_at": user["deletion_due_at"],
    })


@bp.route("/api/auth/account-recovery", methods=["POST"])
def recover_account():
    user_id = session.get("account_recovery_user_id")
    if not isinstance(user_id, int):
        return jsonify({"error": "Fresh Discord sign-in required for recovery."}), 401
    user = cancel_account_deletion(user_id)
    if not user:
        session.clear()
        return jsonify({
            "error": "The recovery deadline has passed; permanent deletion is in progress."
        }), 410
    session.clear()
    session["user_id"] = user["id"]
    session["discord_username"] = user["discord_username"]
    return jsonify({"status": "recovered"})


@bp.route("/api/auth/logout", methods=["POST"])
def logout():
    """Clear the user's session."""
    session.clear()
    return jsonify({"status": "ok"})
