"""Regression checks for byte identity, concern preservation and public metadata."""
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ap-web"), str(ROOT / "ap-lib"), str(ROOT / "scripts")]
import security_reviews as reviews
from ap_lib.apworld_index import parse_index_dir
from export_security_evidence import export


def record(**changes):
    result = dict(module="fixture", version="1.0", sha256="a" * 64, status="pass",
                  reviewed_at="2026-09-09T12:00:00Z", method="automated-source-review", report_sha256="b" * 64)
    result.update(changes)
    return result


class EvidenceTests(unittest.TestCase):
    def world(self, **changes):
        version = dict(version="1.0", sha256="a" * 64)
        version.update(changes)
        return dict(name="fixture", versions=[version])

    def test_all_identity_fields_required(self):
        self.assertEqual(reviews.join_reviews(self.world(), [record()])["versions"][0]["security_review"]["status"], "pass")
        for changes in ({"version": "1.1"}, {"sha256": "c" * 64}, {"sha256": None}):
            self.assertIsNone(reviews.join_reviews(self.world(**changes), [record()])["versions"][0]["security_review"])
        world = self.world(); world["name"] = "other"
        self.assertIsNone(reviews.join_reviews(world, [record()])["versions"][0]["security_review"])

    def test_automated_pass_cannot_clear_concern_or_hold(self):
        for status in ("needs_review", "fail", "held"):
            evidence = [record(status=status), record(reviewed_at="2026-09-14T12:00:00Z")]
            self.assertEqual(reviews.join_reviews(self.world(), evidence)["versions"][0]["security_review"]["status"], status)
        accepted = record(status="human_accepted", method="maintainer-decision", reviewed_at="2026-09-14T13:00:00Z")
        evidence = [record(status="held"), accepted]
        self.assertEqual(reviews.join_reviews(self.world(), evidence)["versions"][0]["security_review"]["status"], "human_accepted")
        evidence.append(record(status="held", reviewed_at="2026-09-14T14:00:00Z"))
        self.assertEqual(reviews.join_reviews(self.world(), evidence)["versions"][0]["security_review"]["status"], "held")

    def test_private_or_malformed_fields_rejected(self):
        for changes in ({"report": "PRIVATE REPORT"}, {"status": []}, {"method": []}, {"sha256": "a" * 12}, {"reviewed_at": "2026-02-30T12:00:00Z"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                reviews.validate_catalog({"schema": 1, "records": [record(**changes)]})
        self.assertEqual(reviews.record_id(record()), reviews.record_id(dict(reversed(list(record().items())))))
        self.assertNotEqual(reviews.record_id(record()), reviews.record_id(record(status="fail")))

    def test_rationale_is_bounded_and_original_record_is_preserved(self):
        original = record(status="needs_review")
        enriched = record(status="needs_review", rationale="The review flagged an unchecked archive extraction path. Human assessment is still required.")
        reviews.validate_catalog({"schema": 1, "records": [original, enriched]})
        chosen = reviews.join_reviews(self.world(), [original, enriched])["versions"][0]["security_review"]
        self.assertEqual(chosen["status"], "needs_review")
        self.assertEqual(chosen["rationale"], enriched["rationale"])
        self.assertNotEqual(reviews.record_id(original), reviews.record_id(enriched))
        # A rationale never changes severity or overrides a later review.
        newer = record(status="needs_review", reviewed_at="2026-09-14T12:00:00Z")
        self.assertNotIn("rationale", reviews.join_reviews(self.world(), [enriched, newer])["versions"][0]["security_review"])
        failed = record(status="fail")
        self.assertEqual(reviews.join_reviews(self.world(), [enriched, failed])["versions"][0]["security_review"]["status"], "fail")
        for text in ("One sentence. Two sentences. Three sentences.", "Private source /home/stef/report.md.",
                     "Visit https://example.com for details.", "Not enough", "<script>Bad output.</script>", "A" * 601 + "."):
            with self.subTest(text=text), self.assertRaises(ValueError):
                reviews.validate_catalog({"schema": 1, "records": [record(rationale=text)]})

    def test_module_lock_wins_and_legacy_fallback_only_when_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / "index").mkdir()
            (root / "index/fixture.toml").write_text('name = "Display Name"\n[versions]\n"1.0" = {}\n')
            lock = root / "index.lock"
            lock.write_text('[fixture]\n"1.0" = "' + "A" * 64 + '"\n["Display Name"]\n"1.0" = "' + "b" * 64 + '"\n')
            self.assertEqual(parse_index_dir(root)[0].versions[0].sha256, "a" * 64)
            lock.write_text('["Display Name"]\n"1.0" = "' + "b" * 64 + '"\n')
            self.assertEqual(parse_index_dir(root)[0].versions[0].sha256, "b" * 64)
            lock.write_text('[fixture]\n"1.0" = "invalid"\n["Display Name"]\n"1.0" = "' + "b" * 64 + '"\n')
            self.assertIsNone(parse_index_dir(root)[0].versions[0].sha256)

    def test_export_is_read_only_exact_and_never_contains_private_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); database = root / "audit.db"
            connection = sqlite3.connect(database)
            connection.execute("CREATE TABLE audits (sha256 TEXT, verdict TEXT, report TEXT, audited_at TEXT)")
            connection.execute("INSERT INTO audits VALUES (?, ?, ?, ?)", ("a" * 64, "PASS", "PRIVATE /secret/source.md", "2026-09-09 12:00:00"))
            connection.commit(); connection.close()
            before = database.read_bytes()
            holds = root / "holds.json"
            holds.write_text(json.dumps({"version_holds": {"fixture": {"1.0": "maintainer hold"}}}))
            output = export(database, {"fixture": {"1.0": "a" * 64, "1.1": "c" * 64}}, holds=holds)
            self.assertEqual({r["status"] for r in output["records"]}, {"pass", "held"})
            self.assertEqual({r["version"] for r in output["records"]}, {"1.0"})
            self.assertNotIn("PRIVATE", json.dumps(output)); self.assertNotIn("/secret", json.dumps(output))
            self.assertEqual(before, database.read_bytes())
            self.assertEqual(export(database, {"fixture": {"1.0": "a" * 64}}, holds=holds, previous=output["records"]), output)

    def test_api_reloads_atomic_overlay_and_keeps_immutable_records(self):
        from flask import Flask
        import api.apworlds as api
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); index = root / "index-repo"; (index / "index").mkdir(parents=True)
            (index / "index/fixture.toml").write_text('name = "Fixture"\n[versions]\n"1.0" = {}\n')
            (index / "index.lock").write_text('[fixture]\n"1.0" = "' + "a" * 64 + '"\n')
            seed = root / "seed.json"; overlay = root / "overlay.json"
            seed.write_text(json.dumps({"schema": 1, "records": [record()]}))
            app = Flask(__name__); app.config.update(AP_INDEX_DIR=str(index), AP_WORLDS_DIR=str(root / "worlds"))
            app.register_blueprint(api.bp)
            api._index_cache = api._index_worlds_cache = api._index_lookup_cache = None
            client = app.test_client()
            with patch.object(api, "_review_paths", return_value=(seed, overlay)):
                with app.app_context():
                    self.assertEqual(api._get_index()[0]["versions"][0]["security_review"]["status"], "pass")
                held = record(status="held")
                overlay.write_text(json.dumps({"schema": 1, "records": [held]}))
                with app.app_context():
                    self.assertEqual(api._get_index()[0]["versions"][0]["security_review"]["status"], "held")
                response = client.get("/api/apworlds/security-reviews/" + reviews.record_id(record()))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json["sha256"], "a" * 64)
                self.assertIn("immutable", response.headers["Cache-Control"])
                self.assertEqual(client.get("/api/apworlds/security-reviews/" + "0" * 64).status_code, 404)
                overlay.write_text('{"schema": 1, "records": [{"report": "private"}]}')
                with app.app_context():
                    self.assertEqual(api._get_index()[0]["versions"][0]["security_review"]["status"], "held")

    def test_publisher_refuses_prod_and_validates_before_replace(self):
        from publish_beta_evidence import REMOTE_PUBLISH
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments = [sys.executable, str(ROOT / "scripts/publish_beta_evidence.py"), "--beta-url", "https://ap-pie.com",
                         "--ssh-target", "unused", "--db", "unused", "--holds", "unused", "--emitter", "unused", "--work-dir", str(root / "work")]
            refused = subprocess.run(arguments, capture_output=True)
            self.assertEqual(refused.returncode, 2)
            self.assertFalse((root / "work").exists())
            code = REMOTE_PUBLISH.replace("Path('/app/.state')", "Path(" + repr(str(root)) + ")")
            environment = {"PYTHONPATH": str(ROOT / "ap-web")}
            payload = {"security": {"schema": 1, "records": [record(status="held")]}, "fuzz": {"schema": 1, "records": []}}
            completed = subprocess.run([sys.executable, "-c", code], input=json.dumps(payload), text=True, capture_output=True, env=environment)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            before = (root / "security-evidence.json").read_bytes()
            payload["fuzz"]["records"] = [{"report": "private"}]
            invalid = subprocess.run([sys.executable, "-c", code], input=json.dumps(payload), text=True, capture_output=True, env=environment)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertEqual((root / "security-evidence.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
