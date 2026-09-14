import hashlib
import tempfile
import unittest
from pathlib import Path
from verify_queue import store_artifact


class ArtifactStorageTests(unittest.TestCase):
    def test_destination_staging_is_durable_idempotent_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'download'
            source.write_bytes(b'verified bytes')
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            target = store_artifact(source, root / 'archives', digest)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(target.stat().st_mode & 0o777, 0o444)
            self.assertTrue(source.exists())
            self.assertEqual(store_artifact(source, root / 'archives', digest), target)
            self.assertEqual(list((root / 'archives').iterdir()), [target])

    def test_checksum_mismatch_never_publishes_or_leaves_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'download'
            source.write_bytes(b'wrong bytes')
            with self.assertRaises(RuntimeError):
                store_artifact(source, root / 'archives', 'a' * 64)
            self.assertEqual(list((root / 'archives').iterdir()), [])
