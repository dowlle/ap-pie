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
    # This is explicitly a disposable-database check. Isolate its exact-count
    # assertions from any analytics written by checks that ran before it.
    cur.execute(
        """TRUNCATE events, events_daily, events_daily_segments,
                    guide_entry_daily, analytics_write_buckets RESTART IDENTITY"""
    )
    cur.execute(
        """INSERT INTO users (discord_id, discord_username, is_admin, is_approved)
           VALUES ('analytics-check-admin', 'Analytics check', TRUE, TRUE)
           ON CONFLICT (discord_id) DO UPDATE
               SET discord_username = EXCLUDED.discord_username,
                   is_admin = TRUE,
                   is_approved = TRUE
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
db.increment_guide_entry_daily("analytics-check-ctr", "search")
db.increment_guide_entry_daily("analytics-check-ctr", "search")
db.increment_guide_entry_daily("analytics-check-getting-started", "internal")

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
guide_entries = {
    (row["guide_slug"], row["entry_channel"]): row["entries"]
    for row in scorecard["guide_entries"]
}
assert guide_entries[("analytics-check-ctr", "search")] == 2, guide_entries
assert guide_entries[("analytics-check-getting-started", "internal")] == 1, guide_entries

with conn.cursor() as cur:
    cur.execute(
        """SELECT column_name
             FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'guide_entry_daily'
         ORDER BY ordinal_position"""
    )
    guide_columns = [row[0] for row in cur.fetchall()]
assert guide_columns == ["day", "guide_slug", "entry_channel", "entry_count"], guide_columns

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
