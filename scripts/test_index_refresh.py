#!/usr/bin/env python3
"""Checks for the OPS-21 index refresh path.

Two things are being protected here:

1. The refresh endpoint's auth. It accepts an admin session (the Refresh
   button) or a bearer token (the merge pipeline). The token must fail
   closed on every malformed or unconfigured case, because it is the only
   part of the app that authenticates something other than a logged-in
   human.

2. That a failed git sync cannot report success. `fetch_index` used to
   discard every git return code, so a broken fetch left the old clone in
   place while the endpoint answered "refreshed" - which is how the live
   index silently went stale after merges.

No database and no network: the "remote" is a local git repo in a temp dir.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

repo_app = os.path.join(os.path.dirname(__file__), "..", "ap-web")
repo_lib = os.path.join(os.path.dirname(__file__), "..", "ap-lib")
sys.path.insert(0, repo_app if os.path.isdir(repo_app) else "/app")
if os.path.isdir(repo_lib):
    sys.path.insert(0, repo_lib)

from flask import Flask

import config
from ap_lib.apworld_index import fetch_index, index_head_sha, parse_index_dir

TOKEN = "o" * 40


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def _make_upstream(root: Path) -> Path:
    up = root / "upstream"
    (up / "index").mkdir(parents=True)
    (up / "index" / "foo.toml").write_text('name = "Foo"\n\n[versions]\n"1.0" = {}\n')
    _git("init", "-q", "-b", "main", cwd=up)
    _git("config", "user.email", "test@example.invalid", cwd=up)
    _git("config", "user.name", "test", cwd=up)
    _git("add", "-A", cwd=up)
    _git("commit", "-qm", "initial", cwd=up)
    return up


class IndexRefresh(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.up = _make_upstream(self.root)
        self.clone = self.root / "clone"
        _git("clone", "-q", "--depth", "1", str(self.up), str(self.clone), cwd=self.root)

        self._saved_token = config.INDEX_REFRESH_TOKEN
        config.INDEX_REFRESH_TOKEN = TOKEN

        import api.apworlds as apworlds

        self.apworlds = apworlds
        # The module caches the parsed index in globals; clear between tests
        # so one test's parse can't satisfy the next test's assertion.
        apworlds._index_cache = None
        apworlds._index_worlds_cache = None
        apworlds._index_lookup_cache = None

        app = Flask(__name__)
        app.secret_key = "test-only"
        app.config.update(
            AP_INDEX_DIR=str(self.clone),
            AP_INDEX_REPO=str(self.up),
            AP_WORLDS_DIR=str(self.root / "worlds"),
        )
        app.register_blueprint(apworlds.bp)
        self.client = app.test_client()

    def tearDown(self) -> None:
        config.INDEX_REFRESH_TOKEN = self._saved_token
        self._temp_dir.cleanup()

    def _post(self, token: str | None = None, header: str | None = None):
        headers = {}
        if header is not None:
            headers["Authorization"] = header
        elif token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.post("/api/apworlds/refresh", headers=headers)

    # -- auth ---------------------------------------------------------

    def test_anonymous_is_refused(self) -> None:
        self.assertEqual(self._post().status_code, 401)

    def test_token_auth_fails_closed(self) -> None:
        """Every malformed or unconfigured case must fall back to the
        session check (401 here), never authenticate."""
        cases = {
            "wrong value": {"token": "x" * 40},
            "no scheme": {"header": TOKEN},
            "wrong scheme": {"header": f"Basic {TOKEN}"},
            "empty bearer": {"header": "Bearer "},
            "bearer, no value": {"header": "Bearer"},
        }
        for name, kwargs in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self._post(**kwargs).status_code, 401)

    def test_unset_token_disables_machine_auth(self) -> None:
        config.INDEX_REFRESH_TOKEN = ""
        self.assertEqual(self._post(TOKEN).status_code, 401)

    def test_short_token_is_refused_even_when_it_matches(self) -> None:
        """A placeholder must not become a live credential."""
        config.INDEX_REFRESH_TOKEN = "too-short"
        self.assertEqual(self._post("too-short").status_code, 401)

    def test_valid_token_refreshes(self) -> None:
        res = self._post(TOKEN)
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["commit"], _git("rev-parse", "HEAD", cwd=self.up))
        self.assertEqual(body["count"], 1)
        self.assertFalse(body["changed"], "re-syncing the same commit is a no-op")

    def test_non_admin_session_is_refused(self) -> None:
        config.INDEX_REFRESH_TOKEN = ""
        import db

        saved, db.get_user = db.get_user, lambda uid: {"id": uid, "is_admin": False}
        try:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 7
            self.assertEqual(self._post().status_code, 403)
        finally:
            db.get_user = saved

    def test_admin_session_still_works_without_a_token(self) -> None:
        """The Refresh button must keep working on deploys that never set
        the token."""
        config.INDEX_REFRESH_TOKEN = ""
        import db

        saved, db.get_user = db.get_user, lambda uid: {"id": uid, "is_admin": True}
        try:
            with self.client.session_transaction() as sess:
                sess["user_id"] = 1
            self.assertEqual(self._post().status_code, 200)
        finally:
            db.get_user = saved

    # -- actually refreshing ------------------------------------------

    def test_new_upstream_commit_is_picked_up(self) -> None:
        (self.up / "index" / "bar.toml").write_text(
            'name = "Bar"\n\n[versions]\n"2.0" = {}\n'
        )
        _git("add", "-A", cwd=self.up)
        _git("commit", "-qm", "add bar", cwd=self.up)

        body = self._post(TOKEN).get_json()
        self.assertEqual(body["commit"], _git("rev-parse", "HEAD", cwd=self.up))
        self.assertTrue(body["changed"])
        self.assertEqual(body["count"], 2, "the new world should be visible")

    def test_failed_sync_does_not_report_success(self) -> None:
        """The regression that kept the live index silently stale."""
        _git("remote", "set-url", "origin", str(self.root / "gone"), cwd=self.clone)
        before = index_head_sha(self.clone)

        with self.assertRaises(RuntimeError):
            fetch_index(self.clone, str(self.root / "gone"))

        self.client.application.config["AP_INDEX_REPO"] = str(self.root / "gone")
        self.assertEqual(self._post(TOKEN).status_code, 500)
        self.assertEqual(
            index_head_sha(self.clone), before, "a failed sync must not move the clone"
        )

    def test_partial_destination_is_recovered(self) -> None:
        broken = self.root / "partial-clone"
        broken.mkdir()
        (broken / "leftover").write_text("partial")

        fetch_index(broken, str(self.up), validate=lambda p: parse_index_dir(p, strict=True))

        self.assertEqual(index_head_sha(broken), index_head_sha(self.up))
        self.assertFalse((broken / "leftover").exists())

    def test_changed_repo_url_retargets_existing_clone(self) -> None:
        replacement = _make_upstream(self.root / "replacement-root")
        (replacement / "index" / "bar.toml").write_text(
            'name = "Bar"\n\n[versions]\n"2.0" = {}\n'
        )
        _git("add", "-A", cwd=replacement)
        _git("commit", "-qm", "replacement", cwd=replacement)

        fetch_index(self.clone, str(replacement))

        self.assertEqual(index_head_sha(self.clone), index_head_sha(replacement))

    def test_invalid_candidate_does_not_replace_live_clone(self) -> None:
        before = index_head_sha(self.clone)
        (self.up / "index" / "broken.toml").write_text("not = [valid")
        _git("add", "-A", cwd=self.up)
        _git("commit", "-qm", "broken index", cwd=self.up)

        res = self._post(TOKEN)

        self.assertEqual(res.status_code, 500)
        self.assertEqual(index_head_sha(self.clone), before)
        self.assertEqual(len(parse_index_dir(self.clone, strict=True)), 1)

    def test_concurrent_refresh_is_refused(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        original = self.apworlds.fetch_index

        def slow_fetch(*args, **kwargs):
            entered.set()
            release.wait(timeout=5)
            return original(*args, **kwargs)

        self.apworlds.fetch_index = slow_fetch
        first_result = []
        try:
            worker = threading.Thread(target=lambda: first_result.append(self._post(TOKEN)))
            worker.start()
            self.assertTrue(entered.wait(timeout=2))
            self.assertEqual(self._post(TOKEN).status_code, 409)
            release.set()
            worker.join(timeout=5)
            self.assertEqual(first_result[0].status_code, 200)
        finally:
            release.set()
            self.apworlds.fetch_index = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
