#!/usr/bin/env python3
"""Regression checks for safe cross-module APWorld option metadata parsing."""

from __future__ import annotations

import io
import json
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
    def test_package_resource_range_and_dictionary_groups(self):
        for resource, expected in [("data/pads.json", 3), ("../outside.json", None)]:
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w") as archive:
                archive.writestr("fixture/__init__.py", 'class World:\n game = "Resource Game"\n')
                archive.writestr("fixture/data/pads.json", '{"pads": [1, 2, 3]}')
                archive.writestr("outside.json", '{"pads": [1, 2]}')
                archive.writestr("fixture/characters.py", f'''import json, pkgutil
PHYSICAL_PAD_COUNT = len(json.loads(pkgutil.get_data(__package__, "{resource}").decode("utf-8"))["pads"])
raise RuntimeError("Archive source must never execute")
''')
                archive.writestr("fixture/Options.py", '''from Options import Range, PerGameCommonOptions
from . import characters
class RacerLocks(Range):
    range_start = 0
    range_end = characters.PHYSICAL_PAD_COUNT
    default = 0
class Settings(PerGameCommonOptions):
    racer_locked_pads: RacerLocks
option_groups = {"Characters": [RacerLocks]}
''')
            schema = parse_apworld_options_bytes(output.getvalue())
            if expected is None:
                self.assertEqual(schema["options"], [])
            else:
                self.assertEqual(schema["options"][0]["max"], expected)
                self.assertEqual(schema["options"][0]["category"], "Characters")

    def fixture_identity(self, source, manifest=None, root=False, extra=None):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("fixture/__init__.py", source)
            if manifest is not None:
                archive.writestr("archipelago.json" if root else "fixture/archipelago.json", manifest)
            if extra:
                archive.writestr("fixture/constants.py", extra)
        return parse_apworld_options_bytes(output.getvalue())

    def test_manifest_identity_without_executing_world(self):
        schema = self.fixture_identity('raise RuntimeError("must not execute")\nclass W:\n    game = constants.GAME_NAME\n', json.dumps({"game": "Lego Star Wars: The Complete Saga"}))
        self.assertEqual(schema["game"], "Lego Star Wars: The Complete Saga")

    def test_root_manifest_identity(self):
        self.assertEqual(self.fixture_identity('class W: pass', '{"game":"Root Game"}', root=True)["game"], "Root Game")

    def test_invalid_manifests_preserve_legacy_fallback(self):
        for manifest in ('invalid', '[]', '{"game":null}', '{"game":42}', '{"game":"  "}'):
            with self.subTest(manifest=manifest):
                self.assertEqual(self.fixture_identity('class W:\n    game = "Legacy"\n', manifest)["game"], "Legacy")

    def test_literal_class_namespace(self):
        schema = self.fixture_identity('class W:\n    game = SPZ.game_name\n', extra='class SPZ:\n    game_name = "shapez 2"\n')
        self.assertEqual(schema["game"], "shapez 2")

    def test_literal_dictionary_identity(self):
        schema = self.fixture_identity('data = {"game_name": "Air Delivery", "unused": None}\nclass W:\n    game = data["game_name"]\n')
        self.assertEqual(schema["game"], "Air Delivery")

    def test_dynamic_and_ambiguous_identity_remain_unsupported(self):
        self.assertIsNone(self.fixture_identity('class W:\n    game = load_game()\n'))
        self.assertIsNone(self.fixture_identity('data={"game":"A"}\nclass W:\n    game=data["game"]\n', extra='data={"game":"B"}\n'))

    def test_split_options_bom_and_dataclass_preference(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("fixture/__init__.py", 'class W:\n    game = "Fixture"\n')
            archive.writestr("fixture/constants/options.py", 'class Constants:\n    title = "Wrong file"\n')
            archive.writestr("fixture/gameoptions.py", '\ufefffrom Options import PerGameCommonOptions\nfrom .fields import Lives as StartingLives\nclass Settings(PerGameCommonOptions):\n    lives: StartingLives\n')
            archive.writestr("fixture/fields.py", 'raise RuntimeError("never execute")\nfrom Options import Range\nclass Lives(Range):\n    range_start=1\n    range_end=9\n    default=3\n')
        options = parse_apworld_options_bytes(output.getvalue())["options"]
        self.assertEqual([o["name"] for o in options], ["lives"])
        self.assertEqual(options[0]["default"], 3)

    def test_alternate_source_and_inherited_fields(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("fixture/__init__.py", 'class W:\n    game = "Fixture"\n')
            archive.writestr("fixture/Settings.py", 'from Options import Toggle, PerGameCommonOptions\nclass Enabled(Toggle):\n    pass\nclass SharedFields:\n    enabled: Enabled\nclass Settings(SharedFields, PerGameCommonOptions):\n    pass\n')
        options = parse_apworld_options_bytes(output.getvalue())["options"]
        self.assertEqual([o["name"] for o in options], ["enabled"])

    def test_no_options_is_a_valid_empty_schema(self):
        self.assertEqual(self.fixture_identity('class W:\n    game = "No options"\n')["options"], [])

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
