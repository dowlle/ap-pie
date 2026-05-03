from __future__ import annotations

from functools import wraps

from flask import Blueprint, jsonify, request, session

from db import (
    _db_url,
    create_listing,
    create_tracker,
    create_tracker_listing,
    delete_listing,
    get_listings,
    get_matches,
    get_tracker,
    get_tracker_by_url,
    get_tracker_listings,
    get_tracker_matches,
    get_user,
    list_trackers,
    update_listing,
    update_tracker_sync,
)
from tracker import fetch_tracker_data, parse_tracker_url

bp = Blueprint("market", __name__)


def requires_db(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if _db_url is None:
            return jsonify({"error": "Database not available. Market features require PostgreSQL."}), 503
        return f(*args, **kwargs)
    return wrapper


def requires_admin(f):
    """Gate market mutation endpoints - only admins can create / update / delete
    markets and listings. The market blueprint is mounted under the public_prefixes
    in auth.py (so reads stay open without a session), which means the global auth
    middleware never populates g.user for these routes - hence the manual session
    check here.

    MVP scope decision (2026-05-01): we ship as a YAML collector first; market
    creation by random users would expose a half-built feature surface. Reads
    stay open for any admin-created markets that exist.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        user = get_user(user_id)
        if not user or not user.get("is_admin"):
            return jsonify({"error": "Market mutations are admin-only for now."}), 403
        return f(*args, **kwargs)
    return wrapper


# ── Legacy seed-based endpoints (kept for backwards compat) ──────


@bp.route("/api/market/<seed>")
@requires_db
def list_market(seed: str):
    status = request.args.get("status", "active")
    return jsonify(get_listings(seed, status=status))


@bp.route("/api/market/<seed>/matches")
@requires_db
def market_matches(seed: str):
    return jsonify(get_matches(seed))


@bp.route("/api/market/<seed>", methods=["POST"])
@requires_db
@requires_admin
def create_market_listing(seed: str):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    required = ["slot", "player_name", "item_name", "listing_type"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"'{field}' is required"}), 400

    if data["listing_type"] not in ("offer", "request"):
        return jsonify({"error": "listing_type must be 'offer' or 'request'"}), 400

    listing = create_listing(
        seed=seed,
        slot=data["slot"],
        player_name=data["player_name"],
        item_name=data["item_name"],
        listing_type=data["listing_type"],
        quantity=data.get("quantity", 1),
    )
    return jsonify(listing), 201


@bp.route("/api/market/<seed>/<int:listing_id>", methods=["PUT"])
@requires_db
@requires_admin
def update_market_listing(seed: str, listing_id: int):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    listing = update_listing(listing_id, **data)
    if not listing:
        return jsonify({"error": "Listing not found"}), 404
    return jsonify(listing)


@bp.route("/api/market/<seed>/<int:listing_id>", methods=["DELETE"])
@requires_db
@requires_admin
def delete_market_listing(seed: str, listing_id: int):
    if delete_listing(listing_id):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Listing not found"}), 404


# ── Tracker endpoints ────────────────────────────────────────────


@bp.route("/api/trackers", methods=["POST"])
@requires_db
@requires_admin
def register_tracker():
    """Register or look up a tracker by URL, fetch its data."""
    data = request.get_json()
    if not data or "tracker_url" not in data:
        return jsonify({"error": "tracker_url is required"}), 400

    url = data["tracker_url"].strip()
    parsed = parse_tracker_url(url)
    if not parsed:
        return jsonify({"error": "Invalid Archipelago tracker URL"}), 400

    # Check if already registered
    existing = get_tracker_by_url(url)
    if existing:
        tracker = existing
    else:
        tracker = create_tracker(
            tracker_url=url,
            display_name=data.get("display_name", f"Game on {parsed['host']}"),
            host=parsed["host"],
        )

    # Fetch tracker data
    tracker_data = fetch_tracker_data(url)
    update_tracker_sync(tracker["id"])

    return jsonify({**tracker, "tracker_data": tracker_data}), 201


@bp.route("/api/trackers")
@requires_db
def get_trackers():
    """List recently tracked games."""
    limit = request.args.get("limit", 20, type=int)
    return jsonify(list_trackers(limit=limit))


@bp.route("/api/trackers/<tracker_id>")
@requires_db
def get_tracker_info(tracker_id: str):
    """Get tracker info + live data."""
    tracker = get_tracker(tracker_id)
    if not tracker:
        return jsonify({"error": "Tracker not found"}), 404

    tracker_data = fetch_tracker_data(tracker["tracker_url"])
    update_tracker_sync(tracker_id)

    return jsonify({**tracker, "tracker_data": tracker_data})


@bp.route("/api/trackers/<tracker_id>/listings")
@requires_db
def tracker_listings(tracker_id: str):
    """Get all listings for a tracked game."""
    tracker = get_tracker(tracker_id)
    if not tracker:
        return jsonify({"error": "Tracker not found"}), 404

    status = request.args.get("status", "active")
    return jsonify(get_tracker_listings(tracker_id, status=status))


@bp.route("/api/trackers/<tracker_id>/listings", methods=["POST"])
@requires_db
@requires_admin
def create_tracker_market_listing(tracker_id: str):
    """Create a listing for a tracked game."""
    tracker = get_tracker(tracker_id)
    if not tracker:
        return jsonify({"error": "Tracker not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    required = ["slot", "player_name", "item_name", "listing_type"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"'{field}' is required"}), 400

    if data["listing_type"] not in ("offer", "request"):
        return jsonify({"error": "listing_type must be 'offer' or 'request'"}), 400

    listing = create_tracker_listing(
        tracker_id=tracker_id,
        slot=data["slot"],
        player_name=data["player_name"],
        item_name=data["item_name"],
        listing_type=data["listing_type"],
        quantity=data.get("quantity", 1),
    )
    return jsonify(listing), 201


@bp.route("/api/trackers/<tracker_id>/listings/<int:listing_id>", methods=["PUT"])
@requires_db
@requires_admin
def update_tracker_market_listing(tracker_id: str, listing_id: int):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    listing = update_listing(listing_id, **data)
    if not listing:
        return jsonify({"error": "Listing not found"}), 404
    return jsonify(listing)


@bp.route("/api/trackers/<tracker_id>/listings/<int:listing_id>", methods=["DELETE"])
@requires_db
@requires_admin
def delete_tracker_market_listing(tracker_id: str, listing_id: int):
    if delete_listing(listing_id):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Listing not found"}), 404


@bp.route("/api/trackers/<tracker_id>/matches")
@requires_db
def tracker_match_list(tracker_id: str):
    """Get matching offers/requests for a tracked game."""
    tracker = get_tracker(tracker_id)
    if not tracker:
        return jsonify({"error": "Tracker not found"}), 404

    return jsonify(get_tracker_matches(tracker_id))
