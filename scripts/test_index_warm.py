#!/usr/bin/env python3
"""The game list is warm before an upload needs it, and nothing on the request path waits for a parse.

MW-12 found the first YAML upload after a restart taking minutes: `auto_pin_for_room_game` loaded the
index while holding the lock every other reader needed. No database and no network: the index is a
small local directory and the parse is slowed down on purpose.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

repo_app = os.path.join(os.path.dirname(__file__), "..", "ap-web")
repo_lib = os.path.join(os.path.dirname(__file__), "..", "ap-lib")
sys.path.insert(0, repo_app if os.path.isdir(repo_app) else "/app")
if os.path.isdir(repo_lib):
    sys.path.insert(0, repo_lib)

from flask import Flask

import api.apworlds as apworlds

DELAY = 1.0


class IndexWarm(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        root = Path(self._temp.name)
        (root / "index" / "index").mkdir(parents=True)
        (root / "index" / "index" / "foo.toml").write_text(
            'name = "Foo"\ndisplay_name = "Foo Game"\n\n[versions]\n"1.0" = {}\n')
        self.app = Flask(__name__)
        self.app.config.update(AP_INDEX_DIR=str(root / "index"), AP_WORLDS_DIR=str(root / "worlds"))
        self._reset()
        real = apworlds._build_index_snapshot

        def slow():
            time.sleep(DELAY)
            return real()

        self.slow = mock.patch.object(apworlds, "_build_index_snapshot", slow)
        self.slow.start()

    def tearDown(self) -> None:
        self.slow.stop()
        self._reset()
        self._temp.cleanup()

    def _reset(self) -> None:
        apworlds._index_cache = apworlds._index_worlds_cache = apworlds._index_lookup_cache = None

    def test_warm_loads_in_the_background_and_readers_then_do_not_wait(self) -> None:
        started = time.monotonic()
        thread = apworlds.warm_index(self.app)
        self.assertLess(time.monotonic() - started, DELAY / 2, "warm_index must return at once")
        self.assertFalse(apworlds.index_loaded())
        thread.join(10)
        self.assertTrue(apworlds.index_loaded())
        with self.app.app_context():
            started = time.monotonic()
            self.assertIn("Foo", apworlds._get_game_lookup())
            self.assertEqual(len(apworlds._get_index_worlds()), 1)
            self.assertLess(time.monotonic() - started, 0.2)

    def test_upload_pin_does_not_wait_for_a_cold_index_and_still_pins(self) -> None:
        pinned: list[tuple] = []
        db = mock.MagicMock()
        db.get_room.return_value = {}
        db.get_room_apworlds.return_value = []
        db.set_room_apworld.side_effect = lambda *a: pinned.append(a)
        with mock.patch.dict(sys.modules, {"db": db}), self.app.app_context():
            started = time.monotonic()
            apworlds.auto_pin_for_room_game("room1", "Foo")
            self.assertLess(time.monotonic() - started, DELAY / 2, "the upload path must not wait for the parse")
            self.assertEqual(pinned, [])
            deadline = time.monotonic() + 10
            while not pinned and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertEqual(pinned, [("room1", "foo", "1.0")])
            started = time.monotonic()
            apworlds.auto_pin_for_room_game("room1", "Foo")  # warm now: synchronous and instant
            self.assertLess(time.monotonic() - started, 0.5)

    def test_a_rebuild_does_not_block_readers_of_the_old_snapshot(self) -> None:
        with self.app.app_context():
            apworlds._load_index_into_cache()
            first = apworlds._get_game_lookup()
            def rebuild_in_thread() -> None:
                with self.app.app_context():
                    apworlds._load_index_into_cache()

            rebuild = threading.Thread(target=rebuild_in_thread)
            started = time.monotonic()
            rebuild.start()
            time.sleep(0.2)  # the rebuild is mid-parse
            self.assertIs(apworlds._get_game_lookup(), first)
            self.assertLess(time.monotonic() - started, DELAY, "readers must not wait for the rebuild")
            rebuild.join(10)
            self.assertIsNot(apworlds._get_game_lookup(), first)

    def test_concurrent_cold_readers_share_one_parse(self) -> None:
        calls = []
        real = apworlds._build_index_snapshot

        def counting():
            calls.append(1)
            return real()

        with mock.patch.object(apworlds, "_build_index_snapshot", counting), self.app.app_context():
            def load() -> None:
                with self.app.app_context():
                    apworlds._ensure_index_loaded()

            threads = [threading.Thread(target=load) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
