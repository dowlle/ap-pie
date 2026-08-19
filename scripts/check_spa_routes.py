"""Fail when a React route would receive a 404 on direct navigation.

Flask serves the SPA shell from a catch-all route, but deliberately marks
unknown paths as 404. React owns the actual client route table, so this check
keeps Flask's allowlist in sync without importing the application or needing
its database/runtime configuration.

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


def flask_route_policy() -> tuple[set[str], tuple[re.Pattern[str], ...]]:
    tree = ast.parse(FLASK_APP.read_text(encoding="utf-8"))
    static_paths: set[str] | None = None
    dynamic_patterns: list[re.Pattern[str]] = []

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = {target.id for target in node.targets if isinstance(target, ast.Name)}
        if "SPA_STATIC_PATHS" in names:
            static_paths = set(ast.literal_eval(node.value))
        elif "SPA_DYNAMIC_PATHS" in names and isinstance(node.value, ast.Tuple):
            for item in node.value.elts:
                if (
                    isinstance(item, ast.Call)
                    and isinstance(item.func, ast.Attribute)
                    and item.func.attr == "compile"
                    and item.args
                ):
                    dynamic_patterns.append(re.compile(ast.literal_eval(item.args[0])))

    if static_paths is None or not dynamic_patterns:
        raise RuntimeError("Could not read Flask SPA route policy")
    return static_paths, tuple(dynamic_patterns)


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


static_paths, dynamic_patterns = flask_route_policy()
client_paths = react_paths()
uncovered = sorted(
    route
    for route in client_paths
    if example_path(route) not in static_paths
    and not any(pattern.fullmatch(example_path(route)) for pattern in dynamic_patterns)
)

if uncovered:
    print("FAIL  React routes missing from Flask's SPA allowlist:")
    for route in uncovered:
        print(f"  - {route}")
    raise SystemExit(1)

print(f"PASS  all {len(client_paths)} React routes receive the SPA shell")
