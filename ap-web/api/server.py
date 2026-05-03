from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

import config

bp = Blueprint("server", __name__)


@bp.before_request
def _gate_on_generation():
    """All AP-server management lives under the generation flag. One
    blueprint-level gate covers list/status/serve/command/stop in one place."""
    if not config.FEATURES.get("generation", False):
        return jsonify({
            "error": "The 'generation' feature is currently disabled on this server.",
            "feature": "generation",
            "enabled": False,
        }), 403
    return None


def _can_manage_seed(seed: str) -> bool:
    """Audit-2026-05-04 #17: only the room's host (or an admin) may launch,
    command, or stop the AP server attached to a given seed. Without this
    any approved user could grief any other host's running game.

    Returns False on missing-user or missing-room (caller treats both as
    403 to avoid distinguishing "not found" from "not yours" - the existing
    404 paths in the route handlers cover the genuinely-missing case).
    """
    user = getattr(g, "user", None)
    if user is None:
        return True  # auth-disabled local-dev mode
    if user.get("is_admin"):
        return True
    from db import get_room_by_seed
    room = get_room_by_seed(seed)
    if not room:
        return False
    host_id = room.get("host_user_id")
    return host_id is not None and host_id == user.get("id")

# Commands approved users may forward to the AP server's stdin.
# Anything not on this list is rejected to prevent exploiting server console
# verbs we don't intend to expose over HTTP (e.g. /exit kills the server -
# use DELETE /api/serve/<seed> for that instead).
ALLOWED_SERVER_COMMANDS = frozenset({
    "help",
    "status",
    "players",
    "save",
    "release",
    "forfeit",
    "collect",
    "remaining",
    "send",
    "senddir",
    "hint",
    "option",
    "countitem",
})


def _validate_command(command: str) -> tuple[bool, str]:
    """Return (ok, reason). Enforces: starts with /, no control chars,
    verb is in ALLOWED_SERVER_COMMANDS, reasonable length."""
    if len(command) > 500:
        return False, "Command too long"
    if any(c in command for c in "\r\n\x00"):
        return False, "Command contains control characters"
    if not command.startswith("/"):
        return False, "Command must start with /"
    verb = command[1:].split(maxsplit=1)[0].lower() if len(command) > 1 else ""
    if verb not in ALLOWED_SERVER_COMMANDS:
        return False, f"Command '/{verb}' is not permitted"
    return True, ""


def _manager():
    return current_app.config["server_manager"]


@bp.route("/api/servers")
def list_servers():
    return jsonify(_manager().list_all())


@bp.route("/api/servers/<seed>")
def server_status(seed: str):
    instance = _manager().status(seed)
    if not instance:
        return jsonify({"error": "No server for this seed"}), 404
    host = current_app.config.get("AP_HOST", "localhost")
    return jsonify(instance.to_dict(host))


@bp.route("/api/serve/<seed>", methods=["POST"])
def serve(seed: str):
    if not _can_manage_seed(seed):
        return jsonify({"error": "Not your room"}), 403
    from app import get_records

    records = get_records()
    matches = [r for r in records if r.seed == seed]
    if not matches:
        return jsonify({"error": "Game not found"}), 404

    record = matches[0]
    if not record.zip_path:
        return jsonify({"error": "No zip path for this game"}), 400

    try:
        instance = _manager().start(
            seed=seed,
            zip_path=str(record.zip_path),
            players=[p.name for p in record.players],
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    host = current_app.config.get("AP_HOST", "localhost")
    return jsonify(instance.to_dict(host))


@bp.route("/api/servers/<seed>/command", methods=["POST"])
def send_command(seed: str):
    if not _can_manage_seed(seed):
        return jsonify({"error": "Not your room"}), 403
    body = request.get_json(silent=True) or {}
    command = body.get("command", "").strip()
    if not command:
        return jsonify({"error": "No command provided"}), 400
    ok, reason = _validate_command(command)
    if not ok:
        return jsonify({"error": reason}), 400
    if _manager().send_command(seed, command):
        return jsonify({"status": "sent", "command": command})
    return jsonify({"error": "Server not running"}), 400


@bp.route("/api/serve/<seed>", methods=["DELETE"])
def stop(seed: str):
    if not _can_manage_seed(seed):
        return jsonify({"error": "Not your room"}), 403
    if _manager().stop(seed):
        return jsonify({"status": "stopped", "seed": seed})
    return jsonify({"error": "No server for this seed"}), 404
