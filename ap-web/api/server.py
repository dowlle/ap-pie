from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

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
    if _manager().stop(seed):
        return jsonify({"status": "stopped", "seed": seed})
    return jsonify({"error": "No server for this seed"}), 404
