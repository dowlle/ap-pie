import json
import tempfile
import unittest
from pathlib import Path
from ledger import Ledger
from import_security import process


class SecurityImportTests(unittest.TestCase):
    def test_exact_identity_preserves_conflicting_results_and_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / 'state.db')
            try:
                ledger.register('game', {})
                candidate = ledger.discover('game', '1', 'https://github.com/o/r/releases/download/1/game.apworld', None, origin='index')
                ledger.db.commit()
                release = ledger.verified(candidate, 'a' * 64)
                ledger.hold('game', '1', 'Maintainer decision required')
                ledger.db.commit()
                record = dict(module='game', version='1', sha256='a' * 64,
                              status='fail', reviewed_at='2026-09-14T12:00:00Z',
                              method='automated-source-review', report_sha256='b' * 64)
                self.assertEqual(process(ledger, [record, dict(record, status='pass')]), 1)
                result = json.loads(ledger.db.execute("SELECT result FROM jobs WHERE release_id=? AND kind='security'", (release,)).fetchone()[0])
                self.assertEqual({r['status'] for r in result['records']}, {'fail', 'pass'})
                self.assertEqual(ledger.status()['holds'], 1)
                self.assertEqual(process(ledger, [record]), 0)
            finally:
                ledger.db.close()

    def test_invalid_batch_does_not_claim_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / 'state.db')
            try:
                ledger.register('game', {})
                candidate = ledger.discover('game', '1', 'https://github.com/o/r/releases/download/1/game.apworld', None, origin='index')
                ledger.db.commit()
                ledger.verified(candidate, 'a' * 64)
                before = ledger.status()
                with self.assertRaises(ValueError):
                    process(ledger, [{'module': 'game', 'status': 'pass'}])
                self.assertEqual(ledger.status(), before)
            finally:
                ledger.db.close()
