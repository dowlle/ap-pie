import tempfile
import unittest
from pathlib import Path
from reconcile import archived_audit_observations, standing_holds, add_world
from ledger import Ledger


class ArchiveMetadataTests(unittest.TestCase):
    def test_index_stored_artifact_is_pinned_and_requires_download_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Ledger(Path(tmp)/'state.db')
            data={'name':'Twilight Princess','versions':{'1':{'local':'../apworlds/Twilight Princess-1.apworld'}}}
            count=add_world(ledger,'Twilight Princess',data,{'Twilight Princess':{'1':'a'*64}},'index',{'commit':'b'*40})
            row=dict(ledger.db.execute('SELECT * FROM candidates').fetchone())
            self.assertEqual(count,1)
            self.assertEqual(row['url'],'https://raw.githubusercontent.com/dowlle/Archipelago-index/'+'b'*40+'/apworlds/Twilight%20Princess-1.apworld')
            self.assertEqual(row['expected'],'a'*64)
            self.assertEqual(ledger.status()['releases'],0)
            for local in ('../private/game.apworld','../apworlds/../../game.apworld','../apworlds/sub/game.apworld'):
                data['versions']['1']['local']=local
                with self.assertRaises(ValueError):add_world(ledger,'Twilight Princess',data,{},'index',{'commit':'b'*40})
            ledger.db.close()

    def test_retired_source_remains_registered_without_new_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=Ledger(Path(tmp)/'state.db')
            count=add_world(ledger,'game',{'disabled':True,'versions':{'1':{'url':'https://github.com/o/r/releases/download/1/game.apworld'}}},{},'index',{})
            self.assertEqual(count,0)
            self.assertEqual(ledger.status()['sources'],1)
            ledger.db.close()

    def test_historical_unknown_hash_is_not_invented_from_current_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'1 — Audit.md').write_text('---\napworld: game\nversion: "1"\nverdict: FAIL\n---\nPrivate report body. https://github.com/o/r/releases/download/1/game.apworld?token=private\n')
            rows=archived_audit_observations(root)
            self.assertEqual(len(rows),1)
            self.assertIsNone(rows[0]['sha256'])
            self.assertFalse(rows[0]['historical_checksum_known'])
            self.assertEqual(rows[0]['url'],'https://github.com/o/r/releases/download/1/game.apworld')
            self.assertNotIn('report',rows[0])

    def test_archive_link_to_another_version_is_not_associated_with_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'1 — Audit.md').write_text('---\napworld: game\nversion: "1"\nverdict: FAIL\n---\nhttps://github.com/o/r/releases/download/2/game.apworld\n')
            self.assertEqual(archived_audit_observations(root),[])

    def test_active_watchlist_holds_exclude_historical_fuzz_rejections(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'watch.md'
            p.write_text('## Historical\n| old | 1 | FAIL |\n## Blocked at the audit gate\n| APworld | Version | Verdict |\n| game | 2 | FAIL | reason |\n| another | 3 | NEEDS_REVIEW, existing hold retained | reason |\n## Process when filing\n')
            self.assertEqual(standing_holds(p),[('game','2'),('another','3')])


if __name__ == '__main__':
    unittest.main()
