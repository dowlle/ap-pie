import tempfile
import unittest
from pathlib import Path
from ledger import Ledger
from coverage import export


class CoverageTests(unittest.TestCase):
    def test_historical_observation_gaps_are_explicit_without_inventing_old_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Ledger(Path(tmp)/'state.db');ledger.register('game',{})
            cid=ledger.discover('game','old','https://github.com/o/r/releases/download/old/game.apworld',None,
                                origin='archived-audit',detail={'historical_checksum_known':False})
            report=export(ledger.db)
            self.assertEqual(report['summary']['audit_gaps'],1)
            self.assertFalse(report['audit_observations'][0]['historical_checksum_known'])
            ledger.verified(cid,'a'*64)
            self.assertEqual(export(ledger.db)['summary']['audit_gaps'],0)
            self.assertIsNone(ledger.db.execute('SELECT expected FROM candidates').fetchone()[0])
            ledger.db.close()
    def test_duplicate_pr_checksum_mismatch_is_reconciled_only_with_verified_held_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Ledger(Path(tmp)/'state.db');ledger.register('game',{})
            url='https://github.com/o/r/releases/download/1/game.apworld'
            original=ledger.discover('game','1',url,'a'*64,origin='pr:1')
            duplicate=ledger.discover('game','1',url,'a'*64,origin='github',revision='asset')
            observed=ledger.record_checksum_mismatch(duplicate,'b'*64)
            self.assertEqual(export(ledger.db,[{'number':1}])['summary']['pr_gaps'],1)
            ledger.verified(observed,'b'*64)
            report=export(ledger.db,[{'number':1}])
            self.assertEqual(report['summary']['pr_gaps'],0)
            self.assertEqual(report['prs'][0]['candidate_states'],{'quarantined':1})
            self.assertEqual(ledger.db.execute('SELECT expected FROM candidates WHERE id=?',(original,)).fetchone()[0],'a'*64)
            self.assertEqual(ledger.status()['holds'],1)
            ledger.db.close()
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
