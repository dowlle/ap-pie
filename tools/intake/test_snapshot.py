import json
import tempfile
import unittest
from pathlib import Path
from ledger import Ledger
from snapshot import export, write_atomic


class SnapshotTests(unittest.TestCase):
    def test_failed_audit_observations_remain_unverified_and_scrubbed(self):
        with tempfile.TemporaryDirectory() as tmp:
            l=Ledger(Path(tmp)/'state.db')
            l.register('game',{'name':'Game'})
            cid=l.discover('game','1','https://github.com/o/r/releases/download/1/game.apworld',origin='recorded-audit',detail={'private':'secret'})
            l.db.execute("UPDATE candidates SET state='blocked',error='/private/report: Unsafe archive member' WHERE id=?",(cid,))
            l.db.commit()
            data=export(l)
            self.assertEqual(data['releases'],[])
            item=data['observations'][0]
            self.assertFalse(item['verified'])
            self.assertIsNone(item['expected_sha256'])
            self.assertEqual(item['reason'],'archive_verification_rejected')
            self.assertNotIn('private',json.dumps(data))
            l.verified(cid,'a'*64)
            self.assertEqual(export(l)['observations'],[])
            l.db.close()
    def test_pending_candidate_is_not_a_verified_download_and_private_fields_are_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            l=Ledger(Path(tmp)/'state.db')
            l.register('game', {'name':'Game','setup_guide':'https://example.com/guide','private':'secret'})
            l.hold('game','1','private policy text')
            cid=l.discover('game','1','https://github.com/o/r/releases/download/1/game.apworld',origin='pr:1')
            l.db.commit()
            self.assertEqual(export(l)['releases'],[])
            l.verified(cid,'a'*64)
            result=export(l)
            self.assertTrue(result['releases'][0]['held'])
            self.assertEqual(result['releases'][0]['jobs']['security'],'queued')
            self.assertNotIn('private',json.dumps(result))
            out=Path(tmp)/'discovery.json'
            write_atomic(out,result)
            self.assertEqual(json.loads(out.read_text()),result)
            l.db.close()

    def test_same_version_changed_bytes_retain_two_immutable_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            l=Ledger(Path(tmp)/'state.db')
            l.register('game',{'name':'Game'})
            cid=l.discover('game','1','https://github.com/o/r/releases/download/1/game.apworld',origin='source')
            l.db.commit()
            l.verified(cid,'a'*64)
            l.verified(cid,'b'*64)
            self.assertEqual(len(export(l)['releases']),2)
            l.db.close()
