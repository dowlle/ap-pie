import tempfile
import unittest
from pathlib import Path
from ledger import Ledger
from register_sources import register


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.l=Ledger(Path(self.tmp.name)/'state.db')
        self.r={'module':'game','name':'Game','version':'1','url':'https://github.com/o/r/releases/download/1/game.apworld'}

    def tearDown(self):
        self.l.db.close()
        self.tmp.cleanup()

    def test_invalid_batch_does_not_register_earlier_valid_record(self):
        with self.assertRaises(ValueError):register(self.l,[self.r,{**self.r,'module':'../escape'}])
        self.assertEqual(self.l.status()['sources'],0)

    def test_duplicate_submission_deduplicates_and_preserves_existing_guide(self):
        self.l.register('game',{'setup_guide':'https://example.com/guide'})
        self.l.db.commit()
        register(self.l,[self.r])
        register(self.l,[self.r])
        self.assertEqual(self.l.status()['candidates'],{'queued':1})
        self.assertEqual(self.l.status()['releases'],0)
        self.assertIn('https://example.com/guide',self.l.db.execute('SELECT metadata FROM sources').fetchone()[0])
