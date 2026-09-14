import tempfile
import unittest
from pathlib import Path
from ledger import Ledger


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.l = Ledger(Path(self.tmp.name) / 'state.db')
        self.l.register('game', {'setup_guide': 'https://example.com/guide'})
        self.l.db.commit()

    def tearDown(self):
        self.l.db.close()
        self.tmp.cleanup()

    def candidate(self, digest=None, origin='index'):
        cid = self.l.discover('game', '1.0', 'https://github.com/o/r/releases/download/1/game.apworld',
                              digest, origin=origin)
        self.l.db.commit()
        return cid

    def test_unreviewed_verified_release_is_discoverable_and_jobs_independent(self):
        rid = self.l.verified(self.candidate(), 'a' * 64)
        self.assertEqual(self.l.status()['releases'], 1)
        self.assertEqual(self.l.status()['jobs'], {'queued': 3})
        job = self.l.claim('security')
        self.l.finish(rid, 'security', job['token'], {'status': 'fail'})
        self.assertEqual(self.l.status()['releases'], 1)
        self.assertEqual(self.l.status()['jobs'], {'completed': 1, 'queued': 2})

    def test_same_bytes_deduplicate_jobs_and_changed_bytes_do_not_inherit_evidence(self):
        cid = self.candidate()
        first = self.l.verified(cid, 'a' * 64)
        self.assertEqual(first, self.l.verified(self.candidate(origin='pr:42'), 'a' * 64))
        second = self.l.verified(cid, 'b' * 64)
        self.assertNotEqual(first, second)
        self.assertEqual(self.l.status()['jobs'], {'queued': 6})
        self.assertEqual(self.l.db.execute('SELECT count(*) FROM origins').fetchone()[0], 2)

    def test_checksum_mismatch_never_publishes(self):
        with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
            self.l.verified(self.candidate('a' * 64), 'b' * 64)
        self.assertEqual(self.l.status()['releases'], 0)

    def test_expired_worker_cannot_overwrite_reclaimed_job(self):
        rid = self.l.verified(self.candidate(), 'a' * 64)
        old = self.l.claim('generation', now=1, lease_seconds=1)
        new = self.l.claim('generation', now=3)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.l.finish(rid, 'generation', old['token'], {'status': 'pass'}, now=4)
        self.l.finish(rid, 'generation', new['token'], {'status': 'broken'}, now=4)

    def test_expired_lease_cannot_write_even_before_reclaim(self):
        rid = self.l.verified(self.candidate(), 'a' * 64)
        job = self.l.claim('security', now=1, lease_seconds=1)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.l.finish(rid, 'security', job['token'], {'status': 'pass'}, now=3)

    def test_hold_and_existing_guide_survive_source_refresh(self):
        self.l.hold('game', '1.0', 'Explicit unresolved policy')
        self.l.register('game', {'setup_guide': None, 'home': 'https://github.com/o/r'})
        self.l.db.commit()
        self.l.verified(self.candidate(), 'a' * 64)
        self.assertEqual(self.l.status()['holds'], 1)
        self.assertIn('https://example.com/guide', self.l.db.execute('SELECT metadata FROM sources').fetchone()[0])

    def test_backoff_and_permanent_block_are_distinct(self):
        cid = self.candidate()
        self.l.retry_candidate(cid, 'temporary timeout')
        self.assertEqual(self.l.status()['candidates'], {'retry': 1})
        self.l.retry_candidate(cid, 'disallowed download host', permanent=True)
        self.assertEqual(self.l.status()['candidates'], {'blocked': 1})


if __name__ == '__main__':
    unittest.main()
