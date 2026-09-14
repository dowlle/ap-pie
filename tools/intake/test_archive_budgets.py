import tempfile
import unittest
import zipfile
from pathlib import Path
from artifact_worker import inspect_archive, InvalidArtifact, MAX_SOURCE


class ArchiveBudgetTests(unittest.TestCase):
    def test_binary_members_can_exceed_python_budget_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'game.apworld'
            with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
                archive.writestr('game/__init__.py', 'raise RuntimeError("must never execute")')
                archive.writestr('game/native/library.so', b'x' * (MAX_SOURCE + 1))
            self.assertEqual(inspect_archive(path)['python_files'], 1)

    def test_large_python_source_remains_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'game.apworld'
            with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
                archive.writestr('game/__init__.py', b'x' * (MAX_SOURCE + 1))
            with self.assertRaisesRegex(InvalidArtifact, 'Python source member'):
                inspect_archive(path)
