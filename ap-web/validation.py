"""YAML validation for Archipelago player configs.

Mirrors what Archipelago's Generate.py actually accepts (AP 0.6.7 reference).
The goal is to fail-fast on YAMLs AP itself would reject, and pass anything
AP would generate, even if the eventual output is unusual (truncated names,
random game pick).
"""

from __future__ import annotations

import re
import string
from collections import Counter

import yaml

# Mirror Archipelago's Utils.get_file_safe_name strip set: AP silently strips
# these from generated filenames, but the in-game name keeps them. The rejection
# we enforce here is narrower than AP's own (none); we keep it as a guardrail
# so a malformed name doesn't silently lose every character at filename time.
_FILENAME_STRIP_CHARS = '<>:"/\\|?*'

_NAME_TEMPLATE_TOKEN = re.compile(r"\{(NUMBER|number|PLAYER|player)\}|%(number|player)%")

# AP's player-name length limit, applied AFTER templating + strip.
_NAME_MAX_LEN = 16

# AP rejects this exact post-templated name (Generate.py:379).
_RESERVED_NAMES = {"Archipelago"}


class _SafeFormatter(string.Formatter):
    """Mirrors Generate.SafeFormatter - leaves unknown {tokens} intact."""

    def get_value(self, key, args, kwargs):
        if isinstance(key, int):
            return args[key] if key < len(args) else "{" + str(key) + "}"
        return kwargs.get(key, "{" + key + "}")


def _resolve_name_template(name: str, slot: int = 1, number: int = 1) -> str:
    """Resolve a name the same way AP's Generate.handle_name does.

    Defaults (slot=1, number=1) match the FIRST occurrence - `{NUMBER}` and
    `{PLAYER}` collapse to empty, so `Neui{NUMBER}` -> `Neui`. AP truncates
    to 16 chars after stripping whitespace.
    """
    # Mirror legacy %number% / %player% conversion (Generate.py:369)
    parts = name.split("%%")
    parts = [p.replace("%number%", "{number}").replace("%player%", "{player}") for p in parts]
    converted = "%".join(parts)

    resolved = _SafeFormatter().vformat(
        converted,
        (),
        {
            "number": number,
            "NUMBER": (number if number > 1 else ""),
            "player": slot,
            "PLAYER": (slot if slot > 1 else ""),
        },
    )
    return resolved.strip()[:_NAME_MAX_LEN].strip()


def validate_yaml(content: str, existing_names: list[str] | None = None) -> tuple[bool, str | None]:
    """Validate a player YAML string. Returns (is_valid, error_message)."""
    try:
        docs = list(yaml.safe_load_all(content))
    except yaml.YAMLError as e:
        return False, f"Invalid YAML syntax: {e}"

    if not docs or all(d is None for d in docs):
        return False, "YAML file is empty"

    # Replay AP's counter (Generate.handle_name + Generate.py:281) over the
    # existing siblings to learn (a) what their resolved names are and (b)
    # what counter value the next same-literal name would get. The N-th
    # occurrence of the same lowercase literal resolves with counter=N, so two
    # 'Neui{NUMBER}' YAMLs in series resolve to 'Neui' + 'Neui2', while
    # 'Neui' + 'Neui{NUMBER}' both resolve to 'Neui' (a collision).
    sibling_counter: Counter[str] = Counter()
    sibling_resolved: set[str] = set()
    for n in existing_names or []:
        if not n:
            continue
        nl = n.lower()
        sibling_counter[nl] += 1
        c = sibling_counter[nl]
        sibling_resolved.add(_resolve_name_template(n, slot=c, number=c).lower())

    # Multi-doc YAMLs share the same counter as the siblings - AP's counter
    # is per-generation, not per-file.
    upload_counter = Counter(sibling_counter)
    own_resolved: set[str] = set()

    for doc in docs:
        if doc is None:
            continue
        ok, err = _validate_single_doc(doc, sibling_resolved, upload_counter, own_resolved)
        if not ok:
            return False, err

    return True, None


def _validate_single_doc(
    doc: dict,
    sibling_resolved: set[str],
    upload_counter: Counter,
    own_resolved: set[str],
) -> tuple[bool, str | None]:
    if not isinstance(doc, dict):
        return False, "YAML document must be a mapping"

    raw_name = doc.get("name")
    if not raw_name:
        return False, "Missing required field: 'name'"

    raw_name = str(raw_name)

    # Reject only chars AP would silently strip from output filenames. Apostrophes,
    # parentheses, hyphens etc. are all fine - AP allows arbitrary unicode in names.
    if any(c in raw_name for c in _FILENAME_STRIP_CHARS):
        bad = sorted({c for c in raw_name if c in _FILENAME_STRIP_CHARS})
        return False, (
            f"Player name '{raw_name}' contains characters that would be stripped from "
            f"output filenames: {''.join(bad)}"
        )

    nl = raw_name.lower()
    upload_counter[nl] += 1
    occurrence = upload_counter[nl]
    resolved = _resolve_name_template(raw_name, slot=occurrence, number=occurrence)
    if not resolved:
        return False, f"Player name '{raw_name}' resolves to empty after templating + truncation"

    if resolved in _RESERVED_NAMES:
        return False, f"Player name '{resolved}' is reserved by Archipelago"

    resolved_lower = resolved.lower()
    if resolved_lower in sibling_resolved:
        return False, f"Duplicate player name: '{resolved}' (collides with an already-uploaded YAML)"

    if resolved_lower in own_resolved:
        return False, f"Duplicate player name within this YAML: '{resolved}'"

    own_resolved.add(resolved_lower)

    # Game can be a string, a dict (weighted random), or a list (uniform random).
    # AP rolls one game per generation via Generate.get_choice (Generate.py:341).
    # The YAML must have a top-level section for every possible game key.
    game = doc.get("game")
    if not game:
        return False, f"Missing required field: 'game' for player '{resolved}'"

    candidate_games: list[str] = []
    if isinstance(game, str):
        candidate_games = [game]
    elif isinstance(game, dict):
        candidate_games = [str(k) for k, v in game.items() if _is_positive_weight(v)]
        if not candidate_games:
            return False, f"Random `game:` pool for '{resolved}' has no entries with positive weight"
    elif isinstance(game, list):
        candidate_games = [str(g) for g in game if g]
        if not candidate_games:
            return False, f"Random `game:` list for '{resolved}' is empty"
    else:
        return False, f"`game:` must be a string, dict, or list for player '{resolved}'"

    for candidate in candidate_games:
        if candidate not in doc:
            if len(candidate_games) == 1:
                return False, f"Missing game-specific section '{candidate}' for player '{resolved}'"
            return False, (
                f"Missing game-specific section '{candidate}' for player '{resolved}' "
                f"(part of random game pool: {candidate_games})"
            )
        if not isinstance(doc[candidate], dict):
            return False, f"Game section '{candidate}' must be a mapping for player '{resolved}'"

    return True, None


def _is_positive_weight(value) -> bool:
    """A weight entry is 'live' if its weight is > 0. AP filters zero-weighted
    keys out of get_choice (Generate.py:350-351)."""
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def extract_required_apworld_versions(content: str) -> dict[str, str]:
    """Parse the AP-standard `requires.game` block from a YAML.

    AP YAMLs may include a per-game APWorld version requirement under
    `requires`:

        requires:
          version: 0.6.7        # AP core required
          game:
            Ship of Harkinian: 1.2.1   # APWorld version required

    When present, this is what the YAML was authored against - much more
    accurate than guessing "latest from index". Returns a `{game_name:
    version_string}` map. Multi-doc YAMLs aggregate; later docs win on
    conflict (PyYAML's last-write semantics, matches Generate.py's
    handling).

    Returns `{}` for YAMLs that don't include the block, parse-fail
    YAMLs, or YAMLs where requires.game is absent / malformed. Never
    raises - YAML version sniffing is opportunistic.
    """
    out: dict[str, str] = {}
    try:
        for doc in yaml.safe_load_all(content):
            if not isinstance(doc, dict):
                continue
            requires = doc.get("requires")
            if not isinstance(requires, dict):
                continue
            game_versions = requires.get("game")
            if not isinstance(game_versions, dict):
                continue
            for k, v in game_versions.items():
                if k and v is not None:
                    out[str(k)] = str(v).strip()
    except yaml.YAMLError:
        pass
    return out


def extract_player_info(content: str) -> tuple[str, str] | None:
    """Extract (player_name, game) from a YAML string. Returns None on failure.

    Used for surfacing a YAML in the lobby table, so we return the *raw*
    player_name (with any `{NUMBER}` token intact) and a display form of `game`
    that handles dict/list pools by joining keys, so the host can see the pool
    rather than a Python repr.
    """
    try:
        doc = yaml.safe_load(content)
    except yaml.YAMLError:
        return None

    if not isinstance(doc, dict):
        return None

    name = doc.get("name")
    game = doc.get("game")
    if not name or not game:
        return None

    if isinstance(game, dict):
        keys = [str(k) for k, v in game.items() if _is_positive_weight(v)]
        game_display = " / ".join(keys) if keys else str(game)
    elif isinstance(game, list):
        game_display = " / ".join(str(g) for g in game if g) or str(game)
    else:
        game_display = str(game)

    return str(name), game_display
