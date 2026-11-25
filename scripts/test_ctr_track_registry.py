#!/usr/bin/env python3
"""Exercise the public CTR catalogue without network or database access."""

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

import requests
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ap-web"))

from api.ctr import bp
from ctr_track_registry import RegistryCache, _fetch_json, _load_catalog, make_catalog


class TrackRegistryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / "tests/fixtures/browser/ctr-track-registry.json").read_text())
        self.commit = self.fixture["registry_commit"]
        self.registry = self.fixture["registry"]
        self.sources = self.fixture["sources"]

    def catalog(self):
        return make_catalog(self.commit, self.registry, self.sources)

    def test_matches_both_hashes_and_keeps_every_exact_slot(self):
        catalog = self.catalog()
        copper = catalog["tracks"][0]
        newest, saphi, patch_revision = copper["revisions"]
        self.assertEqual(newest["revision"], "1.10.0")
        self.assertEqual(newest["modes"], [])
        self.assertEqual(newest["sources"], [])
        self.assertEqual(saphi["sources"], [{"kind": "saphi", "url": "https://www.projectsaphi.com/tracks/121"}])
        self.assertEqual([source["bigfile_index"] for source in patch_revision["sources"]], [7, 9])
        self.assertEqual(catalog["unmatched_patches"][0]["slots"], [8])

    def test_sources_can_be_absent_and_schema_versions_are_checked(self):
        catalog = make_catalog(self.commit, self.registry, None)
        self.assertEqual(catalog["unmatched_patches"], [])
        self.assertEqual(catalog["tracks"][0]["revisions"][2]["sources"], [])
        with self.assertRaises(ValueError):
            make_catalog(self.commit, {**self.registry, "schema_version": 2}, None)
        with self.assertRaises(ValueError):
            make_catalog(self.commit, self.registry, {**self.sources, "schema_version": True})

    def test_bad_publication_link_is_omitted(self):
        self.sources["patches"][0]["source_url"] = "javascript:alert(1)"
        patch_source = self.catalog()["tracks"][0]["revisions"][2]["sources"][0]
        self.assertIsNone(patch_source["url"])

    @patch("ctr_track_registry._fetch_json")
    def test_fetches_both_files_at_the_same_commit(self, fetch):
        fetch.side_effect = [{"object": {"sha": self.commit}}, self.registry, self.sources]
        self.assertEqual(_load_catalog(), self.catalog())
        calls = fetch.call_args_list
        self.assertTrue(calls[0].args[1].endswith("/git/ref/heads/main"))
        self.assertTrue(calls[1].args[1].endswith(f"/{self.commit}/registry.json"))
        self.assertTrue(calls[2].args[1].endswith(f"/{self.commit}/sources.json"))
        self.assertEqual(calls[2].kwargs, {"optional": True})
        self.assertFalse(calls[0].args[0].trust_env)

    @patch("ctr_track_registry.is_safe_outbound_host", return_value=True)
    def test_fetch_disallows_redirects_and_bounds_stream(self, allowed):
        session = MagicMock()
        response = session.get.return_value.__enter__.return_value
        url = "https://raw.githubusercontent.com/example"
        response.status_code = 302
        with self.assertRaisesRegex(ValueError, "HTTP 302"):
            _fetch_json(session, url, 10)
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])
        allowed.assert_called_with("raw.githubusercontent.com")
        response.status_code = 200
        response.headers = {}
        response.iter_content.return_value = [b"123456", b"78901"]
        with self.assertRaisesRegex(ValueError, "size limit"):
            _fetch_json(session, url, 10)
        with self.assertRaisesRegex(ValueError, "host is not allowed"):
            _fetch_json(session, "https://example.org/file", 10)
        allowed.return_value = False
        with self.assertRaisesRegex(ValueError, "host is not allowed"):
            _fetch_json(session, url, 10)

    def test_stale_snapshot_survives_failure_and_is_replaced_after_interval(self):
        first = self.catalog()
        second = {**first, "registry_commit": "2" * 40}
        load = Mock(side_effect=[first, requests.ConnectionError(), second])
        clock = Mock(return_value=0)
        cache = RegistryCache(load=load, clock=clock)
        self.assertIs(cache.get(), first)
        clock.return_value = 899
        self.assertIs(cache.get(), first)
        self.assertEqual(load.call_count, 1)
        clock.return_value = 900
        with self.assertLogs("ctr_track_registry", level="WARNING"):
            self.assertIs(cache.get(), first)
        clock.return_value = 1799
        self.assertIs(cache.get(), first)
        self.assertEqual(load.call_count, 2)
        clock.return_value = 1800
        self.assertIs(cache.get(), second)
        self.assertEqual(load.call_count, 3)

    def test_public_routes_serve_unavailable_then_recover(self):
        catalog = self.catalog()
        load = Mock(side_effect=[requests.ConnectionError(), catalog])
        clock = Mock(return_value=0)
        cache = RegistryCache(load=load, clock=clock)
        app = Flask(__name__)
        app.register_blueprint(bp)
        client = app.test_client()
        with patch("api.ctr.registry_cache", cache):
            with self.assertLogs("ctr_track_registry", level="WARNING"):
                self.assertEqual(client.get("/api/ctr/tracks").status_code, 503)
            page = client.get("/ctr/tracks")
            self.assertEqual(page.status_code, 503)
            self.assertIn(b"The track registry is temporarily unavailable", page.data)
            self.assertEqual(load.call_count, 1)
            clock.return_value = 900
            self.assertEqual(client.get("/api/ctr/tracks").get_json(), catalog)
            self.assertEqual(client.get("/ctr/tracks/unknown").status_code, 404)
            self.assertEqual(client.post("/api/ctr/tracks").status_code, 405)


if __name__ == "__main__":
    unittest.main(verbosity=2)
