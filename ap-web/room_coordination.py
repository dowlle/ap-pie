"""Pure reconciliation helpers for generated-room slot identity.

The route layer fetches tracker data and owns authorization. This module only
compares the generated roster with room YAMLs so it stays deterministic and
unit-testable without Flask or PostgreSQL.
"""

from __future__ import annotations


def build_roster_preview(players: list[dict], yamls: list[dict]) -> list[dict]:
    """Return one reconciliation row per generated slot.

    Exact player-name equality is the only automatic match. A duplicate exact
    name is ambiguous and remains unbound. Normalized/fuzzy matching belongs in
    a later, explicitly-approved policy because a false ownership assignment is
    worse than asking the host to choose.
    """
    by_name: dict[str, list[dict]] = {}
    for yaml_row in yamls:
        by_name.setdefault(str(yaml_row.get("player_name") or ""), []).append(yaml_row)

    preview: list[dict] = []
    for player in sorted(players, key=lambda p: (int(p.get("team", 0)), int(p.get("slot", 0)))):
        name = str(player.get("name") or "")
        matches = by_name.get(name, [])
        selected = matches[0] if len(matches) == 1 else None
        preview.append({
            "team": int(player.get("team", 0)),
            "slot": int(player.get("slot") or 0),
            "player_name": name,
            "game": str(player.get("game") or ""),
            "match_status": "exact" if selected else ("ambiguous" if matches else "unmatched"),
            "suggested_yaml_id": selected.get("id") if selected else None,
            "candidates": [
                {
                    "yaml_id": row.get("id"),
                    "player_name": row.get("player_name"),
                    "game": row.get("game"),
                    "submitter_username": row.get("submitter_username"),
                    "has_owner": row.get("submitter_user_id") is not None,
                }
                for row in matches
            ],
        })
    return preview


def apply_host_mappings(preview: list[dict], yamls: list[dict], mappings: list[dict]) -> list[dict]:
    """Validate host selections and return DB-ready slot rows."""
    yaml_by_id = {int(row["id"]): row for row in yamls}
    valid_slots = {(int(row["team"]), int(row["slot"])) for row in preview}
    mapping_by_slot: dict[tuple[int, int], int | None] = {}
    used_yaml_ids: set[int] = set()
    for mapping in mappings:
        key = (int(mapping.get("team", 0)), int(mapping["slot"]))
        if key not in valid_slots:
            raise ValueError(f"Generated slot {key[0]}:{key[1]} is not in the current tracker roster")
        if key in mapping_by_slot:
            raise ValueError(f"Generated slot {key[0]}:{key[1]} is mapped more than once")
        raw_yaml_id = mapping.get("yaml_id")
        yaml_id = int(raw_yaml_id) if raw_yaml_id is not None else None
        if yaml_id is not None:
            if yaml_id not in yaml_by_id:
                raise ValueError(f"YAML {yaml_id} is not part of this room")
            if yaml_id in used_yaml_ids:
                raise ValueError(f"YAML {yaml_id} is mapped to more than one generated slot")
            used_yaml_ids.add(yaml_id)
        mapping_by_slot[key] = yaml_id

    out: list[dict] = []
    for row in preview:
        key = (row["team"], row["slot"])
        if key in mapping_by_slot:
            yaml_id = mapping_by_slot[key]
        else:
            yaml_id = row.get("suggested_yaml_id")
            if yaml_id in used_yaml_ids:
                yaml_id = None
            elif yaml_id is not None:
                used_yaml_ids.add(yaml_id)
        yaml_row = yaml_by_id.get(int(yaml_id)) if yaml_id is not None else None
        out.append({
            "team": row["team"],
            "slot": row["slot"],
            "player_name": row["player_name"],
            "game": row["game"],
            "yaml_id": yaml_id,
            "yaml_owner_user_id": yaml_row.get("submitter_user_id") if yaml_row else None,
        })
    return out
