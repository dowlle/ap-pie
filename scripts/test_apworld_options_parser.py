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
from Options import OptionCounter, OptionDict, PerGameCommonOptions, OptionSet
from .data import GAME_REGIONS

class Regions(OptionSet):
    display_name = "Regions"
    valid_keys = frozenset(GAME_REGIONS)
    default = frozenset({"Kanto"})

class _BaseTrapWeights(OptionCounter):
    display_name = "Trap Weights"
    valid_keys = ["slow", "spin"]
    default = {"slow": 2, "spin": 1}

class TrapWeights(_BaseTrapWeights):
    pass

class _BaseCustomTracks(OptionDict):
    display_name = "Custom Tracks"
    valid_keys = ["baby-t-park"]
    default = {}

class CustomTracks(_BaseCustomTracks):
    pass

class RequirementWeights(OptionDict):
    display_name = "Requirement Weights"
    valid_keys = ["easy", "hard"]
    default = {}

@dataclass
class FixtureOptions(PerGameCommonOptions):
    regions: Regions
    trap_weights: TrapWeights
    custom_tracks: CustomTracks
    requirement_weights: RequirementWeights
""",
        )
    return output.getvalue()


def _derived_weight_fixture_apworld() -> bytes:
    """Match CTR Alpha 6's registry-derived OptionDict metadata shape."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "fixture/__init__.py",
            'class FixtureWorld:\n    game = "Fixture Game"\n',
        )
        archive.writestr(
            "fixture/traps.py",
            """from typing import NamedTuple

class TrapEntry(NamedTuple):
    key: str
    weight: int
    buildable: bool

TRAP_REGISTRY = (
    TrapEntry("slow", 5, True),
    TrapEntry("spin", 2, True),
    TrapEntry("reserved", 9, False),
)
TRAP_WEIGHT_KEYS = tuple(entry.key for entry in TRAP_REGISTRY if entry.buildable)
DEFAULT_TRAP_WEIGHTS = {entry.key: entry.weight for entry in TRAP_REGISTRY if entry.buildable}
""",
        )
        archive.writestr(
            "fixture/Options.py",
            """from dataclasses import dataclass
from Options import OptionDict, PerGameCommonOptions
from .traps import DEFAULT_TRAP_WEIGHTS, TRAP_WEIGHT_KEYS

class TrapWeights(OptionDict):
    display_name = "Trap Weights"
    default = dict(DEFAULT_TRAP_WEIGHTS)
    valid_keys = list(TRAP_WEIGHT_KEYS)

@dataclass
class FixtureOptions(PerGameCommonOptions):
    trap_weights: TrapWeights
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

    def test_option_counter_emits_counter_dict_kind(self) -> None:
        schema = parse_apworld_options_bytes(_fixture_apworld(), stem_hint="fixture")

        self.assertIsNotNone(schema)
        assert schema is not None
        option = next(o for o in schema["options"] if o["name"] == "trap_weights")
        self.assertEqual(option["type"], "dict")
        self.assertEqual(option["dict_kind"], "counter")
        self.assertEqual(option["valid_keys"], ["slow", "spin"])

    def test_option_dict_emits_mapping_dict_kind(self) -> None:
        schema = parse_apworld_options_bytes(_fixture_apworld(), stem_hint="fixture")

        self.assertIsNotNone(schema)
        assert schema is not None
        option = next(o for o in schema["options"] if o["name"] == "custom_tracks")
        self.assertEqual(option["type"], "dict")
        self.assertEqual(option["dict_kind"], "mapping")
        self.assertEqual(option["default"], {})
        self.assertEqual(option["valid_keys"], ["baby-t-park"])
        self.assertNotIn("mapping_value_kind", option)

    def test_flat_numeric_option_dict_emits_weight_map_capability(self) -> None:
        schema = parse_apworld_options_bytes(_fixture_apworld(), stem_hint="fixture")

        self.assertIsNotNone(schema)
        assert schema is not None
        option = next(o for o in schema["options"] if o["name"] == "requirement_weights")
        self.assertEqual(option["dict_kind"], "mapping")
        self.assertEqual(option["mapping_value_kind"], "number")
        self.assertEqual(option["valid_keys"], ["easy", "hard"])

    def test_registry_derived_weight_map_matches_ctr_alpha6_shape(self) -> None:
        schema = parse_apworld_options_bytes(
            _derived_weight_fixture_apworld(), stem_hint="fixture"
        )

        self.assertIsNotNone(schema)
        assert schema is not None
        option = next(o for o in schema["options"] if o["name"] == "trap_weights")
        self.assertEqual(option["dict_kind"], "mapping")
        self.assertEqual(option["mapping_value_kind"], "number")
        self.assertEqual(option["valid_keys"], ["slow", "spin"])
        self.assertEqual(option["default"], {"slow": 5, "spin": 2})


if __name__ == "__main__":
    unittest.main(verbosity=2)
