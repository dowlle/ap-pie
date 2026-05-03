"""Parse option definitions from .apworld files to generate template data."""

from __future__ import annotations

import ast
import re
import zipfile
from pathlib import Path


def parse_apworld_options(apworld_path: Path) -> dict | None:
    """Parse an .apworld zip and extract game options as template-compatible data.

    Returns a dict matching the format of template_parser.parse_template(),
    or None if the apworld cannot be parsed.
    """
    try:
        zf = zipfile.ZipFile(apworld_path)
    except (zipfile.BadZipFile, OSError):
        return None

    stem = apworld_path.stem  # e.g. "timberborn"

    # Find __init__.py to get the game name
    game_name = _extract_game_name(zf, stem)
    if not game_name:
        return None

    # Find Options.py
    options_src = _find_options_source(zf, stem)
    if not options_src:
        return None

    # Parse option classes
    options = _parse_options_source(options_src)
    if not options:
        return None

    categories = []
    for opt in options:
        if opt["category"] not in categories:
            categories.append(opt["category"])

    return {
        "game": game_name,
        "ap_version": "",
        "world_version": "",
        "categories": categories,
        "options": options,
    }


def _extract_game_name(zf: zipfile.ZipFile, stem: str) -> str | None:
    """Extract the game name from the world's __init__.py."""
    init_candidates = [f"{stem}/__init__.py", f"{stem.lower()}/__init__.py"]
    for candidate in init_candidates:
        if candidate in zf.namelist():
            try:
                src = zf.read(candidate).decode("utf-8", errors="replace")
                # Look for: game = "Name" or game: str = "Name"
                m = re.search(r'^\s+game\s*(?::\s*str\s*)?=\s*["\'](.+?)["\']', src, re.MULTILINE)
                if m:
                    return m.group(1)
            except Exception:
                pass
    return None


def _find_options_source(zf: zipfile.ZipFile, stem: str) -> str | None:
    """Find and read the Options.py file from the apworld."""
    # Common patterns: stem/Options.py, stem/options.py, stem/StemOptions.py
    for name in zf.namelist():
        lower = name.lower()
        if lower.startswith(stem.lower() + "/") and lower.endswith("options.py"):
            try:
                return zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                pass
    return None


def _parse_options_source(src: str) -> list[dict]:
    """Parse option class definitions from Python source code using AST."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    # Map of AP option base classes to our types
    ap_type_map = {
        "Choice": "choice",
        "Range": "range",
        "Toggle": "toggle",
        "OptionSet": "list",
        "TextChoice": "choice",
        "DefaultOnToggle": "toggle",
    }

    options = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Determine the AP option type from base classes
        opt_type = None
        for base in node.bases:
            base_name = _get_name(base)
            if base_name in ap_type_map:
                opt_type = ap_type_map[base_name]
                break
        if opt_type is None:
            continue

        # Skip the aggregate dataclass (e.g. TimberbornOptions)
        if any(_get_name(b) in ("PerGameCommonOptions", "CommonOptions") for b in node.bases):
            continue

        # Extract info from class body
        display_name = None
        description = ast.get_docstring(node) or ""
        default = None
        option_values = {}  # option_xxx = N
        range_start = None
        range_end = None
        valid_keys = None

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    name = _get_name(target)
                    if name is None:
                        continue
                    value = _get_literal(item.value)

                    if name == "display_name":
                        display_name = value
                    elif name == "default":
                        default = value
                    elif name == "range_start":
                        range_start = value
                    elif name == "range_end":
                        range_end = value
                    elif name == "valid_keys":
                        valid_keys = value
                    elif name.startswith("option_"):
                        option_values[name[7:]] = value

        opt_name = _camel_to_snake(node.name)
        clean_desc = description.strip()

        if opt_type == "choice" and option_values:
            # Sort choices by their numeric value
            sorted_choices = sorted(option_values.items(), key=lambda x: x[1] if isinstance(x[1], int) else 0)
            choices = [k for k, v in sorted_choices]
            default_val = choices[0]
            if isinstance(default, int):
                for k, v in sorted_choices:
                    if v == default:
                        default_val = k
                        break
            options.append({
                "name": opt_name,
                "type": "choice",
                "description": clean_desc,
                "category": "Game Options",
                "default": default_val,
                "choices": choices,
            })

        elif opt_type == "range" and range_start is not None and range_end is not None:
            options.append({
                "name": opt_name,
                "type": "range",
                "description": clean_desc,
                "category": "Game Options",
                "default": default if isinstance(default, int) else range_start,
                "min": range_start,
                "max": range_end,
                "named_values": None,
            })

        elif opt_type == "toggle":
            default_bool = bool(default) if default is not None else False
            options.append({
                "name": opt_name,
                "type": "toggle",
                "description": clean_desc,
                "category": "Game Options",
                "default": default_bool,
            })

        elif opt_type == "list" and valid_keys is not None:
            default_list = list(default) if isinstance(default, (set, list)) else []
            options.append({
                "name": opt_name,
                "type": "list",
                "description": clean_desc,
                "category": "Game Options",
                "default": default_list,
                "choices": sorted(valid_keys) if isinstance(valid_keys, set) else list(valid_keys),
            })

    return options


def _get_name(node: ast.AST) -> str | None:
    """Get a simple name from an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _get_literal(node: ast.AST):
    """Safely evaluate a constant/literal AST node."""
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()
