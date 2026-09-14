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
    def test_index_stored_url_requires_canonical_repository_and_full_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'discovery.json'
            record=self.record()
            base='https://raw.githubusercontent.com/dowlle/Archipelago-index/'
            for suffix,valid in [('b'*40+'/apworlds/Game%20Name.apworld',True),('main/apworlds/game.apworld',False),('b'*40+'/private/game.apworld',False)]:
                record['url']=base+suffix
                path.write_text(json.dumps({'schema':1,'releases':[record]}))
                if valid:self.assertEqual(len(discovery.load(path)['releases']),1)
                else:
                    with self.assertRaises(ValueError):discovery.load(path)

    def test_module_hold_applies_to_accepted_versions_without_discovery_record(self):
        original=APWorldInfo(name='game',display_name='Game',versions=[APWorldVersion('1'),APWorldVersion('2')])
        world=discovery.merge([original],{'releases':[],'policies':[{'module':'game','version':'*'}]})[0]
        public=discovery.attach_public_metadata(world,world.to_dict())
        self.assertTrue(all(v['policy_hold'] for v in public['versions']))
        self.assertTrue(all('discovery' not in v for v in public['versions']))
        self.assertFalse(hasattr(original.versions[0],'policy_held'))

    def test_exact_policy_hold_does_not_inherit_to_another_version(self):
        original=APWorldInfo(name='game',display_name='Game',versions=[APWorldVersion('1'),APWorldVersion('2')])
        world=discovery.merge([original],{'releases':[],'policies':[{'module':'game','version':'1'}]})[0]
        public=discovery.attach_public_metadata(world,world.to_dict())
        self.assertTrue(public['versions'][0]['policy_hold'])
        self.assertIsNone(public['versions'][1]['policy_hold'])

    def test_policy_private_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'discovery.json'
            path.write_text(json.dumps({'schema':1,'releases':[],'policies':[{'module':'game','version':'1','reason':'private'}]}))
            with self.assertRaises(ValueError):discovery.load(path)

    def test_private_or_invalid_queue_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'discovery.json'
            for queue in [{'error':'private'}, {'sources':-1}, {'jobs':{'secret':1}}, {'holds':True}]:
                p.write_text(json.dumps({'schema':1,'releases':[],'queue':queue}))
                with self.assertRaises(ValueError): discovery.load(p)

    def test_matching_accepted_bytes_still_receive_the_independent_hold(self):
        original=APWorldInfo(name='game',display_name='Game',versions=[APWorldVersion('2',url=self.record()['url'],sha256='a'*64)])
        merged=discovery.merge([original],{'releases':[self.record()]})[0]
        public=discovery.attach_public_metadata(merged,merged.to_dict())
        self.assertTrue(public['versions'][0]['discovery']['held'])
        self.assertEqual(len(merged.versions),1)

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
        public=discovery.attach_public_metadata(w,w.to_dict())
        self.assertTrue(public['versions'][0]['discovery']['held'])
        self.assertNotIn('security_review',public['versions'][0])
        self.assertNotIn('discovery',public['versions'][1])

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
