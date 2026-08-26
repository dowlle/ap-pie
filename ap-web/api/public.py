"""Public, no-auth-required read endpoints for room landing pages.

The Bananium-shaped public landing page needs to render basic room state
(name, YAMLs, status, external server host:port if set) for visitors who
don't have an Archipelago Pie account. This blueprint serves a sanitized subset of
the room model - no generation logs, no host activity feed, no anything
that could aid enumeration of the host's environment.

The room ID itself is the capability for read access (UUIDs aren't
enumerable from the outside), matching how the Play page treats seeds. A
host who wants to keep a room private should not share the room URL.
"""

from __future__ import annotations

from io import BytesIO

from flask import Blueprint, current_app, jsonify, request, send_file, session

from db import (
    _db_url,
    add_activity,
    claim_yaml,
    count_yamls_by_submitter,
    get_room,
    get_room_apworlds,
    get_user,
    get_yaml,
    get_yamls,
    get_yamls_with_submitters,
    maybe_auto_close_room,
    release_yaml,
    remove_yaml,
    update_yaml_content,
    update_yaml_validation,
)
from validation import extract_player_info, validate_yaml

import analytics

bp = Blueprint("public", __name__)


def _requires_db():
    if _db_url is None:
        return jsonify({"error": "Database not available"}), 503
    return None


def _current_session_user() -> dict | None:
    """Return the logged-in user dict, or None for anonymous visitors. The
    blueprint sits in public_prefixes so the global auth middleware never
    enforces a session - this helper is for routes that opt into a soft
    session check (FEAT-13: submitter self-delete; conditional submitter
    exposure on the public yaml list).
    """
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user(user_id) or None


def _sanitize_room(room: dict) -> dict:
    """Strip host-only fields before exposing publicly."""
    return {
        "id": room["id"],
        "name": room["name"],
        "description": room.get("description") or "",
        "status": room["status"],
        "host_name": room["host_name"],
        "seed": room.get("seed"),
        "external_host": room.get("external_host"),
        "external_port": room.get("external_port"),
        "max_players": room.get("max_players") or 0,
        "max_yamls_per_user": room.get("max_yamls_per_user") or 0,
        "race_mode": room.get("race_mode") or False,
        "spoiler_level": room.get("spoiler_level"),
        "require_discord_login": room.get("require_discord_login") or False,
        "submit_deadline": room.get("submit_deadline"),
        "tracker_url": room.get("tracker_url"),
        "claim_mode": room.get("claim_mode") or False,
        "allow_mixed_apworld_versions": room.get("allow_mixed_apworld_versions") or False,
        "force_latest_apworld_versions": room.get("force_latest_apworld_versions") or False,
        # FEAT-28 v2: surface so the public room can decide whether to
        # render version-mismatch warnings the same way RoomDetail does.
        # (When this is off and the host's pin disagrees with a YAML's
        # declared version, the warning is still useful info for the
        # player - upgrade off only stops auto-pin rewriting, not the UI.)
        "auto_upgrade_apworld_pins": (
            True if room.get("auto_upgrade_apworld_pins") is None
            else bool(room.get("auto_upgrade_apworld_pins"))
        ),
        "created_at": room.get("created_at"),
    }


def _sanitize_yaml(y: dict, *, expose_submitter: bool = False) -> dict:
    """The validation_error string is included because it tells the
    submitting player what's wrong with their YAML; it never contains
    anything more sensitive than the player name + game (already public).
    filename is also public - the in-browser viewer endpoint already
    returns it, so listing it in the table doesn't widen the trust model.

    submitter_username (FEAT-13) is included only when expose_submitter is
    True, which the route handler sets based on whether the requester has
    a session. Anonymous Internet visitors don't see Discord identities;
    logged-in viewers do (so co-players can know who to ping for hints).
    """
    out = {
        "id": y["id"],
        "player_name": y["player_name"],
        "game": y["game"],
        "filename": y.get("filename"),
        "validation_status": y["validation_status"],
        "validation_error": y.get("validation_error"),
        "uploaded_at": y.get("uploaded_at"),
        # FEAT-28 v2: cached `{game_name: version}` map from the YAML's
        # `requires.game` block. None when the YAML doesn't declare
        # versions or hasn't been parsed yet (legacy YAMLs - the room-
        # wide auto-pin button backfills these). Public because the
        # warning surface (orange version mismatch) is on the public
        # room page too, not just host-side.
        "apworld_versions": y.get("apworld_versions"),
    }
    if expose_submitter:
        out["submitter_username"] = y.get("submitter_username")
        # FEAT-20: numeric submitter id is included alongside the username
        # so the frontend can determine "did *I* claim this?" reliably from
        # AuthUser.id, instead of falling back to a brittle name match.
        # Same trust model - only logged-in viewers get this.
        out["submitter_user_id"] = y.get("submitter_user_id")
    return out


@bp.route("/api/public/rooms/<room_id>")
def public_room_read(room_id: str):
    db_err = _requires_db()
    if db_err:
        return db_err

    # FEAT-04: lazy auto-close - if a deadline has passed, the public landing
    # page should reflect 'closed' immediately rather than wait for the next
    # sweeper tick. Returns the up-to-date row (or {} if unknown).
    room = maybe_auto_close_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404

    # Logged-in viewers get the submitter Discord username for each YAML
    # (FEAT-13). Anonymous visitors get the same shape minus that field.
    user = _current_session_user()
    if user is not None:
        yamls = get_yamls_with_submitters(room_id)
    else:
        yamls = get_yamls(room_id)

    payload = _sanitize_room(room)
    payload["yamls"] = [_sanitize_yaml(y, expose_submitter=user is not None) for y in yamls]
    payload["player_count"] = len(yamls)
    # FEAT-31: the public room page is where a shared link lands, so this is
    # the arrival event for players who never touch the SPA landing page.
    analytics.record_event(
        "room_public_view",
        user_id=(user or {}).get("id"),
        room_id=room_id,
        props={"has_session": user is not None},
        req=request,
    )
    return jsonify(payload)


@bp.route("/api/public/rooms/<room_id>/apworlds")
def public_room_apworlds(room_id: str):
    """Public "APWorlds you need to install" panel.

    Same join as the host endpoint but with `host=False`, which (a) hides
    the full version list and (b) drops games where the host hasn't pinned
    a version yet (no point telling players "we don't know yet"). Players
    get one row per pinned game with display name, source link, and a
    `download_url` pointing at the index download proxy.
    """
    db_err = _requires_db()
    if db_err:
        return db_err

    from api.apworlds import apworlds_for_room

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    yamls = get_yamls(room_id)
    pins = get_room_apworlds(room_id)
    return jsonify(apworlds_for_room(
        yamls, pins, host=False,
        force_latest=bool(room.get("force_latest_apworld_versions")),
        allow_mixed=bool(room.get("allow_mixed_apworld_versions")),
    ))


@bp.route("/api/public/rooms/<room_id>/builder-schemas")
def public_room_builder_schemas(room_id: str):
    """FEAT-38: per-game option schemas for the guided YAML builder.

    One entry per APWorld the host pinned, carrying the Tier-1 option form
    derived from that exact pinned artifact (so the builder's `requires`
    version and option set always match what the room will run). Anonymous
    access is deliberate - anyone with the room URL can build + download a
    YAML; SUBMITTING it still goes through the room's existing claim/login
    gates on the submit endpoint. The schema data is game metadata (option
    names, defaults, ranges), nothing sensitive.
    """
    db_err = _requires_db()
    if db_err:
        return db_err

    from api.apworlds import builder_schemas_for_pins

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    pins = get_room_apworlds(room_id)
    return jsonify(builder_schemas_for_pins(
        pins,
        force_latest=bool(room.get("force_latest_apworld_versions")),
    ))


@bp.route("/api/public/rooms/<room_id>/yamls/<int:yaml_id>")
def public_yaml_read(room_id: str, yaml_id: int):
    """Return a single YAML's contents for in-browser viewing.

    Mirrors Bananium's per-YAML 'View' link: anyone with the room URL can
    inspect any submitted YAML. The transparency is intentional - players
    want to see what others submitted to spot duplicate names, conflicting
    item links, etc. The YAML format itself doesn't carry secrets (passwords
    are room-level not per-YAML), so exposing yaml_content publicly is the
    same trust model as exposing player_name + game already.
    """
    db_err = _requires_db()
    if db_err:
        return db_err

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404

    yamls = get_yamls(room_id)
    target = next((y for y in yamls if y["id"] == yaml_id), None)
    if not target:
        return jsonify({"error": "YAML not found in this room"}), 404

    return jsonify({
        "id": target["id"],
        "player_name": target["player_name"],
        "game": target["game"],
        "filename": target["filename"],
        "validation_status": target["validation_status"],
        "validation_error": target.get("validation_error"),
        "yaml_content": target["yaml_content"],
        "uploaded_at": target.get("uploaded_at"),
    })


@bp.route("/api/public/rooms/<room_id>/yamls/<int:yaml_id>/download")
def public_yaml_download(room_id: str, yaml_id: int):
    """Public per-YAML file download. Same trust model as the JSON read above -
    the room URL is the capability. Lets players grab their own (or anyone's)
    submitted YAML as a file rather than copying it out of the in-browser viewer.
    """
    db_err = _requires_db()
    if db_err:
        return db_err

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404

    yamls = get_yamls(room_id)
    target = next((y for y in yamls if y["id"] == yaml_id), None)
    if not target:
        return jsonify({"error": "YAML not found in this room"}), 404

    buf = BytesIO(target["yaml_content"].encode("utf-8"))
    return send_file(
        buf,
        download_name=target["filename"] or f"player_{target['id']}.yaml",
        as_attachment=True,
        mimetype="text/yaml",
    )


def _serialize_generated_slot(slot_row: dict, user: dict | None) -> dict:
    """Public-safe slot overlay. Discord identity is session-gated."""
    is_mine = bool(user and slot_row.get("owner_user_id") == user.get("id"))
    out = {
        "team": slot_row["team"],
        "slot": slot_row["slot"],
        "player_name": slot_row["player_name"],
        "game": slot_row.get("game") or "",
        "claimed": slot_row.get("owner_user_id") is not None,
        "is_mine": is_mine,
        "owner_username": slot_row.get("owner_username") if user else None,
        "bk_since": slot_row.get("bk_since"),
        "bk_confirmed_at": slot_row.get("bk_confirmed_at"),
        "go_mode_since": slot_row.get("go_mode_since"),
        "slot_note": slot_row.get("slot_note") or "",
        "state_updated_at": slot_row.get("state_updated_at"),
    }
    return out


@bp.route("/api/public/rooms/<room_id>/slots")
def public_generated_slots(room_id: str):
    db_err = _requires_db()
    if db_err:
        return db_err
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    from db import get_generated_room, list_room_slots
    association = get_generated_room(room_id)
    user = _current_session_user()
    return jsonify({
        "associated": association is not None,
        "slots": [_serialize_generated_slot(row, user) for row in list_room_slots(room_id)],
    })


@bp.route("/api/public/rooms/<room_id>/slots/<int:team>/<int:slot>/claim", methods=["POST"])
def public_generated_slot_claim(room_id: str, team: int, slot: int):
    db_err = _requires_db()
    if db_err:
        return db_err
    user = _current_session_user()
    if not user:
        return jsonify({"error": "Log in with Discord to claim this generated slot"}), 401
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    from db import claim_room_slot, get_generated_room, get_room_slot
    if not get_generated_room(room_id):
        return jsonify({"error": "This room is not attached to a generated room"}), 409
    current = get_room_slot(room_id, team, slot)
    if not current:
        return jsonify({"error": "Generated slot not found"}), 404
    if current.get("owner_user_id") is not None:
        return jsonify({"error": "This generated slot is already claimed"}), 409
    claimed = claim_room_slot(room_id, team, slot, int(user["id"]))
    if not claimed:
        return jsonify({"error": "This generated slot was just claimed by someone else"}), 409
    add_activity(
        room_id, "generated_slot_claimed",
        f"{user.get('discord_username') or 'Player'} claimed generated slot {current['player_name']}",
    )
    return jsonify({"status": "claimed", "team": team, "slot": slot})


@bp.route("/api/public/rooms/<room_id>/slots/<int:team>/<int:slot>/release", methods=["POST"])
def public_generated_slot_release(room_id: str, team: int, slot: int):
    db_err = _requires_db()
    if db_err:
        return db_err
    user = _current_session_user()
    if not user:
        return jsonify({"error": "Log in with Discord to release this generated slot"}), 401
    from db import release_room_slot
    released = release_room_slot(room_id, team, slot, int(user["id"]))
    if not released:
        return jsonify({"error": "You do not own this generated slot"}), 403
    add_activity(
        room_id, "generated_slot_released",
        f"{user.get('discord_username') or 'Player'} released generated slot {released['player_name']}",
    )
    return jsonify({"status": "released", "team": team, "slot": slot})


@bp.route("/api/public/rooms/<room_id>/slots/<int:team>/<int:slot>/state", methods=["PATCH"])
def public_generated_slot_state(room_id: str, team: int, slot: int):
    db_err = _requires_db()
    if db_err:
        return db_err
    user = _current_session_user()
    if not user:
        return jsonify({"error": "Log in with Discord to update slot coordination"}), 401
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    from db import get_room_slot, update_room_slot_state
    current = get_room_slot(room_id, team, slot)
    if not current:
        return jsonify({"error": "Generated slot not found"}), 404
    may_edit = (
        current.get("owner_user_id") == user.get("id")
        or room.get("host_user_id") == user.get("id")
        or bool(user.get("is_admin"))
    )
    if not may_edit:
        return jsonify({"error": "Only the slot owner or room host can update coordination state"}), 403
    data = request.get_json() or {}
    allowed = {"bk_action", "go_mode", "slot_note"}
    if any(key not in allowed for key in data):
        return jsonify({"error": "Unknown coordination field"}), 400
    bk_action = data.get("bk_action")
    if bk_action is not None and bk_action not in ("set", "confirm", "clear"):
        return jsonify({"error": "bk_action must be set, confirm, or clear"}), 400
    go_mode = data.get("go_mode")
    if go_mode is not None and not isinstance(go_mode, bool):
        return jsonify({"error": "go_mode must be true or false"}), 400
    note = data.get("slot_note")
    if note is not None:
        if not isinstance(note, str):
            return jsonify({"error": "slot_note must be text"}), 400
        note = note.strip()
        if len(note) > 280:
            return jsonify({"error": "slot_note is too long (maximum 280 characters)"}), 400
    updated = update_room_slot_state(
        room_id, team, slot, int(user["id"]),
        bk_action=bk_action, go_mode=go_mode, slot_note=note,
    )
    action_parts = []
    # Still-BK confirmations update bk_confirmed_at but deliberately do not
    # append a fresh room-activity row every time. This is the coalescing
    # boundary for large asyncs: the current timestamp stays visible on the
    # slot while the shared feed remains readable.
    if bk_action and bk_action != "confirm":
        action_parts.append({"set": "marked BK", "confirm": "confirmed Still BK", "clear": "cleared BK"}[bk_action])
    if go_mode is not None:
        action_parts.append("entered go mode" if go_mode else "left go mode")
    if note is not None:
        action_parts.append("updated their slot note")
    if action_parts:
        add_activity(
            room_id, "slot_coordination_updated",
            f"{user.get('discord_username') or 'Player'} {'; '.join(action_parts)} for {current['player_name']}",
        )
    return jsonify(_serialize_generated_slot(updated, user))


@bp.route("/api/public/rooms/<room_id>/tracker")
def public_room_tracker(room_id: str):
    """FEAT-08: public mirror of /api/rooms/<id>/tracker. Returns tracker
    data for an external archipelago.gg tracker URL only - we don't expose
    locally-generated apsave parsing here (that's host-only). Anonymous
    visitors of /r/<id> can see the live tracker for an external game.
    """
    db_err = _requires_db()
    if db_err:
        return db_err

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404

    tracker_url = room.get("tracker_url")
    if not tracker_url:
        return jsonify({"status": "no_tracker"})

    # Reuse the host-side adapter so the JSON shape matches LiveTracker's
    # contract one-to-one. The function only reads room dict fields the
    # public sanitiser already exposes (external_host/port, seed, etc).
    from api.rooms import _external_tracker_to_room_shape
    return jsonify(_external_tracker_to_room_shape(room, tracker_url))


@bp.route("/api/public/rooms/<room_id>/tracker/slot/<int:slot>")
def public_room_tracker_slot(room_id: str, slot: int):
    """FEAT-14: public mirror of the per-slot tracker endpoint.

    Returns the same shape as the host route but sanitises owner
    attribution for anonymous viewers - Discord identities only flow to
    logged-in viewers (mirrors FEAT-13's `_sanitize_yaml` rule).

    FEAT-17 V1.4: same WebSocket-cache overlay as the host route. Hint /
    status data is identical for both anon and logged-in viewers; only
    submitter attribution differs.
    """
    db_err = _requires_db()
    if db_err:
        return db_err

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
        user = _current_session_user()
        from api.rooms import _attribute_slot_to_submitter, _coordination_slot_overlay
        coordination = _coordination_slot_overlay(room_id, team, slot)
        if coordination:
            safe_coordination = {
                key: value for key, value in coordination.items()
                if key not in ("owner_user_id", "owner_source")
            }
            safe_coordination["is_mine"] = bool(
                user and coordination.get("owner_user_id") == user.get("id")
            )
            if user is None:
                safe_coordination["owner_username"] = None
            data["coordination"] = safe_coordination
            data["submitter_user_id"] = coordination.get("owner_user_id") if user else None
            data["submitter_username"] = coordination.get("owner_username") if user else None
        elif user is not None:
            data.update(_attribute_slot_to_submitter(room_id, data.get("name")))
        else:
            # FEAT-13 rule: anonymous visitors don't see Discord identities.
            data["submitter_user_id"] = None
            data["submitter_username"] = None
        from api.rooms import _augment_slot_with_ws
        data = _augment_slot_with_ws(room_id, slot, data)
    return jsonify(data)


@bp.route("/api/public/rooms/<room_id>/activity-stream")
def public_room_activity_stream(room_id: str):
    """FEAT-17 V1.5: public mirror of the activity-stream endpoint.

    PrintJSON events are broadcast to all clients on the AP server - no
    per-slot privacy at the protocol level - so anonymous visitors see
    the same stream as the host. Useful for /r/<id> visitors who want a
    live activity panel without needing a Discord login."""
    db_err = _requires_db()
    if db_err:
        return db_err

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    from flask import request as _req
    since = _req.args.get("since", type=float)
    limit = _req.args.get("limit", default=200, type=int)
    try:
        from tracker_ws import read_activity
        result = read_activity(room_id, since=since, limit=limit)
    except Exception:
        return jsonify({"status": "error", "events": []})
    if result is None:
        return jsonify({"status": "no_connection", "events": []})
    return jsonify(result)


@bp.route("/api/public/rooms/<room_id>/yamls/<int:yaml_id>", methods=["PUT"])
def public_yaml_update(room_id: str, yaml_id: int):
    """FEAT-18: a logged-in submitter updates their own YAML in place
    (vs the current delete-then-resubmit churn). Same auth gate as
    public_yaml_delete: must be logged in, must own the row, room must
    be open. Anonymous submits stay non-updatable since there's no
    identity to match.

    Re-runs validation against the room's other YAMLs (excluding this
    one - otherwise the row would conflict with itself on player_name).
    Accepts either a multipart `file` upload or a JSON body with
    `yaml_content`, mirroring submit_yaml's contract.

    Activity log entry distinguishes a content edit from a rename so
    the host's feed reads as a change-log instead of churn:
      - same player_name: "<user> updated <game> YAML for player X"
      - changed player_name: "<user> renamed YAML 'Old' → 'New'"
    """
    db_err = _requires_db()
    if db_err:
        return db_err

    user = _current_session_user()
    if user is None:
        return jsonify({"error": "Login required to update a submission."}), 401

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] != "open":
        return jsonify({
            "error": "Room is no longer open - only the host can change YAMLs after closing.",
        }), 400

    target = get_yaml(yaml_id)
    if not target or target.get("room_id") != room_id:
        return jsonify({"error": "YAML not found in this room"}), 404
    if target.get("submitter_user_id") != user["id"]:
        return jsonify({"error": "You can only update your own submission."}), 403

    # Accept the same shapes as POST /api/submit/<room_id>: multipart file
    # OR JSON with yaml_content. Filename falls back to a derived
    # "<player> - <game>.yaml" so a JSON-body submitter doesn't end up
    # with a blank filename column.
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

    # Duplicate-name validation must EXCLUDE the current row, otherwise
    # editing without renaming would always fail (the row collides with
    # itself). Reusing the old name on the new content is fine; collisions
    # only matter against OTHER rows.
    siblings = [y for y in get_yamls(room_id) if y["id"] != yaml_id]
    existing_names = [y["player_name"] for y in siblings]
    is_valid, error = validate_yaml(yaml_content, existing_names)

    old_player_name = target.get("player_name") or ""
    old_game = target.get("game") or ""

    updated = update_yaml_content(
        yaml_id=yaml_id,
        player_name=new_player_name,
        game=new_game,
        yaml_content=yaml_content,
        filename=filename,
    )

    uploader = user.get("discord_username") or "Unknown"
    if is_valid:
        update_yaml_validation(yaml_id, "validated")
        updated["validation_status"] = "validated"
        updated["validation_error"] = None
    else:
        update_yaml_validation(yaml_id, "failed", error)
        updated["validation_status"] = "failed"
        updated["validation_error"] = error

    # Activity log: distinguish rename from content-only edit. Both events
    # use the same `yaml_updated` type so a host filtering the feed gets
    # all updates in one bucket; the message text carries the nuance.
    renamed = old_player_name != new_player_name
    if renamed:
        message = (
            f"{uploader} renamed YAML '{old_player_name}' → '{new_player_name}'"
            f" ({new_game})"
        )
    else:
        if is_valid:
            message = f"{uploader} updated {new_game} YAML for player {new_player_name}"
        else:
            message = (
                f"{uploader} updated {new_game} YAML for player "
                f"{new_player_name} (now invalid: {error})"
            )
    add_activity(
        room_id, "yaml_updated", message,
        actor_user_id=user["id"], subject_yaml_id=yaml_id,
    )

    return jsonify({
        "id": updated["id"],
        "player_name": new_player_name,
        "game": new_game,
        "validation_status": updated["validation_status"],
        "validation_error": updated.get("validation_error"),
        "renamed": renamed,
        "previous_player_name": old_player_name if renamed else None,
    })


@bp.route("/api/public/rooms/<room_id>/yamls/<int:yaml_id>", methods=["DELETE"])
def public_yaml_delete(room_id: str, yaml_id: int):
    """FEAT-13: a logged-in submitter can delete their own YAML row from the
    public lobby while the room is still open. Anonymous submits stay
    deletable only by the host (no submitter_user_id to match against).
    Hosts already delete via the auth-gated /api/rooms/<id>/yamls/<id> path.
    """
    db_err = _requires_db()
    if db_err:
        return db_err

    user = _current_session_user()
    if user is None:
        return jsonify({"error": "Login required to delete a submission."}), 401

    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    if room["status"] != "open":
        return jsonify({
            "error": "Room is no longer open - only the host can remove YAMLs after closing."
        }), 400

    # Pull the row directly via get_yamls_with_submitters so we can read
    # submitter_user_id without a separate query.
    rows = get_yamls_with_submitters(room_id)
    target = next((y for y in rows if y["id"] == yaml_id), None)
    if not target:
        return jsonify({"error": "YAML not found in this room"}), 404

    if target.get("submitter_user_id") != user["id"]:
        return jsonify({
            "error": "You can only delete your own submission."
        }), 403

    if remove_yaml(yaml_id):
        # Activity log entry mirrors the upload format so the host's feed
        # tells a coherent story: "<user> uploaded ..." followed later by
        # "<user> deleted ...". Without this the row just disappears with
        # no record.
        actor = user.get("discord_username") or "Unknown"
        add_activity(
            room_id, "yaml_deleted",
            f"{actor} deleted {target['game']} YAML for player {target['player_name']}",
            actor_user_id=user["id"],
        )
        return jsonify({"status": "deleted"})
    return jsonify({"error": "YAML not found"}), 404


# ── FEAT-20: claim-mode YAML rooms ────────────────────────────────


def _gate_claim_action(room_id: str, yaml_id: int, user) -> tuple[dict, dict] | tuple[None, tuple]:
    """Shared preflight for /claim and /release. Returns (room, yaml_row) on
    success, or (None, (jsonify, status)) for the route to return verbatim.
    Centralised so the two routes don't drift on auth / room-state checks.
    """
    if user is None:
        return None, (jsonify({"error": "Login required to claim a slot."}), 401)

    room = get_room(room_id)
    if not room:
        return None, (jsonify({"error": "Room not found"}), 404)
    if not room.get("claim_mode"):
        return None, (jsonify({
            "error": "This room isn't in claim mode."
        }), 400)
    # BUG-05: claim/release stay open while the room is "open" OR "closed".
    # Once status flips to generating/generated/playing, the seed locks slot
    # mappings and changing them post-hoc would corrupt the game. Hosts
    # explicitly close rooms (or auto-close fires) to freeze YAML uploads
    # while still letting late joiners pick from the unclaimed pool.
    if room["status"] not in ("open", "closed"):
        return None, (jsonify({
            "error": "Room has already been generated - claims are frozen.",
        }), 400)

    target = get_yaml(yaml_id)
    if not target or target["room_id"] != room_id:
        return None, (jsonify({"error": "YAML not found in this room"}), 404)

    return room, target


@bp.route("/api/public/rooms/<room_id>/yamls/<int:yaml_id>/claim", methods=["POST"])
def public_yaml_claim(room_id: str, yaml_id: int):
    """FEAT-20: a logged-in player claims an unclaimed YAML in a claim-mode
    room. Atomic write: two simultaneous claims resolve to one 200 + one
    409. Honours the per-user cap (max_yamls_per_user) so a player can't
    grab more slots than the host's quota.
    """
    db_err = _requires_db()
    if db_err:
        return db_err

    user = _current_session_user()
    gate = _gate_claim_action(room_id, yaml_id, user)
    if gate[0] is None:
        return gate[1]
    room, target = gate

    # FEAT-31: recorded after the gate so it counts real attempts on a
    # claimable slot, which is what the attempt-vs-race ratio needs.
    analytics.record_event(
        "claim_attempted", user_id=user["id"], room_id=room_id, req=request
    )

    if target.get("submitter_user_id") is not None:
        # Already claimed - surface the username so the UI can render
        # "Already claimed by @<user>" without an extra round-trip.
        owner = get_user(target["submitter_user_id"]) or {}
        return jsonify({
            "error": "This slot is already claimed.",
            "claimed_by": owner.get("discord_username"),
        }), 409

    cap = room.get("max_yamls_per_user") or 0
    if cap > 0:
        already = count_yamls_by_submitter(room_id, user["id"])
        if already >= cap:
            return jsonify({
                "error": f"You've reached this room's per-player cap ({cap}). "
                         f"Release a slot before claiming another.",
            }), 400

    claimed = claim_yaml(yaml_id, user["id"])
    if claimed is None:
        # Lost the race - somebody else's UPDATE landed first.
        analytics.record_event(
            "claim_raced", user_id=user["id"], room_id=room_id, req=request
        )
        owner = None
        latest = get_yaml(yaml_id)
        if latest and latest.get("submitter_user_id"):
            owner = get_user(latest["submitter_user_id"]) or {}
        return jsonify({
            "error": "This slot was just claimed by someone else.",
            "claimed_by": (owner or {}).get("discord_username") if owner else None,
        }), 409

    actor = user.get("discord_username") or "Unknown"
    add_activity(
        room_id, "yaml_claimed",
        f"{actor} claimed {claimed['game']} YAML for player {claimed['player_name']}",
        actor_user_id=user["id"], subject_yaml_id=yaml_id,
    )
    analytics.record_event(
        "claim_succeeded", user_id=user["id"], room_id=room_id, req=request
    )
    return jsonify({
        "status": "claimed",
        "yaml_id": yaml_id,
        "submitter_user_id": user["id"],
        "submitter_username": actor,
    })


@bp.route("/api/public/rooms/<room_id>/yamls/<int:yaml_id>/release", methods=["POST"])
def public_yaml_release(room_id: str, yaml_id: int):
    """FEAT-20: the current claimer drops the slot back into the unclaimed
    pool. Atomic on submitter_user_id == requester so a user can never
    release someone else's claim. Hosts who want to forcibly unclaim a
    slot can still use the host-side delete + the host-side edit paths.
    """
    db_err = _requires_db()
    if db_err:
        return db_err

    user = _current_session_user()
    gate = _gate_claim_action(room_id, yaml_id, user)
    if gate[0] is None:
        return gate[1]
    _room, target = gate

    if target.get("submitter_user_id") != user["id"]:
        return jsonify({
            "error": "You can only release a slot you've claimed yourself."
        }), 403

    released = release_yaml(yaml_id, user["id"])
    if released is None:
        return jsonify({"error": "Slot is no longer claimed by you."}), 409

    actor = user.get("discord_username") or "Unknown"
    add_activity(
        room_id, "yaml_released",
        f"{actor} released their claim on {released['game']} YAML for player {released['player_name']}",
        actor_user_id=user["id"], subject_yaml_id=yaml_id,
    )
    return jsonify({
        "status": "released",
        "yaml_id": yaml_id,
    })
