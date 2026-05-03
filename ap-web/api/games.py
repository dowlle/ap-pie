from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from ap_lib import GameRecord, format_version, search_records

bp = Blueprint("games", __name__)


def _get_records() -> list[GameRecord]:
    from app import get_records
    return get_records()


@bp.route("/api/games")
def list_games():
    records = _get_records()

    # Parse filter params
    game = request.args.get("game") or None
    player = request.args.get("player") or None
    seed = request.args.get("seed") or None
    version = request.args.get("version") or None

    has_save_param = request.args.get("has_save")
    has_save = None
    if has_save_param == "true":
        has_save = True
    elif has_save_param == "false":
        has_save = False

    results = search_records(
        records,
        game=game,
        player=player,
        seed=seed,
        has_save=has_save,
        version=version,
    )

    # Sort
    sort = request.args.get("sort", "date")
    if sort == "date":
        results.sort(key=lambda r: r.creation_time or datetime.min, reverse=True)
    elif sort == "seed":
        results.sort(key=lambda r: r.seed)
    elif sort == "players":
        results.sort(key=lambda r: r.player_count, reverse=True)
    elif sort == "completion":
        results.sort(key=lambda r: r.overall_completion_pct, reverse=True)
    elif sort == "last_played":
        results.sort(key=lambda r: r.last_activity or datetime.min, reverse=True)

    # Limit
    limit = request.args.get("limit", type=int)
    if limit:
        results = results[:limit]

    return jsonify([r.to_dict() for r in results])


@bp.route("/api/games/<seed>")
def get_game(seed: str):
    records = _get_records()
    matches = [r for r in records if r.seed == seed]
    if not matches:
        return jsonify({"error": "Game not found"}), 404
    return jsonify(matches[0].to_dict())
