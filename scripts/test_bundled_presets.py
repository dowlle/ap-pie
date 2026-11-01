#!/usr/bin/env python3
"""The presets route offers the presets an APWorld ships (CTR: Quick, Standard,
Full Adventure) as official presets for the version being built, ahead of the
stored community presets, with negative ids and no uses or votes."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ap-web"))

from flask import Flask  # noqa: E402

import api.presets as presets  # noqa: E402

SCHEMA_ROW = {
    "version": "0.3.0",
    "schema": {
        "options": [{"name": "oxide_goal"}, {"name": "death_link"}],
        "bundled_presets": [
            {"id": "quick", "label": "Quick", "summary": "Short goal, few locks",
             "values": {"oxide_goal": "any_percent", "death_link": "off"}},
            {"id": "standard", "label": "Standard", "summary": "The release defaults",
             "values": {"death_link": "off"}},
        ],
    },
}
STORED = {
    "id": 7, "apworld_name": "ctr", "version": "0.2.4", "name": "Community", "description": "d",
    "kind": "simple", "values": {"oxide_goal": "none", "gone": 1}, "yaml_content": None,
    "author_username": "someone", "is_official": False, "status": "published", "uses": 3, "score": 1,
}


class BundledPresetsRoute(unittest.TestCase):
    def get(self, stored, schema_row):
        app = Flask(__name__)
        app.register_blueprint(presets.bp)
        with mock.patch.object(presets, "_db_url", "postgres://x"), \
                mock.patch.object(presets, "list_presets_for_apworld", return_value=stored), \
                mock.patch.object(presets, "_schema_for", return_value=(object(), schema_row)), \
                mock.patch.object(presets, "has_voted", return_value=set()):
            return app.test_client().get("/api/apworlds/ctr/presets?version=0.3.0").get_json()["presets"]

    def test_bundled_come_first_then_stored_with_their_own_checks(self):
        rows = self.get([dict(STORED)], SCHEMA_ROW)
        self.assertEqual([r["id"] for r in rows], [-1, -2, 7])
        quick = rows[0]
        self.assertEqual((quick["name"], quick["description"], quick["version"]),
                         ("Quick", "Short goal, few locks", "0.3.0"))
        self.assertTrue(quick["is_official"] and quick["bundled"])
        self.assertEqual(quick["applies"], {"oxide_goal": "any_percent", "death_link": "off"})
        self.assertEqual(quick["stale_keys"], [])
        self.assertEqual((quick["uses"], quick["score"], quick["voted"]), (0, 0, False))
        self.assertFalse(rows[2]["bundled"])
        self.assertEqual(rows[2]["stale_keys"], ["gone"])

    def test_bundled_alone_and_neither(self):
        self.assertEqual([r["id"] for r in self.get([], SCHEMA_ROW)], [-1, -2])
        self.assertEqual(self.get([], {"version": "0.2.4", "schema": {"options": []}}), [])
        self.assertEqual(self.get([], None), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
