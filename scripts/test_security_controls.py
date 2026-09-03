#!/usr/bin/env python3
"""Focused integration checks for the 2026-08-19 security wave.

Run inside the application image with DATABASE_URL pointing at a disposable
PostgreSQL database. No production data is read or changed.
"""

from __future__ import annotations

import os
import sys
import unittest

import psycopg2
import psycopg2.extras
from flask import Flask

repo_app = os.path.join(os.path.dirname(__file__), "..", "ap-web")
sys.path.insert(0, repo_app if os.path.isdir(repo_app) else "/app")

import config
import db
from api.presets import _count_use, _option_values_too_large as preset_values_too_large
from api.user_yamls import _option_values_too_large as yaml_values_too_large
from request_ip import client_ip


class SecurityControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db.init_db(os.environ["DATABASE_URL"])

    def test_option_value_caps(self) -> None:
        self.assertFalse(yaml_values_too_large({"choice": "x"}))
        self.assertFalse(preset_values_too_large({"choice": "x"}))
        oversized = {"choice": "x" * 65_536}
        self.assertTrue(yaml_values_too_large(oversized))
        self.assertTrue(preset_values_too_large(oversized))

    def test_client_ip_fails_closed(self) -> None:
        app = Flask(__name__)
        headers = {
            "CF-Connecting-IP": "203.0.113.9",
            "X-AP-Origin-Verified": "cloudflare",
        }
        original = config.TRUST_CLOUDFLARE_HEADERS
        try:
            config.TRUST_CLOUDFLARE_HEADERS = False
            with app.test_request_context("/", headers=headers, environ_base={"REMOTE_ADDR": "127.0.0.1"}):
                self.assertEqual(client_ip(), "127.0.0.1")
            config.TRUST_CLOUDFLARE_HEADERS = True
            with app.test_request_context("/", headers=headers, environ_base={"REMOTE_ADDR": "127.0.0.1"}):
                self.assertEqual(client_ip(), "203.0.113.9")
            headers["CF-Connecting-IP"] = "not-an-ip"
            with app.test_request_context("/", headers=headers, environ_base={"REMOTE_ADDR": "127.0.0.1"}):
                self.assertEqual(client_ip(), "127.0.0.1")
        finally:
            config.TRUST_CLOUDFLARE_HEADERS = original

    def test_preset_use_is_deduplicated(self) -> None:
        self.assertTrue(_count_use("198.51.100.8", 12345))
        self.assertFalse(_count_use("198.51.100.8", 12345))
        self.assertTrue(_count_use("198.51.100.9", 12345))

    def test_report_dedupe_and_storage_constraint(self) -> None:
        conn = db._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (discord_id, discord_username) VALUES (%s, %s) RETURNING id",
                ("security-test-user", "security-test-user"),
            )
            user_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO apworld_presets
                       (apworld_name, version, name, kind, option_values, author_user_id)
                   VALUES ('test', '1', 'test', 'simple', '{}'::jsonb, %s)
                   RETURNING id""",
                (user_id,),
            )
            preset_id = cur.fetchone()[0]
        conn.commit()

        self.assertTrue(db.report_preset(preset_id, user_id))
        self.assertFalse(db.report_preset(preset_id, user_id))
        with conn.cursor() as cur:
            cur.execute("SELECT reports FROM apworld_presets WHERE id = %s", (preset_id,))
            self.assertEqual(cur.fetchone()[0], 1)

        with self.assertRaises(psycopg2.errors.CheckViolation):
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO user_yamls
                           (user_id, apworld_name, version, player_name, kind, option_values)
                       VALUES (%s, 'test', '1', 'slot', 'simple', %s)""",
                    (user_id, psycopg2.extras.Json({"x": "y" * 65_536})),
                )
        conn.rollback()

    def test_global_analytics_ceiling(self) -> None:
        original = config.ANALYTICS_EVENTS_GLOBAL_PER_MINUTE
        conn = db._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM analytics_write_buckets WHERE minute = date_trunc('minute', NOW())"
            )
            cur.execute("SELECT COUNT(*) FROM events")
            events_before = int(cur.fetchone()[0])
            cur.execute("SELECT COALESCE(SUM(entry_count), 0) FROM guide_entry_daily")
            entries_before = int(cur.fetchone()[0])
        conn.commit()

        config.ANALYTICS_EVENTS_GLOBAL_PER_MINUTE = 2
        try:
            db.insert_event("page_view", props={})
            db.increment_guide_entry_daily("security-check", "search")
            db.insert_event("page_view", props={})
        finally:
            config.ANALYTICS_EVENTS_GLOBAL_PER_MINUTE = original

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM events")
            events_after = int(cur.fetchone()[0])
            cur.execute("SELECT COALESCE(SUM(entry_count), 0) FROM guide_entry_daily")
            entries_after = int(cur.fetchone()[0])
        self.assertEqual((events_after - events_before) + (entries_after - entries_before), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
