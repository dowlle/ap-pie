import tempfile
import unittest
from pathlib import Path
from ledger import Ledger
from coverage import export


class CoverageTests(unittest.TestCase):
    def test_manifest_retains_gaps_and_deduplicates_only_verified_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / 'state.db')
            ledger.register('game', {})
            url = 'https://github.com/o/r/releases/download/1/game.apworld'
            first = ledger.discover('game', '1', url, 'a'*64, origin='pr:1')
            equivalent = ledger.discover('game', '1', url, None, origin='pr:1')
            ledger.verified(first, 'a'*64)
            later = ledger.discover('game', '1', url, None, origin='pr:2', revision='later')
            ledger.hold('game', '1', 'Private policy explanation')
            ledger.register('missing', {})
            report = export(ledger.db, [{'number': 3}])
            game = next(r for r in report['sources'] if r['module'] == 'game')
            self.assertEqual(game['candidate_states'], {'verified': 2, 'queued': 1})
            self.assertEqual(report['summary']['pr_gaps'], 2)
            self.assertEqual(report['summary']['hold_gaps'], 0)
            self.assertNotIn('Private policy', str(report))
            self.assertEqual(next(p for p in report['prs'] if p['number'] == 3)['gap'], 'no_candidate_origin')
            ledger.db.close()


if __name__ == '__main__':
    unittest.main()
