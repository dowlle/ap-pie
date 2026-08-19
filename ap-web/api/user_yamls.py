"""FEAT-43: a player's own YAML library, and their submissions across rooms.

Before this, nothing in the product was "my YAML". A submission lived inside
one room and could not be seen from anywhere else; a preset was a
configuration with no slot name; a hand-edited document lived nowhere until
it was sent somewhere. This is the player's own view of their own work, and
it is what gives version-drift notices and option warnings somewhere to
appear that a person will actually revisit.

Storage follows the preset split (design D2): a form-built YAML is kept as
option values so it survives a version bump and can be re-checked, and a
hand-edited one is kept verbatim because rewriting somebody's plando block
would be worse than not storing it at all.
"""

from __future__ import annotations

import json
import yaml
from flask import Blueprint, g, jsonify, request

from auth import requires_auth
from db import (
    _db_url,
    create_user_yaml,
    delete_user_yaml,
    get_user_yaml,
    list_submissions_by_user,
    list_user_yamls,
    update_user_yaml,
)
import option_check

bp = Blueprint("user_yamls", __name__)

MAX_LABEL = 120
MAX_YAML_BYTES = 64 * 1024
MAX_OPTION_VALUES_BYTES = 64 * 1024
MAX_LIBRARY_ENTRIES = 200


def _option_values_too_large(values: dict) -> bool:
    try:
        # Match PostgreSQL jsonb's textual separators so the API and the
        # storage-layer CHECK enforce the same byte boundary.
        encoded = json.dumps(values, ensure_ascii=False)
    except (TypeError, ValueError):
        return True
    return len(encoded.encode("utf-8")) > MAX_OPTION_VALUES_BYTES


def _requires_db():
    if _db_url is None:
        return jsonify({"error": "Database not available"}), 503
    return None


def _schema_for(apworld_name: str, version: str | None):
    from api.apworlds import _get_index_worlds, builder_schemas_for_pins

    world = next((w for w in _get_index_worlds() if w.name == apworld_name), None)
    if world is None:
        return None, None
    if not version:
        ver = next((v for v in world.versions if v.url or v.local), None)
        version = ver.version if ver else None
    if not version:
        return world, None
    rows = builder_schemas_for_pins([{"apworld_name": apworld_name, "version": version}])
    return world, (rows[0] if rows else None)


def _annotate(entry: dict) -> dict:
    """Attach a freshness verdict against the newest indexed version.

    This is the payoff of storing configurations rather than files: a saved
    YAML can say "two of these options no longer exist" long before its owner
    submits it somewhere and finds out the hard way.
    """
    out = dict(entry)
    world, schema_row = _schema_for(entry["apworld_name"], None)
    latest = None
    if world is not None:
        ver = next((v for v in world.versions if v.url or v.local), None)
        latest = ver.version if ver else None
    out["latest_version"] = latest
    out["outdated"] = bool(latest and latest != entry["version"])

    schema = (schema_row or {}).get("schema") if schema_row else None
    if entry.get("kind") == "simple" and schema:
        out["warnings"] = option_check.check_options(entry.get("values") or {}, schema)
    elif entry.get("kind") == "advanced" and schema and entry.get("yaml_content"):
        try:
            doc = yaml.safe_load(entry["yaml_content"])
            game = (schema or {}).get("game") or ""
            out["warnings"] = option_check.check_document(doc, game, schema)
        except Exception:
            out["warnings"] = []
    else:
        out["warnings"] = []
    return out


@bp.route("/api/my/yamls")
@requires_auth
def list_mine():
    """The library, each row checked against the newest indexed version."""
    db_err = _requires_db()
    if db_err:
        return db_err
    entries = [_annotate(e) for e in list_user_yamls(g.user["id"])]
    return jsonify({"yamls": entries})


@bp.route("/api/my/submissions")
@requires_auth
def list_submissions():
    """Everything this account has submitted, across every room.

    Derived from the submissions themselves rather than from the library, so
    it covers everything sent before the library existed.
    """
    db_err = _requires_db()
    if db_err:
        return db_err
    return jsonify({"submissions": list_submissions_by_user(g.user["id"])})


@bp.route("/api/my/yamls", methods=["POST"])
@requires_auth
def create():
    db_err = _requires_db()
    if db_err:
        return db_err

    if len(list_user_yamls(g.user["id"])) >= MAX_LIBRARY_ENTRIES:
        return jsonify({
            "error": f"Your library holds the maximum of {MAX_LIBRARY_ENTRIES} entries. "
                     f"Delete one before saving another.",
        }), 400

    body = request.get_json(silent=True) or {}
    apworld_name = (body.get("apworld_name") or "").strip()
    version = (body.get("version") or "").strip()
    player_name = (body.get("player_name") or "").strip()
    label = (body.get("label") or "").strip()[:MAX_LABEL]
    kind = (body.get("kind") or "simple").strip()

    if not apworld_name or not version or not player_name:
        return jsonify({"error": "apworld_name, version and player_name are required"}), 400
    if kind not in ("simple", "advanced"):
        return jsonify({"error": "kind must be simple or advanced"}), 400

    option_values = None
    yaml_content = None
    if kind == "simple":
        values = body.get("values")
        if not isinstance(values, dict):
            return jsonify({"error": "A form-built YAML needs its option values"}), 400
        if _option_values_too_large(values):
            return jsonify({"error": "Those option values are too large to save"}), 400
        option_values = values
    else:
        text = body.get("yaml_content")
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "A hand-edited YAML needs its content"}), 400
        if len(text.encode("utf-8")) > MAX_YAML_BYTES:
            return jsonify({"error": "That YAML is too large to save"}), 400
        try:
            yaml.safe_load(text)
        except yaml.YAMLError as e:
            return jsonify({"error": f"That is not valid YAML: {e}"}), 400
        yaml_content = text

    entry = create_user_yaml(
        user_id=g.user["id"],
        apworld_name=apworld_name,
        version=version,
        player_name=player_name,
        label=label,
        kind=kind,
        option_values=option_values,
        yaml_content=yaml_content,
    )
    return jsonify(_annotate(entry)), 201


@bp.route("/api/my/yamls/<int:yaml_id>", methods=["PATCH"])
@requires_auth
def edit(yaml_id: int):
    db_err = _requires_db()
    if db_err:
        return db_err
    entry = get_user_yaml(yaml_id)
    if not entry:
        return jsonify({"error": "Not found"}), 404
    if entry["user_id"] != g.user["id"]:
        return jsonify({"error": "Not yours"}), 403

    body = request.get_json(silent=True) or {}
    updates: dict = {}
    if "label" in body:
        updates["label"] = (body.get("label") or "").strip()[:MAX_LABEL]
    if "player_name" in body:
        name = (body.get("player_name") or "").strip()
        if not name:
            return jsonify({"error": "A slot name cannot be empty"}), 400
        updates["player_name"] = name
    if "values" in body and entry["kind"] == "simple":
        if not isinstance(body["values"], dict):
            return jsonify({"error": "values must be an object"}), 400
        if _option_values_too_large(body["values"]):
            return jsonify({"error": "Those option values are too large to save"}), 400
        updates["option_values"] = body["values"]
    if "yaml_content" in body and entry["kind"] == "advanced":
        text = body["yaml_content"]
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_YAML_BYTES:
            return jsonify({"error": "Invalid YAML content"}), 400
        updates["yaml_content"] = text
    if "version" in body:
        updates["version"] = (body.get("version") or "").strip() or entry["version"]

    return jsonify(_annotate(update_user_yaml(yaml_id, **updates) or {}))


@bp.route("/api/my/yamls/<int:yaml_id>", methods=["DELETE"])
@requires_auth
def remove(yaml_id: int):
    db_err = _requires_db()
    if db_err:
        return db_err
    entry = get_user_yaml(yaml_id)
    if not entry:
        return jsonify({"error": "Not found"}), 404
    if entry["user_id"] != g.user["id"]:
        return jsonify({"error": "Not yours"}), 403
    delete_user_yaml(yaml_id)
    return jsonify({"status": "deleted"})
