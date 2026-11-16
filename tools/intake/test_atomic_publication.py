import json
import tempfile
import unittest
from pathlib import Path
from snapshot import write_atomic


class AtomicPublicationTests(unittest.TestCase):
    def test_rejected_snapshot_preserves_previous_bytes_and_cleans_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'discovery.json'
            path.write_text('previous valid snapshot')
            def reject(staged):
                self.assertEqual(json.loads(staged.read_text()), {'schema': 1})
                raise ValueError('Invalid release')
            with self.assertRaises(ValueError):
                write_atomic(path, {'schema': 1}, validate=reject)
            self.assertEqual(path.read_text(), 'previous valid snapshot')
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_validation_occurs_before_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'discovery.json'
            path.write_text('old')
            def validate(staged):
                self.assertEqual(path.read_text(), 'old')
                self.assertEqual(json.loads(staged.read_text()), {'schema': 1})
            write_atomic(path, {'schema': 1}, validate=validate)
            self.assertEqual(json.loads(path.read_text()), {'schema': 1})
