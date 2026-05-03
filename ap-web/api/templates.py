"""API for listing and serving parsed Archipelago YAML templates."""

from __future__ import annotations

import threading
from pathlib import Path
from urllib.parse import unquote

from flask import Blueprint, current_app, jsonify

import config
from apworld_options_parser import parse_apworld_options
from template_parser import list_templates, parse_template

bp = Blueprint("templates", __name__)

_cache: dict[str, dict] = {}
_list_cache: list[dict] | None = None
_apworld_cache: dict[str, dict] = {}  # game_name -> parsed options
_lock = threading.Lock()


def _get_templates_dir() -> Path:
    return Path(config.TEMPLATES_DIR)


def _get_worlds_dir() -> Path | None:
    d = current_app.config.get("AP_WORLDS_DIR") or config.WORLDS_DIR
    if d:
        p = Path(d)
        return p if p.is_dir() else None
    return None


def _scan_apworlds() -> dict[str, dict]:
    """Scan custom worlds directory for .apworld files and parse their options."""
    worlds_dir = _get_worlds_dir()
    if not worlds_dir:
        return {}
    results = {}
    for f in worlds_dir.glob("*.apworld"):
        parsed = parse_apworld_options(f)
        if parsed and parsed["game"]:
            results[parsed["game"]] = parsed
    return results


def _ensure_apworld_cache() -> dict[str, dict]:
    """Lazily populate the apworld cache."""
    global _apworld_cache
    if not _apworld_cache:
        _apworld_cache = _scan_apworlds()
    return _apworld_cache


@bp.route("/api/templates")
def get_template_list():
    global _list_cache
    with _lock:
        if _list_cache is None:
            # Built-in templates from YAML files
            items = list_templates(_get_templates_dir())
            existing_games = {t["game"] for t in items}

            # Add custom apworld games not already covered by templates
            apworlds = _ensure_apworld_cache()
            for game_name in sorted(apworlds):
                if game_name not in existing_games:
                    items.append({"game": game_name, "filename": f"{game_name} (apworld)"})

            _list_cache = items
    return jsonify(_list_cache)


@bp.route("/api/templates/<path:game>")
def get_template(game: str):
    game = unquote(game)
    templates_dir = _get_templates_dir()

    # Try exact filename match in templates directory
    filepath = templates_dir / f"{game}.yaml"
    if not filepath.is_file():
        filepath = templates_dir / f"{game}.yml"

    if filepath.is_file():
        cache_key = str(filepath)
        with _lock:
            if cache_key not in _cache:
                try:
                    _cache[cache_key] = parse_template(filepath)
                except Exception as e:
                    return jsonify({"error": f"Failed to parse template: {e}"}), 500
        return jsonify(_cache[cache_key])

    # Fall back to apworld-parsed options
    with _lock:
        apworlds = _ensure_apworld_cache()
        if game in apworlds:
            return jsonify(apworlds[game])

    return jsonify({"error": f"Template not found for '{game}'"}), 404


@bp.route("/api/templates/refresh", methods=["POST"])
def refresh_templates():
    global _list_cache, _apworld_cache
    with _lock:
        _cache.clear()
        _list_cache = None
        _apworld_cache = {}
    return jsonify({"status": "ok"})
