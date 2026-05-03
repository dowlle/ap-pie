from __future__ import annotations

import zipfile
from pathlib import Path

from flask import Blueprint, jsonify, request

import config
from api.features import requires_feature

bp = Blueprint("upload", __name__)


@bp.route("/api/upload", methods=["POST"])
@requires_feature("generation")
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    raw_filename = file.filename or ""

    # SEC: strip directory components from the user-supplied filename and
    # reject anything that would escape output_dir. Without this, a name
    # like `../../etc/cron.d/foo.zip` writes outside the intended directory.
    safe_name = Path(raw_filename).name
    if (
        not safe_name
        or not safe_name.endswith(".zip")
        or safe_name.startswith(".")
        or "/" in safe_name
        or "\\" in safe_name
        or "\x00" in safe_name
    ):
        return jsonify({"error": "Invalid filename"}), 400

    data = file.read()

    try:
        zf = zipfile.ZipFile(file.stream)
        file.stream.seek(0)
    except zipfile.BadZipFile:
        return jsonify({"error": "Invalid zip file"}), 400

    arch_files = [n for n in zf.namelist() if n.endswith(".archipelago")]
    if not arch_files:
        return jsonify({"error": "Zip does not contain an .archipelago multidata file"}), 400

    output_dir = Path(config.OUTPUT_DIR).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = (output_dir / safe_name).resolve()

    # Defense-in-depth: confirm the resolved path is still inside output_dir.
    try:
        dest.relative_to(output_dir)
    except ValueError:
        return jsonify({"error": "Invalid filename"}), 400

    if dest.exists():
        return jsonify({"error": f"File {safe_name} already exists"}), 409

    dest.write_bytes(data)

    from app import _refresh_records
    records = _refresh_records()

    return jsonify({
        "status": "uploaded",
        "filename": safe_name,
        "total_games": len(records),
    })
