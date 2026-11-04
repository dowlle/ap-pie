#!/usr/bin/env python3
"""Regression checks for final-release catalog and room selection."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ap-web"), str(ROOT / "ap-lib")]

from ap_lib.apworld_index import is_test_build, parse_world_toml, pin_default_version
from api.apworlds import select_pin_version
from builtin_builder import build_versions


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


class StableDefaultPin(unittest.TestCase):
    """A newer test build stays selectable but is not the default."""

    VERSIONS = ["0.2.3", "0.2.4", "0.3.0-alpha1", "0.2.1-alpha2"]

    def world(self):
        return ReleaseOrdering.world(self, self.VERSIONS)

    def test_pinned_stable_is_every_default(self):
        world = self.world()
        self.assertEqual(world.latest_version.version, "0.3.0-alpha1")
        self.assertTrue(pin_default_version(world, "0.2.4"))
        self.assertEqual(world.latest_version.version, "0.2.4")
        self.assertEqual(world.to_dict()["downloadable_versions"][0]["version"], "0.2.4")
        self.assertEqual(select_pin_version(world, None), "0.2.4")
        built = build_versions(world)
        self.assertEqual(built[0], {"version": "0.2.4", "test_build": False})
        self.assertIn({"version": "0.3.0-alpha1", "test_build": True}, built)

    def test_explicit_test_build_still_wins_a_room_request(self):
        world = self.world()
        pin_default_version(world, "0.2.4")
        self.assertEqual(select_pin_version(world, ["0.3.0-alpha1"]), "0.3.0-alpha1")

    def test_unindexed_pin_leaves_order(self):
        world = self.world()
        self.assertFalse(pin_default_version(world, "9.9.9"))
        self.assertFalse(pin_default_version(world, None))
        self.assertEqual(world.latest_version.version, "0.3.0-alpha1")

    def test_ctr_stable_pin_is_applied_on_load(self):
        from api import apworlds
        from api.ctr import STABLE
        world = parse_world_toml("ctr", {
            "name": "Crash Team Racing",
            "default_url": "https://example.invalid/{version}/ctr.apworld",
            "versions": {"0.3.0-alpha1": {}, STABLE["version"]: {}},
        })
        apworlds._pin_stable_defaults([world])
        self.assertEqual(world.latest_version.version, STABLE["version"])

    def test_saved_yaml_freshness_target(self):
        from unittest.mock import patch
        from api import user_yamls
        world = self.world()
        pin_default_version(world, "0.2.4")
        with patch("api.apworlds._get_index_worlds", return_value=[world]):
            target = lambda saved: user_yamls._freshness_target("ctr", saved)
            self.assertEqual(target("0.2.3"), "0.2.4")
            self.assertEqual(target("0.2.4"), "0.2.4")
            # A test build save is not sent back to the older stable release.
            self.assertEqual(target("0.3.0-alpha1"), "0.3.0-alpha1")
            # An older test build save is offered the stable release.
            self.assertEqual(target("0.2.1-alpha2"), "0.2.4")

    def test_test_build_shape(self):
        for version in ["0.3.0-alpha1", "1.0.0-rc3", "0.6.0-alpha.2", "1.1.1-TEST"]:
            self.assertTrue(is_test_build(version), version)
        for version in ["0.2.4", "spyro-v0.4.1", "2.0.0+pre-release-2b", "CrystalProject-v0.17.0", ""]:
            self.assertFalse(is_test_build(version), version)


if __name__ == "__main__":
    unittest.main()
