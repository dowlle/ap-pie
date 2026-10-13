from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Stub types matching Archipelago's NetUtils so we can unpickle without the full AP install
NetworkSlot = namedtuple("NetworkSlot", ["name", "game", "type", "group_members"])
NetworkItem = namedtuple("NetworkItem", ["item", "location", "player", "flags"])
Hint = namedtuple(
    "Hint",
    [
        "receiving_player",
        "finding_player",
        "location",
        "item",
        "found",
        "entrance",
        "item_flags",
        "status",
    ],
)

CLIENT_STATUS = {
    0: "unknown",
    5: "connected",
    10: "ready",
    20: "playing",
    30: "goal",
}


@dataclass
class PlayerInfo:
    slot: int
    name: str
    game: str
    checks_done: int = 0
    checks_total: int = 0
    client_status: int = 0

    @property
    def completion_pct(self) -> float:
        return (self.checks_done / self.checks_total * 100) if self.checks_total > 0 else 0.0

    @property
    def status_label(self) -> str:
        return CLIENT_STATUS.get(self.client_status, f"unknown({self.client_status})")

    @property
    def goal_completed(self) -> bool:
        return self.client_status >= 30

    def to_dict(self) -> dict:
        return {
            "slot": self.slot,
            "name": self.name,
            "game": self.game,
            "checks_done": self.checks_done,
            "checks_total": self.checks_total,
            "completion_pct": round(self.completion_pct, 1),
            "client_status": self.client_status,
            "status_label": self.status_label,
            "goal_completed": self.goal_completed,
        }


@dataclass
class GameRecord:
    seed: str
    ap_version: tuple[int, ...]
    creation_time: datetime | None
    players: list[PlayerInfo]
    has_save: bool = False
    zip_path: Path | None = None
    save_path: Path | None = None
    patch_files: list[str] = field(default_factory=list)
    race_mode: int = 0
    hint_cost: int | None = None
    release_mode: str | None = None
    collect_mode: str | None = None
    spoiler: bool = False
    last_activity: datetime | None = None
    game_versions: dict[str, str] = field(default_factory=dict)  # game name → world version

    @property
    def player_count(self) -> int:
        return len(self.players)

    @property
    def games(self) -> list[str]:
        return sorted({p.game for p in self.players})

    @property
    def overall_completion_pct(self) -> float:
        total = sum(p.checks_total for p in self.players)
        done = sum(p.checks_done for p in self.players)
        return (done / total * 100) if total > 0 else 0.0

    @property
    def all_goals_completed(self) -> bool:
        playable = [p for p in self.players if p.checks_total > 0]
        return bool(playable) and all(p.goal_completed for p in playable)

    def to_dict(self) -> dict:
        from ap_lib.search import format_version

        return {
            "seed": self.seed,
            "ap_version": format_version(self.ap_version),
            "creation_time": self.creation_time.isoformat() if self.creation_time else None,
            "players": [p.to_dict() for p in self.players],
            "player_count": self.player_count,
            "games": self.games,
            "has_save": self.has_save,
            "zip_path": str(self.zip_path) if self.zip_path else None,
            "save_path": str(self.save_path) if self.save_path else None,
            "patch_files": self.patch_files,
            "race_mode": self.race_mode,
            "hint_cost": self.hint_cost,
            "release_mode": self.release_mode,
            "collect_mode": self.collect_mode,
            "spoiler": self.spoiler,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "overall_completion_pct": round(self.overall_completion_pct, 1),
            "all_goals_completed": self.all_goals_completed,
            "game_versions": self.game_versions,
        }
