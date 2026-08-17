"""FEAT-31 self-check: the analytics recorder's privacy and failure contract.

Runs on the standard library plus flask (already a runtime dependency). No
test framework is installed in this project, so this is a plain script:

    python scripts/check_analytics.py

It asserts the properties the /privacy page promises, so a change that
quietly starts storing more than it should fails here rather than in
production:

  1. props are validated against the per-kind allowlist, unknown keys dropped
  2. free text is length-capped and wrong-typed values are discarded
  3. an unknown event kind is refused outright
  4. Sec-GPC / DNT strip user_id and visit_id (Art. 21 objection)
  5. no IP address and no User-Agent string ever reach the storage layer
  6. record_event never raises, even when the database write blows up
"""

from __future__ import annotations

import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ap-web"))

# Stub the storage layer before analytics imports it: the writer thread
# resolves `db` lazily, so this captures rows instead of hitting Postgres.
captured: list[dict] = []
raise_on_write = False


def _insert_event(kind, **kwargs):
    if raise_on_write:
        raise RuntimeError("simulated database failure")
    captured.append({"kind": kind, **kwargs})


db_stub = types.ModuleType("db")
db_stub.insert_event = _insert_event  # type: ignore[attr-defined]
sys.modules["db"] = db_stub

import analytics  # noqa: E402
from flask import Flask  # noqa: E402

app = Flask(__name__)
failures: list[str] = []


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        failures.append(label)


def drain(expected: int, timeout: float = 2.0) -> None:
    """Wait for the async writer to flush."""
    deadline = time.time() + timeout
    while len(captured) < expected and time.time() < deadline:
        time.sleep(0.01)


# ── 1 + 2: props allowlist and coercion ──────────────────────────
props = analytics.sanitize_props(
    "submit_rejected",
    {
        "reason_code": "yaml_syntax",
        "has_session": True,
        "player_name": "Appie",              # not declared -> dropped
        "yaml": "x" * 5000,                  # not declared -> dropped
        "ip": "203.0.113.9",                 # not declared -> dropped
    },
)
check("declared props survive", props.get("reason_code") == "yaml_syntax")
check("undeclared props are dropped", set(props) == {"reason_code", "has_session"})

long_props = analytics.sanitize_props("guide_view", {"slug": "s" * 500})
check("strings are length-capped", len(long_props["slug"]) == 120)

typed = analytics.sanitize_props(
    "submit_attempted", {"has_session": "yes", "content_bytes": "many"}
)
check("wrong-typed values are discarded", typed == {})

fields = analytics.sanitize_props(
    "room_settings_changed", {"fields": ["name", "description", 7, None]}
)
check("list props keep only scalars", fields["fields"] == ["name", "description", "7"])

# ── 3: unknown kinds are refused ─────────────────────────────────
with app.test_request_context("/x"):
    analytics.record_event("definitely_not_a_kind", props={"a": 1})
time.sleep(0.1)
check("unknown kind is not recorded", len(captured) == 0)

# ── 5: nothing sensitive reaches storage ─────────────────────────
with app.test_request_context(
    "/guides/ctr",
    headers={
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
        "CF-Connecting-IP": "203.0.113.9",
        "CF-IPCountry": "NL",
        "X-Forwarded-For": "203.0.113.9",
    },
):
    analytics.record_event("guide_view", user_id=42, props={"slug": "ctr"}, visit_id="abc123")
drain(1)
row = captured[-1] if captured else {}
serialized = repr(row)
check("event was recorded", row.get("kind") == "guide_view")
check("path is stored", row.get("path") == "/guides/ctr")
check("country is stored", row.get("cf_country") == "NL")
check("UA is reduced to a class", row.get("ua_class") == "mobile")
check("no IP anywhere in the row", "203.0.113.9" not in serialized)
check("no User-Agent string in the row", "Mozilla" not in serialized)
check("user_id kept without an objection signal", row.get("user_id") == 42)
check("visit_id kept without an objection signal", row.get("visit_id") == "abc123")

# ── 4: objection signals ─────────────────────────────────────────
for header in ({"Sec-GPC": "1"}, {"DNT": "1"}):
    before = len(captured)
    with app.test_request_context("/apworlds", headers=header):
        analytics.record_event(
            "builder_schema_served",
            user_id=42,
            props={"game": "Crash Team Racing", "version": "0.1.5", "derivable": True},
            visit_id="abc123",
        )
    drain(before + 1)
    r = captured[-1]
    name = list(header)[0]
    check(f"{name}: counter still recorded", r.get("kind") == "builder_schema_served")
    check(f"{name}: user_id stripped", r.get("user_id") is None)
    check(f"{name}: visit_id stripped", r.get("visit_id") is None)
    check(f"{name}: props kept (no personal data in them)", r["props"]["game"] == "Crash Team Racing")

# ── 6: failure posture ───────────────────────────────────────────
raise_on_write = True
try:
    with app.test_request_context("/"):
        analytics.record_event("room_created", user_id=1, room_id="abc")
    time.sleep(0.2)
    check("record_event survives a failing database write", True)
except Exception as e:  # pragma: no cover
    check(f"record_event survives a failing database write ({e})", False)
raise_on_write = False

# The bot classifier feeds the only UA-derived field we keep.
check("bot UA classified", analytics._ua_class("Googlebot/2.1") == "bot")
check("desktop UA classified", analytics._ua_class("Mozilla/5.0 (Windows NT 10.0)") == "desktop")
check("empty UA tolerated", analytics._ua_class("") == "unknown")

# Every client-postable kind must also be a known kind.
check(
    "client kinds are a subset of the taxonomy",
    analytics.CLIENT_KINDS <= set(analytics.KIND_SPECS),
)

# ── 7: every caller actually imports the module ──────────────────
# The recorders are one-liners dropped into existing routes, which makes it
# easy to add a call and forget the import - a NameError that only fires when
# that route is hit. This shipped once (api/apworlds.py, the builder-schema
# and download routes, caught on beta 2026-08-17). No linter is installed in
# this project, so the check lives here.
import ast  # noqa: E402

web_root = Path(__file__).resolve().parent.parent / "ap-web"
missing_imports: list[str] = []
for path in sorted(web_root.rglob("*.py")):
    if path.name == "analytics.py":
        continue
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    # Real attribute access on a name `analytics`, not a mention in a comment
    # or docstring - db.py legitimately talks about the module in prose.
    uses = any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "analytics"
        for node in ast.walk(tree)
    )
    if not uses:
        continue
    imported = any(
        isinstance(node, ast.Import) and any(a.name == "analytics" for a in node.names)
        for node in ast.walk(tree)
    )
    if not imported:
        missing_imports.append(str(path.relative_to(web_root)))

check(
    f"every analytics caller imports the module ({missing_imports or 'all good'})",
    not missing_imports,
)

print()
if failures:
    print(f"{len(failures)} check(s) FAILED:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")
