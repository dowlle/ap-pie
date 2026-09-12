#!/usr/bin/env python3
"""Regression checks for final-release catalog and room selection."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ap-web"), str(ROOT / "ap-lib")]

from ap_lib.apworld_index import parse_world_toml
from api.apworlds import select_pin_version


class ReleaseOrdering(unittest.TestCase):
    def world(self, versions):
        return parse_world_toml("ctr", {
            "name": "Crash Team Racing",
            "default_url": "https://example.invalid/{version}/ctr.apworld",
            "versions": {version: {} for version in versions},
        })

    def test_stable_is_catalog_and_default_room_choice(self):
        world = self.world(["0.2.0-alpha7", "0.1.5", "0.2.0", "0.2.0-rc.1"])
        self.assertEqual(world.latest_version.version, "0.2.0")
        self.assertEqual(world.to_dict()["downloadable_versions"][0]["version"], "0.2.0")
        self.assertEqual(select_pin_version(world, None), "0.2.0")
        self.assertEqual(select_pin_version(world, ["0.2.0-alpha7", "0.2.0"]), "0.2.0")

    def test_explicit_prerelease_remains_available(self):
        world = self.world(["0.2.0-alpha6", "0.2.0-alpha7", "0.2.0"])
        self.assertEqual(select_pin_version(world, ["0.2.0-alpha7"]), "0.2.0-alpha7")
        self.assertEqual(select_pin_version(world, ["0.2.0-alpha6", "0.2.0-alpha7"]), "0.2.0-alpha7")

    def test_newer_numeric_bases_still_win(self):
        for newer, older in [("0.2.1-alpha1", "0.2.0"), ("0.2.0.1", "0.2.0"),
                             ("0.10.0", "0.9.0"), ("0.2.0", "0.2")]:
            with self.subTest(newer=newer, older=older):
                world = self.world([older, newer])
                self.assertEqual(world.latest_version.version, newer)
                self.assertEqual(select_pin_version(world, [older, newer]), newer)


if __name__ == "__main__":
    unittest.main()
