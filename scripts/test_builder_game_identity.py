#!/usr/bin/env python3
"""Builder YAML identity must match its APWorld on cold and warm paths."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ap-web"))
from flask import Flask
from api import apworlds
from apworld_options_parser import BUILDER_SCHEMA_FORMAT_VERSION


class BuilderIdentityTests(unittest.TestCase):
    def test_archive_identity_wins_on_cold_and_warm_paths(self):
        schema = {"game": "Rayman 2", "_format_version": BUILDER_SCHEMA_FORMAT_VERSION, "options": []}
        version = SimpleNamespace(version="1.2.2", sha256=None, url="https://example.com/world.apworld", local=None)
        world = SimpleNamespace(name="rayman2", game_name="Rayman 2: The Great Escape", display_name="Rayman 2: The Great Escape", versions=[version])
        for cached in [None, {"schema": schema}]:
            with self.subTest(cached=bool(cached)), Flask(__name__).app_context(), \
                 patch.object(apworlds, "_get_index_worlds", return_value=[world]), \
                 patch("db.get_builder_schema_by_version", return_value=cached), \
                 patch("db.set_builder_schema"), \
                 patch.object(apworlds, "_fetch_apworld_bytes", return_value=b"fixture"), \
                 patch("apworld_options_parser.parse_apworld_options_bytes", return_value=schema):
                entry = apworlds.builder_schemas_for_pins([{"apworld_name": "rayman2", "version": "1.2.2"}])[0]
                self.assertEqual(entry["game"], "Rayman 2")
                self.assertEqual(entry["display_name"], "Rayman 2: The Great Escape")


if __name__ == "__main__":
    unittest.main()
