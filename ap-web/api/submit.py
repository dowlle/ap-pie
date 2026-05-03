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
from validation import extract_player_info, validate_yaml

bp = Blueprint("submit", __name__)

PUBLIC_SUBMIT_DEFAULT_CAP = 50
# Per-IP sliding-window rate limit. Anonymous public submits only - logged-in
# submits skip this check (they have a Discord identity that the per-user cap
# can attribute against). 30/hour is loose enough not to bite legitimate
# playtesting (pleb 2026-05-03 hit the prior 5/hour while testing the system).
PUBLIC_SUBMIT_PER_IP_PER_HOUR = 30
_RATE_LIMIT_WINDOW_SECONDS = 3600

_rate_limit_buckets: dict[str, deque] = defaultdict(deque)
_rate_limit_lock = threading.Lock()


def _client_ip() -> str:
    """Resolve the submitting client IP, honouring a single layer of proxy."""
    fwd = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return fwd or request.remote_addr or "unknown"


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
    room = maybe_auto_close_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] != "open":
        return jsonify({"error": "This room is no longer accepting YAMLs"}), 400

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
        return jsonify({
            "error": "This room requires a Discord login before submitting a YAML.",
            "require_discord_login": True,
        }), 401

    # FEAT-07: per-user cap enforcement (logged-in submits only - anonymous
    # has no identity to count against). max_yamls_per_user = 0 means no cap.
    per_user_cap = room.get("max_yamls_per_user") or 0
    if submitter_user_id is not None and per_user_cap > 0:
        existing_for_user = count_yamls_by_submitter(room_id, submitter_user_id)
        if existing_for_user >= per_user_cap:
            return jsonify({
                "error": f"You've reached the per-player limit ({per_user_cap}) for this room.",
                "max_yamls_per_user": per_user_cap,
            }), 400

    # Rate-limit anonymous submits only. Logged-in users have a stable
    # Discord identity that the per-user cap (FEAT-07) and the host-side
    # banlist can attribute against; the per-IP bucket is for unidentified
    # traffic that has no other gate.
    if submitter_user_id is None:
        ip = _client_ip()
        allowed, retry_after = _check_and_record_rate_limit(ip)
        if not allowed:
            return jsonify({
                "error": "Too many submissions from this IP. Try again later.",
                "retry_after_seconds": retry_after,
            }), 429

    cap = room["max_players"] if room.get("max_players") and room["max_players"] > 0 \
        else PUBLIC_SUBMIT_DEFAULT_CAP
    existing = get_yamls(room_id)
    if len(existing) >= cap:
        return jsonify({"error": f"Room has reached its YAML cap ({cap})"}), 400

    # Accept either multipart file upload (form) or JSON body with yaml_content.
    yaml_content: str | None = None
    filename: str | None = None
    if "file" in request.files:
        f = request.files["file"]
        if not f.filename:
            return jsonify({"error": "No filename"}), 400
        try:
            yaml_content = f.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return jsonify({"error": "File must be UTF-8 text"}), 400
        filename = f.filename
    else:
        data = request.get_json(silent=True) or {}
        if "yaml_content" in data and isinstance(data["yaml_content"], str):
            yaml_content = data["yaml_content"]

    if not yaml_content:
        return jsonify({"error": "No YAML provided"}), 400

    info = extract_player_info(yaml_content)
    if not info:
        return jsonify({"error": "Could not extract player name and game from YAML"}), 400
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
        )
    else:
        update_yaml_validation(yaml_record["id"], "failed", error)
        yaml_record["validation_status"] = "failed"
        yaml_record["validation_error"] = error
        add_activity(
            room_id, "yaml_submitted_invalid",
            f"{uploader} uploaded invalid {game} YAML for player {player_name}: {error}",
        )

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
    }), 201
