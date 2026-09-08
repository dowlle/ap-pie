"""The signed-in account summary, export and deletion scheduling surface."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO

from flask import Blueprint, g, jsonify, request, send_file, session

import config
from auth import requires_auth
from db import export_account_data, get_account_summary, schedule_account_deletion, get_favorite_games, set_favorite_game

bp = Blueprint("account", __name__)


@bp.route("/api/my/rooms")
@requires_auth
def my_rooms():
    from db import get_my_rooms
    return jsonify({"rooms": get_my_rooms(g.user["id"])})


@bp.route("/api/my/rooms/<room_id>", methods=["PUT", "DELETE"])
@requires_auth
def room_membership(room_id: str):
    from db import get_my_rooms, set_room_membership
    if not request.is_json:
        return jsonify({"error": "Expected application/json"}), 415
    try:
        set_room_membership(g.user["id"], room_id, request.method == "PUT")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"rooms": get_my_rooms(g.user["id"])})


@bp.route("/api/my/favorite-games")
@requires_auth
def favorite_games():
    return jsonify({"games": get_favorite_games(g.user["id"])})


@bp.route("/api/my/favorite-games/<name>", methods=["PUT", "DELETE"])
@requires_auth
def favorite_game(name: str):
    if not request.is_json:
        return jsonify({"error": "Expected application/json"}), 415
    if len(name) > 200:
        return jsonify({"error": "Invalid game name"}), 400
    if request.method == "PUT":
        from api.apworlds import _get_index_worlds
        if not any(world.name == name and not world.disabled for world in _get_index_worlds()):
            return jsonify({"error": "Game not found"}), 404
    try:
        set_favorite_game(g.user["id"], name, request.method == "PUT")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"games": get_favorite_games(g.user["id"])})


@bp.route("/api/my/account")
@requires_auth
def account_summary():
    summary = get_account_summary(g.user["id"])
    if not summary:
        return jsonify({"error": "Account not found"}), 404
    summary["is_owner"] = bool(
        config.OWNER_DISCORD_ID
        and summary["account"].get("discord_id") == config.OWNER_DISCORD_ID
    )
    summary["deletion_grace_days"] = config.ACCOUNT_DELETION_GRACE_DAYS
    return jsonify(summary)


@bp.route("/api/my/account/export")
@requires_auth
def account_export():
    payload = export_account_data(g.user["id"])
    if not payload:
        return jsonify({"error": "Account not found"}), 404
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return send_file(
        BytesIO(data),
        as_attachment=True,
        download_name="archipelago-pie-account-data.json",
        mimetype="application/json",
        max_age=0,
    )


@bp.route("/api/my/account/deletion", methods=["POST"])
@requires_auth
def schedule_deletion():
    if config.OWNER_DISCORD_ID and g.user.get("discord_id") == config.OWNER_DISCORD_ID:
        return jsonify({
            "error": "The owner account requires the manual verified deletion process."
        }), 403
    body = request.get_json(silent=True) or {}
    if body.get("confirmation") != "DELETE":
        return jsonify({"error": "Type DELETE to confirm."}), 400
    raw_token = session.pop("account_deletion_token", None)
    if not raw_token:
        return jsonify({
            "error": "Reauthenticate with Discord before scheduling deletion.",
            "code": "reauth_required",
        }), 409
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    user = schedule_account_deletion(
        g.user["id"], token_hash, config.ACCOUNT_DELETION_GRACE_DAYS
    )
    if not user:
        return jsonify({
            "error": "The reauthentication expired or was already used.",
            "code": "reauth_expired",
        }), 409
    due_at = user["deletion_due_at"]
    session.clear()
    response = jsonify({
        "status": "scheduled",
        "deletion_due_at": due_at,
        "recoverable_until": due_at,
    })
    response.headers["Clear-Site-Data"] = '"cache", "storage"'
    return response
