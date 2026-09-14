import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ap-web'),str(ROOT/'ap-lib')]
import discovery
from ap_lib.apworld_index import APWorldInfo, APWorldVersion
from builtin_builder import build_versions


class DiscoveryTests(unittest.TestCase):
    def test_invalid_replacement_preserves_last_valid_snapshot_and_removal_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'discovery.json'
            p.write_text(json.dumps({'schema':1,'releases':[self.record()]}))
            self.assertEqual(len(discovery.load_for_serving(p)['releases']),1)
            p.write_text('{malformed')
            self.assertEqual(len(discovery.load_for_serving(p)['releases']),1)
            p.unlink()
            self.assertEqual(discovery.load_for_serving(p)['releases'],[])

    def record(self):
        r={'module':'game','version':'2','sha256':'a'*64,'url':'https://github.com/o/r/releases/download/2/game.apworld',
           'source':{'name':'Game'},'held':True,'verified_at':1}
        r['id']=hashlib.sha256(json.dumps(('game','2','a'*64),separators=(',',':')).encode()).hexdigest()
        return r

    def test_new_release_is_visible_but_not_eligible_for_request_time_builder(self):
        original=APWorldInfo(name='game',display_name='Game',setup_guide='https://example.com/guide',
                             versions=[APWorldVersion('1',url='https://github.com/o/r/releases/download/1/game.apworld')])
        w=discovery.merge([original],{'releases':[self.record()]})[0]
        self.assertEqual([v.version for v in w.versions],['2','1'])
        self.assertEqual(build_versions(w),[{'version':'1'}])
        self.assertTrue(w.versions[0].discovery_held)
        self.assertEqual(w.setup_guide,original.setup_guide)
        self.assertEqual(len(original.versions),1)

    def test_invalid_identity_or_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'discovery.json'
            r=self.record()
            p.write_text(json.dumps({'schema':1,'releases':[r]}))
            self.assertEqual(len(discovery.load(p)['releases']),1)
            r['url']='javascript:alert(1)'
            p.write_text(json.dumps({'schema':1,'releases':[r]}))
            with self.assertRaises(ValueError): discovery.load(p)

    def test_malformed_timestamp_source_and_job_metadata_are_rejected(self):
        changes=[{'verified_at':float('nan')},{'verified_at':True},{'source':{'name':[]}},
                 {'source':{'setup_guide':'javascript:alert(1)'}},{'jobs':{'security':'approved'}},
                 {'url':'https://github.com/o/r/issues/1'}, {'sha256':42}]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'discovery.json'
            for change in changes:
                with self.subTest(change=change):
                    p.write_text(json.dumps({'schema':1,'releases':[{**self.record(),**change}]}))
                    with self.assertRaises(ValueError): discovery.load(p)
