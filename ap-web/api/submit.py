"""Public YAML submission endpoint.

The Bananium-shaped flow: an approved host creates a room and shares the
public room URL with their players. Players (without an Archipelago Pie account, or
with an unapproved one) drop their YAML files in. The host watches submissions
roll in, validates as they go, and hits Generate when ready.

This endpoint is intentionally separate from the auth-gated
/api/rooms/<id>/yamls upload: that one stays as the host's own bulk-upload
path (used by the existing RoomDetail page); this one is the front door for
strangers. Mounted under public_prefixes so the auth middleware lets it
through without a session.

Abuse mitigation:
- Per-room cap (room.max_players if set, otherwise PUBLIC_SUBMIT_DEFAULT_CAP)
- Per-IP sliding-window rate limit (PUBLIC_SUBMIT_PER_IP_PER_HOUR submissions/hour)
- File size cap inherited from MAX_CONTENT_LENGTH (50 MB by default)
- Closed rooms reject all submissions
- Validation runs server-side and rejects malformed YAML before persisting
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from flask import Blueprint, jsonify, request, session

from db import (
    _db_url,
    add_activity,
    add_yaml,
    count_yamls_by_submitter,
    get_room,
    get_user,
    get_yamls,
    maybe_auto_close_room,
    update_yaml_validation,
)
from validation import classify_validation_error, extract_player_info, validate_yaml
from request_ip import client_ip

import option_check

import analytics

bp = Blueprint("submit", __name__)


def _reject(room_id: str, reason_code: str, has_session: bool, payload: dict, status: int):
    """FEAT-31: record why a submission bounced, then return the response.

    Every early return in submit_yaml goes through here so the rejection
    taxonomy can't drift from the code paths. `reason_code` is a canonical
    short string; the user-facing message is not recorded.
    """
    analytics.record_event(
        "submit_rejected",
        room_id=room_id,
        props={"reason_code": reason_code, "has_session": has_session},
        req=request,
    )
    return jsonify(payload), status

PUBLIC_SUBMIT_DEFAULT_CAP = 50
# Per-IP sliding-window rate limit. Anonymous public submits only - logged-in
# submits skip this check (they have a Discord identity that the per-user cap
# can attribute against). 30/hour is loose enough not to bite legitimate
# playtesting (pleb 2026-05-03 hit the prior 5/hour while testing the system).
PUBLIC_SUBMIT_PER_IP_PER_HOUR = 30
_RATE_LIMIT_WINDOW_SECONDS = 3600

_rate_limit_buckets: dict[str, deque] = defaultdict(deque)
_rate_limit_lock = threading.Lock()


def _check_and_record_rate_limit(ip: str) -> tuple[bool, int]:
    """Sliding-window rate limit. Returns (allowed, retry_after_seconds)."""
    now = time.time()
    with _rate_limit_lock:
        bucket = _rate_limit_buckets[ip]
        cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= PUBLIC_SUBMIT_PER_IP_PER_HOUR:
            retry = int(bucket[0] + _RATE_LIMIT_WINDOW_SECONDS - now) + 1
            return False, max(retry, 1)
        bucket.append(now)
        return True, 0


def _requires_db():
    if _db_url is None:
        return jsonify({"error": "Database not available"}), 503
    return None


@bp.route("/api/submit/<room_id>", methods=["POST"])
def submit_yaml(room_id: str):
    db_err = _requires_db()
    if db_err:
        return db_err

    # FEAT-04: lazy auto-close on the public submit path - a stale 'open'
    # status post-deadline would let a YAML through that the host doesn't
    # want, so close it before the rate-limit and validation work happens.
    has_session = bool(session.get("user_id"))
    analytics.record_event(
        "submit_attempted",
        room_id=room_id,
        props={
            "has_session": has_session,
            "content_bytes": int(request.content_length or 0),
        },
        req=request,
    )

    room = maybe_auto_close_room(room_id)
    if not room:
        return _reject(room_id, "room_not_found", has_session,
                       {"error": "Room not found"}, 404)
    if room["status"] != "open":
        return _reject(room_id, "room_closed", has_session,
                       {"error": "This room is no longer accepting YAMLs"}, 400)

    # Discord-login gate: if the room requires it, refuse anonymous submits.
    # Logged-in submits regardless of room.require_discord_login also have their
    # user id captured for host-side display.
    submitter_user_id: int | None = None
    session_user_id = session.get("user_id")
    if session_user_id:
        u = get_user(session_user_id)
        if u:
            submitter_user_id = u["id"]
    if room.get("require_discord_login") and submitter_user_id is None:
        return _reject(room_id, "requires_discord_login", has_session, {
            "error": "This room requires a Discord login before submitting a YAML.",
            "require_discord_login": True,
        }, 401)

    # FEAT-07: per-user cap enforcement (logged-in submits only - anonymous
    # has no identity to count against). max_yamls_per_user = 0 means no cap.
    per_user_cap = room.get("max_yamls_per_user") or 0
    if submitter_user_id is not None and per_user_cap > 0:
        existing_for_user = count_yamls_by_submitter(room_id, submitter_user_id)
        if existing_for_user >= per_user_cap:
            return _reject(room_id, "per_user_cap", has_session, {
                "error": f"You've reached the per-player limit ({per_user_cap}) for this room.",
                "max_yamls_per_user": per_user_cap,
            }, 400)

    # Rate-limit anonymous submits only. Logged-in users have a stable
    # Discord identity that the per-user cap (FEAT-07) and the host-side
    # banlist can attribute against; the per-IP bucket is for unidentified
    # traffic that has no other gate.
    if submitter_user_id is None:
        ip = client_ip()
        allowed, retry_after = _check_and_record_rate_limit(ip)
        if not allowed:
            analytics.record_event(
                "submit_rate_limited",
                room_id=room_id,
                props={"has_session": has_session},
                req=request,
            )
            return jsonify({
                "error": "Too many submissions from this IP. Try again later.",
                "retry_after_seconds": retry_after,
            }), 429

    cap = room["max_players"] if room.get("max_players") and room["max_players"] > 0 \
        else PUBLIC_SUBMIT_DEFAULT_CAP
    existing = get_yamls(room_id)
    if len(existing) >= cap:
        return _reject(room_id, "room_cap", has_session,
                       {"error": f"Room has reached its YAML cap ({cap})"}, 400)

    # Accept either multipart file upload (form) or JSON body with yaml_content.
    yaml_content: str | None = None
    filename: str | None = None
    if "file" in request.files:
        f = request.files["file"]
        if not f.filename:
            return _reject(room_id, "no_filename", has_session,
                           {"error": "No filename"}, 400)
        try:
            yaml_content = f.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return _reject(room_id, "not_utf8", has_session,
                           {"error": "File must be UTF-8 text"}, 400)
        filename = f.filename
    else:
        data = request.get_json(silent=True) or {}
        if "yaml_content" in data and isinstance(data["yaml_content"], str):
            yaml_content = data["yaml_content"]

    if not yaml_content:
        return _reject(room_id, "no_yaml", has_session,
                       {"error": "No YAML provided"}, 400)

    info = extract_player_info(yaml_content)
    if not info:
        return _reject(
            room_id, "no_player_info", has_session,
            {"error": "Could not extract player name and game from YAML"}, 400,
        )
    player_name, game = info

    if not filename:
        filename = f"{player_name} - {game}.yaml"

    existing_names = [y["player_name"] for y in existing]
    is_valid, error = validate_yaml(yaml_content, existing_names)

    # FEAT-28 v2: cache the YAML's `requires.game` map (same as host
    # upload paths) so the room overview can render version warnings.
    try:
        from validation import extract_required_apworld_versions
        apworld_versions = extract_required_apworld_versions(yaml_content)
    except Exception:
        apworld_versions = {}

    yaml_record = add_yaml(
        room_id=room_id,
        player_name=player_name,
        game=game,
        yaml_content=yaml_content,
        apworld_versions=apworld_versions,
        filename=filename,
        submitter_user_id=submitter_user_id,
    )

    # Activity message format: "<uploader> uploaded <game> YAML for player <player_name>".
    # When the uploader is logged in we name them by Discord display name;
    # anonymous submits get "Anonymous" so the host can still tell the
    # difference from a Discord-attributed row.
    uploader = (
        get_user(submitter_user_id)["discord_username"]
        if submitter_user_id is not None else "Anonymous"
    )
    if is_valid:
        update_yaml_validation(yaml_record["id"], "validated")
        yaml_record["validation_status"] = "validated"
        add_activity(
            room_id, "yaml_submitted",
            f"{uploader} uploaded {game} YAML for player {player_name}",
            actor_user_id=submitter_user_id,
            subject_yaml_id=yaml_record["id"],
        )
        # FEAT-31: the game name is index metadata, not personal data. The
        # player name and the YAML body are never recorded.
        analytics.record_event(
            "submit_succeeded",
            user_id=submitter_user_id,
            room_id=room_id,
            props={"game": game, "has_session": has_session},
            req=request,
        )
    else:
        update_yaml_validation(yaml_record["id"], "failed", error)
        yaml_record["validation_status"] = "failed"
        yaml_record["validation_error"] = error
        add_activity(
            room_id, "yaml_submitted_invalid",
            f"{uploader} uploaded invalid {game} YAML for player {player_name}: {error}",
            actor_user_id=submitter_user_id,
            subject_yaml_id=yaml_record["id"],
        )
        # A validator failure still stores the YAML (the host can see it and
        # ask the player to fix it), so this is "rejected by the validator",
        # not "refused at the door" like the early returns above. Same event
        # kind, distinguishable by reason_code.
        analytics.record_event(
            "submit_rejected",
            user_id=submitter_user_id,
            room_id=room_id,
            props={
                "reason_code": classify_validation_error(error),
                "has_session": has_session,
            },
            req=request,
        )

    # FEAT-31 gap 2: advisory option-level check against the version this
    # room has pinned. Never blocks the submission - see option_check's
    # module docstring for why - but tells the submitter now, rather than
    # letting the host discover it at generation time.
    warnings: list = []
    try:
        import yaml as _yaml

        from api.apworlds import _get_game_lookup, builder_schemas_for_pins

        world = _get_game_lookup().get(game)
        if world is not None:
            pinned = None
            try:
                from db import get_room_apworlds

                pinned = next(
                    (p["version"] for p in get_room_apworlds(room_id)
                     if p["apworld_name"] == world.name),
                    None,
                )
            except Exception:
                pinned = None
            if pinned is None:
                ver = next((v for v in world.versions if v.url or v.local), None)
                pinned = ver.version if ver else None
            if pinned:
                rows = builder_schemas_for_pins(
                    [{"apworld_name": world.name, "version": pinned}],
                    fetch_budget_seconds=4.0,
                )
                schema = rows[0].get("schema") if rows else None
                if schema:
                    doc = _yaml.safe_load(yaml_content)
                    warnings = option_check.check_document(doc, game, schema)
                    if warnings:
                        from db import set_yaml_option_warnings

                        set_yaml_option_warnings(yaml_record["id"], warnings)
    except Exception as e:
        # A failed advisory check must never affect a submission.
        from flask import current_app

        current_app.logger.warning(f"option check failed for {room_id}: {e}")

    # FEAT-21 auto-pin: even public submits trigger the first-game-sets-pin
    # behaviour, so the host doesn't have to come back and pin every game
    # players bring in. Honours the YAML's `requires.game` declaration
    # when present (FEAT-28 follow-up).
    try:
        from api.apworlds import auto_pin_for_room_game
        auto_pin_for_room_game(room_id, game, yaml_content=yaml_content)
    except Exception:
        pass

    return jsonify({
        "id": yaml_record["id"],
        "player_name": player_name,
        "game": game,
        "validation_status": yaml_record["validation_status"],
        "validation_error": yaml_record.get("validation_error"),
        # Advisory: the YAML is stored and accepted either way.
        "option_warnings": warnings,
    }), 201
