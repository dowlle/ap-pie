"""Stale catalog requests serve a snapshot while one background build runs."""
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ap-web"), str(ROOT / "ap-lib")]

from flask import Flask
import api.apworlds as api


class IndexRefreshTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        extra = tuple(name for name in ("_discovery_stamp", "_schema_stamp") if hasattr(api, name))
        self.extra = tuple(None for _ in extra)
        self.previous = (api._index_cache, api._index_worlds_cache,
                         api._index_lookup_cache, api._review_stamp, api._fuzz_stamp,
                         *(getattr(api, name) for name in extra))
        self.old = [{"name": "old"}]
        self.fresh = [{"name": "fresh"}]
        api._install_index_snapshot((self.old, [], {}, "old", "old", *self.extra))

    def tearDown(self):
        api._install_index_snapshot(self.previous)

    def test_stale_readers_return_during_one_blocked_rebuild(self):
        entered, release, installed = threading.Event(), threading.Event(), threading.Event()
        real_install = api._install_index_snapshot

        def build():
            entered.set()
            self.assertTrue(release.wait(5))
            return self.fresh, [], {}, "fresh", "fresh", *self.extra

        def install(snapshot):
            real_install(snapshot)
            installed.set()

        with patch.object(api, "_index_is_stale", side_effect=lambda: api._review_stamp != "fresh"), \
                patch.object(api, "_build_index_snapshot", side_effect=build) as rebuild, \
                patch.object(api, "_install_index_snapshot", side_effect=install):
            try:
                with self.app.app_context():
                    self.assertIs(api._get_index(), self.old)
                    self.assertTrue(entered.wait(2))
                    for _ in range(20):
                        self.assertIs(api._get_index(), self.old)
                    self.assertEqual(rebuild.call_count, 1)
            finally:
                release.set()
            self.assertTrue(installed.wait(5))
            # Wait for the worker's finally block before leaving the test.
            with api._index_build_lock:
                pass
            with self.app.app_context():
                self.assertIs(api._get_index(), self.fresh)
                self.assertEqual(rebuild.call_count, 1)

    def test_failed_refresh_retains_snapshot_and_releases_lock(self):
        with patch.object(api, "_index_is_stale", return_value=True), \
                patch.object(api, "_build_index_snapshot", side_effect=ValueError("bad data")):
            thread = api._refresh_index_in_background(self.app)
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertIs(api._index_cache, self.old)
            self.assertTrue(api._index_build_lock.acquire(blocking=False))
            api._index_build_lock.release()

    def test_current_snapshot_does_not_schedule_refresh(self):
        with patch.object(api, "_index_is_stale", return_value=False), \
                patch.object(api, "_refresh_index_in_background") as refresh, self.app.app_context():
            self.assertIs(api._get_index(), self.old)
            refresh.assert_not_called()

    def test_no_longer_stale_does_not_rebuild(self):
        with patch.object(api, "_index_is_stale", return_value=False), \
                patch.object(api, "_build_index_snapshot") as build:
            thread = api._refresh_index_in_background(self.app)
            thread.join(5)
            build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
