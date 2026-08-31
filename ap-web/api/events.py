"""FEAT-31: the client event endpoint and the admin read surface.

POST /api/events is public and deliberately dull: it accepts a short list of
allowlisted event kinds from the browser, throws away anything it does not
recognise, and always answers 204. It exists because two things are invisible
to the server - which SPA view is on screen (the catch-all serves the same
index.html for every client route) and how far someone gets inside the YAML
builder modal before leaving.

Everything the endpoint stores goes through analytics.record_event, so the
same privacy rules apply as to server-recorded events: no IP, no User-Agent
string, no device storage, props validated against a per-kind allowlist.

Abuse posture: the endpoint writes one small row per accepted call, behind a
per-IP hourly bucket. The IP is used for the bucket only - it is never handed
to the recorder. A caller that exceeds the bucket, sends garbage, or posts a
server-only kind gets the same 204 as everyone else; the endpoint reveals
nothing about why a call was ignored.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from flask import Blueprint, jsonify, request, session

import analytics
import config
from auth import requires_admin
from db import _db_url
from request_ip import client_ip

bp = Blueprint("events", __name__)

_RATE_WINDOW_SECONDS = 3600
_buckets: dict[str, deque] = defaultdict(deque)
_buckets_lock = threading.Lock()

# A single sendBeacon may carry a small batch (the builder emits an "opened"
# and an "abandoned" event on unload). Ten is generous for that and low
# enough that one call can never be a bulk-write primitive.
_MAX_BATCH = 10
_MAX_BODY_BYTES = 4096


def _rate_ok(ip: str) -> bool:
    now = time.time()
    cap = config.ANALYTICS_EVENTS_PER_IP_PER_HOUR
    with _buckets_lock:
        bucket = _buckets[ip]
        cutoff = now - _RATE_WINDOW_SECONDS
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= cap:
            return False
        bucket.append(now)
        return True


@bp.route("/api/events", methods=["POST"])
def post_events():
    """Accept browser-side events. Always 204, whatever happens."""
    NO_CONTENT = ("", 204)

    if not config.ANALYTICS_ENABLED or _db_url is None:
        return NO_CONTENT
    if (request.content_length or 0) > _MAX_BODY_BYTES:
        return NO_CONTENT
    if not _rate_ok(client_ip()):
        return NO_CONTENT

    # force=True because navigator.sendBeacon can only send CORS-safelisted
    # content types, so unload-path events arrive as text/plain. The body is
    # parsed as JSON either way and every field is validated below, so the
    # declared type carries no trust.
    payload = request.get_json(silent=True, force=True)
    if not isinstance(payload, dict):
        return NO_CONTENT

    raw = payload.get("events")
    if not isinstance(raw, list):
        raw = [payload]

    # One session lookup for the whole batch. Logged-in browser events carry
    # the user id for the same reason server-side ones do: it is the identity
    # already behind every action they take on the site.
    user_id = session.get("user_id") if not analytics.objection_signalled(request) else None

    for item in raw[:_MAX_BATCH]:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        if not isinstance(kind, str) or kind not in analytics.CLIENT_KINDS:
            continue
        visit_id = item.get("visit_id")
        if not isinstance(visit_id, str) or not visit_id.isalnum() or len(visit_id) > 64:
            visit_id = None
        room_id = item.get("room_id")
        if not isinstance(room_id, str) or len(room_id) > 64:
            room_id = None
        analytics.record_event(
            kind,
            # Anonymous kinds (the Pokepelago ones) never carry the account
            # id, even when an apie_session cookie rides along.
            user_id=None if kind in analytics.ANONYMOUS_KINDS else user_id,
            room_id=room_id,
            props=item.get("props") if isinstance(item.get("props"), dict) else None,
            req=request,
            visit_id=visit_id,
        )

    return NO_CONTENT


# ── Admin read surface ───────────────────────────────────────────
# These live under /api/admin/*, so the auth middleware already enforces
# is_admin before the handler runs; @requires_admin is the belt-and-braces
# layer the SEC-10 fix asked every admin route to keep.


@bp.route("/api/admin/events", methods=["GET"])
@requires_admin
def list_events():
    if _db_url is None:
        return jsonify({"error": "Database not available"}), 503
    from db import query_events

    args = request.args
    user_id = args.get("user_id", type=int)
    rows = query_events(
        kind=args.get("kind"),
        since=args.get("since"),
        until=args.get("until"),
        room_id=args.get("room_id"),
        user_id=user_id,
        visit_id=args.get("visit_id"),
        limit=args.get("limit", default=200, type=int),
    )
    return jsonify({"events": rows, "count": len(rows)})


@bp.route("/api/admin/events/summary", methods=["GET"])
@requires_admin
def events_summary():
    """The standing questions, precomputed, so checking the funnel does not
    need a psql session."""
    if _db_url is None:
        return jsonify({"error": "Database not available"}), 503
    from db import events_counts_by_kind, events_funnel

    days = request.args.get("days", default=7, type=int)
    summary = events_funnel(days)
    summary["by_kind"] = events_counts_by_kind(days)
    summary["recorder"] = {
        "enabled": config.ANALYTICS_ENABLED,
        "visit_id": config.ANALYTICS_VISIT_ID,
        "retention_days": config.ANALYTICS_RETENTION_DAYS,
        "queue_depth": analytics.queue_depth(),
        "dropped": analytics.dropped_count(),
    }
    return jsonify(summary)


@bp.route("/api/admin/events/erase", methods=["POST"])
@requires_admin
def erase_user_events():
    """GDPR Art. 17: delete every analytics row belonging to one user.

    Kept as an explicit admin action rather than a self-serve button: the
    request arrives out of band (Discord, e-mail), and the operator needs to
    confirm which account it came from before erasing anything.
    """
    if _db_url is None:
        return jsonify({"error": "Database not available"}), 503
    from db import delete_events_for_user

    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    if not isinstance(user_id, int):
        return jsonify({"error": "user_id (int) is required"}), 400
    removed = delete_events_for_user(user_id)
    return jsonify({"user_id": user_id, "rows_deleted": removed})
