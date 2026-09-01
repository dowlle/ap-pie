"""Integration check for analytics traffic classes, scorecard, and retention.

Run against a disposable PostgreSQL database only:

    DATABASE_URL=postgresql://... python scripts/check_analytics_scorecard.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ap-web"))

import db  # noqa: E402


database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise SystemExit("DATABASE_URL is required and must point at a disposable database")

db.init_db(database_url)
conn = db._get_conn()
with conn.cursor() as cur:
    cur.execute(
        """INSERT INTO users (discord_id, discord_username, is_admin, is_approved)
           VALUES ('analytics-check-admin', 'Analytics check', TRUE, TRUE)
           RETURNING id"""
    )
    admin_id = int(cur.fetchone()[0])
conn.commit()

attempt_external = "1111111111111111"
attempt_internal = "2222222222222222"
db.insert_event("page_view", ua_class="desktop", visit_id="external-visit", props={"view": "yaml_builder"})
db.insert_event(
    "builder_opened", ua_class="desktop", visit_id="external-visit",
    props={"game": "Check Game", "version": "1", "attempt_id": attempt_external},
)
db.insert_event(
    "builder_yaml_emitted", ua_class="desktop", visit_id="external-visit",
    props={"game": "Check Game", "version": "1", "attempt_id": attempt_external},
)
db.insert_event(
    "builder_opened", user_id=admin_id, ua_class="desktop", visit_id="internal-visit",
    props={"game": "Check Game", "version": "1", "attempt_id": attempt_internal},
)
db.insert_event("page_view", ua_class="bot", props={"view": "yaml_builder"})
db.insert_event("page_view", ua_class="synthetic", props={"view": "yaml_builder"})

by_kind = {row["kind"]: row for row in db.events_counts_by_kind(1)}
page_views = by_kind["page_view"]
assert page_views["external_count"] == 1, page_views
assert page_views["internal_count"] == 0, page_views
assert page_views["bot_count"] == 1, page_views
assert page_views["synthetic_count"] == 1, page_views
builder_opens = by_kind["builder_opened"]
assert builder_opens["external_count"] == 1, builder_opens
assert builder_opens["internal_count"] == 1, builder_opens

scorecard = db.events_scorecard(1)
device = next(row for row in scorecard["devices"] if row["device"] == "desktop")
assert device["page_views"] == 1, device
assert device["attempts"] == 1, device
assert device["outputs"] == 1, device
game = scorecard["builder_games"][0]
assert game["game"] == "Check Game" and game["attempts"] == 1 and game["outputs"] == 1, game

with conn.cursor() as cur:
    cur.execute(
        """UPDATE events SET ts = NOW() - INTERVAL '31 days'
            WHERE props->>'attempt_id' = %s""",
        (attempt_external,),
    )
conn.commit()
result = db.rollup_and_prune_events(180)
assert result["attempt_rows_pruned"] == 2, result
with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM events_daily_segments")
    segment_rows = int(cur.fetchone()[0])
assert segment_rows >= 4, segment_rows

print("all analytics scorecard integration checks passed")
