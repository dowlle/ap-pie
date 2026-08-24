#!/usr/bin/env python3
"""Focused contract checks for the reviewed APWorld metadata overlay."""

from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "ap-web"))

from apworld_editorial import (  # noqa: E402
    CONTENT_DIR,
    EditorialValidationError,
    _record_from_data,
    join_index_record,
    load_reviewed_apworlds,
    tomllib,
)


class ReviewedAPWorldMetadataTests(unittest.TestCase):
    def test_current_fixtures_load_and_keep_drafts_private(self) -> None:
        records = load_reviewed_apworlds()
        self.assertEqual(set(records), {"sm", "animal_well", "ctr"})
        self.assertTrue(records["sm"].is_beta_preview)
        self.assertFalse(records["sm"].is_public)
        self.assertFalse(records["animal_well"].is_public)
        self.assertEqual(records["ctr"].route.path, "/ctr")

    def test_join_keeps_upstream_and_editorial_namespaces_separate(self) -> None:
        records = load_reviewed_apworlds()
        joined = join_index_record({"name": "sm", "display_name": "Super Metroid"}, records)
        self.assertEqual(joined["index"]["display_name"], "Super Metroid")
        self.assertEqual(joined["review_state"], "reviewed")
        self.assertIsNone(joined["editorial"])
        beta_joined = join_index_record(
            {"name": "sm", "display_name": "Super Metroid"}, records, include_beta_previews=True
        )
        self.assertEqual(beta_joined["editorial"]["slug"], "super-metroid")
        self.assertTrue(beta_joined["editorial"]["beta_preview_only"])
        self.assertNotIn("claims", beta_joined["editorial"])
        draft = join_index_record({"name": "animal_well"}, records)
        self.assertEqual(draft["review_state"], "draft")
        self.assertIsNone(draft["editorial"])
        absent = join_index_record({"name": "not-reviewed"}, records)
        self.assertEqual(absent["review_state"], "absent")
        self.assertIsNone(absent["editorial"])

    def test_misattributed_minecraft_fixture_does_not_publish(self) -> None:
        invalid_path = CONTENT_DIR / "fixtures-invalid" / "minecraft-neoforge-misattributed.toml"
        data = tomllib.loads(invalid_path.read_text(encoding="utf-8"))
        record = _record_from_data(data, invalid_path)
        self.assertEqual(record.review_state, "draft")
        self.assertFalse(record.is_public)
        self.assertIsNone(record.public_overlay())
        data["review_state"] = "reviewed"
        data["publication_status"] = "published"
        data["editorial"]["copy_status"] = "approved_original"
        data["editorial"]["copy_reviewed_by"] = "Appie"
        data["editorial"]["copy_reviewed_at"] = "2026-08-24"
        with self.assertRaisesRegex(EditorialValidationError, "require a primary, official, maintainer"):
            _record_from_data(data, invalid_path)

    def test_published_records_reject_unreviewed_and_non_original_copy(self) -> None:
        data = tomllib.loads((CONTENT_DIR / "super-metroid.toml").read_text(encoding="utf-8"))
        data["review_state"] = "draft"
        with self.assertRaisesRegex(EditorialValidationError, "only reviewed records may be published or previewed"):
            _record_from_data(data, Path("bad.toml"))
        data["review_state"] = "reviewed"
        data["editorial"]["copy_status"] = "original_draft"
        data["editorial"].pop("copy_reviewed_by")
        data["editorial"].pop("copy_reviewed_at")
        with self.assertRaisesRegex(EditorialValidationError, "approved original AP-Pie copy"):
            _record_from_data(data, Path("bad.toml"))

    def test_unknown_fields_bad_dates_and_missing_sources_fail(self) -> None:
        data = tomllib.loads((CONTENT_DIR / "animal-well.toml").read_text(encoding="utf-8"))
        data["unexpected"] = True
        data["reviewed_at"] = "24-08-2026"
        data["claims"][0]["source_refs"] = ["does-not-exist"]
        with self.assertRaises(EditorialValidationError) as raised:
            _record_from_data(data, Path("bad.toml"))
        message = str(raised.exception)
        self.assertIn("unknown field(s): unexpected", message)
        self.assertIn("expected an ISO date", message)
        self.assertIn("unknown source id(s): does-not-exist", message)

    def test_duplicate_slug_and_source_id_fail_across_records(self) -> None:
        first = (CONTENT_DIR / "super-metroid.toml").read_text(encoding="utf-8")
        duplicate = first.replace('apworld_name = "sm"', 'apworld_name = "another-world"')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "first.toml").write_text(first, encoding="utf-8")
            (root / "second.toml").write_text(duplicate, encoding="utf-8")
            with self.assertRaisesRegex(EditorialValidationError, "duplicate slug"):
                load_reviewed_apworlds(root)
            duplicate = duplicate.replace('slug = "super-metroid"', 'slug = "another-world"')
            (root / "second.toml").write_text(duplicate, encoding="utf-8")
            with self.assertRaisesRegex(EditorialValidationError, "duplicate source id"):
                load_reviewed_apworlds(root)

    def test_route_overrides_require_reviewed_publication(self) -> None:
        data = tomllib.loads((CONTENT_DIR / "ctr.toml").read_text(encoding="utf-8"))
        data["review_state"] = "draft"
        data["publication_status"] = "unpublished"
        with self.assertRaisesRegex(EditorialValidationError, "route overrides require a reviewed published record"):
            _record_from_data(data, Path("bad.toml"))

    def test_route_overrides_require_explicit_route_kind(self) -> None:
        data = tomllib.loads((CONTENT_DIR / "ctr.toml").read_text(encoding="utf-8"))
        del data["route"]["kind"]
        with self.assertRaisesRegex(EditorialValidationError, "expected a non-empty string"):
            _record_from_data(data, Path("missing-kind.toml"))

        data["route"]["kind"] = "external"
        with self.assertRaisesRegex(EditorialValidationError, "expected 'spa' or 'server'"):
            _record_from_data(data, Path("bad-kind.toml"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
