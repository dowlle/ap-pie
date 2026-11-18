import tempfile
import unittest
from pathlib import Path
from ledger import Ledger
from verify_queue import batch_rows, run_batch


class BulkTests(unittest.TestCase):
    def test_batch_spreads_sources_deduplicates_and_preserves_failure_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp)/'state.db')
            for module in ('one', 'two', 'three'):
                ledger.register(module, {})
                for version in ('1', '2'):
                    url = f'https://github.com/o/r/releases/download/{version}/{module}.apworld'
                    ledger.discover(module, version, url, None, origin='index')
                    ledger.discover(module, version, url, None, origin='github', revision='duplicate')
            ledger.db.commit()
            rows = batch_rows(ledger, 3)
            self.assertEqual(len({r['module'] for r in rows}), 3)
            self.assertEqual(len(batch_rows(ledger, 20)), 6)
            def download(row, archives):
                if row['module'] == 'two':raise TimeoutError('private network detail')
                return {'status':'verified', 'sha256':'a'*64}
            results = run_batch(ledger, rows, Path(tmp)/'archives', workers=2, download=download)
            self.assertEqual(ledger.status()['releases'], 2)
            self.assertEqual(sum(r['status'] == 'retry' for r in results), 1)
            self.assertNotIn('private network', str(results))
            ledger.db.close()


if __name__ == '__main__':
    unittest.main()
