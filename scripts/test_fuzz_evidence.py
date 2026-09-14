"""Verify exact-result report matching and public-link validation."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ap-web"), str(ROOT / "ap-lib")]
from ap_lib.apworld_index import parse_world_toml
from fuzz_evidence import attach_fuzz_evidence, github_report_url

class FuzzEvidenceTests(unittest.TestCase):
    def world(self, **changes):
        record = dict(version="0.4.1", verdict="broken", fuzzed_at="2026-08-29", seeds=2134, default_rate=1.0, worst_hook="default", worst_hook_rate=1.0)
        record.update(changes)
        return parse_world_toml("crash2", {"name": "Crash 2", "versions": {"0.4.1": {}}, "fuzz_results": [record]})

    def test_exact_historical_result_links_to_published_report(self):
        world = self.world()
        attach_fuzz_evidence(world, "a" * 40)
        result = world.versions[0].fuzz_result.to_dict()
        self.assertEqual(result["report_url"], "https://github.com/dowlle/Archipelago-index/pull/754")
        self.assertIn("/blob/" + "a" * 40 + "/index/crash2.toml", result["record_url"])

    def test_changed_result_does_not_inherit_report(self):
        for changes in ({"fuzzed_at": "2026-09-13"}, {"default_rate": .5}, {"seeds": 5000}, {"worst_hook": "check-ut"}):
            with self.subTest(changes=changes):
                world = self.world(**changes)
                attach_fuzz_evidence(world, None)
                self.assertIsNone(world.versions[0].fuzz_result.report_url)

    def test_explicit_run_provenance_survives(self):
        url = "https://github.com/dowlle/Archipelago-index/actions/runs/123"
        world = self.world(report_url=url)
        attach_fuzz_evidence(world, None)
        self.assertEqual(world.versions[0].fuzz_result.report_url, url)

    def test_non_report_or_unsafe_urls_rejected(self):
        for value in ("javascript:alert(1)", "https://github.com.evil.test/a/b/pull/1", "https://github.com/a/b", "https://example.com/report", 123):
            self.assertIsNone(github_report_url(value))

if __name__ == "__main__":
    unittest.main()
