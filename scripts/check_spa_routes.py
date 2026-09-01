"""Fail when a React route would receive a 404 on direct navigation.

Flask serves the SPA shell from a catch-all route, but deliberately marks
unknown paths as 404. React owns the actual client route table, so this check
keeps Flask's allowlist in sync without importing the application or needing
its database/runtime configuration.

Some routes are served on beta and withheld from production on purpose, which
is what SPA_BETA_DYNAMIC_PATHS records. Those count as covered here, and are
listed separately in the output so the gate stays visible rather than reading
as an accidental gap.

Run from the repository root:

    python scripts/check_spa_routes.py
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FLASK_APP = ROOT / "ap-web" / "app.py"
REACT_APP = ROOT / "ap-web" / "frontend" / "src" / "App.tsx"


def _compiled_patterns(value: ast.expr) -> list[re.Pattern[str]]:
    if not isinstance(value, ast.Tuple):
        return []
    patterns = []
    for item in value.elts:
        if (
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
            and item.func.attr == "compile"
            and item.args
        ):
            patterns.append(re.compile(ast.literal_eval(item.args[0])))
    return patterns


def flask_route_policy() -> tuple[
    set[str], tuple[re.Pattern[str], ...], tuple[re.Pattern[str], ...]
]:
    tree = ast.parse(FLASK_APP.read_text(encoding="utf-8"))
    static_paths: set[str] | None = None
    dynamic_patterns: list[re.Pattern[str]] = []
    beta_patterns: list[re.Pattern[str]] = []

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = {target.id for target in node.targets if isinstance(target, ast.Name)}
        if "SPA_STATIC_PATHS" in names:
            static_paths = set(ast.literal_eval(node.value))
        elif "SPA_DYNAMIC_PATHS" in names:
            dynamic_patterns = _compiled_patterns(node.value)
        elif "SPA_BETA_DYNAMIC_PATHS" in names:
            beta_patterns = _compiled_patterns(node.value)

    if static_paths is None or not dynamic_patterns:
        raise RuntimeError("Could not read Flask SPA route policy")
    return static_paths, tuple(dynamic_patterns), tuple(beta_patterns)


def react_paths() -> set[str]:
    source = REACT_APP.read_text(encoding="utf-8")
    return {
        path
        for path in re.findall(r'<Route\b[^>]*\bpath="([^"]+)"', source)
        if path != "*"
    }


def example_path(route: str) -> str:
    """Turn `/rooms/:id` into a concrete path Flask must accept."""
    return re.sub(r":[^/]+", "route-value", route).strip("/")


static_paths, dynamic_patterns, beta_patterns = flask_route_policy()
client_paths = react_paths()

uncovered = []
beta_only = []
for route in sorted(client_paths):
    example = example_path(route)
    if example in static_paths or any(p.fullmatch(example) for p in dynamic_patterns):
        continue
    if any(p.fullmatch(example) for p in beta_patterns):
        beta_only.append(route)
    else:
        uncovered.append(route)

if uncovered:
    print("FAIL  React routes missing from Flask's SPA allowlist:")
    for route in uncovered:
        print(f"  - {route}")
    raise SystemExit(1)

everywhere = len(client_paths) - len(beta_only)
print(f"PASS  {everywhere} React routes receive the SPA shell in every environment")
for route in beta_only:
    print(f"      {route} is served on beta only, by SPA_BETA_DYNAMIC_PATHS")
