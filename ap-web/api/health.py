"""Public health endpoint for container/load-balancer/monitoring probes.

Returns 200 if the app is up and responsive. Reports database connectivity
and the Archipelago binary version as best-effort fields without failing
when they are unavailable.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify

import config

bp = Blueprint("health", __name__)

_AP_VERSION_MARKER = Path("/opt/archipelago/.installed-ap-version")


def _ap_binary_version() -> str | None:
    try:
        if _AP_VERSION_MARKER.is_file():
            return _AP_VERSION_MARKER.read_text(encoding="utf-8").strip() or None
    except OSError:
        pass
    return None


def _db_status() -> str:
    from db import _db_url, _get_conn
    if _db_url is None:
        return "unconfigured"
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return "ok"
    except Exception:
        return "error"


@bp.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "db": _db_status(),
        "ap_version": _ap_binary_version(),
        "ap_host": config.HOST,
    })
