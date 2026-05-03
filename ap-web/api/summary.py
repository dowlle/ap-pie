from flask import Blueprint, jsonify

from ap_lib import compute_summary

bp = Blueprint("summary", __name__)


@bp.route("/api/summary")
def summary():
    from app import get_records
    records = get_records()
    return jsonify(compute_summary(records))
