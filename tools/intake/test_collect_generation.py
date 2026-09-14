import base64
import json
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from ledger import Ledger
from collect_generation import collect, collect_incremental


class ActionsCollectionTests(unittest.TestCase):
    def test_refresh_limit_rotates_past_failures_and_repairs_invalid_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ledger=Ledger(root/'state.db');cache=root/'cache'
            prs=[{'number':i,'headRefOid':'a'*40} for i in (1,2,3)]
            def refresh(ledger,rows,producer):
                if rows[0]['number']==1:raise TimeoutError('private error')
                return {'schema':1,'records':[]}
            with patch('collect_generation.collect',side_effect=refresh) as fetch:
                collect_incremental(ledger,prs,None,cache,limit=2)
                self.assertEqual([call.args[1][0]['number'] for call in fetch.call_args_list],[1,2])
                fetch.reset_mock()
                collect_incremental(ledger,prs,None,cache,limit=2)
                self.assertEqual([call.args[1][0]['number'] for call in fetch.call_args_list],[3])
                (cache/('2-'+'a'*40+'.json')).write_text('{bad cache')
                fetch.reset_mock()
                collect_incremental(ledger,prs,None,cache,limit=2)
                self.assertEqual([call.args[1][0]['number'] for call in fetch.call_args_list],[2])
            self.assertTrue(json.loads((cache/('1-'+'a'*40+'.json')).read_text())['retry'])
            ledger.db.close()
    def test_run_checksum_selects_exact_release_among_mutated_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp)/'state.db')
            ledger.register('game', {})
            for digest in ('a'*64, 'b'*64):
                candidate = ledger.discover('game', '1', 'https://github.com/o/r/releases/download/1/game.apworld', digest, origin='pr:1')
                ledger.verified(candidate, digest)
            check = {'name':'matrix', 'conclusion':'SUCCESS', 'detailsUrl':'https://github.com/dowlle/Archipelago-index/actions/runs/123/job/456'}
            def gh(*args):
                if args[0]=='pr':return {'headRefOid':'c'*40,'statusCheckRollup':[check]}
                if args[0]=='run':return {'headSha':'c'*40,'status':'completed'}
                return {'content':base64.b64encode(('[game]\n"1" = "'+'a'*64+'"\n').encode()).decode()}
            verdict={'verdict':'clean','default_rate':1.0,'worst_hook':None,'worst_hook_rate':None,'seeds':1,'fuzzed_at':'2026-09-14T00:00:00Z'}
            producer=SimpleNamespace(parse_check_name=lambda name:('game','1','default'),_pull_pr_verdict_from_checks=lambda *args:verdict)
            with patch('collect_generation.gh_json',side_effect=gh),patch('collect_generation.validate',side_effect=lambda rows:rows):
                result=collect(ledger,[{'number':1,'headRefOid':'c'*40},{'number':2,'headRefOid':'c'*40}],producer)
            self.assertEqual(len(result['records']),1)
            self.assertEqual(result['records'][0]['sha256'],'a'*64)
            ledger.db.close()


if __name__ == '__main__':
    unittest.main()
