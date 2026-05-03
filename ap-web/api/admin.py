"""Admin endpoints for user management."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from auth import requires_admin
from db import list_users, set_user_approved

bp = Blueprint("admin", __name__)


@bp.route("/api/admin/users")
@requires_admin
def get_users():
    """List all registered users."""
    return jsonify(list_users())


@bp.route("/api/admin/users/<int:user_id>/approve", methods=["POST"])
@requires_admin
def approve_user(user_id: int):
    """Set a user's approval status."""
    data = request.get_json(silent=True) or {}
    approved = data.get("approved", True)
    user = set_user_approved(user_id, approved)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)


# FEAT-17 V0: introspect the WebSocket tracker manager. Lets us verify the
# bg thread + connections are healthy before V1 wires the cache into the
# room_tracker API.
@bp.route("/api/admin/tracker_ws")
@requires_admin
def tracker_ws_status():
    """Return per-room tracker_ws state snapshots. Empty {} when the
    feature is off (TRACKER_WS_ENABLED=false) or no rooms are connected."""
    try:
        from tracker_ws import manager
        return jsonify(manager.list_states())
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


@bp.route("/api/admin/tracker_ws/<room_id>")
@requires_admin
def tracker_ws_room(room_id: str):
    """Return one room's full tracker_ws snapshot, or 404 if no live
    connection exists for it."""
    try:
        from tracker_ws import manager
        state = manager.get_state(room_id)
        if state is None:
            return jsonify({"error": "No active connection for this room"}), 404
        return jsonify(state.snapshot())
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


@bp.route("/api/admin/tracker_ws/<room_id>/connect", methods=["POST"])
@requires_admin
def tracker_ws_connect(room_id: str):
    """Manually trigger a tracker_ws connection for a room. Useful while
    iterating in V0 - kicks off without waiting for app restart. Reads
    the room from DB to pull tracker_url + external host:port."""
    try:
        from tracker_ws import manager, discover_slot_name, scrape_first_slot_name
        from db import get_room
        room = get_room(room_id)
        if not room:
            return jsonify({"error": "Room not found"}), 404
        tracker_url = room.get("tracker_url")
        host = room.get("external_host")
        port = room.get("external_port")
        if not (tracker_url and host and port):
            return jsonify({"error": "Room missing tracker_url or external_host/port"}), 400
        slot_name = discover_slot_name(room_id, room.get("host_user_id")) \
            or scrape_first_slot_name(tracker_url)
        if not slot_name:
            return jsonify({"error": "Couldn't discover a slot name to connect as"}), 400
        ok = manager.schedule(
            room_id=room_id,
            tracker_url=tracker_url,
            host=host,
            port=int(port),
            slot_name=slot_name,
        )
        return jsonify({"scheduled": ok, "slot_name": slot_name})
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


@bp.route("/api/admin/tracker_ws/<room_id>/cancel", methods=["POST"])
@requires_admin
def tracker_ws_cancel(room_id: str):
    """Tear down a tracker_ws connection for a room."""
    try:
        from tracker_ws import manager
        manager.cancel(room_id)
        return jsonify({"cancelled": room_id})
    except Exception as e:
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500
