import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from artifact_worker import InvalidArtifact, validate_url, inspect_archive, MAX_MEMBER


class ArtifactTests(unittest.TestCase):
    def test_reject_non_registered_hosts_credentials_private_addresses_and_ports(self):
        for url in ['http://github.com/x', 'https://localhost/x', 'https://github.com.evil.test/x',
                    'https://user:password@github.com/x', 'https://github.com:444/x']:
            with self.subTest(url=url), self.assertRaises(InvalidArtifact):
                validate_url(url, resolve=False)
        with patch('socket.getaddrinfo', return_value=[(None,None,None,None,('127.0.0.1',443))]):
            with self.assertRaises(InvalidArtifact):
                validate_url('https://github.com/o/r/releases/download/v/a.apworld')

    def archive(self, entries):
        f = tempfile.NamedTemporaryFile()
        with zipfile.ZipFile(f.name, 'w') as z:
            for name, body in entries:
                z.writestr(name, body)
        self.addCleanup(f.close)
        return Path(f.name)

    def test_valid_source_package_is_inspected_without_execution(self):
        p = self.archive([('world/__init__.py', 'raise RuntimeError("must never execute")'),
                          ('world/readme.txt', 'Guide')])
        self.assertEqual(inspect_archive(p)['python_files'], 1)

    def test_traversal_windows_paths_duplicate_and_oversized_members_rejected(self):
        for name in ['../escape.py', '/absolute.py', 'C:/escape.py', 'world\\escape.py']:
            with self.subTest(name=name), self.assertRaises(InvalidArtifact):
                inspect_archive(self.archive([(name,'pass')]))
        with self.assertRaises(InvalidArtifact):
            inspect_archive(self.archive([('world/a.py','pass'),('world/a.py','pass')]))
        with self.assertRaises(InvalidArtifact):
            inspect_archive(self.archive([('world/a.py',b'x'*(MAX_MEMBER+1))]))

    def test_binary_only_packages_are_explicitly_blocked(self):
        with self.assertRaisesRegex(InvalidArtifact,'No reviewable'):
            inspect_archive(self.archive([('world/a.pyc',b'compiled')]))


if __name__ == '__main__':
    unittest.main()
