"""CTR custom-track name registry: read API, submissions and the review queue.

Design: the vault note "CTR custom-track name registry - 2026-10-13". Everything
here is behind config.FEATURES["ctr_registry"] (on for beta, off elsewhere);
while it is off every route answers 404.

Public reads are anonymous, versioned by `schema_version` in every body, and
cacheable (ETag). Writes need a signed-in Discord account; the review routes
live under /api/admin where the auth middleware also demands is_admin.
Generation and the native client never call these routes.
"""

from __future__ import annotations

import hashlib
import json

from flask import Blueprint, abort, g, jsonify, make_response, request, session

import config
from auth import requires_admin, requires_auth
from ctr_registry import export, notify, rules, store
from ctr_registry.rules import RuleError
from db import _serialize

bp = Blueprint("ctr_tracks", __name__)

FEATURE = "ctr_registry"
DEFAULT_LIMIT = 100
MAX_LIMIT = 200

_submit_limiter = rules.SlidingWindowLimiter(rules.SUBMISSIONS_PER_USER_PER_HOUR)
_report_limiter = rules.SlidingWindowLimiter(rules.REPORTS_PER_USER_PER_HOUR)

_STATUS = {"not_found": 404, "target_not_found": 404, "already_decided": 409, "bad_state": 409,
           "already_named": 409, "name_frozen": 409, "content_id_exists": 409, "frozen": 409,
           "blocks_exhausted": 409, "target_not_open": 409, "revision_exists": 409}


@bp.before_request
def _require_feature():
    if not config.FEATURES.get(FEATURE):
        abort(404)


@bp.errorhandler(RuleError)
def _rule_error(err: RuleError):
    return jsonify({"error": str(err), "code": err.code}), _STATUS.get(err.code, 400)


def _db_check():
    import db
    if db._db_url is None:
        import os
        if not os.environ.get("DATABASE_URL"):
            return jsonify({"error": "Database not available"}), 503
    return None


def _json_response(body: dict, etag_source: str | None = None, max_age: int = 60):
    resp = make_response(jsonify(body))
    resp.headers["Cache-Control"] = f"public, max-age={max_age}"
    resp.set_etag(etag_source or hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:32])
    return resp.make_conditional(request)


def _public_view(entry: dict, revs: list[dict], apworld: str | None, mode: str | None):
    """An entry as the picker sees it, or None when nothing fits the filters."""
    usable = [r for r in revs if r.get("content_id") and rules.revision_compatible(r, apworld)]
    if (apworld or mode) and not usable:
        return None
    if mode and not any(mode in (r.get("modes") or []) for r in usable):
        return None
    doc = export.entry_doc(entry, usable if (apworld or mode) else revs, {}, False)
    doc["review"]["superseded_by"] = None
    return doc


def _public_records(conn=None):
    entries = store.list_entries(rules.PUBLIC_STATES, conn=conn)
    revs = store.revisions_for([e["id"] for e in entries], conn=conn)
    return [(e, revs.get(e["id"], [])) for e in entries]


@bp.route("/api/ctr/tracks")
def list_tracks():
    if (err := _db_check()):
        return err
    apworld = (request.args.get("apworld") or "").strip() or None
    mode = (request.args.get("mode") or "").strip() or None
    q = (request.args.get("q") or "").strip().casefold()
    try:
        limit = max(1, min(int(request.args.get("limit", DEFAULT_LIMIT)), MAX_LIMIT))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return jsonify({"error": "limit and offset must be numbers"}), 400
    out = []
    for entry, revs in _public_records():
        doc = _public_view(entry, revs, apworld, mode)
        if doc is None:
            continue
        if q:
            hay = " ".join([entry["track_key"], entry["display_title"],
                            *(c["name"] for c in entry.get("credits") or [])]).casefold()
            if q not in hay:
                continue
        out.append(doc)
    return _json_response({
        "schema_version": rules.SCHEMA_VERSION, "total": len(out), "limit": limit,
        "offset": offset, "tracks": out[offset: offset + limit],
    })


@bp.route("/api/ctr/tracks/publication")
def publication():
    if (err := _db_check()):
        return err
    doc = export.public_publication(store.record_entries())
    return _json_response(doc, etag_source=doc["digest"], max_age=300)


@bp.route("/api/ctr/tracks/<track_key>")
def track_detail(track_key: str):
    if (err := _db_check()):
        return err
    entry = store.get_entry(track_key=track_key) if rules.valid_key(track_key) else None
    if entry is None or entry["state"] not in rules.PUBLIC_STATES:
        return jsonify({"error": "Track not found"}), 404
    revs = store.revisions_for([entry["id"]]).get(entry["id"], [])
    doc = export.entry_doc(entry, revs, {}, False)
    doc["review"]["superseded_by"] = None
    return _json_response({"schema_version": rules.SCHEMA_VERSION, "track": doc})


@bp.route("/api/ctr/tracks/<track_key>/revisions/<content_id>/descriptor")
def revision_descriptor(track_key: str, content_id: str):
    """The exact descriptor the picker writes into the YAML, plus the fields it
    adds around it (track_key, title, credits)."""
    if (err := _db_check()):
        return err
    entry = store.get_entry(track_key=track_key) if rules.valid_key(track_key) else None
    if entry is None or entry["state"] not in rules.PUBLIC_STATES:
        return jsonify({"error": "Track not found"}), 404
    rev = next((r for r in store.revisions_for([entry["id"]]).get(entry["id"], [])
                if r.get("content_id") == content_id), None)
    if rev is None or rev.get("descriptor") is None:
        return jsonify({"error": "Revision not found"}), 404
    return _json_response({
        "schema_version": rules.SCHEMA_VERSION,
        "track_key": entry["track_key"],
        "content_id": content_id,
        "revision": rev["revision"],
        "descriptor_schema": rev.get("descriptor_schema"),
        "descriptor": rev["descriptor"],
        "fill": {"track_key": entry["track_key"], "title": entry["display_title"],
                 "credits": entry.get("credits") or []},
    })


# ── Submissions ──────────────────────────────────────────────────

def _user_id() -> int | None:
    return session.get("user_id")


def _public_submission(row: dict) -> dict:
    payload = row.get("payload") or {}
    return {
        "id": row["id"], "kind": row["kind"], "status": row["status"],
        "title": payload.get("title") or (payload.get("changes") or {}).get("display_title"),
        "target_track_key": row.get("target_track_key"),
        "reject_reason": row.get("reject_reason"),
        "created_at": _serialize({"v": row["created_at"]})["v"],
    }


@bp.route("/api/ctr/tracks/submissions", methods=["POST"])
@requires_auth
def submit():
    if (err := _db_check()):
        return err
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Send a JSON object"}), 400
    kind = body.get("kind", "new_track")
    target_id = None
    if kind in ("new_revision", "correction"):
        key = body.get("track_key")
        target = store.get_entry(track_key=key) if rules.valid_key(key) else None
        if target is None:
            raise RuleError("target_not_found", "That track is not in the registry")
        target_id = target["id"]
    payload = store.clean_submission_payload(kind, body)
    user_id = g.user["id"]
    if store.count_pending(user_id) >= rules.PENDING_PER_USER_MAX:
        return jsonify({"error": "You have too many submissions waiting for review.",
                        "code": "pending_cap"}), 429
    if not _submit_limiter.allow(user_id):
        return jsonify({"error": "Too many submissions in the last hour.", "code": "rate_limited"}), 429
    row = store.create_submission(user_id, kind, payload, target_entry_id=target_id)
    notify.push("CTR registry: new submission",
                f"{kind}: {(payload.get('title') or body.get('track_key') or '')[:60]}")
    return jsonify(_public_submission(row)), 201


@bp.route("/api/ctr/tracks/submissions/mine")
@requires_auth
def my_submissions():
    if (err := _db_check()):
        return err
    rows = store.list_submissions(user_id=g.user["id"])
    return jsonify({"schema_version": rules.SCHEMA_VERSION,
                    "submissions": [_public_submission(r) for r in rows]})


@bp.route("/api/ctr/tracks/<track_key>/report", methods=["POST"])
@requires_auth
def report(track_key: str):
    if (err := _db_check()):
        return err
    entry = store.get_entry(track_key=track_key) if rules.valid_key(track_key) else None
    if entry is None or entry["state"] not in rules.PUBLIC_STATES:
        return jsonify({"error": "Track not found"}), 404
    if not _report_limiter.allow(g.user["id"]):
        return jsonify({"error": "Too many reports in the last hour.", "code": "rate_limited"}), 429
    reason = (request.get_json(silent=True) or {}).get("reason", "")
    if store.add_report(entry["id"], g.user["id"], reason if isinstance(reason, str) else ""):
        notify.push("CTR registry: track reported", entry["track_key"])
        return jsonify({"status": "reported"})
    return jsonify({"status": "already_reported"})


# ── Admin ────────────────────────────────────────────────────────

def _admin_entry(entry: dict, revs: list[dict]) -> dict:
    row = _serialize(entry)
    row["revisions"] = [
        {k: (_serialize({"v": r[k]})["v"] if hasattr(r.get(k), "isoformat") else r[k])
         for k in ("id", "revision", "content_id", "hash_state", "modes", "provenance", "created_at")}
        for r in revs
    ]
    return row


@bp.route("/api/admin/ctr/track-submissions")
@requires_admin
def admin_submissions():
    if (err := _db_check()):
        return err
    status = request.args.get("status") or "pending"
    rows = store.list_submissions(status=None if status == "all" else status)
    return jsonify({"schema_version": rules.SCHEMA_VERSION,
                    "submissions": [_serialize(r) for r in rows]})


@bp.route("/api/admin/ctr/tracks")
@requires_admin
def admin_tracks():
    if (err := _db_check()):
        return err
    state = request.args.get("state")
    if state and state not in rules.STATES:
        return jsonify({"error": "Unknown state"}), 400
    entries = store.list_entries([state] if state else None)
    revs = store.revisions_for([e["id"] for e in entries])
    return jsonify({"schema_version": rules.SCHEMA_VERSION,
                    "tracks": [_admin_entry(e, revs.get(e["id"], [])) for e in entries]})


def _body() -> dict:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


@bp.route("/api/admin/ctr/track-submissions/<int:sub_id>/approve", methods=["POST"])
@requires_admin
def admin_approve_submission(sub_id: int):
    if (err := _db_check()):
        return err
    row = store.approve_submission(sub_id, g.user["id"], _body().get("overrides"))
    return jsonify(_serialize(row))


@bp.route("/api/admin/ctr/track-submissions/<int:sub_id>/reject", methods=["POST"])
@requires_admin
def admin_reject_submission(sub_id: int):
    if (err := _db_check()):
        return err
    return jsonify(_serialize(store.reject_submission(sub_id, g.user["id"], _body().get("reason", ""))))


@bp.route("/api/admin/ctr/track-submissions/<int:sub_id>/merge", methods=["POST"])
@requires_admin
def admin_merge_submission(sub_id: int):
    if (err := _db_check()):
        return err
    entry_id = _body().get("entry_id")
    if type(entry_id) is not int:
        return jsonify({"error": "entry_id is required"}), 400
    return jsonify(_serialize(store.merge_submission(sub_id, entry_id, g.user["id"])))


@bp.route("/api/admin/ctr/tracks/approve", methods=["POST"])
@requires_admin
def admin_approve_batch():
    """Approve several Saphi candidates in one go. Each approval is its own
    transaction; one that fails is reported and the rest still go through."""
    if (err := _db_check()):
        return err
    ids = _body().get("ids")
    if not isinstance(ids, list) or not ids or len(ids) > 200 or not all(type(i) is int for i in ids):
        return jsonify({"error": "ids must be a list of 1 to 200 track ids"}), 400
    done, failed = [], []
    for entry_id in ids:
        try:
            done.append(store.approve_entry(entry_id, g.user["id"])["track_key"])
        except RuleError as exc:
            failed.append({"id": entry_id, "code": exc.code, "error": str(exc)})
    return jsonify({"approved": done, "failed": failed})


@bp.route("/api/admin/ctr/tracks/<int:entry_id>", methods=["PATCH"])
@requires_admin
def admin_edit_track(entry_id: int):
    if (err := _db_check()):
        return err
    body = _body()
    if "ap_name" in body or "track_key" in body or "block_index" in body:
        return jsonify({"error": "Identity fields are not editable here", "code": "frozen"}), 409
    row = store.update_presentation(entry_id, g.user["id"], body)
    if "superseded_by" in body:
        other = body["superseded_by"]
        row = store.set_superseded(entry_id, other if type(other) is int else None, g.user["id"])
    return jsonify(_serialize(row))


@bp.route("/api/admin/ctr/tracks/<int:entry_id>/approve", methods=["POST"])
@requires_admin
def admin_approve_track(entry_id: int):
    if (err := _db_check()):
        return err
    return jsonify(_serialize(store.approve_entry(entry_id, g.user["id"], _body().get("overrides"))))


@bp.route("/api/admin/ctr/tracks/<int:entry_id>/promote", methods=["POST"])
@requires_admin
def admin_promote(entry_id: int):
    if (err := _db_check()):
        return err
    return jsonify(_serialize(store.promote_entry(entry_id, g.user["id"], _body().get("ap_name"))))


@bp.route("/api/admin/ctr/tracks/<int:entry_id>/minting", methods=["POST"])
@requires_admin
def admin_minting(entry_id: int):
    if (err := _db_check()):
        return err
    body = _body()
    return jsonify(_serialize(store.set_minting(entry_id, g.user["id"], str(body.get("status", "")),
                                                body.get("maps_to"))))


@bp.route("/api/admin/ctr/tracks/<int:entry_id>/<action>", methods=["POST"])
@requires_admin
def admin_state(entry_id: int, action: str):
    if (err := _db_check()):
        return err
    if action not in ("withdraw", "restore", "source_unavailable"):
        abort(404)
    return jsonify(_serialize(store.set_state(entry_id, g.user["id"], action)))


@bp.route("/api/admin/ctr/tracks/mark-shipped", methods=["POST"])
@requires_admin
def admin_mark_shipped():
    if (err := _db_check()):
        return err
    body = _body()
    keys = body.get("track_keys")
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        return jsonify({"error": "track_keys must be a list"}), 400
    rows = store.mark_shipped(str(body.get("version", "")), keys, g.user["id"])
    return jsonify({"shipped": [r["track_key"] for r in rows]})
