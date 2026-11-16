import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from refresh_sources import refresh, REPO


class SourceRefreshTests(unittest.TestCase):
    def test_unregistered_repository_is_rejected_before_pr_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'index'
            repo.mkdir()
            with patch('refresh_sources.command', return_value='https://github.com/other/repo.git') as command:
                with self.assertRaises(ValueError):
                    refresh(object(), repo, None)
                self.assertEqual(command.call_count, 1)

    def test_all_listed_immutable_heads_are_fetched_and_reconciled(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / 'index'
            repo.mkdir()
            prs = [{'number': 1, 'title': 'Add game 1', 'headRefOid': 'a' * 40},
                   {'number': 2, 'title': 'Add game 2', 'headRefOid': 'b' * 40}]
            calls = []
            def command(args, **kwargs):
                calls.append(args)
                if 'get-url' in args:
                    return REPO
                if args[0] == 'gh':
                    return json.dumps(prs)
                return ''
            with patch('refresh_sources.command', side_effect=command), patch('refresh_sources.reconcile', return_value={'prs': 2}) as reconcile:
                self.assertEqual(refresh(object(), repo, None), {'prs': 2})
                self.assertEqual(reconcile.call_args.args[3], prs)
                fetched = next(args for args in calls if 'fetch' in args)
                self.assertIn('a' * 40, fetched)
                self.assertIn('b' * 40, fetched)
                self.assertEqual(json.loads((repo.parent / 'queued-prs.json').read_text()), prs)
