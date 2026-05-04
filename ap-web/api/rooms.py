from __future__ import annotations

import zipfile
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, send_file

import config
from db import (
    _db_url,
    add_activity,
    add_yaml,
    clear_room_apworld,
    create_room,
    delete_room,
    enqueue_generation_job,
    get_activity,
    get_generation_job,
    get_latest_generation_job,
    get_room,
    get_room_apworlds,
    get_yamls,
    get_yamls_with_submitters,
    list_rooms,
    maybe_auto_close_room,
    remove_yaml,
    set_room_apworld,
    update_room,
    update_yaml_content,
    update_yaml_validation,
)
from validation import extract_player_info, validate_yaml
from api.features import requires_feature

bp = Blueprint("rooms", __name__)


def requires_db(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if _db_url is None:
            return jsonify({"error": "Database not available"}), 503
        return f(*args, **kwargs)

    return wrapper


# ── Room CRUD ────────────────────────────────────────────────────


def _current_user() -> dict | None:
    """Return the authenticated user dict from the auth middleware, or None
    if running with auth disabled. Routes here are NOT in public_prefixes,
    so g.user is set whenever Discord OAuth is configured.
    """
    return getattr(g, "user", None)


def _is_admin(user: dict | None) -> bool:
    return bool(user and user.get("is_admin"))


def _can_access_room(room: dict, user: dict | None) -> bool:
    """Admins see everything. Otherwise, only the host of the room.

    Auth-disabled mode (user is None): return True so local dev keeps working.
    Legacy rooms with host_user_id=NULL: admin-only - no non-admin can claim them.
    """
    if user is None:
        return True
    if _is_admin(user):
        return True
    return room.get("host_user_id") is not None and room["host_user_id"] == user["id"]


@bp.before_request
def _enforce_room_ownership():
    """Gate every <room_id>-scoped route in this blueprint on ownership.
    Collection routes (GET/POST /api/rooms) have no room_id arg and pass
    through unchanged - they handle filtering themselves.

    Also performs a FEAT-04 lazy close: if the room's submit_deadline has
    passed and it's still 'open', flip it to 'closed' before the handler
    sees it. Cheaper than a sweep tick for the request-path case and
    guarantees the host never sees a stale 'open' status after a deadline.

    Note: public per-room reads for players live in api/public.py, not here,
    so this gate doesn't affect the /r/<id> player flow.
    """
    view_args = request.view_args or {}
    room_id = view_args.get("room_id")
    if not room_id:
        return None
    if _db_url is None:
        # let requires_db on the handler return 503
        return None
    # maybe_auto_close_room returns the (possibly auto-closed) room, or {}
    # if the id is unknown.
    room = maybe_auto_close_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if not _can_access_room(room, _current_user()):
        return jsonify({"error": "Not your room"}), 403
    g.room = room
    return None


@bp.route("/api/rooms")
@requires_db
def rooms_list():
    status = request.args.get("status")
    user = _current_user()

    # Admins may view a specific user's rooms via ?as_user=<id> (FEAT-03).
    # Non-admins can never override the filter - they always see only their own.
    if _is_admin(user):
        as_user = request.args.get("as_user", type=int)
        owner_filter = as_user  # None means "all rooms"
    elif user is not None:
        owner_filter = user["id"]
    else:
        # Auth disabled (local dev with OAuth not configured) - return everything.
        owner_filter = None

    return jsonify(list_rooms(status=status, host_user_id=owner_filter))


@bp.route("/api/rooms", methods=["POST"])
@requires_db
def rooms_create():
    data = request.get_json()
    if not data or "name" not in data or "host_name" not in data:
        return jsonify({"error": "name and host_name are required"}), 400

    user = _current_user()
    host_user_id = user["id"] if user else None

    # FEAT-04: optional submit_deadline (ISO 8601 string from the frontend,
    # already converted to UTC client-side). Pass through verbatim - Postgres
    # parses TIMESTAMPTZ from ISO. Empty string from a cleared input becomes
    # NULL.
    submit_deadline = data.get("submit_deadline") or None

    # FEAT-07 + FEAT-08: settable on create too. tracker_url is treated as
    # a free-form URL - the validator (tracker.parse_tracker_url) will reject
    # bad shapes when the LiveTracker tries to fetch.
    max_yamls_per_user = max(0, int(data.get("max_yamls_per_user", 0) or 0))
    tracker_url = (data.get("tracker_url") or "").strip() or None

    # FEAT-21 + FEAT-28 v2: APWorld version policy is now picked at room
    # creation alongside the rest of the form, instead of forcing the host
    # back into Settings after the fact. The frontend always sends both
    # display flags as a coherent pair (radio: strict / flexible / latest);
    # auto_upgrade defaults to True per the existing column default.
    allow_mixed = bool(data.get("allow_mixed_apworld_versions", False))
    force_latest = bool(data.get("force_latest_apworld_versions", False))
    auto_upgrade = bool(data.get("auto_upgrade_apworld_pins", True))

    room = create_room(
        name=data["name"],
        host_name=data["host_name"],
        description=data.get("description", ""),
        spoiler_level=data.get("spoiler_level", 3),
        race_mode=data.get("race_mode", False),
        max_players=data.get("max_players", 0),
        require_discord_login=bool(data.get("require_discord_login", False)),
        host_user_id=host_user_id,
        submit_deadline=submit_deadline,
        max_yamls_per_user=max_yamls_per_user,
        tracker_url=tracker_url,
        allow_mixed_apworld_versions=allow_mixed,
        force_latest_apworld_versions=force_latest,
        auto_upgrade_apworld_pins=auto_upgrade,
    )
    return jsonify(room), 201


@bp.route("/api/rooms/<room_id>")
@requires_db
def rooms_get(room_id: str):
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404

    if not _can_access_room(room, _current_user()):
        return jsonify({"error": "Not your room"}), 403

    # Auto-correct stale "playing" status if server is no longer running
    if room["status"] == "playing" and room.get("seed"):
        manager = current_app.config["server_manager"]
        server = manager.status(room["seed"])
        if not server or server.status != "running":
            update_room(room_id, status="generated")
            room["status"] = "generated"

    # Host-side view: includes the submitter's Discord username when known.
    # Only this auth-gated endpoint exposes submitter identity; the public
    # /api/public/rooms/<id> read uses get_yamls() and never exposes it.
    room["yamls"] = get_yamls_with_submitters(room_id)
    room["activity"] = get_activity(room_id, limit=20)
    return jsonify(room)


@bp.route("/api/rooms/<room_id>", methods=["PUT"])
@requires_db
def rooms_update(room_id: str):
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if not _can_access_room(room, _current_user()):
        return jsonify({"error": "Not your room"}), 403
    data = request.get_json() or {}
    # Don't let a non-admin reassign room ownership via PUT.
    if not _is_admin(_current_user()):
        data.pop("host_user_id", None)
    # FEAT-04: an empty string from a cleared deadline picker means "remove
    # the deadline". Normalize to None so Postgres stores NULL instead of
    # rejecting the value.
    if "submit_deadline" in data and data["submit_deadline"] in ("", None):
        data["submit_deadline"] = None
    # FEAT-08: same normalisation for tracker_url - empty input clears it.
    if "tracker_url" in data:
        v = (data["tracker_url"] or "").strip() if isinstance(data["tracker_url"], str) else None
        data["tracker_url"] = v or None
    # FEAT-17: same normalisation for tracker_slot_name.
    if "tracker_slot_name" in data:
        v = (data["tracker_slot_name"] or "").strip() if isinstance(data["tracker_slot_name"], str) else None
        data["tracker_slot_name"] = v or None
    # SEC-03: validate external_host through the same outbound-host check that
    # tracker_url uses. Without this an authed room creator could set
    # external_host=127.0.0.1 + external_port=2019 (Caddy admin) and the
    # tracker_ws background thread would happily attempt outbound websocket
    # connections from the prod VPS to internal services.
    if "external_host" in data:
        v = (data["external_host"] or "").strip() if isinstance(data["external_host"], str) else None
        if not v:
            data["external_host"] = None
        else:
            from tracker import is_safe_outbound_host
            if not is_safe_outbound_host(v):
                return jsonify({
                    "error": "external_host must be a public, routable host (no localhost / private IPs / loopback)",
                }), 400
            data["external_host"] = v
    if "external_port" in data:
        raw = data["external_port"]
        if raw in (None, ""):
            data["external_port"] = None
        else:
            try:
                p = int(raw)
            except (TypeError, ValueError):
                return jsonify({"error": "external_port must be an integer"}), 400
            if not (1 <= p <= 65535):
                return jsonify({"error": "external_port must be between 1 and 65535"}), 400
            data["external_port"] = p
    # FEAT-07: clamp the per-user cap to a non-negative int.
    if "max_yamls_per_user" in data:
        try:
            data["max_yamls_per_user"] = max(0, int(data["max_yamls_per_user"] or 0))
        except (TypeError, ValueError):
            data["max_yamls_per_user"] = 0
    updated = update_room(room_id, **data)
    # FEAT-17: if any tracker-relevant field changed AND the tracker_ws
    # subsystem is on AND the room has the prerequisites, bounce the
    # WebSocket connection so the new slot/URL takes effect immediately.
    # Cancel + reschedule is the cheapest way to pick up changes; the cost
    # is one Join broadcast in the AP server's chat per relevant edit.
    try:
        import config as _cfg
        if _cfg.TRACKER_WS_ENABLED:
            relevant = ("tracker_url", "tracker_slot_name", "external_host", "external_port")
            if any(room.get(k) != updated.get(k) for k in relevant):
                _maybe_reschedule_tracker_ws(updated)
    except Exception as e:
        current_app.logger.warning(f"FEAT-17 reschedule on PUT failed: {e}")
    return jsonify(updated)


def _maybe_reschedule_tracker_ws(room: dict) -> None:
    """FEAT-17: bounce the WebSocket connection for a room. No-op if the
    room is missing tracker_url + external_host + external_port."""
    tracker_url = room.get("tracker_url")
    host = room.get("external_host")
    port = room.get("external_port")
    if not (tracker_url and host and port):
        # Pre-conditions not met - cancel any existing connection so we
        # don't leave a stale one running with old config.
        from tracker_ws import manager
        manager.cancel(room["id"])
        return
    from tracker_ws import manager, discover_slot_name, scrape_first_slot_name
    slot_name = discover_slot_name(
        room["id"], room.get("host_user_id"), room.get("tracker_slot_name"),
    ) or scrape_first_slot_name(tracker_url)
    if not slot_name:
        from tracker_ws import manager as _m
        _m.cancel(room["id"])
        return
    manager.reschedule(
        room["id"], tracker_url, host, int(port), slot_name,
    )


@bp.route("/api/rooms/<room_id>", methods=["DELETE"])
@requires_db
def rooms_delete(room_id: str):
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if not _can_access_room(room, _current_user()):
        return jsonify({"error": "Not your room"}), 403
    if delete_room(room_id):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Room not found"}), 404


# ── YAML Management ──────────────────────────────────────────────


@bp.route("/api/rooms/<room_id>/yamls", methods=["POST"])
@requires_db
def yaml_upload(room_id: str):
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] != "open":
        return jsonify({"error": "Room is not open for YAML uploads"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No filename"}), 400

    content = file.read().decode("utf-8-sig")

    # Extract player info
    info = extract_player_info(content)
    if not info:
        return jsonify({"error": "Could not extract player name and game from YAML"}), 400
    player_name, game = info

    # Check max players
    existing = get_yamls(room_id)
    if room["max_players"] > 0 and len(existing) >= room["max_players"]:
        return jsonify({"error": f"Room is full ({room['max_players']} players max)"}), 400

    # Validate
    existing_names = [y["player_name"] for y in existing]
    is_valid, error = validate_yaml(content, existing_names)

    # Capture the host's Discord identity on bulk uploads too - the host is
    # always logged in here (route is auth-gated), so submitter_user_id is
    # always set when OAuth is configured. Activity log uses the same
    # "<uploader> uploaded <game> YAML for player <player>" format as the
    # public submit path.
    #
    # FEAT-20 exception: when room.claim_mode is on, the host is pre-loading
    # an anonymous slot for players to claim. Storing the host's id here
    # would defeat the whole point - players couldn't claim it because the
    # row would already have a "submitter". Force NULL so claim_yaml can
    # later atomically attach the real player.
    user = _current_user()
    claim_mode = bool(room.get("claim_mode"))
    submitter_user_id = None if claim_mode else (user["id"] if user else None)
    uploader = (user or {}).get("discord_username") or room["host_name"]

    # FEAT-28 v2: cache the YAML's `requires.game` map alongside the row
    # so the room overview can render per-YAML version warnings without
    # re-parsing on every request.
    try:
        from validation import extract_required_apworld_versions
        apworld_versions = extract_required_apworld_versions(content)
    except Exception:
        apworld_versions = {}

    # Save to database
    yaml_record = add_yaml(
        room_id=room_id,
        player_name=player_name,
        game=game,
        yaml_content=content,
        filename=file.filename,
        submitter_user_id=submitter_user_id,
        apworld_versions=apworld_versions,
    )

    # Update validation status
    if is_valid:
        update_yaml_validation(yaml_record["id"], "validated")
        yaml_record["validation_status"] = "validated"
        if claim_mode:
            add_activity(
                room_id, "yaml_preloaded",
                f"{uploader} pre-loaded {game} YAML for player {player_name} (claim-mode)",
            )
        else:
            add_activity(
                room_id, "yaml_uploaded",
                f"{uploader} uploaded {game} YAML for player {player_name}",
            )
    else:
        update_yaml_validation(yaml_record["id"], "failed", error)
        yaml_record["validation_status"] = "failed"
        yaml_record["validation_error"] = error
        add_activity(
            room_id, "yaml_invalid",
            f"{uploader} uploaded invalid {game} YAML for player {player_name}: {error}",
        )

    # FEAT-21 auto-pin: first YAML for a game in this room sets the pin.
    # Prefers the version the YAML declares in its `requires.game.<Name>`
    # block (when present and in the index); falls back to index latest.
    # No-op if pin already exists or game isn't in the index.
    try:
        from api.apworlds import auto_pin_for_room_game
        auto_pin_for_room_game(room_id, game, yaml_content=content)
    except Exception as e:
        current_app.logger.warning(f"FEAT-21 auto-pin (upload) failed: {e}")

    return jsonify(yaml_record), 201


@bp.route("/api/rooms/<room_id>/yamls/create", methods=["POST"])
@requires_db
def yaml_create(room_id: str):
    """Create a YAML from the in-browser editor (JSON body instead of file upload)."""
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] != "open":
        return jsonify({"error": "Room is not open for YAML uploads"}), 400

    data = request.get_json()
    if not data or "yaml_content" not in data:
        return jsonify({"error": "yaml_content is required"}), 400

    content = data["yaml_content"]
    player_name = data.get("player_name", "")
    game = data.get("game", "")

    # Try extracting from content if not provided
    if not player_name or not game:
        info = extract_player_info(content)
        if info:
            player_name, game = info
        elif not player_name or not game:
            return jsonify({"error": "Could not determine player name and game"}), 400

    # Check max players
    existing = get_yamls(room_id)
    if room["max_players"] > 0 and len(existing) >= room["max_players"]:
        return jsonify({"error": f"Room is full ({room['max_players']} players max)"}), 400

    # Validate
    existing_names = [y["player_name"] for y in existing]
    is_valid, error = validate_yaml(content, existing_names)

    filename = f"{player_name} - {game}.yaml"

    user = _current_user()
    # Same FEAT-20 exception as the file-upload path: claim-mode rooms
    # store editor-created YAMLs as anonymous so players can claim them.
    claim_mode = bool(room.get("claim_mode"))
    submitter_user_id = None if claim_mode else (user["id"] if user else None)
    uploader = (user or {}).get("discord_username") or room["host_name"]

    # FEAT-28 v2: cache requires.game map (same as upload path).
    try:
        from validation import extract_required_apworld_versions
        apworld_versions = extract_required_apworld_versions(content)
    except Exception:
        apworld_versions = {}

    yaml_record = add_yaml(
        room_id=room_id,
        player_name=player_name,
        game=game,
        yaml_content=content,
        filename=filename,
        submitter_user_id=submitter_user_id,
        apworld_versions=apworld_versions,
    )

    if is_valid:
        update_yaml_validation(yaml_record["id"], "validated")
        yaml_record["validation_status"] = "validated"
        if claim_mode:
            add_activity(
                room_id, "yaml_preloaded",
                f"{uploader} pre-loaded {game} YAML for player {player_name} (via editor, claim-mode)",
            )
        else:
            add_activity(
                room_id, "yaml_created",
                f"{uploader} uploaded {game} YAML for player {player_name} (via editor)",
            )
    else:
        update_yaml_validation(yaml_record["id"], "failed", error)
        yaml_record["validation_status"] = "failed"
        yaml_record["validation_error"] = error
        add_activity(
            room_id, "yaml_invalid",
            f"{uploader} uploaded invalid {game} YAML for player {player_name} (via editor): {error}",
        )

    # FEAT-21 auto-pin (editor path). Honours `requires.game` like the
    # upload path - the editor accepts the same YAML format.
    try:
        from api.apworlds import auto_pin_for_room_game
        auto_pin_for_room_game(room_id, game, yaml_content=content)
    except Exception as e:
        current_app.logger.warning(f"FEAT-21 auto-pin (create) failed: {e}")

    return jsonify(yaml_record), 201


@bp.route("/api/rooms/<room_id>/yamls/<int:yaml_id>/validation", methods=["PUT"])
@requires_db
def yaml_set_validation(room_id: str, yaml_id: int):
    """Override a YAML's validation status. Used for the ManuallyValidated
    escape hatch: a host trusts a player whose YAML the validator can't
    reason about (custom apworld, version skew, etc.) and wants to let it
    through generation. Auth-gated by the existing approval middleware.
    """
    from db import VALID_VALIDATION_STATUSES, get_yamls

    data = request.get_json() or {}
    status = data.get("status")
    if status not in VALID_VALIDATION_STATUSES:
        return jsonify({
            "error": f"status must be one of {list(VALID_VALIDATION_STATUSES)}"
        }), 400

    yamls = get_yamls(room_id)
    if not any(y["id"] == yaml_id for y in yamls):
        return jsonify({"error": "YAML not found in this room"}), 404

    error = None if status in ("validated", "manually_validated") else data.get("error")
    updated = update_yaml_validation(yaml_id, status, error)
    add_activity(room_id, "yaml_validation_override",
                 f"YAML {updated['player_name']} set to {status}")
    return jsonify(updated)


@bp.route("/api/rooms/<room_id>/yamls/<int:yaml_id>", methods=["PUT"])
@requires_db
def yaml_update(room_id: str, yaml_id: int):
    """FEAT-18 host variant: room host updates ANY YAML in their room.

    Mirrors the public PUT contract (multipart `file` OR JSON
    `yaml_content`) but doesn't require submitter_user_id match - the
    host has admin-level control over every YAML in the room. The
    blueprint's `_enforce_room_ownership` before_request hook already
    authenticates the caller as the host (or admin); we don't repeat
    that check here.

    Activity log uses the same `yaml_updated` event type as the public
    path - the message text shows both the actor (the host) and the
    player_name, so a reader can spot host edits by the actor != player
    case (e.g. "Appie updated XCOM YAML for player BennoXCOM").
    """
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] not in ("open", "closed"):
        return jsonify({"error": "Cannot modify YAMLs in current room state"}), 400

    target = next((y for y in get_yamls(room_id) if y["id"] == yaml_id), None)
    if not target:
        return jsonify({"error": "YAML not found in this room"}), 404

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
    new_player_name, new_game = info

    if not filename:
        filename = f"{new_player_name} - {new_game}.yaml"

    siblings = [y for y in get_yamls(room_id) if y["id"] != yaml_id]
    existing_names = [y["player_name"] for y in siblings]
    is_valid, error = validate_yaml(yaml_content, existing_names)

    old_player_name = target.get("player_name") or ""

    # FEAT-28 v2: re-extract requires.game from the new content (the
    # YAML body has changed, so the cached map could be stale).
    try:
        from validation import extract_required_apworld_versions
        apworld_versions = extract_required_apworld_versions(yaml_content)
    except Exception:
        apworld_versions = {}

    updated = update_yaml_content(
        yaml_id=yaml_id,
        player_name=new_player_name,
        game=new_game,
        yaml_content=yaml_content,
        filename=filename,
        apworld_versions=apworld_versions,
    )

    user = _current_user()
    actor = (
        (user or {}).get("discord_username")
        or room.get("host_name")
        or "Host"
    )

    if is_valid:
        update_yaml_validation(yaml_id, "validated")
        updated["validation_status"] = "validated"
        updated["validation_error"] = None
    else:
        update_yaml_validation(yaml_id, "failed", error)
        updated["validation_status"] = "failed"
        updated["validation_error"] = error

    renamed = old_player_name != new_player_name
    if renamed:
        message = (
            f"{actor} renamed YAML '{old_player_name}' → '{new_player_name}'"
            f" ({new_game})"
        )
    else:
        if is_valid:
            message = f"{actor} updated {new_game} YAML for player {new_player_name}"
        else:
            message = (
                f"{actor} updated {new_game} YAML for player "
                f"{new_player_name} (now invalid: {error})"
            )
    add_activity(room_id, "yaml_updated", message)

    return jsonify({
        "id": updated["id"],
        "player_name": new_player_name,
        "game": new_game,
        "validation_status": updated["validation_status"],
        "validation_error": updated.get("validation_error"),
        "renamed": renamed,
        "previous_player_name": old_player_name if renamed else None,
    })


@bp.route("/api/rooms/<room_id>/yamls/<int:yaml_id>", methods=["DELETE"])
@requires_db
def yaml_delete(room_id: str, yaml_id: int):
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] not in ("open", "closed"):
        return jsonify({"error": "Cannot modify YAMLs in current room state"}), 400

    # Capture player_name + game before the row vanishes so the activity
    # log entry can read like "Appie deleted XCOM 2 YAML for player
    # BennoXCOM" instead of an opaque id reference. Same shape as the
    # corresponding upload activity entries.
    target = next((y for y in get_yamls(room_id) if y["id"] == yaml_id), None)

    if remove_yaml(yaml_id):
        if target:
            user = _current_user()
            actor = (
                (user or {}).get("discord_username")
                or room.get("host_name")
                or "Host"
            )
            add_activity(
                room_id, "yaml_deleted",
                f"{actor} deleted {target['game']} YAML for player {target['player_name']}",
            )
        return jsonify({"status": "deleted"})
    return jsonify({"error": "YAML not found"}), 404


@bp.route("/api/rooms/<room_id>/yamls/<int:yaml_id>/download")
@requires_db
def yaml_download(room_id: str, yaml_id: int):
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    yamls = get_yamls(room_id)
    target = next((y for y in yamls if y["id"] == yaml_id), None)
    if not target:
        return jsonify({"error": "YAML not found"}), 404
    from io import BytesIO
    buf = BytesIO(target["yaml_content"].encode("utf-8"))
    return send_file(buf, download_name=target["filename"], as_attachment=True, mimetype="text/yaml")


@bp.route("/api/rooms/<room_id>/yamls/download-all")
@requires_db
def yamls_download_all(room_id: str):
    """Bundle every YAML in the room into a single zip archive."""
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    yamls = get_yamls(room_id)
    if not yamls:
        return jsonify({"error": "No YAMLs uploaded"}), 400

    from io import BytesIO
    buf = BytesIO()
    seen_names: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for y in yamls:
            # Strip path components from user-supplied filename (defensive against "../" or weird uploads)
            raw = (y.get("filename") or "").replace("\\", "/").rsplit("/", 1)[-1]
            name = raw or f"player_{y['id']}.yaml"
            if name in seen_names:
                stem, dot, ext = name.rpartition(".")
                name = f"{stem}_{y['id']}{dot}{ext}" if stem else f"{name}_{y['id']}"
            seen_names.add(name)
            zf.writestr(name, y["yaml_content"])
    buf.seek(0)

    safe_room = "".join(c if c.isalnum() or c in "-_" else "_" for c in (room.get("name") or room_id))
    download_name = f"{safe_room}-yamls.zip"
    return send_file(buf, download_name=download_name, as_attachment=True, mimetype="application/zip")


# ── Room Actions ─────────────────────────────────────────────────


@bp.route("/api/rooms/<room_id>/test-generate", methods=["POST"])
@requires_db
@requires_feature("generation")
def room_test_generate(room_id: str):
    """Dry-run generation to test if the current YAMLs would generate successfully."""
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] not in ("open", "closed"):
        return jsonify({"error": "Room must be open or closed to test generate"}), 400

    yamls = get_yamls(room_id)
    if not yamls:
        return jsonify({"error": "No YAMLs uploaded"}), 400

    from db import GENERATION_READY_STATUSES
    invalid = [y for y in yamls if y["validation_status"] not in GENERATION_READY_STATUSES]
    if invalid:
        names = ", ".join(y["player_name"] for y in invalid)
        return jsonify({"error": f"Invalid YAMLs: {names}"}), 400

    # Run generation with --skip_output (validates without producing files)
    import os
    import subprocess
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix="ap_test_") as tmpdir:
        players_dir = Path(tmpdir) / "Players"
        players_dir.mkdir()
        # Defensive: filename comes from the uploader, so strip any path
        # components before joining with players_dir. Mirrors the same
        # protection on the bulk-download endpoint.
        for y in yamls:
            raw = (y.get("filename") or "").replace("\\", "/").rsplit("/", 1)[-1]
            safe_name = raw or f"player_{y['id']}.yaml"
            (players_dir / safe_name).write_text(y["yaml_content"], encoding="utf-8")

        cmd = [
            config.GENERATOR_EXE,
            "--player_files_path", str(players_dir),
            "--outputpath", tmpdir,
            "--skip_output",
        ]

        # The frozen AP generator looks for custom_worlds/ relative to its
        # own binary, so we must run from the generator directory.
        generator_dir = Path(config.GENERATOR_EXE).parent
        cwd = str(generator_dir)

        # If custom_worlds doesn't exist next to the generator but we have
        # a separate managed worlds dir, symlink it in (if writable).
        custom_worlds_dir = config.WORLDS_DIR
        if custom_worlds_dir:
            custom_dest = generator_dir / "custom_worlds"
            custom_src = Path(custom_worlds_dir)
            if custom_src.is_dir() and not custom_dest.exists():
                if os.access(str(generator_dir), os.W_OK):
                    try:
                        custom_dest.symlink_to(custom_src)
                    except OSError:
                        pass

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.GENERATION_TIMEOUT,
                cwd=cwd,
            )
        except FileNotFoundError:
            return jsonify({"success": False, "error": "Generator not found", "log": ""}), 500
        except subprocess.TimeoutExpired:
            return jsonify({"success": False, "error": "Test generation timed out", "log": ""}), 500

        log = result.stdout + ("\n" + result.stderr if result.stderr else "")
        success = result.returncode == 0

        return jsonify({
            "success": success,
            "error": None if success else f"Generator exited with code {result.returncode}",
            "log": log,
        }), 200 if success else 500


@bp.route("/api/rooms/<room_id>/close", methods=["POST"])
@requires_db
def room_close(room_id: str):
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] != "open":
        return jsonify({"error": "Room is not open"}), 400

    updated = update_room(room_id, status="closed")
    add_activity(room_id, "room_closed", f"Room closed by {room['host_name']}")
    return jsonify(updated)


@bp.route("/api/rooms/<room_id>/reopen", methods=["POST"])
@requires_db
def room_reopen(room_id: str):
    """Reopen a closed room so the host can accept more YAMLs.

    Only valid from "closed" - generated/playing rooms have a seed and
    going back to YAML collection would invalidate it. To start over
    from a generated room, delete it and create a new one.
    """
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] != "closed":
        return jsonify({"error": "Only closed rooms can be reopened"}), 400

    updated = update_room(room_id, status="open")
    add_activity(room_id, "room_reopened", f"Room reopened by {room['host_name']}")
    return jsonify(updated)


@bp.route("/api/rooms/<room_id>/generate", methods=["POST"])
@requires_db
@requires_feature("generation")
def room_generate(room_id: str):
    """Enqueue a generation job and return immediately.

    Generation takes 30-300 seconds and used to block gunicorn's single
    worker. Now we drop a row in generation_jobs and a background thread
    runs it. The client polls /api/rooms/<id>/generation/<job_id> for status.
    """
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] not in ("closed", "generated"):
        return jsonify({"error": "Room must be closed before generating"}), 400

    # Don't enqueue a second job while one is already in flight for this room.
    latest = get_latest_generation_job(room_id)
    if latest and latest["status"] in ("queued", "running"):
        return jsonify({
            "status": "already_running",
            "job_id": latest["id"],
            "job_status": latest["status"],
        }), 409

    yamls = get_yamls(room_id)
    if not yamls:
        return jsonify({"error": "No YAMLs uploaded"}), 400

    from db import GENERATION_READY_STATUSES
    invalid = [y for y in yamls if y["validation_status"] not in GENERATION_READY_STATUSES]
    if invalid:
        names = ", ".join(y["player_name"] for y in invalid)
        return jsonify({"error": f"Invalid YAMLs: {names}"}), 400

    update_room(room_id, status="generating")
    job = enqueue_generation_job(room_id)
    add_activity(room_id, "generation", f"Generation queued (job {job['id']})")

    # Lazy-start the worker so it survives gunicorn's preload-and-fork.
    from generation_worker import ensure_worker_running
    ensure_worker_running()

    return jsonify({
        "status": "queued",
        "job_id": job["id"],
        "job_status": job["status"],
    }), 202


@bp.route("/api/rooms/<room_id>/generation/latest")
@requires_db
def room_generation_latest(room_id: str):
    job = get_latest_generation_job(room_id)
    if not job:
        return jsonify({"status": "none"})
    return jsonify(job)


@bp.route("/api/rooms/<room_id>/generation/<int:job_id>")
@requires_db
def room_generation_status(room_id: str, job_id: int):
    job = get_generation_job(job_id)
    if not job or job["room_id"] != room_id:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@bp.route("/api/rooms/<room_id>/launch", methods=["POST"])
@requires_db
@requires_feature("generation")
def room_launch(room_id: str):
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if not room.get("seed"):
        return jsonify({"error": "Room has not been generated yet"}), 400

    # Use existing server launch logic
    from app import get_records

    records = get_records()
    matches = [r for r in records if r.seed == room["seed"]]
    if not matches:
        return jsonify({"error": "Generated game not found in library"}), 404

    record = matches[0]
    manager = current_app.config["server_manager"]

    try:
        instance = manager.start(
            seed=room["seed"],
            zip_path=str(record.zip_path),
            players=[p.name for p in record.players],
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    update_room(room_id, status="playing")
    add_activity(room_id, "server", "Server launched")
    host = current_app.config.get("AP_HOST", "localhost")
    return jsonify(instance.to_dict(host))


@bp.route("/api/rooms/<room_id>/stop", methods=["POST"])
@requires_db
@requires_feature("generation")
def room_stop(room_id: str):
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] != "playing":
        return jsonify({"error": "Room is not playing"}), 400

    seed = room.get("seed")
    if seed:
        manager = current_app.config["server_manager"]
        manager.stop(seed)

    update_room(room_id, status="generated")
    add_activity(room_id, "server", "Server stopped")
    return jsonify({"status": "stopped"})


def _status_label_from_int(status: int, checks_done: int) -> tuple[str, bool]:
    """Map archipelago.gg's HTML-tracker status text (mapped to ints by
    `tracker.py:_AP_STATUS_TO_INT`) to one of four labels matching the
    archipelago.gg tracker page vocabulary: connected / playing /
    disconnected / goal_completed. The archipelago.gg HTML uses these text
    values: disconnected (0), ready (5), playing (10), connected (20),
    goal completed (30). "Ready" folds into "playing" since the user-
    facing distinction isn't useful in our grid. Status 0 with prior check
    activity reads as "connected" (the slot was online, its checks remain
    on record); without activity it reads as "disconnected"."""
    if status >= 30:
        return "goal_completed", True
    if status >= 20:
        return "connected", False
    if status >= 10:
        return "playing", False
    if status >= 5:
        return "playing", False  # "ready" folds into "playing"
    return ("connected", False) if checks_done > 0 else ("disconnected", False)


def _external_tracker_to_room_shape(room: dict, tracker_url: str) -> dict:
    """FEAT-08: shape tracker.fetch_tracker_data output into the same dict
    LiveTracker expects from /api/rooms/<id>/tracker. Lets the existing UI
    light up against an external archipelago.gg tracker without changes.

    FEAT-17 V1.4: when the WebSocket tracker is connected for this room,
    overlay live `client_status` / `status_label` / `goal_completed` from
    the in-memory cache on top of the HTML scrape. Per-slot
    checks_done / checks_total stay HTML-sourced - the WS connection
    only sees its own slot's check totals, so HTML remains the
    authoritative source of denominators.
    """
    from tracker import fetch_tracker_data

    data = fetch_tracker_data(tracker_url)
    if "error" in data:
        return {
            "status": "external_error",
            "error": data["error"],
            "tracker_url": tracker_url,
            "has_save": False,
            "seed": room.get("seed"),
            "server_status": "external",
            "connection_url": (
                f"{room['external_host']}:{room['external_port']}"
                if room.get("external_host") and room.get("external_port") else ""
            ),
            "players": [],
            "overall_completion_pct": 0.0,
            "total_checks_done": 0,
            "total_checks_total": 0,
            "goals_completed": 0,
            "goals_total": 0,
            "all_goals_completed": False,
            "last_activity": None,
        }

    # V1.4: pull WS overrides up-front. None when WS isn't connected for
    # this room; the loop below silently falls back to HTML status data
    # in that case.
    try:
        from tracker_ws import grid_overrides
        ws_overrides = grid_overrides(room["id"])
    except Exception as e:
        current_app.logger.warning(
            f"FEAT-17 grid_overrides({room['id']}) failed: {e}"
        )
        ws_overrides = None

    raw_players = data.get("players", [])
    players_out = []
    total_done = 0
    total_total = 0
    goals_done = 0
    used_ws = False
    for p in raw_players:
        done = int(p.get("checks_done") or 0)
        total = int(p.get("checks_total") or 0)
        pct = round(done / total * 100, 1) if total > 0 else 0.0
        slot = int(p.get("slot") or 0)
        ov = ws_overrides.get(slot) if ws_overrides else None
        if ov is not None:
            used_ws = True
            client_status = ov["client_status"]
            label = ov["status_label"]
            goal = ov["goal_completed"]
        else:
            client_status = int(p.get("status") or 0)
            label, goal = _status_label_from_int(client_status, done)
        if goal:
            goals_done += 1
        total_done += done
        total_total += total
        players_out.append({
            "slot": slot,
            "name": p.get("name") or "",
            "game": p.get("game") or "",
            "checks_done": done,
            "checks_total": total,
            "completion_pct": pct,
            "client_status": client_status,
            "status_label": label,
            "goal_completed": goal,
        })
    players_out.sort(key=lambda x: x["completion_pct"], reverse=True)
    overall = round(total_done / total_total * 100, 1) if total_total > 0 else 0.0
    return {
        "status": "ok",
        # `source` distinguishes html-only vs html-augmented-by-ws so the
        # frontend can surface a "live tracker connected" badge later.
        "source": "external+ws" if used_ws else "external",
        "tracker_url": tracker_url,
        "has_save": total_done > 0 or any(p["client_status"] > 0 for p in players_out),
        "seed": room.get("seed") or data.get("room_id"),
        "server_status": "external",
        "connection_url": (
            f"{room['external_host']}:{room['external_port']}"
            if room.get("external_host") and room.get("external_port") else ""
        ),
        "players": players_out,
        "overall_completion_pct": overall,
        "total_checks_done": total_done,
        "total_checks_total": total_total,
        "goals_completed": goals_done,
        "goals_total": len(players_out),
        "all_goals_completed": goals_done == len(players_out) and len(players_out) > 0,
        "last_activity": None,
    }


@bp.route("/api/rooms/<room_id>/tracker")
@requires_db
def room_tracker(room_id: str):
    import copy

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404

    # FEAT-08: external tracker takes priority. When the host has pasted a
    # tracker URL, fetch and shape that - even if there's also a local seed
    # (the host explicitly opted in to the external view).
    tracker_url = room.get("tracker_url")
    if tracker_url:
        return jsonify(_external_tracker_to_room_shape(room, tracker_url))

    seed = room.get("seed")
    if not seed:
        return jsonify({"status": "not_generated"})

    from app import get_records
    from ap_lib.parsing import parse_save

    records = get_records()
    matches = [r for r in records if r.seed == seed]
    if not matches:
        return jsonify({"status": "not_generated"})

    record = matches[0]
    manager = current_app.config["server_manager"]
    server = manager.status(seed)

    host = current_app.config.get("AP_HOST", "localhost")
    server_status = server.status if server else "stopped"
    connection_url = f"{host}:{server.port}" if server else ""

    # Deep-copy players from cached record to avoid mutating cache
    from ap_lib.models import PlayerInfo as PI

    tracker_record = copy.deepcopy(record)

    # Try to find and parse the latest save file
    from pathlib import Path
    import config

    has_save = False
    output_dir = Path(config.OUTPUT_DIR)
    if record.zip_path:
        save_path = Path(record.zip_path).with_suffix(".apsave")
        if save_path.exists():
            has_save = True
            # Reset checks so parse_save fills fresh data
            for p in tracker_record.players:
                p.checks_done = 0
                p.client_status = 0
            tracker_record.last_activity = None
            parse_save(save_path, tracker_record)

    players_data = sorted(
        [p.to_dict() for p in tracker_record.players],
        key=lambda p: p["completion_pct"],
        reverse=True,
    )

    total_done = sum(p["checks_done"] for p in players_data)
    total_total = sum(p["checks_total"] for p in players_data)
    goals_done = sum(1 for p in players_data if p["goal_completed"])
    goals_total = len(players_data)
    overall_pct = round(total_done / total_total * 100, 1) if total_total > 0 else 0.0

    return jsonify({
        "status": "ok",
        "has_save": has_save,
        "seed": seed,
        "server_status": server_status,
        "connection_url": connection_url,
        "players": players_data,
        "overall_completion_pct": overall_pct,
        "total_checks_done": total_done,
        "total_checks_total": total_total,
        "goals_completed": goals_done,
        "goals_total": goals_total,
        "all_goals_completed": goals_done == goals_total and goals_total > 0,
        "last_activity": tracker_record.last_activity.isoformat() if tracker_record.last_activity else None,
    })


def _attribute_slot_to_submitter(room_id: str, slot_name: str | None) -> dict:
    """FEAT-14: look up which Discord user submitted the YAML whose
    in-game player_name matches the tracker slot's display name. Match is
    exact equality on player_name. Players who aliased themselves on
    archipelago.gg won't match - for v1 that just means no attribution
    (no false positives).

    Returns a dict with submitter_user_id + submitter_username (both may
    be None for anonymous submits or no-match cases).
    """
    if not slot_name:
        return {"submitter_user_id": None, "submitter_username": None}
    from db import get_yamls_with_submitters
    yamls = get_yamls_with_submitters(room_id)
    match = next((y for y in yamls if y.get("player_name") == slot_name), None)
    if not match:
        return {"submitter_user_id": None, "submitter_username": None}
    return {
        "submitter_user_id": match.get("submitter_user_id"),
        "submitter_username": match.get("submitter_username"),
    }


def _augment_slot_with_ws(room_id: str, slot: int, data: dict) -> dict:
    """FEAT-17 V1.4: overlay WS state on top of the HTML scrape result.

    - `hints` get replaced when WS has fresher data (subscribed via
      SetNotify, so changes push in within a packet round-trip vs HTML
      scrape's 60s TTL).
    - `client_status`, `status_label`, `goal_completed` get added - fields
      not present in the HTML scrape today.

    Items received and locations stay HTML-sourced (Design C in the arch
    doc - items_received is per-slot-private to the slot's own
    connection, so a single base WS can't see them; locations need full
    name resolution which the HTML page gives us pre-rendered)."""
    if "error" in data:
        return data
    try:
        from tracker_ws import slot_overrides
        ov = slot_overrides(room_id, slot)
    except Exception as e:
        current_app.logger.warning(
            f"FEAT-17 slot_overrides({room_id}, {slot}) failed: {e}"
        )
        return data
    if ov is None:
        return data
    # Replace hints with WS data when WS has any. When WS is connected
    # but has no hints subscribed yet for this slot, KEEP the HTML hints
    # (avoids regressing to "no hints" while subscriptions warm up).
    if ov["hints"]:
        data["hints"] = ov["hints"]
        data["hints_source"] = "ws"
    else:
        data["hints_source"] = "html"
    data["client_status"] = ov["client_status"]
    data["status_label"] = ov["status_label"]
    data["goal_completed"] = ov["goal_completed"]
    return data


@bp.route("/api/rooms/<room_id>/tracker/slot/<int:slot>")
@requires_db
def room_tracker_slot(room_id: str, slot: int):
    """FEAT-14: per-slot detail (items / locations / hints) for the modal.

    External-tracker only - only meaningful when the host has set
    `room.tracker_url`. Adds owner attribution by joining the slot's
    in-game name to a `room_yamls` submitter. Ownership is gated by the
    blueprint's `_enforce_room_ownership` before_request hook, which also
    handles 404 for unknown room ids.

    FEAT-17 V1.4: hints + client_status overlay from the WebSocket cache
    when available (see `_augment_slot_with_ws`).
    """
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    tracker_url = room.get("tracker_url")
    if not tracker_url:
        return jsonify({"error": "Room has no tracker URL"}), 404

    from flask import request as _req
    try:
        team = int(_req.args.get("team", "0"))
    except ValueError:
        team = 0

    from tracker import fetch_slot_data
    data = fetch_slot_data(tracker_url, team, slot)
    if "error" not in data:
        data.update(_attribute_slot_to_submitter(room_id, data.get("name")))
        data = _augment_slot_with_ws(room_id, slot, data)
    return jsonify(data)


@bp.route("/api/rooms/<room_id>/activity-stream")
@requires_db
def room_activity_stream(room_id: str):
    """FEAT-17 V1.5: live in-game activity (PrintJSON events) from the
    WebSocket tracker.

    Distinct from `room["activity"]` (which surfaces application events
    like "yaml uploaded" from the activity table). This endpoint exposes
    the AP server's chat / item / hint / goal events for the room. Polled
    by a future Activity panel - accept `?since=<ts>` to skip events the
    client has already seen, return `now` so the next poll can chain.

    Returns `{status: "no_connection"}` (HTTP 200) when the WS subsystem
    isn't connected for this room - the frontend renders that as "live
    activity not available" rather than treating it as an error.
    """
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    from flask import request as _req
    since = _req.args.get("since", type=float)
    limit = _req.args.get("limit", default=200, type=int)
    try:
        from tracker_ws import read_activity
        result = read_activity(room_id, since=since, limit=limit)
    except Exception as e:
        current_app.logger.warning(
            f"FEAT-17 read_activity({room_id}) failed: {e}"
        )
        return jsonify({"status": "error", "error": str(e)})
    if result is None:
        return jsonify({"status": "no_connection", "events": []})
    return jsonify(result)


# Cache: {seed: (mtime, response_data)}
import threading

_item_tracker_cache: dict[str, tuple[float, dict]] = {}
_item_tracker_lock = threading.Lock()
_ITEM_TRACKER_CACHE_MAX = 100


@bp.route("/api/rooms/<room_id>/tracker/items")
@requires_db
def room_tracker_items(room_id: str):
    from pathlib import Path

    import config
    from ap_lib.parsing import extract_received_items, extract_slot_info
    from datapackage import get_datapackage

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404

    seed = room.get("seed")
    if not seed:
        return jsonify({"status": "not_generated", "has_datapackage": False, "players": []})

    from app import get_records

    records = get_records()
    matches = [r for r in records if r.seed == seed]
    if not matches:
        return jsonify({"status": "not_generated", "has_datapackage": False, "players": []})

    record = matches[0]
    if not record.zip_path:
        return jsonify({"status": "no_data", "has_datapackage": False, "players": []})

    save_path = Path(record.zip_path).with_suffix(".apsave")
    if not save_path.exists():
        return jsonify({"status": "no_save", "has_datapackage": False, "players": []})

    # Check cache by file mtime
    try:
        mtime = save_path.stat().st_mtime
    except OSError:
        mtime = 0.0

    with _item_tracker_lock:
        if seed in _item_tracker_cache:
            cached_mtime, cached_data = _item_tracker_cache[seed]
            if cached_mtime == mtime:
                return jsonify(cached_data)

    # Get DataPackage for name resolution
    manager = current_app.config["server_manager"]
    server = manager.status(seed)
    port = server.port if server else None
    dp = get_datapackage(seed, port)

    # Get slot info for sender name resolution
    slot_info = extract_slot_info(record.zip_path)

    # Extract received items
    received = extract_received_items(save_path)

    # Build response
    players_out = []
    for p in record.players:
        items_raw = received.get(p.slot, [])
        game_dp = dp.get("games", {}).get(p.game, {}) if dp else {}
        item_id_to_name = game_dp.get("item_id_to_name", {})
        location_id_to_name = game_dp.get("location_id_to_name", {})

        items_resolved = []
        counts = {"progression": 0, "useful": 0, "filler": 0, "trap": 0}
        for it in items_raw:
            flags = it["flags"]
            if flags & 4:
                classification = "trap"
            elif flags & 1:
                classification = "progression"
            elif flags & 2:
                classification = "useful"
            else:
                classification = "filler"
            counts[classification] += 1

            sender_slot = it["player"]
            sender_info = slot_info.get(sender_slot, {})

            items_resolved.append({
                "item_name": item_id_to_name.get(str(it["item"]), f"Item #{it['item']}"),
                "item_id": it["item"],
                "sender_name": sender_info.get("name", f"Slot {sender_slot}") if sender_slot else "Server",
                "location_name": location_id_to_name.get(str(it["location"]), f"Location #{it['location']}") if it["location"] >= 0 else "Starting item",
                "flags": flags,
                "classification": classification,
            })

        players_out.append({
            "slot": p.slot,
            "name": p.name,
            "game": p.game,
            "received_items": items_resolved,
            "item_counts": counts,
        })

    response = {
        "status": "ok",
        "has_datapackage": dp is not None,
        "players": players_out,
    }

    with _item_tracker_lock:
        if len(_item_tracker_cache) >= _ITEM_TRACKER_CACHE_MAX:
            # Evict oldest entry
            _item_tracker_cache.pop(next(iter(_item_tracker_cache)))
        _item_tracker_cache[seed] = (mtime, response)
    return jsonify(response)


@bp.route("/api/rooms/<room_id>/spoiler")
@requires_db
def room_spoiler(room_id: str):
    """Return the spoiler log text from the generated game zip."""
    room = get_room(room_id)
    if not room or not room.get("seed"):
        return jsonify({"error": "Room not found or not generated"}), 404

    from app import get_records

    records = get_records()
    matches = [r for r in records if r.seed == room["seed"]]
    if not matches or not matches[0].zip_path:
        return jsonify({"error": "Game zip not found"}), 404

    try:
        with zipfile.ZipFile(matches[0].zip_path) as zf:
            spoiler_files = [n for n in zf.namelist() if n.endswith("_Spoiler.txt")]
            if not spoiler_files:
                return jsonify({"error": "No spoiler log in this game (check spoiler level setting)"}), 404
            content = zf.read(spoiler_files[0]).decode("utf-8", errors="replace")
            return jsonify({"filename": spoiler_files[0], "content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/rooms/<room_id>/download")
@requires_db
def room_download(room_id: str):
    """Download the full generated game zip."""
    room = get_room(room_id)
    if not room or not room.get("seed"):
        return jsonify({"error": "Room not found or not generated"}), 404

    from app import get_records

    records = get_records()
    matches = [r for r in records if r.seed == room["seed"]]
    if not matches or not matches[0].zip_path:
        return jsonify({"error": "Game zip not found"}), 404

    zip_path = Path(matches[0].zip_path)
    if not zip_path.exists():
        return jsonify({"error": "Game zip file missing from disk"}), 404

    return send_file(zip_path, download_name=zip_path.name, as_attachment=True)


@bp.route("/api/rooms/<room_id>/patches")
@requires_db
def room_patches(room_id: str):
    room = get_room(room_id)
    if not room or not room.get("seed"):
        return jsonify({"error": "Room not found or not generated"}), 404

    # Find the zip and list patch files
    from app import get_records

    records = get_records()
    matches = [r for r in records if r.seed == room["seed"]]
    if not matches:
        return jsonify([])

    return jsonify(matches[0].patch_files)


@bp.route("/api/rooms/<room_id>/patches/<path:filename>")
@requires_db
def room_patch_download(room_id: str, filename: str):
    room = get_room(room_id)
    if not room or not room.get("seed"):
        return jsonify({"error": "Room not found or not generated"}), 404

    from app import get_records

    records = get_records()
    matches = [r for r in records if r.seed == room["seed"]]
    if not matches or not matches[0].zip_path:
        return jsonify({"error": "Game zip not found"}), 404

    # Extract the patch file from the zip
    try:
        with zipfile.ZipFile(matches[0].zip_path) as zf:
            if filename not in zf.namelist():
                return jsonify({"error": "Patch file not found in archive"}), 404

            import io
            data = zf.read(filename)
            return send_file(
                io.BytesIO(data),
                download_name=filename,
                as_attachment=True,
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# == Per-room APWorld pins (FEAT-21) ==


@bp.route("/api/rooms/<room_id>/apworlds")
@requires_db
def room_apworlds_get(room_id: str):
    """Host view of what APWorld versions this room needs.

    Auto-derived from the room s YAML game list, joined against the
    Archipelago-index entries and any per-room version pins. Each row
    has the full list of available versions so the host can pick.
    Caller is already gated by _enforce_room_ownership.
    """
    from api.apworlds import apworlds_for_room

    room = get_room(room_id) or {}
    yamls = get_yamls(room_id)
    pins = get_room_apworlds(room_id)
    return jsonify(apworlds_for_room(
        yamls, pins, host=True,
        force_latest=bool(room.get("force_latest_apworld_versions")),
        allow_mixed=bool(room.get("allow_mixed_apworld_versions")),
    ))


@bp.route("/api/rooms/<room_id>/apworlds/download-all")
@requires_db
def room_apworlds_download_all(room_id: str):
    """FEAT-25: bundle every pinned APWorld file for this room into one
    zip the host can download in a single click.

    Sibling to `yamls_download_all` (FEAT-09): same shape (in-memory
    BytesIO + send_file), but yields .apworld files resolved against
    the dowlle/Archipelago-index pins. `local` entries are read from
    the cloned index repo; `url` entries are fetched upstream.
    Built-in-only pins and unindexed YAML games are silently skipped
    (nothing to bundle for either). Returns 400 if the resulting zip
    would be empty so the host gets a clear "pin some APWorlds first"
    signal instead of a useless empty download.

    Already gated on host ownership by `_enforce_room_ownership`.
    """
    from api.apworlds import iter_pinned_apworld_files

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    yamls = get_yamls(room_id)
    if not yamls:
        return jsonify({"error": "No YAMLs uploaded - nothing to resolve"}), 400
    pins = get_room_apworlds(room_id)

    from io import BytesIO
    buf = BytesIO()
    count = 0
    seen_names: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, payload in iter_pinned_apworld_files(
            yamls, pins,
            force_latest=bool(room.get("force_latest_apworld_versions")),
        ):
            # iter_pinned_apworld_files dedupes per-apworld already, but
            # belt-and-braces against the unlikely "same world.name yields
            # the same filename twice" case (it shouldn't - the iterator
            # tracks `seen_apworlds`, but let's not rely on a private
            # invariant in two places).
            if filename in seen_names:
                continue
            seen_names.add(filename)
            zf.writestr(filename, payload)
            count += 1

    if count == 0:
        return jsonify({
            "error": (
                "No downloadable APWorlds pinned for this room. Pin a "
                "version per game in the room's Settings > APWorlds tab "
                "(games must be in the dowlle/Archipelago-index)."
            ),
        }), 400

    buf.seek(0)
    safe_room = "".join(c if c.isalnum() or c in "-_" else "_" for c in (room.get("name") or room_id))
    download_name = f"{safe_room}-apworlds.zip"
    return send_file(
        buf,
        download_name=download_name,
        as_attachment=True,
        mimetype="application/zip",
    )


@bp.route("/api/rooms/<room_id>/apworlds/auto-pin-all", methods=["POST"])
@requires_db
def room_apworlds_auto_pin_all(room_id: str):
    """FEAT-28 + v2: retroactively pin / upgrade every game in this room's
    YAMLs against the dowlle index.

    Behaviour per game:
      - aggregate every `requires.game.<Name>` declaration across the
        room's YAMLs into a `[v1, v2, ...]` list;
      - pick the highest indexed version (or fall back to index latest);
      - if no pin exists -> create it;
      - if a pin exists and the room flag `auto_upgrade_apworld_pins`
        is on, only upgrade when target > current (never downgrade);
      - if the flag is off, leave the existing pin untouched.

    While iterating, also backfills `room_yamls.apworld_versions` for
    rows that pre-date the column - means an old room's YAML overview
    starts showing per-YAML version warnings the moment the host clicks
    the button.

    Already gated on host ownership by `_enforce_room_ownership`.
    """
    from api.apworlds import (
        _compare_versions,
        _get_game_lookup,
        select_pin_version,
        split_yaml_games,
    )
    from validation import extract_required_apworld_versions

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    yamls = get_yamls(room_id)
    if not yamls:
        return jsonify({"error": "No YAMLs uploaded"}), 400

    auto_upgrade = bool(room.get("auto_upgrade_apworld_pins", True))
    lookup = _get_game_lookup()
    existing_pin_versions: dict[str, str] = {
        p["apworld_name"]: p["version"] for p in get_room_apworlds(room_id)
    }

    # Pass 1: aggregate per-game version requests across every YAML in
    # the room AND backfill the cached apworld_versions column for any
    # YAML that's missing it.
    from db import update_yaml_apworld_versions
    requested_versions: dict[str, list[str]] = {}
    for y in yamls:
        body = y.get("yaml_content") or ""
        if not body:
            continue
        try:
            parsed = extract_required_apworld_versions(body)
        except Exception:
            parsed = {}
        if y.get("apworld_versions") is None:
            try:
                update_yaml_apworld_versions(y["id"], parsed)
            except Exception:
                pass
        for g, v in parsed.items():
            requested_versions.setdefault(g, []).append(v)

    pinned: list[str] = []
    upgraded: list[str] = []  # existing pins bumped to a higher version
    pinned_with_yaml_version: list[str] = []  # pinned/upgraded via YAML hint
    skipped_already_pinned: list[str] = []  # already at the right version
    skipped_locked: list[str] = []  # auto-upgrade off and pin exists
    skipped_builtin: list[str] = []  # in the index but ships with AP core
    skipped_not_in_index: list[str] = []  # genuinely no entry in the index

    seen: set[str] = set()
    for y in yamls:
        for game in split_yaml_games(y.get("game") or ""):
            if game in seen:
                continue
            seen.add(game)
            world = lookup.get(game)
            if not world:
                skipped_not_in_index.append(game)
                continue
            requested = requested_versions.get(game)
            target = select_pin_version(world, requested)
            if not target:
                # World exists in the index but has no downloadable
                # version - this is the "built-in / core AP" pattern
                # (TOML stub with name + supported = true and no
                # `[[versions]]` blocks). Distinguishing it from
                # genuinely-not-indexed lets the host see at a glance
                # which games need an index contribution vs which are
                # already covered by AP core.
                skipped_builtin.append(game)
                continue

            current = existing_pin_versions.get(world.name)
            if current is None:
                # No prior pin - create.
                try:
                    set_room_apworld(room_id, world.name, target)
                    existing_pin_versions[world.name] = target
                    pinned.append(game)
                    if requested and target in set(requested):
                        pinned_with_yaml_version.append(game)
                except Exception:
                    pass
                continue

            # Pin exists - decide whether to upgrade.
            cmp = _compare_versions(target, current)
            if cmp <= 0:
                skipped_already_pinned.append(game)
                continue
            if not auto_upgrade:
                skipped_locked.append(game)
                continue
            try:
                set_room_apworld(room_id, world.name, target)
                existing_pin_versions[world.name] = target
                upgraded.append(game)
                if requested and target in set(requested):
                    pinned_with_yaml_version.append(game)
            except Exception:
                pass

    return jsonify({
        "pinned": pinned,
        "upgraded": upgraded,
        "pinned_with_yaml_version": pinned_with_yaml_version,
        "skipped_already_pinned": skipped_already_pinned,
        "skipped_locked": skipped_locked,
        "skipped_builtin": skipped_builtin,
        "skipped_not_in_index": skipped_not_in_index,
    })


@bp.route("/api/rooms/<room_id>/apworlds/<apworld_name>", methods=["PUT"])
@requires_db
def room_apworld_set(room_id: str, apworld_name: str):
    """Pin a specific version, or clear the pin entirely (version=null).

    Body: { "version": "0.5.2" } to set, or { "version": null } to clear.
    We do not validate the version against the index - it can drift (a
    referenced version gets removed upstream); the picker UI surfaces
    stale pins so the host can re-pick rather than the API rejecting
    an unknown version outright.
    """
    data = request.get_json() or {}
    version = data.get("version")
    if version in (None, ""):
        clear_room_apworld(room_id, apworld_name)
        return jsonify({"status": "cleared", "apworld_name": apworld_name})
    row = set_room_apworld(room_id, apworld_name, str(version))
    return jsonify({"status": "pinned", **row})
