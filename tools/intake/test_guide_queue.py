import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ledger import Ledger
from guide_queue import process, validate_evidence


class GuideQueueTests(unittest.TestCase):
    def test_worker_cannot_publish_an_unrelated_or_private_guide_record(self):
        evidence = {'url': 'https://github.com/other/repo/blob/HEAD/setup.md', 'content_sha256': 'b' * 64,
                    'checked_at': 1, 'kind': 'repository-setup-document'}
        release = {'url': 'https://github.com/o/r/releases/download/1/game.apworld'}
        with self.assertRaises(ValueError):
            validate_evidence(evidence, release, {})
        evidence['url'] = 'https://github.com/o/r/blob/HEAD/setup.md'
        self.assertEqual(validate_evidence(evidence, release, {}), evidence)
        with self.assertRaises(ValueError):
            validate_evidence(dict(evidence, report='/home/private'), release, {})

    def test_missing_document_is_retry_and_does_not_remove_published_guide(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / 'state.db')
            try:
                ledger.register('game', {'setup_guide': 'https://github.com/o/r/blob/main/docs/setup.md'})
                cid = ledger.discover('game', '1', 'https://github.com/o/r/releases/download/1/game.apworld', None, origin='index')
                ledger.db.commit()
                ledger.verified(cid, 'a' * 64)
                with patch('guide_queue.run', return_value={'result': None}):
                    self.assertEqual(process(ledger), 0)
                self.assertEqual(ledger.db.execute("SELECT state FROM jobs WHERE kind='guide'").fetchone()[0], 'retry')
                self.assertIn('docs/setup.md', ledger.db.execute('SELECT metadata FROM sources').fetchone()[0])
            finally:
                ledger.db.close()

    def test_reachable_existing_guide_completes_only_guide_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / 'state.db')
            try:
                ledger.register('game', {'setup_guide': 'https://github.com/o/r'})
                cid = ledger.discover('game', '1', 'https://github.com/o/r/releases/download/1/game.apworld', None, origin='index')
                ledger.db.commit()
                ledger.verified(cid, 'a' * 64)
                with patch('guide_queue.run', return_value={'result': {'url': 'https://github.com/o/r', 'content_sha256': 'b' * 64, 'checked_at': 1, 'kind': 'existing-link-reachable'}}):
                    self.assertEqual(process(ledger), 1)
                self.assertEqual(ledger.status()['jobs'], {'completed': 1, 'queued': 3})
            finally:
                ledger.db.close()
