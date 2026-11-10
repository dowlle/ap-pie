from __future__ import annotations

from ap_lib.models import GameRecord


def format_version(v: tuple[int, ...]) -> str:
    return ".".join(str(x) for x in v)


def search_records(
    records: list[GameRecord],
    *,
    game: str | None = None,
    player: str | None = None,
    seed: str | None = None,
    has_save: bool | None = None,
    version: str | None = None,
) -> list[GameRecord]:
    """Filter records by various criteria (case-insensitive substring match)."""
    results = records

    if game:
        game_lower = game.lower()
        results = [r for r in results if any(game_lower in p.game.lower() for p in r.players)]

    if player:
        player_lower = player.lower()
        results = [r for r in results if any(player_lower in p.name.lower() for p in r.players)]

    if seed:
        results = [r for r in results if seed in r.seed]

    if has_save is not None:
        results = [r for r in results if r.has_save == has_save]

    if version:
        results = [r for r in results if format_version(r.ap_version).startswith(version)]

    return results


def compute_summary(records: list[GameRecord]) -> dict:
    """Compute aggregate stats and return as a dict."""
    all_games: dict[str, int] = {}
    all_players: dict[str, int] = {}
    versions: dict[str, int] = {}

    for r in records:
        v = format_version(r.ap_version)
        versions[v] = versions.get(v, 0) + 1
        for p in r.players:
            all_games[p.game] = all_games.get(p.game, 0) + 1
            all_players[p.name] = all_players.get(p.name, 0) + 1

    return {
        "total_games": len(records),
        "games_with_save": sum(1 for r in records if r.has_save),
        "games_by_frequency": sorted(all_games.items(), key=lambda x: -x[1]),
        "players_by_frequency": sorted(all_players.items(), key=lambda x: -x[1]),
        "versions": sorted(versions.items()),
    }
