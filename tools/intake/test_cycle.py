import tempfile
import unittest
from pathlib import Path
from ledger import Ledger
from cycle import cycle


class CycleTests(unittest.TestCase):
    def test_evidence_failure_does_not_delay_or_undo_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp) / 'state.db')
            events = []
            def broken_review():
                events.append('review')
                raise RuntimeError('Private provider details')
            try:
                result = cycle(ledger, scan_sources=lambda: events.append('scan'), verify=lambda: events.append('verify'),
                               publish_discovery=lambda: events.append('publish'),
                               evidence_steps=[('security', broken_review), ('guide', lambda: events.append('guide'))])
                self.assertEqual(events, ['scan', 'verify', 'publish', 'review', 'guide', 'publish'])
                self.assertEqual(result['status'], 'partial')
                row = ledger.db.execute('SELECT * FROM runs').fetchone()
                self.assertIsNotNone(row['finished'])
                self.assertNotIn('Private provider', row['summary'])
            finally:
                ledger.db.close()
