#!/usr/bin/env python3
"""Regression checks for safe cross-module APWorld option metadata parsing."""

from __future__ import annotations

import io
import os
import sys
import unittest
import zipfile

repo_app = os.path.join(os.path.dirname(__file__), "..", "ap-web")
sys.path.insert(0, repo_app)

from apworld_options_parser import (  # noqa: E402
    BUILDER_SCHEMA_FORMAT_VERSION,
    parse_apworld_options_bytes,
)


def _fixture_apworld() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "fixture/__init__.py",
            'class FixtureWorld:\n    game = "Fixture Game"\n',
        )
        archive.writestr(
            "fixture/data.py",
            'REGION_DATA = {"Kanto": {}, "Johto": {}, "Hoenn": {}}\n'
            'GAME_REGIONS = list(REGION_DATA.keys())\n',
        )
        archive.writestr(
            "fixture/Options.py",
            """from dataclasses import dataclass
from Options import PerGameCommonOptions, OptionSet
from .data import GAME_REGIONS

class Regions(OptionSet):
    display_name = "Regions"
    valid_keys = frozenset(GAME_REGIONS)
    default = frozenset({"Kanto"})

@dataclass
class FixtureOptions(PerGameCommonOptions):
    regions: Regions
""",
        )
    return output.getvalue()


class APWorldOptionsParser(unittest.TestCase):
    def test_imported_literal_collection_becomes_choices(self) -> None:
        schema = parse_apworld_options_bytes(_fixture_apworld(), stem_hint="fixture")

        self.assertIsNotNone(schema)
        assert schema is not None
        self.assertEqual(schema["_format_version"], BUILDER_SCHEMA_FORMAT_VERSION)
        self.assertEqual(schema["options"][0]["name"], "regions")
        self.assertEqual(schema["options"][0]["default"], ["Kanto"])
        self.assertEqual(
            schema["options"][0]["choices"],
            ["Hoenn", "Johto", "Kanto"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
