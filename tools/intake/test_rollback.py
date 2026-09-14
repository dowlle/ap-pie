import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from publish_beta_discovery import ROLLBACK_REMOTE

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ap-web'),str(ROOT/'ap-lib')]


class RollbackTests(unittest.TestCase):
    def test_corrupt_or_invalid_history_never_replaces_current_snapshot(self):
        for corrupt_digest in (True, False):
            with self.subTest(corrupt_digest=corrupt_digest), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                current=root/'discovery.json'
                current.write_text('previous serving snapshot')
                body=json.dumps({'schema':999,'releases':[]}).encode()
                digest='a'*64 if corrupt_digest else hashlib.sha256(body).hexdigest()
                history=root/'discovery-history'
                history.mkdir()
                (history/(digest+'.json')).write_bytes(body)
                code=ROLLBACK_REMOTE.replace("Path('/app/.state')", 'Path('+repr(tmp)+')')
                with patch('sys.stdin',io.StringIO(json.dumps({'digest':digest}))), self.assertRaises(ValueError):
                    exec(code,{})
                self.assertEqual(current.read_text(),'previous serving snapshot')
                self.assertFalse(list(root.glob('discovery.restore.*')))
