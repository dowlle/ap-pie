"""Archipelago output directory analyzer (CLI).

Scans AP output zips and apsave files to extract game metadata:
seed, version, players, games, creation date, save state, etc.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import socket

from ap_lib import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SERVER_EXE,
    GameRecord,
    compute_summary,
    format_version,
    scan_output_dir,
    search_records,
)


# ── Display ──────────────────────────────────────────────────────


def print_record(rec: GameRecord, verbose: bool = False) -> None:
    save_marker = " [SAVE]" if rec.has_save else ""
    goal_marker = " [DONE]" if rec.has_save and rec.all_goals_completed else ""
    ts = rec.creation_time.strftime("%Y-%m-%d %H:%M") if rec.creation_time else "unknown date"
    header = f"Seed {rec.seed}  (AP {format_version(rec.ap_version)})  {ts}{save_marker}{goal_marker}"
    if rec.has_save:
        header += f"  {rec.overall_completion_pct:.0f}% complete"
    if rec.last_activity:
        header += f"  |  last played {rec.last_activity.strftime('%Y-%m-%d %H:%M')}"
    print(header)
    for p in rec.players:
        line = f"  P{p.slot}: {p.name} - {p.game}"
        if rec.has_save and p.checks_total > 0:
            status = f" [{p.status_label}]" if p.client_status > 0 else ""
            line += f"  ({p.checks_done}/{p.checks_total} = {p.completion_pct:.0f}%{status})"
        print(line)
    if verbose:
        if rec.patch_files:
            print(f"  Patch files: {', '.join(rec.patch_files)}")
        print(f"  Race mode: {rec.race_mode}  |  Hint cost: {rec.hint_cost}")
        print(f"  Release: {rec.release_mode}  |  Collect: {rec.collect_mode}")
        print(f"  Spoiler: {'yes' if rec.spoiler else 'no'}")
        if rec.zip_path:
            print(f"  Zip: {rec.zip_path}")
        if rec.save_path:
            print(f"  Save: {rec.save_path}")
    print()


def print_summary(records: list[GameRecord]) -> None:
    summary = compute_summary(records)
    print(f"Total generated games: {summary['total_games']}")
    print(f"Games with save file:  {summary['games_with_save']}")
    print()
    print("Games by frequency:")
    for game, count in summary["games_by_frequency"]:
        print(f"  {game}: {count}")
    print()
    print("Players by frequency:")
    for name, count in summary["players_by_frequency"][:20]:
        print(f"  {name}: {count}")
    if len(summary["players_by_frequency"]) > 20:
        print(f"  ... and {len(summary['players_by_frequency']) - 20} more")
    print()
    print("AP versions:")
    for v, count in summary["versions"]:
        print(f"  {v}: {count}")


# ── Server launch ────────────────────────────────────────────────


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except OSError:
            return True


def serve_game(record: GameRecord, server_exe: str = DEFAULT_SERVER_EXE) -> None:
    if not record.zip_path:
        print("Error: no zip path for this record", file=sys.stderr)
        sys.exit(1)

    if not Path(server_exe).is_file():
        print(f"Error: server not found at {server_exe}", file=sys.stderr)
        sys.exit(1)

    multidata = record.zip_path

    port = 38281
    while port < 38381:
        if is_port_in_use(port):
            print(f"Port {port} is in use, trying next...")
            port += 1
            continue

        print(f"Starting server for seed {record.seed} on port {port}...")
        print(f"  Players: {', '.join(p.name for p in record.players)}")
        print(f"  Command: {server_exe} --port {port} {multidata}")
        print()

        subprocess.run([server_exe, "--port", str(port), str(multidata)])
        break


def pick_game(results: list[GameRecord]) -> GameRecord:
    for i, rec in enumerate(results, 1):
        save_marker = " [SAVE]" if rec.has_save else ""
        done_marker = " [DONE]" if rec.has_save and rec.all_goals_completed else ""
        ts = rec.creation_time.strftime("%Y-%m-%d %H:%M") if rec.creation_time else "unknown"
        completion = f"  {rec.overall_completion_pct:.0f}% complete" if rec.has_save else ""
        last = ""
        if rec.last_activity:
            last = f"  |  last played {rec.last_activity.strftime('%Y-%m-%d %H:%M')}"
        players = ", ".join(f"{p.name} ({p.game})" for p in rec.players)
        print(f"  {i}) Seed {rec.seed}  {ts}{save_marker}{done_marker}{completion}{last}")
        print(f"     {players}")
    print()
    while True:
        try:
            choice = input(f"Select game [1-{len(results)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                return results[idx]
        except (ValueError, EOFError):
            pass
        print(f"Please enter a number between 1 and {len(results)}.")


# ── CLI ──────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze Archipelago output directory"
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Path to Archipelago output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument("--game", "-g", help="Filter by game name (substring match)")
    parser.add_argument("--player", "-p", help="Filter by player name (substring match)")
    parser.add_argument("--seed", "-s", help="Filter by seed (substring match)")
    parser.add_argument(
        "--has-save", action="store_true", default=None, help="Only show games with a save file"
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Only show games without a save file"
    )
    parser.add_argument("--version", help="Filter by AP version prefix (e.g. '0.6.6')")
    parser.add_argument(
        "--summary", action="store_true", help="Show aggregate summary stats"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show full details for each game"
    )
    parser.add_argument(
        "--sort",
        choices=["date", "seed", "players"],
        default="date",
        help="Sort order (default: date)",
    )
    parser.add_argument("--limit", "-n", type=int, help="Limit number of results shown")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Launch the AP server for the selected game",
    )
    parser.add_argument(
        "--server-exe",
        default=DEFAULT_SERVER_EXE,
        help=f"Path to ArchipelagoServer.exe (default: {DEFAULT_SERVER_EXE})",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_dir():
        print(f"Error: {output_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {output_dir} ...")
    records = scan_output_dir(output_dir)
    print(f"Found {len(records)} generated games.\n")

    if args.summary:
        print_summary(records)
        return

    has_save = None
    if args.has_save:
        has_save = True
    elif args.no_save:
        has_save = False

    results = search_records(
        records,
        game=args.game,
        player=args.player,
        seed=args.seed,
        has_save=has_save,
        version=args.version,
    )

    if args.sort == "date":
        results.sort(key=lambda r: r.creation_time or datetime.min, reverse=True)
    elif args.sort == "seed":
        results.sort(key=lambda r: r.seed)
    elif args.sort == "players":
        results.sort(key=lambda r: r.player_count, reverse=True)

    if args.limit:
        results = results[: args.limit]

    if not results:
        print("No matching games found.")
        return

    if args.serve:
        if len(results) == 1:
            record = results[0]
            print_record(record)
        else:
            print(f"Multiple matches ({len(results)}), pick one:\n")
            record = pick_game(results)
            print()
            print_record(record)
        serve_game(record, server_exe=args.server_exe)
        return

    print(f"Showing {len(results)} result(s):\n")
    for rec in results:
        print_record(rec, verbose=args.verbose)


if __name__ == "__main__":
    main()
