"""FEAT-33: per-user room creation templates.

Routes are mounted under /api/users/me/room-templates so the auth middleware
in auth.py treats them as auth-required (not in public_prefixes), and g.user
is populated by the time route handlers run. Cross-user access is impossible
because every helper scopes by g.user["id"].
"""

from __future__ import annotations

import json

from flask import Blueprint, g, jsonify, request

import db

bp = Blueprint("room_templates", __name__)


# ── Validation ────────────────────────────────────────────────────

# Caps mirrored at the schema level (CHECK constraints) for name; payload size
# is enforced in the route layer because there's no clean way to length-check
# JSONB content via CHECK without a helper function.
MAX_NAME_LENGTH = 80
MAX_PAYLOAD_BYTES = 16_384  # ~16 KB serialized; real payloads are <2 KB
MAX_TEMPLATES_PER_USER = 50

# Allowed payload keys + their type validators. Unknown keys are silently
# dropped so a future schema bump on either side doesn't 400 old clients.
_VALID_POLICIES = {"strict", "flexible", "latest"}
_VALID_TIME_RE = __import__("re").compile(r"^[0-2]\d:[0-5]\d$")


def _validate_payload(raw: object) -> tuple[dict | None, str | None]:
    """Return (sanitized_payload, error). The sanitized payload is a dict
    with only known keys, type-coerced. error is None when valid."""
    if not isinstance(raw, dict):
        return None, "payload must be an object"

    # Size cap before parsing — a 100 MB payload would die in json.dumps anyway,
    # but failing fast keeps the error message useful.
    blob = json.dumps(raw)
    if len(blob.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        return None, f"payload exceeds {MAX_PAYLOAD_BYTES} byte cap"

    out: dict = {}

    # room_name: optional pre-fill for the room-name field when applied.
    # Empty string = no pre-fill; host types it themselves. Cap matches the
    # SEC-21 rooms.name CHECK constraint (200).
    room_name = raw.get("room_name", "")
    if not isinstance(room_name, str):
        return None, "room_name must be a string"
    if len(room_name) > 200:
        return None, "room_name exceeds 200 char cap"
    out["room_name"] = room_name

    # description: string, max 8000 chars (matches SEC-21 rooms.description cap)
    desc = raw.get("description", "")
    if not isinstance(desc, str):
        return None, "description must be a string"
    if len(desc) > 8000:
        return None, "description exceeds 8000 char cap"
    out["description"] = desc

    # require_discord_login: bool
    out["require_discord_login"] = bool(raw.get("require_discord_login", False))

    # claim_mode: bool
    out["claim_mode"] = bool(raw.get("claim_mode", False))

    # max_yamls_per_user: int >= 0; 0 = unlimited (matches the rooms column)
    cap = raw.get("max_yamls_per_user", 0)
    try:
        cap_int = int(cap)
    except (TypeError, ValueError):
        return None, "max_yamls_per_user must be an integer"
    if cap_int < 0:
        return None, "max_yamls_per_user must be >= 0"
    if cap_int > 10_000:
        return None, "max_yamls_per_user exceeds sanity cap"
    out["max_yamls_per_user"] = cap_int

    # deadline: { enabled: bool, time_of_day: "HH:MM", day_offset: 0..30 }
    deadline_in = raw.get("deadline", {})
    if not isinstance(deadline_in, dict):
        return None, "deadline must be an object"
    deadline_out = {
        "enabled": bool(deadline_in.get("enabled", False)),
        "time_of_day": "19:00",
        "day_offset": 0,
    }
    tod = deadline_in.get("time_of_day", "19:00")
    if not isinstance(tod, str) or not _VALID_TIME_RE.match(tod):
        return None, "deadline.time_of_day must match HH:MM"
    deadline_out["time_of_day"] = tod
    off = deadline_in.get("day_offset", 0)
    try:
        off_int = int(off)
    except (TypeError, ValueError):
        return None, "deadline.day_offset must be an integer"
    if off_int < 0 or off_int > 30:
        return None, "deadline.day_offset must be 0..30"
    deadline_out["day_offset"] = off_int
    out["deadline"] = deadline_out

    # apworld_policy: enum
    pol = raw.get("apworld_policy", "strict")
    if pol not in _VALID_POLICIES:
        return None, f"apworld_policy must be one of {sorted(_VALID_POLICIES)}"
    out["apworld_policy"] = pol

    # auto_upgrade_apworld_pins: bool (default true)
    out["auto_upgrade_apworld_pins"] = bool(raw.get("auto_upgrade_apworld_pins", True))

    return out, None


def _validate_name(raw: object) -> tuple[str | None, str | None]:
    if not isinstance(raw, str):
        return None, "name must be a string"
    name = raw.strip()
    if not name:
        return None, "name must not be empty"
    if len(name) > MAX_NAME_LENGTH:
        return None, f"name exceeds {MAX_NAME_LENGTH} char cap"
    return name, None


# ── Routes ────────────────────────────────────────────────────────


@bp.route("/api/users/me/room-templates", methods=["GET"])
def list_my_room_templates():
    user_id = g.user["id"]
    return jsonify({"templates": db.list_room_templates(user_id)})


@bp.route("/api/users/me/room-templates", methods=["POST"])
def create_my_room_template():
    user_id = g.user["id"]
    body = request.get_json(silent=True) or {}

    name, err = _validate_name(body.get("name"))
    if err:
        return jsonify({"error": err}), 400
    payload, err = _validate_payload(body.get("payload"))
    if err:
        return jsonify({"error": err}), 400
    is_default = bool(body.get("is_default", False))

    if db.count_room_templates(user_id) >= MAX_TEMPLATES_PER_USER:
        return jsonify({
            "error": f"You have hit the {MAX_TEMPLATES_PER_USER}-template limit. "
                     "Delete some old templates before creating new ones.",
        }), 400

    row = db.create_room_template(user_id, name, payload, is_default=is_default)
    return jsonify(row), 201


@bp.route("/api/users/me/room-templates/<int:template_id>", methods=["PATCH"])
def update_my_room_template(template_id: int):
    user_id = g.user["id"]
    body = request.get_json(silent=True) or {}

    kwargs: dict = {}
    if "name" in body:
        name, err = _validate_name(body.get("name"))
        if err:
            return jsonify({"error": err}), 400
        kwargs["name"] = name
    if "payload" in body:
        payload, err = _validate_payload(body.get("payload"))
        if err:
            return jsonify({"error": err}), 400
        kwargs["payload"] = payload
    if "is_default" in body:
        kwargs["is_default"] = bool(body.get("is_default"))

    row = db.update_room_template(user_id, template_id, **kwargs)
    if row is None:
        return jsonify({"error": "template not found"}), 404
    return jsonify(row)


@bp.route("/api/users/me/room-templates/<int:template_id>", methods=["DELETE"])
def delete_my_room_template(template_id: int):
    user_id = g.user["id"]
    if not db.delete_room_template(user_id, template_id):
        return jsonify({"error": "template not found"}), 404
    return jsonify({"ok": True})
