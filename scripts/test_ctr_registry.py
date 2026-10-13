#!/usr/bin/env python3
"""CTR custom-track name registry: rules, export and checker run anywhere; the
database, import and API checks need DATABASE_URL (same convention as the other
backend tests)."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from flask import Flask

repo_app = os.path.join(os.path.dirname(__file__), "..", "ap-web")
sys.path.insert(0, repo_app if os.path.isdir(repo_app) else "/app")

import config
from ctr_registry import check as registry_check
from ctr_registry import export, rules, saphi, store
from ctr_registry.rules import RuleError

H = lambda c: hashlib.sha256(c.encode()).hexdigest()  # noqa: E731 - a valid 64-hex string per label


def make_entry(i, key, state="named", block=None, name=None, shipped=None, title=None, rid=None):
    return {
        "id": rid or i, "track_key": key, "state": state, "block_index": block, "ap_name": name,
        "shipped_in": shipped, "display_title": title or key.title(), "credits": [{"name": "Maker", "role": "track"}],
        "links": {"saphi": f"https://www.projectsaphi.com/t/{i}"}, "provenance": {"saphi": {"track_id": i, "category": "community", "url": None}},
        "reviewed_at": datetime(2026, 10, 14, tzinfo=timezone.utc), "superseded_by": None,
    }


def make_rev(i, content="a", state="verified", label="1.0.0", with_id=True):
    return {"revision": label, "content_id": H(content) if with_id else None, "hash_state": state,
            "files": {"lev": {"sha256": H(content), "size": 10}} if with_id else {}, "modes": ["time_trial"],
            "evidence": {"level": "static"}, "descriptor_schema": 1, "apworld_min": None, "apworld_max": None,
            "descriptor": {"content_id": H(content), "title": "x"}, "provenance": {}}


class IdAssignment(unittest.TestCase):
    def test_codes_follow_the_ruled_budgets(self):
        self.assertEqual(rules.location_code(0, 0), 35_200_000)
        self.assertEqual(rules.location_code(1, 0), 35_200_200)
        self.assertEqual(rules.location_code(9999, 199), 37_199_999)
        self.assertEqual(rules.item_code(0, 0), 35_100_000)
        self.assertEqual(rules.item_code(9999, 4), 35_149_999)

    def test_offsets_and_blocks_are_range_checked(self):
        for bad in (-1, 10_000, 1.5, True):
            with self.assertRaises(RuleError):
                rules.check_block_index(bad)  # type: ignore[arg-type]
        with self.assertRaises(RuleError):
            rules.location_code(0, 200)
        with self.assertRaises(RuleError):
            rules.item_code(0, 5)

    def test_next_block_index_is_monotonic_and_never_reuses_gaps(self):
        self.assertEqual(rules.next_block_index([]), 0)
        self.assertEqual(rules.next_block_index([0, 1, 2]), 3)
        self.assertEqual(rules.next_block_index([0, 5]), 6)  # gap at 1..4 stays a gap
        with self.assertRaises(RuleError):
            rules.next_block_index([9999])

    def test_range_summary_matches_the_ruling(self):
        r = rules.id_ranges()
        self.assertEqual((r["locations"]["first"], r["locations"]["last"]), (35_200_000, 37_199_999))
        self.assertEqual((r["items"]["first"], r["items"]["last"]), (35_100_000, 35_149_999))
        self.assertEqual((r["locations"]["per_track"], r["items"]["per_track"]), (200, 5))
        self.assertLess(r["items"]["last"], r["locations"]["first"])  # the #306 overlap is gone

    def test_checker_constants_match_rules(self):
        self.assertEqual(registry_check.MAX_BLOCKS, rules.MAX_BLOCKS)
        self.assertEqual((registry_check.LOCATION_BASE, registry_check.LOCATIONS_PER_TRACK),
                         (rules.LOCATION_BASE, rules.LOCATIONS_PER_TRACK))
        self.assertEqual((registry_check.ITEM_BASE, registry_check.ITEMS_PER_TRACK),
                         (rules.ITEM_BASE, rules.ITEMS_PER_TRACK))
        self.assertEqual(registry_check.SCHEMA_VERSION, rules.SCHEMA_VERSION)
        self.assertEqual(registry_check.NAME_MAX_BYTES, rules.ROOM_TITLE_MAX_BYTES)


class FreezeRules(unittest.TestCase):
    def test_identity_cannot_change_once_set(self):
        old = {"track_key": "a", "block_index": 3, "ap_name": "A", "shipped_in": None}
        self.assertEqual(rules.freeze_violations(old, {**old, "track_key": "b"}), ["track_key"])
        self.assertEqual(rules.freeze_violations(old, {**old, "block_index": 4}), ["block_index"])
        self.assertEqual(rules.freeze_violations(old, {**old, "block_index": None}), ["block_index"])

    def test_name_is_correctable_until_shipped_then_frozen(self):
        old = {"track_key": "a", "block_index": 3, "ap_name": "A", "shipped_in": None}
        self.assertEqual(rules.freeze_violations(old, {**old, "ap_name": "A2"}), [])
        shipped = {**old, "shipped_in": "0.3.0"}
        self.assertEqual(rules.freeze_violations(shipped, {**shipped, "ap_name": "A2"}), ["ap_name"])
        self.assertEqual(rules.freeze_violations(shipped, {**shipped, "shipped_in": "0.3.1"}), ["shipped_in"])

    def test_presentation_is_never_frozen(self):
        old = {"track_key": "a", "block_index": 3, "ap_name": "A", "shipped_in": "0.3.0",
               "display_title": "Old", "credits": []}
        self.assertEqual(rules.freeze_violations(old, {**old, "display_title": "New", "credits": [{"name": "X"}]}), [])

    def test_verified_revision_hashes_are_frozen_but_content_id_can_be_filled_once(self):
        pending = {"content_id": None, "hash_state": "pending", "files": {}}
        self.assertEqual(rules.revision_violations(pending, {"content_id": H("a"), "hash_state": "verified", "files": {"lev": {}}}), [])
        verified = {"content_id": H("a"), "hash_state": "verified", "files": {"lev": {"sha256": H("a")}}}
        self.assertIn("content_id", rules.revision_violations(verified, {**verified, "content_id": H("b")}))
        self.assertIn("files", rules.revision_violations(verified, {**verified, "files": {}}))
        self.assertIn("hash_state", rules.revision_violations(verified, {**verified, "hash_state": "claimed"}))

    def test_state_machine(self):
        self.assertTrue(rules.can_transition("candidate", "approved"))
        self.assertTrue(rules.can_transition("approved", "named"))
        self.assertFalse(rules.can_transition("candidate", "named"))
        self.assertFalse(rules.can_transition("named", "approved"))
        self.assertEqual(rules.restored_state({"track_key": "a", "block_index": 2}), "named")
        self.assertEqual(rules.restored_state({"track_key": "a", "block_index": None}), "approved")
        self.assertEqual(rules.restored_state({"track_key": None, "block_index": None}), "candidate")


class ClashSuffixes(unittest.TestCase):
    def test_plain_title_is_kept(self):
        self.assertEqual(rules.ap_name_for("Baby T Park"), "Baby T Park")

    def test_retail_clash_gets_custom_even_with_other_case(self):
        self.assertEqual(rules.ap_name_for("Crash Cove"), "Crash Cove (Custom)")
        self.assertEqual(rules.ap_name_for("crash cove"), "crash cove (Custom)")
        self.assertEqual(rules.ap_name_for("N. Gin Labs"), "N. Gin Labs (Custom)")

    def test_generic_slot_name_gets_custom(self):
        self.assertEqual(rules.ap_name_for("Custom Track 3"), "Custom Track 3 (Custom)")

    def test_second_custom_with_same_title_gets_the_author(self):
        taken = ["Baby T Park"]
        self.assertEqual(rules.ap_name_for("Baby T Park", "Lockheart", taken=taken), "Baby T Park (Custom, Lockheart)")

    def test_retail_clash_taken_twice_gets_author_suffix(self):
        taken = ["Crash Cove (Custom)"]
        self.assertEqual(rules.ap_name_for("Crash Cove", "Author", taken=taken), "Crash Cove (Custom, Author)")

    def test_author_suffix_that_is_also_taken_is_numbered(self):
        taken = ["Crash Cove (Custom)", "Crash Cove (Custom, Author)"]
        self.assertEqual(rules.ap_name_for("Crash Cove", "Author", taken=taken), "Crash Cove (Custom, Author 2)")

    def test_missing_author_falls_back(self):
        self.assertEqual(rules.ap_name_for("Foo", None, taken=["Foo"]), "Foo (Custom, Unknown)")

    def test_taken_names_keep_their_place(self):
        taken = ["Foo (Custom, A)"]
        self.assertEqual(rules.ap_name_for("Foo", "A", taken=["foo"]), "Foo (Custom, A)")
        self.assertEqual(rules.ap_name_for("Bar", "A", taken=taken), "Bar")

    def test_sanitizing_matches_the_apworld(self):
        self.assertEqual(rules.sanitize_title("  A [B]\n{C}  "), "A (B) (C)")
        self.assertEqual(rules.sanitize_title("x" * 80), "x" * 40)
        self.assertIsNone(rules.sanitize_title("​ \t"))
        self.assertIsNone(rules.sanitize_title(None))
        with self.assertRaises(RuleError):
            rules.ap_name_for("   ")

    def test_track_keys_never_reuse_or_shadow_routes(self):
        self.assertEqual(rules.slugify_key("Baby T Park"), "baby-t-park")
        self.assertEqual(rules.slugify_key("Baby T Park", {"baby-t-park"}), "baby-t-park-2")
        self.assertEqual(rules.slugify_key("Baby T Park", {"baby-t-park", "baby-t-park-2"}), "baby-t-park-3")
        self.assertEqual(rules.slugify_key("Submissions"), "submissions-2")
        self.assertEqual(rules.slugify_key("!!!"), "track")
        self.assertEqual(rules.slugify_key("Café Rush"), "cafe-rush")


class ValidationAndCaps(unittest.TestCase):
    def test_title_cap_is_refused_not_cut_for_submitters(self):
        with self.assertRaises(RuleError) as ctx:
            rules.clean_title("x" * 41)
        self.assertEqual(ctx.exception.code, "title_too_long")
        self.assertEqual(rules.clean_title("x" * 41, strict=False), "x" * 40)

    def test_credits_caps_and_roles(self):
        with self.assertRaises(RuleError):
            rules.clean_credits([{"name": "a", "role": "track"}] * 9)
        with self.assertRaises(RuleError):
            rules.clean_credits([{"name": "a", "role": "boss"}])
        with self.assertRaises(RuleError):
            rules.clean_credits([{"name": "x" * 49, "role": "track"}])
        self.assertEqual(rules.clean_credits([{"name": " A  B "}]), [{"name": "A B", "role": "track"}])

    def test_links_are_https_locators_only(self):
        self.assertEqual(rules.clean_links({"saphi": "https://www.projectsaphi.com/x"}), {"saphi": "https://www.projectsaphi.com/x"})
        for bad in ("http://a.b/c", "https://u:p@a.b/c", "https://a.b/ c", "javascript:alert(1)", "https://" + "a" * 300):
            with self.assertRaises(RuleError):
                rules.clean_links({"creator": bad})
        with self.assertRaises(RuleError):
            rules.clean_links({"download": "https://a.b/c"})

    def test_descriptor_caps(self):
        ok = {"content_id": H("a"), "files": {"lev": {"sha256": H("b"), "size": 5}}, "revision": "1.0.0"}
        self.assertEqual(rules.clean_descriptor(ok), ok)
        with self.assertRaises(RuleError):
            rules.clean_descriptor({"blob": "x" * 20000})
        with self.assertRaises(RuleError):
            rules.clean_descriptor({"content_id": "nothex"})
        with self.assertRaises(RuleError):
            rules.clean_descriptor({"files": {"lev": {"sha256": "short"}}})
        deep = cur = {}
        for _ in range(10):
            cur["a"] = {}
            cur = cur["a"]
        with self.assertRaises(RuleError):
            rules.clean_descriptor(deep)
        with self.assertRaises(RuleError):
            rules.clean_descriptor([1, 2])  # type: ignore[arg-type]

    def test_revision_fields_ignore_submitted_modes(self):
        fields = rules.revision_fields({"content_id": H("a"), "revision": "2.0", "modes": ["arcade"],
                                        "files": {"lev": {"sha256": H("b"), "size": 3}}})
        self.assertEqual(fields["hash_state"], "claimed")
        self.assertNotIn("modes", fields)
        self.assertEqual(rules.revision_fields({"revision": "1"})["hash_state"], "pending")
        with self.assertRaises(RuleError):
            rules.revision_fields({})

    def test_version_compatibility(self):
        rev = {"apworld_min": "0.3.0", "apworld_max": "0.3.5"}
        self.assertTrue(rules.revision_compatible(rev, "0.3.1"))
        self.assertFalse(rules.revision_compatible(rev, "0.2.9"))
        self.assertFalse(rules.revision_compatible(rev, "0.4.0"))
        self.assertTrue(rules.revision_compatible({}, "9.9.9"))
        self.assertTrue(rules.revision_compatible(rev, "garbage"))


class SpaRoutes(unittest.TestCase):
    def test_registry_pages_are_spa_routes_only_while_the_flag_is_on(self):
        import app as appmod
        original = dict(config.FEATURES)
        try:
            config.FEATURES["ctr_registry"] = True
            self.assertTrue(appmod._is_spa_route("custom-tracks"))
            self.assertTrue(appmod._is_spa_route("admin/ctr-tracks/"))
            config.FEATURES["ctr_registry"] = False
            self.assertFalse(appmod._is_spa_route("custom-tracks"))
            self.assertFalse(appmod._is_spa_route("admin/ctr-tracks"))
        finally:
            config.FEATURES.clear()
            config.FEATURES.update(original)


class RateLimit(unittest.TestCase):
    def test_window_slides_per_user(self):
        now = [1000.0]
        lim = rules.SlidingWindowLimiter(2, 3600, clock=lambda: now[0])
        self.assertTrue(lim.allow(1))
        self.assertTrue(lim.allow(1))
        self.assertFalse(lim.allow(1))
        self.assertTrue(lim.allow(2))  # another user is unaffected
        now[0] += 3601
        self.assertTrue(lim.allow(1))

    def test_defaults_are_the_documented_caps(self):
        self.assertEqual(rules.SUBMISSIONS_PER_USER_PER_HOUR, 5)
        self.assertEqual(rules.PENDING_PER_USER_MAX, 10)


class ExportAndChecker(unittest.TestCase):
    def records(self):
        return [
            (make_entry(1, "baby-t-park", block=0, name="Baby T Park", shipped="0.3.0"), [make_rev(1, "a")]),
            (make_entry(2, "crash-cove", block=1, name="Crash Cove (Custom)"), [make_rev(2, "b"), make_rev(2, "c", "pending", "1.1", with_id=False)]),
            (make_entry(3, "plain-approved", state="approved"), []),
            (make_entry(4, "gone", state="withdrawn", block=2, name="Gone"), []),
            ({**make_entry(5, "x"), "track_key": None, "state": "candidate"}, []),
        ]

    def test_layout_and_content(self):
        files, digest = export.build_files(self.records())
        self.assertEqual(sorted(files), ["named_tracks.json", "registry.json", "tracks/baby-t-park.json",
                                         "tracks/crash-cove.json", "tracks/gone.json", "tracks/plain-approved.json"])
        named = json.loads(files["named_tracks.json"])
        self.assertEqual(named["format"], 1)
        self.assertEqual([t["block_index"] for t in named["tracks"]], [0, 1, 2])  # withdrawn block stays recorded
        self.assertEqual(named["tracks"][1]["revisions"], [H("b")])  # unhashed revision has no id yet
        self.assertEqual(named["registry"]["digest"], digest)
        reg = json.loads(files["registry.json"])
        self.assertEqual(reg["schema_version"], rules.SCHEMA_VERSION)
        self.assertNotIn("descriptor", reg["tracks"][0]["revisions"][0])
        self.assertIn("descriptor", json.loads(files["tracks/baby-t-park.json"])["revisions"][0])

    def test_no_private_fields_are_exported(self):
        files, _ = export.build_files(self.records())
        text = b"".join(files.values()).decode()
        for needle in ("reviewed_by", "submitter", "discord", "user_id", "submission_id"):
            self.assertNotIn(needle, text)

    def test_export_is_deterministic_and_digest_changes_with_content(self):
        a = export.build_files(self.records())
        b = export.build_files(list(reversed(self.records())))
        self.assertEqual(a, b)
        changed = self.records()
        changed[0][0]["display_title"] = "Renamed"
        self.assertNotEqual(a[1], export.build_files(changed)[1])

    def test_public_view_only_has_approved_and_named(self):
        doc = export.public_publication(self.records())
        self.assertEqual({t["state"] for t in doc["tracks"]}, {"named", "approved"})
        self.assertIn("digest", doc)

    def test_write_is_atomic_set_with_digest_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "registry"
            (out).mkdir()
            (out / ".git").mkdir()
            first = export.write_export(self.records(), str(out), now=datetime(2026, 1, 1, tzinfo=timezone.utc))
            self.assertTrue((out / ".git").is_dir())
            for rel in ("README.md", "registry.json", "named_tracks.json", "DIGEST.json", "tools/check_registry.py", "tracks/baby-t-park.json"):
                self.assertTrue((out / rel).is_file(), rel)
            stamp = (out / "DIGEST.json").read_bytes()
            again = export.write_export(self.records(), str(out), now=datetime(2027, 1, 1, tzinfo=timezone.utc))
            self.assertEqual(again["changed"], 0)
            self.assertEqual((out / "DIGEST.json").read_bytes(), stamp)
            self.assertEqual(first["digest"], again["digest"])
            # a track that left the record set is removed from tracks/ only
            export.write_export(self.records()[:2], str(out))
            self.assertFalse((out / "tracks" / "gone.json").exists())
            self.assertTrue((out / ".git").is_dir())

    def exported(self, tmp):
        out = Path(tmp) / "r"
        export.write_export(self.records(), str(out))
        return out

    def test_checker_passes_a_fresh_export_and_the_copied_script_runs_standalone(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.exported(tmp)
            self.assertEqual(registry_check.check(out), [])
            import subprocess
            res = subprocess.run([sys.executable, "-I", str(out / "tools" / "check_registry.py"), str(out)],
                                 capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_checker_catches_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.exported(tmp)
            path = out / "registry.json"
            doc = json.loads(path.read_text())
            doc["tracks"][0]["display_title"] = "Tampered"
            path.write_text(json.dumps(doc))
            self.assertTrue(any("DIGEST" in e for e in registry_check.check(out)))

    def test_checker_catches_duplicate_blocks_and_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            recs = self.records()
            recs[1][0]["block_index"] = 0
            recs[1][0]["ap_name"] = "baby t park"
            out = Path(tmp) / "r"
            export.write_export(recs, str(out))
            errors = registry_check.check(out)
            self.assertTrue(any("block_index 0" in e for e in errors), errors)
            self.assertTrue(any("also used" in e for e in errors), errors)

    def test_checker_freeze_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            prev = Path(tmp) / "prev"
            export.write_export(self.records(), str(prev))
            ok = Path(tmp) / "ok"
            recs = copy.deepcopy(self.records())
            recs[0][0]["display_title"] = "New display title"  # presentation may change
            recs.append((make_entry(9, "new-one", block=3, name="New One"), []))
            export.write_export(recs, str(ok))
            self.assertEqual(registry_check.check(ok, prev), [])

            bad = Path(tmp) / "bad"
            recs = copy.deepcopy(self.records())
            recs[0][0]["ap_name"] = "Renamed After Shipping"
            recs[1][0]["block_index"] = 7
            recs[1][1][0]["files"] = {"lev": {"sha256": H("f")}}
            recs.pop(3)  # a recorded track disappears
            export.write_export(recs, str(bad))
            errors = registry_check.check(bad, prev)
            joined = "\n".join(errors)
            self.assertIn("shipped ap_name changed", joined)
            self.assertIn("block_index changed", joined)
            self.assertIn("verified revision 1.0.0 changed", joined)
            self.assertIn("gone disappeared", joined)


class SaphiNormalizing(unittest.TestCase):
    RAW = {"id": 101, "title": "  Baby T Park ", "authors": [{"name": "Lockheart"}, "Co Maker"], "type": "community"}
    DL = [{"id": 727, "version": "1.0.2", "type": "LEV", "crc32": "ABCD1234"},
          {"id": 728, "version": "1.0.2", "type": "vrm", "crc32": "11112222"},
          {"id": 668, "version": "1.0.0", "type": "lev", "crc32": "99990000"}]

    def test_normalize_groups_downloads_by_version(self):
        t = saphi.normalize_track(self.RAW, self.DL)
        self.assertEqual(t["title"], "Baby T Park")
        self.assertEqual(t["authors"], ["Lockheart", "Co Maker"])
        self.assertEqual(sorted(t["versions"]), ["1.0.0", "1.0.2"])
        self.assertEqual(t["versions"]["1.0.2"][0], {"download_id": 727, "kind": "lev", "crc32": "abcd1234"})

    def test_live_shape_ints_crc_paging_and_non_track_files(self):
        raw = {"id": 1, "name": "Drive Thru Danger", "author": "Boxic", "track_type": "saphi", "is_active": True}
        dl = [{"id": 10, "type": "lev", "crc32_hash": 1307466109, "version": "1.0.0"},
              {"id": 64, "type": "track_banner", "crc32_hash": 5, "version": None},
              {"id": 339, "type": "sca", "crc32_hash": 255, "version": "1.0.0"}]
        t = saphi.normalize_track(raw, dl)
        self.assertEqual((t["title"], t["authors"], t["category"]), ("Drive Thru Danger", ["Boxic"], "saphi"))
        self.assertEqual(t["versions"], {"1.0.0": [{"download_id": 10, "kind": "lev", "crc32": "4dee597d"},
                                                    {"download_id": 339, "kind": "sca", "crc32": "000000ff"}]})
        pages = {"u": {"data": [1], "meta": {"total_pages": 2}}, "u?page=2": {"data": [2], "meta": {}}}
        self.assertEqual(saphi.fetch_all(lambda url: pages[url], "u", 0, lambda s: None), [1, 2])

    def test_normalize_rejects_rows_without_id_or_title(self):
        self.assertIsNone(saphi.normalize_track({"id": "x", "title": "a"}))
        self.assertIsNone(saphi.normalize_track({"id": 1}))
        self.assertIsNone(saphi.normalize_track("nope"))  # type: ignore[arg-type]

    def test_only_the_pinned_host_and_never_file_downloads(self):
        with self.assertRaises(saphi.SaphiError):
            saphi.http_get_json("https://evil.example/api/v2/tracks")
        with self.assertRaises(saphi.SaphiError):
            saphi.http_get_json("http://www.projectsaphi.com/api/v2/tracks")
        with self.assertRaises(saphi.SaphiError):
            saphi.http_get_json("https://www.projectsaphi.com/api/v2/tracks/1/downloads/727")


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "DATABASE_URL not set")
class WithDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import db
        db.init_db(os.environ["DATABASE_URL"])
        cls.db = db
        cls.conn = db._get_conn()

    def setUp(self):
        self.original_features = dict(config.FEATURES)
        with self.conn.cursor() as cur:
            for t in ("ctr_track_reports", "ctr_track_review_actions", "ctr_track_submissions",
                      "ctr_track_revisions", "ctr_track_entries"):
                cur.execute(f"DELETE FROM {t}")
        self.conn.commit()
        self.admin = self.make_user(admin=True)
        self.user = self.make_user()
        export_dir = tempfile.TemporaryDirectory()
        self.addCleanup(export_dir.cleanup)
        self.export_dir = export_dir.name

    def tearDown(self):
        config.FEATURES.clear()
        config.FEATURES.update(self.original_features)
        self.conn.rollback()

    def make_user(self, admin=False):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO users (discord_id, discord_username, is_admin, is_approved) "
                        "VALUES (%s, %s, %s, %s) RETURNING id",
                        (f"reg-{uuid.uuid4().hex}", "tester", admin, admin))
            uid = cur.fetchone()[0]
        self.conn.commit()
        return uid

    def submit(self, title="Baby T Park", content="a", user=None, **extra):
        body = {"title": title, "credits": [{"name": "Lockheart", "role": "track"}],
                "descriptor": {"content_id": H(content), "revision": "1.0.0",
                               "files": {"lev": {"sha256": H(content), "size": 4}}}, **extra}
        payload = store.clean_submission_payload("new_track", body)
        return store.create_submission(user or self.user, "new_track", payload)

    def approved(self, title="Baby T Park", content="a"):
        sub = self.submit(title, content)
        store.approve_submission(sub["id"], self.admin)
        return store.get_entry(entry_id=store.get_submission(sub["id"])["result_entry_id"])

    # -- migrations ---------------------------------------------------
    def test_migrations_are_idempotent_and_reversible(self):
        from ctr_registry import migrations
        with self.conn.cursor() as cur:
            migrations.apply_up(cur)
            migrations.apply_up(cur)
            migrations.apply_down(cur)
            cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ANY(%s)",
                        (list(migrations.TABLES),))
            self.assertEqual(cur.fetchone()[0], 0)
            cur.execute("SELECT count(*) FROM pg_proc WHERE proname LIKE 'ctr_track_%_freeze'")
            self.assertEqual(cur.fetchone()[0], 0)
            migrations.apply_down(cur)  # down twice is fine
            migrations.apply_up(cur)
            cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ANY(%s)",
                        (list(migrations.TABLES),))
            self.assertEqual(cur.fetchone()[0], len(migrations.TABLES))
        self.conn.commit()

    # -- submissions, approval, promotion ------------------------------
    def test_new_track_flow_assigns_key_then_block_at_promotion(self):
        entry = self.approved()
        self.assertEqual((entry["state"], entry["track_key"], entry["block_index"]), ("approved", "baby-t-park", None))
        revs = store.revisions_for([entry["id"]])[entry["id"]]
        self.assertEqual(revs[0]["hash_state"], "claimed")
        named = store.promote_entry(entry["id"], self.admin)
        self.assertEqual((named["state"], named["block_index"], named["ap_name"]), ("named", 0, "Baby T Park"))

    def test_block_indexes_are_sequential_and_never_reused_after_withdrawal(self):
        ids = [self.approved(f"Track {n}", chr(97 + n))["id"] for n in range(3)]
        got = [store.promote_entry(i, self.admin)["block_index"] for i in ids]
        self.assertEqual(got, [0, 1, 2])
        store.set_state(ids[1], self.admin, "withdraw")
        extra = self.approved("Track Four", "d")
        self.assertEqual(store.promote_entry(extra["id"], self.admin)["block_index"], 3)
        self.assertEqual(store.set_state(ids[1], self.admin, "restore")["state"], "named")
        self.assertEqual(store.get_entry(entry_id=ids[1])["block_index"], 1)

    def test_clash_suffixes_at_promotion(self):
        a = store.promote_entry(self.approved("Crash Cove", "a")["id"], self.admin)
        self.assertEqual(a["ap_name"], "Crash Cove (Custom)")
        b = store.promote_entry(self.approved("Crash Cove", "b")["id"], self.admin)
        self.assertEqual(b["ap_name"], "Crash Cove (Custom, Lockheart)")

    def test_cannot_promote_unapproved_or_twice(self):
        sub = self.submit()
        with self.assertRaises(RuleError):
            store.promote_entry(1_000_000, self.admin)
        entry = self.approved("Other", "b")
        store.promote_entry(entry["id"], self.admin)
        with self.assertRaises(RuleError) as ctx:
            store.promote_entry(entry["id"], self.admin)
        self.assertEqual(ctx.exception.code, "already_named")
        self.assertEqual(store.get_submission(sub["id"])["status"], "pending")

    def test_shipped_name_is_frozen_in_python_and_in_the_database(self):
        entry = self.approved()
        store.promote_entry(entry["id"], self.admin)
        store.mark_shipped("0.3.0", [entry["track_key"]], self.admin)
        with self.assertRaises(RuleError) as ctx:
            store.promote_entry(entry["id"], self.admin, ap_name="Other Name")
        self.assertEqual(ctx.exception.code, "already_named")
        row = store.update_presentation(entry["id"], self.admin, {"display_title": "Better Title"})
        self.assertEqual((row["display_title"], row["ap_name"]), ("Better Title", "Baby T Park"))
        import psycopg2
        for sql in ("UPDATE ctr_track_entries SET ap_name = 'Hacked' WHERE id = %s",
                    "UPDATE ctr_track_entries SET block_index = 99 WHERE id = %s",
                    "UPDATE ctr_track_entries SET track_key = 'hacked' WHERE id = %s",
                    "UPDATE ctr_track_entries SET shipped_in = '9.9' WHERE id = %s"):
            with self.conn.cursor() as cur:
                with self.assertRaises(psycopg2.errors.CheckViolation):
                    cur.execute(sql, (entry["id"],))
            self.conn.rollback()

    def test_name_can_be_corrected_before_shipping(self):
        entry = self.approved()
        store.promote_entry(entry["id"], self.admin)
        self.assertEqual(store.get_entry(entry_id=entry["id"])["ap_name"], "Baby T Park")
        with self.conn.cursor() as cur:  # not shipped: the trigger allows it
            cur.execute("UPDATE ctr_track_entries SET ap_name = 'Baby T Park 2' WHERE id = %s", (entry["id"],))
        self.conn.commit()

    def test_verified_hashes_are_frozen_in_the_database(self):
        entry = self.approved()
        rev = store.revisions_for([entry["id"]])[entry["id"]][0]
        store.attach_evidence(rev["id"], content_id=H("a"), files={"lev": {"sha256": H("a")}},
                              evidence={"verifier_version": "t"}, modes=["time_trial"])
        with self.assertRaises(RuleError):
            store.attach_evidence(rev["id"], content_id=H("b"), files={"lev": {"sha256": H("b")}}, evidence={}, modes=[])
        import psycopg2
        with self.conn.cursor() as cur:
            with self.assertRaises(psycopg2.errors.CheckViolation):
                cur.execute("UPDATE ctr_track_revisions SET files = '{}'::jsonb WHERE id = %s", (rev["id"],))
        self.conn.rollback()

    def test_duplicate_content_is_refused_at_submit(self):
        self.approved()
        with self.assertRaises(RuleError) as ctx:
            self.submit("Same Bytes", "a")
        self.assertEqual(ctx.exception.code, "content_id_exists")

    def test_new_revision_correction_merge_and_reject(self):
        entry = self.approved()
        payload = store.clean_submission_payload("new_revision", {
            "descriptor": {"content_id": H("b"), "files": {"lev": {"sha256": H("b")}}}, "revision": "1.0.3"})
        sub = store.create_submission(self.user, "new_revision", payload, target_entry_id=entry["id"])
        store.approve_submission(sub["id"], self.admin)
        self.assertEqual(len(store.revisions_for([entry["id"]])[entry["id"]]), 2)

        corr = store.create_submission(self.user, "correction", store.clean_submission_payload(
            "correction", {"title": "Baby T-Park"}), target_entry_id=entry["id"])
        store.approve_submission(corr["id"], self.admin)
        self.assertEqual(store.get_entry(entry_id=entry["id"])["display_title"], "Baby T-Park")

        dup = self.submit("Baby T Park Again", "c", revision="2.0.0")
        merged = store.merge_submission(dup["id"], entry["id"], self.admin)
        self.assertEqual(merged["status"], "merged")
        self.assertEqual(len(store.revisions_for([entry["id"]])[entry["id"]]), 3)

        clash = self.submit("Baby T Park Third", "e")  # same revision label 1.0.0
        with self.assertRaises(RuleError) as ctx:
            store.merge_submission(clash["id"], entry["id"], self.admin)
        self.assertEqual(ctx.exception.code, "revision_exists")
        self.assertEqual(store.get_submission(clash["id"])["status"], "pending")  # rolled back

        rej = self.submit("Spam Track", "d")
        self.assertEqual(store.reject_submission(rej["id"], self.admin, "no")["status"], "rejected")
        with self.assertRaises(RuleError):
            store.approve_submission(rej["id"], self.admin)

    def test_review_actions_are_recorded(self):
        entry = self.approved()
        store.promote_entry(entry["id"], self.admin)
        with self.conn.cursor() as cur:
            cur.execute("SELECT array_agg(action ORDER BY id) FROM ctr_track_review_actions WHERE entry_id = %s", (entry["id"],))
            actions = cur.fetchone()[0]
        self.assertEqual(actions, ["approve_submission", "promote"])
        with self.conn.cursor() as cur:
            cur.execute("SELECT action FROM ctr_track_review_actions WHERE submission_id IS NOT NULL ORDER BY id")
            self.assertEqual([r[0] for r in cur.fetchall()], ["submitted", "approve_submission"])

    # -- Saphi import ----------------------------------------------------
    def fake_fetch(self, tracks, downloads):
        def fetch(url):
            if url.endswith("/tracks"):
                return tracks
            tid = int(url.rsplit("/", 2)[-2])
            if tid not in downloads:
                raise RuntimeError("boom")
            return {"downloads": downloads[tid]}
        return fetch

    def test_import_creates_candidates_and_is_idempotent(self):
        pushes = []
        fetch = self.fake_fetch([SaphiNormalizing.RAW], {101: SaphiNormalizing.DL})
        run = lambda: saphi.run_import(fetch, sleep=lambda s: None, notifier=lambda t, m: pushes.append((t, m)))  # noqa: E731
        first = run()
        self.assertEqual((first["created"], first["seen"]), (1, 1))
        entry = store.list_entries(["candidate"])[0]
        self.assertEqual((entry["display_title"], entry["track_key"], entry["source"]), ("Baby T Park", None, "saphi_import"))
        self.assertEqual(len(store.revisions_for([entry["id"]])[entry["id"]]), 2)
        self.assertEqual(run()["unchanged"], 1)
        self.assertEqual(len(store.list_entries(["candidate"])), 1)
        self.assertTrue(pushes)

    def test_import_never_changes_an_approved_entry_and_queues_drift(self):
        fetch = self.fake_fetch([SaphiNormalizing.RAW], {101: SaphiNormalizing.DL})
        saphi.run_import(fetch, sleep=lambda s: None, notifier=lambda t, m: None)
        entry = store.list_entries(["candidate"])[0]
        store.update_presentation(entry["id"], self.admin, {"display_title": "My Edit"})
        approved = store.approve_entry(entry["id"], self.admin)

        changed = copy.deepcopy(SaphiNormalizing.DL)
        changed[0]["crc32"] = "DEADBEEF"
        changed.append({"id": 900, "version": "1.0.3", "type": "lev", "crc32": "00000001"})
        pushes = []
        out = saphi.run_import(self.fake_fetch([{**SaphiNormalizing.RAW, "title": "Renamed On Saphi"}], {101: changed}),
                               sleep=lambda s: None, notifier=lambda t, m: pushes.append(m))
        self.assertEqual(out["drift"], 1)
        after = store.get_entry(entry_id=approved["id"])
        self.assertEqual((after["display_title"], after["state"]), ("My Edit", "approved"))
        self.assertEqual(len(store.revisions_for([approved["id"]])[approved["id"]]), 2)  # no revision added silently
        pending = store.list_submissions(status="pending")
        self.assertEqual({s["payload"]["revision"] for s in pending}, {"1.0.3", "1.0.2+deadbeef"})
        # a second run does not queue the same alerts again
        saphi.run_import(self.fake_fetch([SaphiNormalizing.RAW], {101: changed}), sleep=lambda s: None, notifier=lambda t, m: None)
        self.assertEqual(len(store.list_submissions(status="pending")), 2)
        # approving a drift submission adds a pending revision with locators only
        drift = next(s for s in pending if s["payload"]["revision"] == "1.0.3")
        store.approve_submission(drift["id"], self.admin)
        revs = store.revisions_for([approved["id"]])[approved["id"]]
        self.assertEqual(sorted(r["revision"] for r in revs), ["1.0.0", "1.0.2", "1.0.3"])
        self.assertEqual({r["hash_state"] for r in revs}, {"pending"})
        self.assertTrue(pushes)

    def test_failed_download_listing_skips_the_track_and_skips_missing_pass(self):
        other = {"id": 202, "title": "Other"}
        out = saphi.run_import(self.fake_fetch([SaphiNormalizing.RAW, other], {101: SaphiNormalizing.DL}),
                               sleep=lambda s: None, notifier=lambda t, m: None)
        self.assertEqual((out["created"], out["errors"], out["missing"]), (1, 1, 0))

    def test_missing_tracks_become_source_unavailable_but_a_truncated_list_does_not(self):
        raws = [{"id": i, "title": f"T{i}"} for i in range(1, 11)]
        dls = {i: [] for i in range(1, 11)}
        saphi.run_import(self.fake_fetch(raws, dls), sleep=lambda s: None, notifier=lambda t, m: None)
        out = saphi.run_import(self.fake_fetch(raws[:5], {i: [] for i in range(1, 6)}), sleep=lambda s: None, notifier=lambda t, m: None)
        self.assertEqual(out["missing"], 0)  # half the catalogue missing looks truncated
        self.assertEqual(len(store.list_entries(["source-unavailable"])), 0)
        out = saphi.run_import(self.fake_fetch(raws[:9], {i: [] for i in range(1, 10)}), sleep=lambda s: None, notifier=lambda t, m: None)
        self.assertEqual(out["missing"], 1)
        self.assertEqual(store.list_entries(["source-unavailable"])[0]["display_title"], "T10")

    def test_import_makes_no_file_download_calls(self):
        seen = []
        def fetch(url):
            seen.append(url)
            return [SaphiNormalizing.RAW] if url.endswith("/tracks") else SaphiNormalizing.DL
        saphi.run_import(fetch, sleep=lambda s: None, notifier=lambda t, m: None)
        self.assertTrue(all("/downloads/" not in u for u in seen), seen)

    # -- export from the database ----------------------------------------
    def test_export_from_database_passes_the_checker(self):
        entry = self.approved()
        store.promote_entry(entry["id"], self.admin)
        self.approved("Second", "b")
        out = Path(self.export_dir) / "reg"
        summary = export.write_export(store.record_entries(), str(out))
        self.assertEqual(summary["tracks"], 2)
        self.assertEqual(registry_check.check(out), [])
        named = json.loads((out / "named_tracks.json").read_text())
        self.assertEqual([t["track_key"] for t in named["tracks"]], ["baby-t-park"])

    # -- API -------------------------------------------------------------
    def make_app(self):
        from api.ctr_tracks import bp, _submit_limiter, _report_limiter
        from auth import apply_auth_to_app
        _submit_limiter.reset()
        _report_limiter.reset()
        app = Flask(__name__)
        app.secret_key = "test-only"
        config.DISCORD_CLIENT_ID, config.DISCORD_CLIENT_SECRET = "id", "secret"
        apply_auth_to_app(app)
        app.register_blueprint(bp)
        return app

    def client(self, app, user_id=None):
        c = app.test_client()
        if user_id:
            with c.session_transaction() as s:
                s["user_id"] = user_id
        return c

    def test_everything_is_404_while_the_flag_is_off(self):
        config.FEATURES["ctr_registry"] = False
        c = self.client(self.make_app(), self.admin)
        for method, path in (("get", "/api/ctr/tracks"), ("get", "/api/ctr/tracks/publication"),
                             ("post", "/api/ctr/tracks/submissions"), ("get", "/api/admin/ctr/tracks"),
                             ("get", "/api/ctr/tracks/some-key")):
            self.assertEqual(getattr(c, method)(path).status_code, 404, path)

    def test_flag_defaults_off_in_production_and_on_for_beta(self):
        import importlib
        for label, env, expected in (("", "", False), ("beta", "", True), ("", "true", True), ("beta", "false", False)):
            with mock.patch.dict(os.environ, {"AP_DEPLOYMENT_LABEL": label, "FEATURE_CTR_REGISTRY": env}, clear=False):
                importlib.reload(config)
                self.assertEqual(config.FEATURES["ctr_registry"], expected, (label, env))
        importlib.reload(config)

    def test_read_api_shape_filters_and_etag(self):
        config.FEATURES["ctr_registry"] = True
        entry = self.approved()
        rev = store.revisions_for([entry["id"]])[entry["id"]][0]
        store.attach_evidence(rev["id"], content_id=H("a"), files={"lev": {"sha256": H("a"), "size": 4}},
                              evidence={"level": "static"}, modes=["time_trial"], apworld_min="0.3.0")
        store.promote_entry(entry["id"], self.admin)
        hidden = self.submit("Still Candidate", "z")  # pending submission, not public
        app = self.make_app()
        c = self.client(app)  # anonymous

        body = c.get("/api/ctr/tracks").get_json()
        self.assertEqual(body["schema_version"], 1)
        self.assertEqual((body["total"], body["limit"], body["offset"]), (1, 100, 0))
        track = body["tracks"][0]
        self.assertEqual(track["track_key"], "baby-t-park")
        self.assertEqual(track["ap_name"], "Baby T Park")
        self.assertEqual(track["revisions"][0]["modes"], ["time_trial"])
        self.assertNotIn("descriptor", track["revisions"][0])
        for private in ("reviewed_by", "submitter"):
            self.assertNotIn(private, json.dumps(body))

        self.assertEqual(c.get("/api/ctr/tracks?apworld=0.3.1").get_json()["total"], 1)
        self.assertEqual(c.get("/api/ctr/tracks?apworld=0.2.0").get_json()["total"], 0)
        self.assertEqual(c.get("/api/ctr/tracks?mode=time_trial").get_json()["total"], 1)
        self.assertEqual(c.get("/api/ctr/tracks?mode=arcade").get_json()["total"], 0)
        self.assertEqual(c.get("/api/ctr/tracks?q=lockheart").get_json()["total"], 1)
        self.assertEqual(c.get("/api/ctr/tracks?q=nothing").get_json()["total"], 0)
        self.assertEqual(c.get("/api/ctr/tracks?limit=abc").status_code, 400)

        detail = c.get("/api/ctr/tracks/baby-t-park").get_json()
        self.assertEqual(detail["track"]["credits"][0]["name"], "Lockheart")
        self.assertEqual(c.get("/api/ctr/tracks/nope").status_code, 404)

        desc = c.get(f"/api/ctr/tracks/baby-t-park/revisions/{H('a')}/descriptor").get_json()
        self.assertEqual(desc["fill"]["title"], "Baby T Park")
        self.assertEqual(desc["descriptor"]["content_id"], H("a"))
        self.assertEqual(c.get(f"/api/ctr/tracks/baby-t-park/revisions/{H('9')}/descriptor").status_code, 404)

        pub = c.get("/api/ctr/tracks/publication")
        self.assertEqual(pub.get_json()["schema_version"], 1)
        etag = pub.headers["ETag"]
        self.assertEqual(c.get("/api/ctr/tracks/publication", headers={"If-None-Match": etag}).status_code, 304)
        self.assertEqual(hidden["status"], "pending")

        store.set_state(entry["id"], self.admin, "withdraw")  # withdrawn tracks leave the picker
        self.assertEqual(c.get("/api/ctr/tracks").get_json()["total"], 0)
        self.assertEqual(c.get("/api/ctr/tracks/baby-t-park").status_code, 404)

    def test_submission_endpoint_auth_caps_and_rate_limit(self):
        config.FEATURES["ctr_registry"] = True
        app = self.make_app()
        body = {"kind": "new_track", "title": "Valid Title"}
        self.assertEqual(self.client(app).post("/api/ctr/tracks/submissions", json=body).status_code, 401)
        c = self.client(app, self.user)
        with mock.patch("ctr_registry.notify.push") as push:
            ok = c.post("/api/ctr/tracks/submissions", json=body)
            self.assertEqual(ok.status_code, 201)
            self.assertEqual(push.call_count, 1)
        self.assertEqual(ok.get_json()["status"], "pending")
        self.assertNotIn("submitter", json.dumps(ok.get_json()))
        too_long = c.post("/api/ctr/tracks/submissions", json={**body, "title": "x" * 41})
        self.assertEqual((too_long.status_code, too_long.get_json()["code"]), (400, "title_too_long"))
        self.assertEqual(c.post("/api/ctr/tracks/submissions", json={**body, "kind": "bogus"}).status_code, 400)
        self.assertEqual(c.post("/api/ctr/tracks/submissions", json={"kind": "new_revision", "track_key": "nope",
                                                                     "descriptor": {}}).status_code, 404)
        for _ in range(3):
            self.assertEqual(c.post("/api/ctr/tracks/submissions", json=body).status_code, 201)
        self.assertEqual(c.post("/api/ctr/tracks/submissions", json=body).status_code, 201)  # fifth of five
        limited = c.post("/api/ctr/tracks/submissions", json=body)
        self.assertEqual((limited.status_code, limited.get_json()["code"]), (429, "rate_limited"))
        mine = c.get("/api/ctr/tracks/submissions/mine").get_json()
        self.assertEqual(len(mine["submissions"]), 5)
        self.assertEqual(self.client(app, self.make_user()).get("/api/ctr/tracks/submissions/mine").get_json()["submissions"], [])

    def test_pending_cap_is_a_hard_ceiling_across_workers(self):
        config.FEATURES["ctr_registry"] = True
        app = self.make_app()
        c = self.client(app, self.user)
        for n in range(rules.PENDING_PER_USER_MAX):
            self.submit(f"Pending {n}", chr(97 + n))
        from api.ctr_tracks import _submit_limiter
        _submit_limiter.reset()
        res = c.post("/api/ctr/tracks/submissions", json={"kind": "new_track", "title": "One More"})
        self.assertEqual((res.status_code, res.get_json()["code"]), (429, "pending_cap"))

    def test_report_endpoint(self):
        config.FEATURES["ctr_registry"] = True
        entry = self.approved()
        app = self.make_app()
        self.assertEqual(self.client(app).post("/api/ctr/tracks/baby-t-park/report").status_code, 401)
        c = self.client(app, self.user)
        self.assertEqual(c.post("/api/ctr/tracks/baby-t-park/report", json={"reason": "wrong name"}).get_json()["status"], "reported")
        self.assertEqual(c.post("/api/ctr/tracks/baby-t-park/report").get_json()["status"], "already_reported")
        self.assertEqual(store.get_entry(entry_id=entry["id"])["report_count"], 1)
        self.assertEqual(c.post("/api/ctr/tracks/missing/report").status_code, 404)

    def test_admin_routes_need_an_admin_and_run_the_whole_flow(self):
        config.FEATURES["ctr_registry"] = True
        app = self.make_app()
        sub = self.submit()
        self.assertEqual(self.client(app).get("/api/admin/ctr/track-submissions").status_code, 401)
        self.assertEqual(self.client(app, self.user).get("/api/admin/ctr/track-submissions").status_code, 403)
        a = self.client(app, self.admin)
        queue = a.get("/api/admin/ctr/track-submissions").get_json()["submissions"]
        self.assertEqual([s["id"] for s in queue], [sub["id"]])
        approved = a.post(f"/api/admin/ctr/track-submissions/{sub['id']}/approve", json={"overrides": {"display_title": "Baby T Park"}})
        self.assertEqual(approved.status_code, 200)
        entry = store.get_entry(track_key="baby-t-park")
        edit = a.patch(f"/api/admin/ctr/tracks/{entry['id']}", json={"display_title": "Baby T. Park"})
        self.assertEqual(edit.get_json()["display_title"], "Baby T. Park")
        self.assertEqual(a.patch(f"/api/admin/ctr/tracks/{entry['id']}", json={"ap_name": "X"}).status_code, 409)
        promoted = a.post(f"/api/admin/ctr/tracks/{entry['id']}/promote").get_json()
        self.assertEqual((promoted["block_index"], promoted["ap_name"]), (0, "Baby T. Park"))
        self.assertEqual(a.post(f"/api/admin/ctr/tracks/{entry['id']}/promote").status_code, 409)
        self.assertEqual(a.post("/api/admin/ctr/tracks/mark-shipped", json={"version": "0.3.0", "track_keys": ["baby-t-park"]}).get_json(),
                         {"shipped": ["baby-t-park"]})
        listing = a.get("/api/admin/ctr/tracks?state=named").get_json()["tracks"]
        self.assertEqual(listing[0]["shipped_in"], "0.3.0")
        self.assertEqual(a.post(f"/api/admin/ctr/tracks/{entry['id']}/bogus").status_code, 404)
        self.assertEqual(a.get("/api/admin/ctr/tracks?state=bogus").status_code, 400)

    def test_batch_approval_reports_failures_without_stopping(self):
        config.FEATURES["ctr_registry"] = True
        fetch = self.fake_fetch([{"id": 1, "title": "One"}, {"id": 2, "title": "Two"}], {1: [], 2: []})
        saphi.run_import(fetch, sleep=lambda s: None, notifier=lambda t, m: None)
        ids = [e["id"] for e in store.list_entries(["candidate"])]
        a = self.client(self.make_app(), self.admin)
        res = a.post("/api/admin/ctr/tracks/approve", json={"ids": ids + [999_999]}).get_json()
        self.assertEqual(sorted(res["approved"]), ["one", "two"])
        self.assertEqual(res["failed"][0]["code"], "not_found")
        self.assertEqual(a.post("/api/admin/ctr/tracks/approve", json={"ids": []}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
