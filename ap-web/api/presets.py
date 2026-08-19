"""FEAT-42: community YAML presets.

A preset is a named configuration for one indexed game, published so that a
newcomer can start from a working setup instead of a form full of options
they cannot evaluate. Two kinds:

- **simple** stores option values and fills the builder's form, so everything
  stays editable afterwards
- **advanced** stores a full YAML document and opens in the review step's
  editor, which is how plando, triggers, item links and weights stay
  shareable at all

Design decisions live in the vault note "2026-08-17 - Design - FEAT-42
Community YAML presets". Two of them shape this module:

- **Saving and publishing are separate.** A preset is created `private` and
  becomes `published` only through an explicit call from the author's own
  presets page. Publishing therefore carries a name and description the
  author chose deliberately, without an approval queue standing in the way.
- **Values are validated on read, not on write.** An apworld's options change
  between versions, so a preset written for 0.1.3 may reference keys 0.1.5
  no longer has. Rather than freezing presets to one version, every read
  checks them against the schema of the version being applied and reports
  what no longer fits.

Security posture: a simple preset can only ever contribute values for keys
the target schema declares, so applying one cannot introduce a `game:`,
plando block or anything else the author was not entitled to set. An
advanced preset is YAML text from a stranger and is treated exactly like the
public submit path already treats one - parsed with safe_load, size-capped,
and required to declare the same game. The applying player's own slot name
always replaces whatever `name` the author wrote.
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict, deque

import yaml
from flask import Blueprint, jsonify, request, session

import analytics
from auth import requires_admin, requires_auth
from db import (
    _db_url,
    create_preset,
    delete_preset,
    get_preset,
    has_voted,
    list_presets_by_author,
    list_presets_for_apworld,
    list_reported_presets,
    record_preset_use,
    report_preset,
    update_preset,
    vote_preset,
)

bp = Blueprint("presets", __name__)

MAX_NAME = 80
MAX_DESCRIPTION = 500
MAX_YAML_BYTES = 64 * 1024
MAX_OPTION_VALUES_BYTES = 64 * 1024
# A generous ceiling that still stops one account filling the table.
PRESETS_PER_USER_PER_HOUR = 20

_publish_buckets: dict[int, deque] = defaultdict(deque)
_publish_lock = threading.Lock()
_use_buckets: dict[tuple[str, int], float] = {}
_use_lock = threading.Lock()


def _option_values_too_large(values: dict) -> bool:
    try:
        encoded = json.dumps(values, ensure_ascii=False)
    except (TypeError, ValueError):
        return True
    return len(encoded.encode("utf-8")) > MAX_OPTION_VALUES_BYTES


def _count_use(ip: str, preset_id: int) -> bool:
    """Count a preset at most once per client and preset per hour."""
    now = time.time()
    key = (ip, preset_id)
    with _use_lock:
        previous = _use_buckets.get(key)
        if previous is not None and previous >= now - 3600:
            return False
        _use_buckets[key] = now
        if len(_use_buckets) > 10_000:
            cutoff = now - 3600
            stale = [k for k, seen in _use_buckets.items() if seen < cutoff]
            for stale_key in stale[:2_000]:
                _use_buckets.pop(stale_key, None)
            while len(_use_buckets) > 10_000:
                _use_buckets.pop(next(iter(_use_buckets)))
        return True


def _requires_db():
    if _db_url is None:
        return jsonify({"error": "Database not available"}), 503
    return None


def _current_user_id() -> int | None:
    """/api/apworlds and /api/presets are outside the auth middleware, so the
    session is read here (same in-body pattern as apworld_requests)."""
    return session.get("user_id")


def _rate_ok(user_id: int) -> bool:
    now = time.time()
    with _publish_lock:
        bucket = _publish_buckets[user_id]
        while bucket and bucket[0] < now - 3600:
            bucket.popleft()
        if len(bucket) >= PRESETS_PER_USER_PER_HOUR:
            return False
        bucket.append(now)
        return True


def _schema_for(apworld_name: str, version: str | None):
    """Builder schema for a world at a version, or None. Reuses the FEAT-38
    cache, so this is a lookup rather than a download in the common case."""
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


def _check_against_schema(preset: dict, schema_row) -> dict:
    """Annotate a preset with how well it still fits the target version.

    Adds `stale_keys` (declared by the preset, absent from the schema) and
    `applies` (the subset that can actually be used). Never mutates stored
    data: drift is reported at read time so the author does not have to
    re-publish every time a game ships a version.
    """
    out = dict(preset)
    if preset.get("kind") != "simple":
        return out
    values = preset.get("values") or {}
    schema = (schema_row or {}).get("schema") if schema_row else None
    if not schema:
        # No schema to check against; hand the values back untouched rather
        # than pretending they are all invalid.
        out["applies"] = values
        out["stale_keys"] = []
        return out
    known = {o["name"] for o in schema.get("options", [])}
    # Archipelago's own options are valid for every game and are not part of
    # a world's declared schema, so they must not read as stale.
    from analytics import KIND_SPECS  # noqa: F401  (import kept local + cheap)

    core = {"progression_balancing", "accessibility"}
    stale = [k for k in values if k not in known and k not in core]
    out["stale_keys"] = stale
    out["applies"] = {k: v for k, v in values.items() if k not in stale}
    return out


def _public_preset(p: dict, voted_ids: set[int]) -> dict:
    """Shape sent to clients. The author's Discord display name is included
    because attribution is the point of publishing; nothing else about them
    is exposed, and private presets are only ever returned to their author."""
    return {
        "id": p["id"],
        "apworld_name": p["apworld_name"],
        "version": p["version"],
        "name": p["name"],
        "description": p["description"],
        "kind": p["kind"],
        "values": p.get("values"),
        "yaml_content": p.get("yaml_content"),
        "author_username": p.get("author_username"),
        "is_official": p["is_official"],
        "status": p["status"],
        "uses": p["uses"],
        "score": p["score"],
        "voted": p["id"] in voted_ids,
        "stale_keys": p.get("stale_keys", []),
        "applies": p.get("applies"),
        "created_at": p.get("created_at"),
    }


@bp.route("/api/apworlds/<name>/presets")
def list_presets(name: str):
    """Presets for a game: everything published, plus the caller's own drafts."""
    db_err = _requires_db()
    if db_err:
        return db_err

    user_id = _current_user_id()
    version = request.args.get("version")
    presets = list_presets_for_apworld(name, viewer_user_id=user_id)
    if not presets:
        return jsonify({"presets": []})

    _, schema_row = _schema_for(name, version)
    voted = has_voted([p["id"] for p in presets], user_id)
    return jsonify({
        "presets": [
            _public_preset(_check_against_schema(p, schema_row), voted)
            for p in presets
        ],
    })


@bp.route("/api/presets/mine")
@requires_auth
def my_presets():
    """The author's own library: drafts and published alike. This is the
    page where publishing happens, and it is the FEAT-23 personal-template
    surface in the same breath."""
    db_err = _requires_db()
    if db_err:
        return db_err
    from flask import g

    presets = list_presets_by_author(g.user["id"])
    voted = has_voted([p["id"] for p in presets], g.user["id"])
    return jsonify({"presets": [_public_preset(p, voted) for p in presets]})


@bp.route("/api/presets", methods=["POST"])
@requires_auth
def create():
    """Save a preset. Always created private; publishing is a second step."""
    db_err = _requires_db()
    if db_err:
        return db_err
    from flask import g

    if not _rate_ok(g.user["id"]):
        return jsonify({"error": "Too many presets saved in the last hour."}), 429

    body = request.get_json(silent=True) or {}
    apworld_name = (body.get("apworld_name") or "").strip()
    version = (body.get("version") or "").strip()
    name = (body.get("name") or "").strip()
    description = (body.get("description") or "").strip()
    kind = (body.get("kind") or "simple").strip()

    if not apworld_name or not version:
        return jsonify({"error": "apworld_name and version are required"}), 400
    if not name:
        return jsonify({"error": "A preset needs a name"}), 400
    if len(name) > MAX_NAME or len(description) > MAX_DESCRIPTION:
        return jsonify({"error": "Name or description is too long"}), 400
    if kind not in ("simple", "advanced"):
        return jsonify({"error": "kind must be simple or advanced"}), 400

    world, schema_row = _schema_for(apworld_name, version)
    if world is None:
        return jsonify({"error": f"'{apworld_name}' is not in the index"}), 404

    option_values = None
    yaml_content = None

    if kind == "simple":
        raw = body.get("values")
        if not isinstance(raw, dict) or not raw:
            return jsonify({"error": "A simple preset needs option values"}), 400
        schema = (schema_row or {}).get("schema") if schema_row else None
        if not schema:
            return jsonify({
                "error": "This version does not have a builder schema for a simple preset",
            }), 400
        if schema:
            # Keep only keys this version declares (plus Archipelago's own),
            # so a preset can never carry a key the game does not accept.
            known = {o["name"] for o in schema.get("options", [])}
            known |= {"progression_balancing", "accessibility"}
            raw = {k: v for k, v in raw.items() if k in known}
            if not raw:
                return jsonify({"error": "None of those options exist for this version"}), 400
        if _option_values_too_large(raw):
            return jsonify({"error": "Those option values are too large for a preset"}), 400
        option_values = raw
    else:
        text = body.get("yaml_content")
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "An advanced preset needs YAML content"}), 400
        if len(text.encode("utf-8")) > MAX_YAML_BYTES:
            return jsonify({"error": "That YAML is too large for a preset"}), 400
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as e:
            return jsonify({"error": f"That is not valid YAML: {e}"}), 400
        if not isinstance(doc, dict):
            return jsonify({"error": "A preset YAML must be a single mapping"}), 400
        declared = doc.get("game")
        if isinstance(declared, str) and world.game_name and declared != world.game_name:
            return jsonify({
                "error": f"That YAML declares game '{declared}', not '{world.game_name}'",
            }), 400
        yaml_content = text

    preset = create_preset(
        apworld_name=apworld_name,
        version=version,
        name=name,
        description=description,
        kind=kind,
        option_values=option_values,
        yaml_content=yaml_content,
        author_user_id=g.user["id"],
    )
    return jsonify(_public_preset(preset, set())), 201


@bp.route("/api/presets/<int:preset_id>", methods=["PATCH"])
@requires_auth
def edit(preset_id: int):
    """Rename, re-describe, publish or unpublish. Author only.

    Publishing is the deliberate step: it is where a name and description
    become public, which is why it lives here and not on save.
    """
    db_err = _requires_db()
    if db_err:
        return db_err
    from flask import g

    preset = get_preset(preset_id)
    if not preset:
        return jsonify({"error": "Preset not found"}), 404
    if preset.get("author_user_id") != g.user["id"]:
        return jsonify({"error": "Not your preset"}), 403
    if preset["status"] == "hidden":
        return jsonify({"error": "This preset was removed by a moderator"}), 403

    body = request.get_json(silent=True) or {}
    updates: dict = {}
    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name or len(name) > MAX_NAME:
            return jsonify({"error": "A preset needs a name of at most 80 characters"}), 400
        updates["name"] = name
    if "description" in body:
        description = (body.get("description") or "").strip()
        if len(description) > MAX_DESCRIPTION:
            return jsonify({"error": "That description is too long"}), 400
        updates["description"] = description
    if "status" in body:
        status = body.get("status")
        if status not in ("private", "published"):
            return jsonify({"error": "status must be private or published"}), 400
        if status == "published":
            target = {**preset, **updates}
            if not (target.get("description") or "").strip():
                return jsonify({
                    "error": "Add a short description before publishing, so people "
                             "know what this preset is for.",
                }), 400
            analytics.record_event(
                "preset_published",
                user_id=g.user["id"],
                props={"game": preset["apworld_name"], "version": preset["version"],
                       "kind": preset["kind"]},
                req=request,
            )
        updates["status"] = status

    return jsonify(_public_preset(update_preset(preset_id, **updates) or {}, set()))


@bp.route("/api/presets/<int:preset_id>", methods=["DELETE"])
@requires_auth
def remove(preset_id: int):
    db_err = _requires_db()
    if db_err:
        return db_err
    from flask import g

    preset = get_preset(preset_id)
    if not preset:
        return jsonify({"error": "Preset not found"}), 404
    if preset.get("author_user_id") != g.user["id"]:
        return jsonify({"error": "Not your preset"}), 403
    delete_preset(preset_id)
    return jsonify({"status": "deleted"})


@bp.route("/api/presets/<int:preset_id>/use", methods=["POST"])
def use(preset_id: int):
    """Record that a preset was applied. Public: applying does not need an
    account, and the visible usage count is the main ranking signal."""
    db_err = _requires_db()
    if db_err:
        return db_err
    preset = get_preset(preset_id)
    if not preset or preset["status"] == "hidden":
        return ("", 204)
    from request_ip import client_ip

    if not _count_use(client_ip(), preset_id):
        return ("", 204)
    record_preset_use(preset_id)
    analytics.record_event(
        "preset_applied",
        user_id=_current_user_id(),
        props={
            "game": preset["apworld_name"],
            "version": preset["version"],
            "kind": preset["kind"],
            "official": preset["is_official"],
        },
        req=request,
    )
    return ("", 204)


@bp.route("/api/presets/<int:preset_id>/vote", methods=["POST"])
@requires_auth
def vote(preset_id: int):
    """Toggle an upvote. Signed-in only, one per user, not on your own."""
    db_err = _requires_db()
    if db_err:
        return db_err
    from flask import g

    preset = get_preset(preset_id)
    if not preset or preset["status"] != "published":
        return jsonify({"error": "Preset not found"}), 404
    if preset.get("author_user_id") == g.user["id"]:
        return jsonify({"error": "You cannot upvote your own preset"}), 400
    updated = vote_preset(preset_id, g.user["id"])
    return jsonify({"score": updated["score"], "voted": updated["voted"]})


@bp.route("/api/presets/<int:preset_id>/report", methods=["POST"])
@requires_auth
def report(preset_id: int):
    """Flag a preset for review. Signed-in so a single actor cannot bury
    something by repeat-reporting anonymously."""
    db_err = _requires_db()
    if db_err:
        return db_err
    preset = get_preset(preset_id)
    if not preset or preset["status"] != "published":
        return jsonify({"error": "Preset not found"}), 404
    from flask import g

    if not report_preset(preset_id, g.user["id"]):
        return jsonify({"status": "already_reported"})
    analytics.record_event("preset_reported", props={}, req=request)
    return jsonify({"status": "reported"})


@bp.route("/api/admin/presets")
@requires_admin
def admin_list():
    db_err = _requires_db()
    if db_err:
        return db_err
    return jsonify({"presets": list_reported_presets()})


@bp.route("/api/admin/presets/<int:preset_id>/hide", methods=["POST"])
@requires_admin
def admin_hide(preset_id: int):
    """Pull a preset. The row survives so the author is not silently confused
    about where it went, and so a mistake is reversible."""
    db_err = _requires_db()
    if db_err:
        return db_err
    if not get_preset(preset_id):
        return jsonify({"error": "Preset not found"}), 404
    return jsonify(_public_preset(update_preset(preset_id, status="hidden") or {}, set()))
