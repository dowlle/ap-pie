"""Public player-connect endpoint.

Returns only the subset of game metadata a player needs to join a session:
seed, AP version, slot list (slot number / player name / game), and live
server connection info. The seed itself is the capability - it's 20 random
digits (~66 bits of entropy) so unguessable in practice. Intentionally omits
host identity, room name, spoiler data, generation logs, and anything else
that could aid enumeration or leak host-side context.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

import config

bp = Blueprint("connect", __name__)


def _public_host() -> str:
    """Resolve the host string we should tell players to connect to.

    Order of preference:
      1. AP_HOST env var, when it's set to something other than 'localhost'.
         This is the explicit production override (e.g. 'ap-pie.com').
      2. X-Forwarded-Host header, if a reverse proxy set it - this is the
         hostname the original browser request targeted.
      3. The request's Host header, stripped of its port.
      4. Fall back to whatever AP_HOST is (including 'localhost') so local dev
         keeps working.

    The reason we override a 'localhost' AP_HOST specifically: it's the
    code-level default and a common mis-config on LAN deployments. A player
    hitting http://192.168.1.x:5001 needs to be told to connect to that IP,
    not to 'localhost' which resolves to their own machine.
    """
    configured = (config.HOST or "").strip()
    if configured and configured.lower() != "localhost":
        return configured

    fwd = request.headers.get("X-Forwarded-Host", "").split(",")[0].strip()
    candidate = fwd or request.host or configured or "localhost"
    # Strip any :port suffix - AP game servers run on different ports
    return candidate.split(":", 1)[0]


def _server_status(seed: str) -> dict:
    # If the room's host runs the AP server on their own machine and registered
    # the address, prefer that over Archipelago Pie's built-in pool. The lobby just
    # points at the external server; it doesn't manage it.
    try:
        from db import get_room_by_seed
        room = get_room_by_seed(seed)
    except Exception:
        room = {}
    ext_host = (room or {}).get("external_host")
    ext_port = (room or {}).get("external_port")
    if ext_host and ext_port:
        return {
            "status": "external",
            "host": ext_host,
            "port": int(ext_port),
            "connection_url": f"{ext_host}:{ext_port}",
        }

    manager = current_app.config["server_manager"]
    instance = manager.status(seed)
    if instance is None:
        return {"status": "never_started"}
    host = _public_host()
    return {
        "status": instance.status,  # starting | running | stopped | crashed
        "host": host,
        "port": instance.port,
        "connection_url": f"{host}:{instance.port}",
        "started_at": instance.started_at,
    }


@bp.route("/api/connect/<seed>")
def connect_info(seed: str):
    from app import get_records

    records = get_records()
    matches = [r for r in records if r.seed == seed]
    if not matches:
        return jsonify({"error": "Game not found"}), 404

    record = matches[0]
    from ap_lib.search import format_version

    players = [
        {"slot": p.slot, "name": p.name, "game": p.game}
        for p in record.players
    ]

    return jsonify({
        "seed": record.seed,
        "ap_version": format_version(record.ap_version),
        "creation_time": record.creation_time.isoformat() if record.creation_time else None,
        "player_count": len(players),
        "players": players,
        "patch_files": record.patch_files,
        "has_zip": record.zip_path is not None,
        "server": _server_status(seed),
    })


def _find_record(seed: str):
    from app import get_records
    for r in get_records():
        if r.seed == seed:
            return r
    return None


@bp.route("/api/connect/<seed>/download")
def connect_download_zip(seed: str):
    """Public download of the multiworld zip so players can pull their patch file.

    Returns the zip stream. Only the seed holder can request it (seeds are
    unguessable). The zip contains player patches and the .archipelago multidata,
    but no spoiler log (those live in a separate .apspoiler file).
    """
    record = _find_record(seed)
    if not record:
        return jsonify({"error": "Game not found"}), 404
    if not record.zip_path:
        return jsonify({"error": "No zip available for this game"}), 404

    return send_file(
        record.zip_path,
        as_attachment=True,
        download_name=f"AP-{seed}.zip",
        mimetype="application/zip",
    )


@bp.route("/api/connect/<seed>/patches/<path:filename>")
def connect_download_patch(seed: str, filename: str):
    """Stream a single per-slot patch file out of the multiworld zip.

    Players don't need the whole multiworld zip when only their own patch matters;
    the filename must be one of the patches listed in /api/connect/<seed>, which
    guards against path traversal since we only serve known entries.
    """
    record = _find_record(seed)
    if not record:
        return jsonify({"error": "Game not found"}), 404
    if not record.zip_path:
        return jsonify({"error": "No zip available for this game"}), 404
    if filename not in record.patch_files:
        return jsonify({"error": "Patch file not found in this multiworld"}), 404

    try:
        with zipfile.ZipFile(record.zip_path) as zf:
            data = zf.read(filename)
    except (KeyError, zipfile.BadZipFile, OSError):
        return jsonify({"error": "Patch file could not be extracted"}), 500

    suffix = Path(filename).suffix.lstrip(".").lower() or "bin"
    mimetype = "application/zip" if suffix == "zip" else "application/octet-stream"
    return send_file(
        BytesIO(data),
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype,
    )
