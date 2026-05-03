"""Parse Archipelago YAML template files into structured option definitions."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


def list_templates(templates_dir: str | Path) -> list[dict]:
    """List available game template files."""
    templates_dir = Path(templates_dir)
    if not templates_dir.is_dir():
        return []
    results = []
    for f in sorted(templates_dir.iterdir()):
        if f.suffix in (".yaml", ".yml") and f.is_file():
            game = f.stem
            results.append({"game": game, "filename": f.name})
    return results


def parse_template(filepath: str | Path) -> dict:
    """Parse an AP YAML template file into structured JSON."""
    filepath = Path(filepath)
    text = filepath.read_text(encoding="utf-8-sig")  # handles BOM

    # Parse preamble with yaml.safe_load for the header fields
    preamble = yaml.safe_load(text)
    game = preamble.get("game", filepath.stem)
    requires = preamble.get("requires", {})
    ap_version = str(requires.get("version", ""))
    game_versions = requires.get("game", {})
    world_version = str(game_versions.get(game, ""))

    # Find the game section and parse options line-by-line
    options = _parse_game_section(text, game)

    # Collect unique categories in order
    seen_cats = []
    for opt in options:
        if opt["category"] not in seen_cats:
            seen_cats.append(opt["category"])

    return {
        "game": game,
        "ap_version": ap_version,
        "world_version": world_version,
        "categories": seen_cats,
        "options": options,
    }


def _parse_game_section(text: str, game: str) -> list[dict]:
    """Parse the game-specific section of a template into option dicts."""
    lines = text.split("\n")

    # Find the game section start
    game_line_re = re.compile(rf"^{re.escape(game)}:\s*$")
    start_idx = None
    for i, line in enumerate(lines):
        if game_line_re.match(line):
            start_idx = i + 1
            break
    if start_idx is None:
        # Try yaml-quoted variant
        for i, line in enumerate(lines):
            if line.strip().startswith(("'", '"')) and line.strip().endswith(":"):
                unquoted = line.strip()[1:-2]
                if unquoted == game:
                    start_idx = i + 1
                    break
    if start_idx is None:
        return []

    options = []
    current_category = "Game Options"
    current_option_name = None
    current_description_lines: list[str] = []
    current_values: list[tuple[str, int, str]] = []  # (key, weight, inline_comment)
    current_raw_value = None  # for list/dict defaults

    def _flush_option():
        nonlocal current_option_name, current_description_lines, current_values, current_raw_value
        if current_option_name is None:
            return
        desc = "\n".join(current_description_lines).strip()
        opt = _classify_option(
            current_option_name, desc, current_values, current_raw_value, current_category,
        )
        if opt:
            options.append(opt)
        current_option_name = None
        current_description_lines = []
        current_values = []
        current_raw_value = None

    category_border_re = re.compile(r"^\s+#{3,}\s*$")
    category_name_re = re.compile(r"^\s+#\s+(.+?)\s+#\s*$")
    option_start_re = re.compile(r"^  (\w[\w_]*):$")
    comment_re = re.compile(r"^\s+#\s?(.*)")
    value_re = re.compile(r"^    (.+?):\s+(\d+)\s*(#.*)?$")
    list_re = re.compile(r"^    (\[.*\])\s*$")
    dict_re = re.compile(r"^    (\{.*\})\s*$")

    i = start_idx
    pending_category = None

    while i < len(lines):
        line = lines[i]

        # End of game section - another top-level key or end of file
        if line and not line[0].isspace() and line[0] != "#":
            break

        # Category border detection
        if category_border_re.match(line):
            # Check next line for category name
            if i + 1 < len(lines):
                m = category_name_re.match(lines[i + 1])
                if m:
                    _flush_option()
                    pending_category = m.group(1)
                    i += 3  # skip border, name, border
                    continue
            i += 1
            continue

        # Option start
        m = option_start_re.match(line)
        if m:
            _flush_option()
            if pending_category:
                current_category = pending_category
                pending_category = None
            current_option_name = m.group(1)
            current_description_lines = []
            current_values = []
            current_raw_value = None
            i += 1
            continue

        # Inside an option block
        if current_option_name is not None:
            # Comment/description line
            m = comment_re.match(line)
            if m:
                current_description_lines.append(m.group(1))
                i += 1
                continue

            # Value entry (key: weight)
            m = value_re.match(line)
            if m:
                key = m.group(1).strip().strip("'\"")
                weight = int(m.group(2))
                comment = m.group(3).strip() if m.group(3) else ""
                current_values.append((key, weight, comment))
                i += 1
                continue

            # List default
            m = list_re.match(line)
            if m:
                try:
                    current_raw_value = yaml.safe_load(m.group(1))
                except Exception:
                    current_raw_value = []
                i += 1
                continue

            # Dict default
            m = dict_re.match(line)
            if m:
                try:
                    current_raw_value = yaml.safe_load(m.group(1))
                except Exception:
                    current_raw_value = {}
                i += 1
                continue

        i += 1

    _flush_option()
    return options


_RANDOM_RE = re.compile(r"^random(-low|-high|-range-.+)?$")


def _classify_option(
    name: str,
    description: str,
    values: list[tuple[str, int, str]],
    raw_value,
    category: str,
) -> dict | None:
    """Determine option type and build structured representation."""

    # List type
    if raw_value is not None and isinstance(raw_value, list):
        return {
            "name": name,
            "type": "list",
            "description": _clean_description(description),
            "category": category,
            "default": raw_value,
        }

    # Dict type
    if raw_value is not None and isinstance(raw_value, dict):
        return {
            "name": name,
            "type": "dict",
            "description": _clean_description(description),
            "category": category,
            "default": raw_value,
        }

    if not values:
        return None

    # Check for Range type via description
    min_match = re.search(r"Minimum value is (-?\d+)", description)
    max_match = re.search(r"Maximum value is (-?\d+)", description)
    if min_match and max_match:
        return _build_range(name, description, values, category,
                            int(min_match.group(1)), int(max_match.group(1)))

    # Check for Toggle type
    value_keys = {v[0] for v in values}
    if value_keys == {"false", "true"}:
        default = False
        for key, weight, _ in values:
            if key == "true" and weight > 0:
                default = True
                break
            if key == "false" and weight > 0:
                default = False
                break
        return {
            "name": name,
            "type": "toggle",
            "description": _clean_description(description),
            "category": category,
            "default": default,
        }

    # Choice type (filter out random entries just in case)
    non_random = [(k, w, c) for k, w, c in values if not _RANDOM_RE.match(k)]
    if not non_random:
        non_random = values

    choices = [k for k, w, c in non_random]
    default = choices[0] if choices else ""
    for k, w, c in non_random:
        if w > 0:
            default = k
            break

    return {
        "name": name,
        "type": "choice",
        "description": _clean_description(description),
        "category": category,
        "default": default,
        "choices": choices,
    }


def _build_range(
    name: str,
    description: str,
    values: list[tuple[str, int, str]],
    category: str,
    range_min: int,
    range_max: int,
) -> dict:
    """Build a range option dict with named aliases."""
    named_values = {}
    default = range_min

    for key, weight, comment in values:
        # Skip random entries
        if _RANDOM_RE.match(key):
            continue

        # Check for "equivalent to N" in comment
        equiv_match = re.search(r"equivalent to (-?\d+)", comment)
        if equiv_match:
            num = int(equiv_match.group(1))
            named_values[key] = num
            if weight > 0:
                default = num
        else:
            # Could be a plain numeric default
            try:
                num = int(key)
                if weight > 0:
                    default = num
            except ValueError:
                # Unknown named value
                named_values[key] = 0
                if weight > 0:
                    default = 0

    return {
        "name": name,
        "type": "range",
        "description": _clean_description(description),
        "category": category,
        "default": default,
        "min": range_min,
        "max": range_max,
        "named_values": named_values if named_values else None,
    }


def _clean_description(desc: str) -> str:
    """Clean up description text from template comments."""
    # Remove the "You can define additional values..." boilerplate
    lines = desc.split("\n")
    cleaned = []
    for line in lines:
        if line.strip().startswith("You can define additional values"):
            continue
        if line.strip().startswith("Minimum value is"):
            continue
        if line.strip().startswith("Maximum value is"):
            continue
        cleaned.append(line)

    # Strip trailing empty lines
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()

    return "\n".join(cleaned).strip()
