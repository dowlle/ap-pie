import sqlite3
import json
import tempfile
import unittest
from pathlib import Path
from ledger import Ledger
from cached_security import export


class CachedSecurityTests(unittest.TestCase):
    def test_changed_bytes_keep_distinct_reviews_and_private_report_is_not_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / 'state.db')
            cache = Path(tmp) / 'audits.db'
            try:
                ledger.register('game', {})
                cid = ledger.discover('game', '1', 'https://github.com/o/r/releases/download/1/game.apworld', None, origin='index')
                ledger.db.commit()
                ledger.verified(cid, 'a' * 64)
                ledger.verified(cid, 'b' * 64)
                with sqlite3.connect(cache) as db:
                    db.execute('CREATE TABLE audits(sha256 TEXT,verdict TEXT,report TEXT,audited_at TEXT)')
                    db.executemany('INSERT INTO audits VALUES(?,?,?,?)', [('a' * 64, 'PASS', 'private report one', '2026-09-14T10:00:00'), ('b' * 64, 'FAIL', 'private report two', '2026-09-14T11:00:00')])
                records = export(ledger, cache)
                self.assertEqual({r['sha256']: r['status'] for r in records}, {'a' * 64: 'pass', 'b' * 64: 'fail'})
                self.assertNotIn('private report', str(records))
                report = Path(tmp) / 'qa.md'
                report.write_text('private QA explanation')
                summary = Path(tmp) / 'summary.json'
                item = {'module': 'game', 'version': '1', 'sha256': 'a' * 64, 'status': 'NEEDS_REVIEW', 'report': str(report), 'qa': True}
                summary.write_text(json.dumps({'results': [item, dict(item, sha256='c' * 64, report='/missing/private-report')]}))
                enriched = export(ledger, cache, [summary])
                self.assertEqual({r['status'] for r in enriched if r['sha256'] == 'a' * 64}, {'pass', 'needs_review'})
                self.assertEqual(len(enriched), 3)
                self.assertEqual(enriched[-1]['method'], 'source-review-with-qa')
                self.assertNotIn('private QA explanation', str(enriched))
                with sqlite3.connect(cache) as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM audits').fetchone()[0], 2)
            finally:
                ledger.db.close()
