import json
import hashlib
import ipaddress
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ap-web'),str(ROOT/'ap-lib')]
from flask import Flask
from api import apworlds
import test_discovery


class IntakeAPITests(unittest.TestCase):
    def test_immutable_download_checks_cached_bytes_and_never_fetches_upstream(self):
        payload=b'verified archive fixture'
        self.record['sha256']=hashlib.sha256(payload).hexdigest()
        self.record['id']=hashlib.sha256(json.dumps((self.record['module'],self.record['version'],self.record['sha256']),separators=(',',':')).encode()).hexdigest()
        self.path.write_text(json.dumps({'schema':1,'releases':[self.record]}))
        folder=self.root/'discovery-archives'
        folder.mkdir()
        path=folder/(self.record['sha256']+'.apworld')
        url='/api/apworlds/intake/releases/'+self.record['id']+'/download'
        with patch.object(apworlds,'_fetch_apworld_bytes',side_effect=AssertionError('no upstream request')):
            self.assertEqual(self.client.get(url).status_code,503)
            path.write_bytes(payload)
            response=self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.data,payload)
            self.assertEqual(response.headers['X-Content-SHA256'],self.record['sha256'])
            response.close()
            path.write_bytes(b'mutated')
            self.assertEqual(self.client.get(url).status_code,409)
            self.assertEqual(self.client.get('/api/apworlds/intake/releases/'+'0'*64+'/download').status_code,404)

    def test_published_schema_cache_updates_catalog_builder_choices(self):
        (self.root/'index'/'index').mkdir(parents=True)
        names=['_index_cache','_index_worlds_cache','_index_lookup_cache','_review_stamp','_fuzz_stamp','_discovery_stamp','_schema_stamp']
        previous={name:getattr(apworlds,name) for name in names}
        try:
            for name in names: setattr(apworlds,name,None)
            with self.client.application.app_context(), patch.object(apworlds,'parse_index_dir',return_value=[]):
                self.assertEqual(apworlds._get_index()[0]['builder_versions'],[])
                (self.root/'discovery-schemas.json').write_text(json.dumps({'schema':1,'records':{self.record['id']:{'sha256':'a'*64,'schema':{'game':'Game','options':[]}}}}))
                self.assertEqual(apworlds._get_index()[0]['builder_versions'],[{'version':'2'}])
        finally:
            for name,value in previous.items(): setattr(apworlds,name,value)

    def test_worker_schema_cache_is_served_only_for_matching_release_checksum(self):
        (self.root/'index'/'index').mkdir(parents=True)
        names=['_index_cache','_index_worlds_cache','_index_lookup_cache','_review_stamp','_fuzz_stamp','_discovery_stamp']
        previous={name:getattr(apworlds,name) for name in names}
        cache=self.root/'discovery-schemas.json'
        schema={'game':'Game','options':[]}
        try:
            for name in names: setattr(apworlds,name,None)
            with self.client.application.app_context(), patch.object(apworlds,'parse_index_dir',return_value=[]), patch.object(apworlds,'_fetch_apworld_bytes',side_effect=AssertionError('must not fetch')):
                for digest,expected in [('a'*64,schema),('b'*64,None)]:
                    cache.write_text(json.dumps({'schema':1,'records':{self.record['id']:{'sha256':digest,'schema':schema}}}))
                    rows=apworlds.builder_schemas_for_pins([{'apworld_name':'game','version':'2'}])
                    self.assertEqual(rows[0]['schema'],expected)
                    self.assertEqual(rows[0].get('pending',False),expected is None)
        finally:
            for name,value in previous.items(): setattr(apworlds,name,value)

    def test_explicit_discovered_builder_request_never_fetches_archive(self):
        (self.root/'index'/'index').mkdir(parents=True)
        names=['_index_cache','_index_worlds_cache','_index_lookup_cache','_review_stamp','_fuzz_stamp','_discovery_stamp']
        previous={name:getattr(apworlds,name) for name in names}
        try:
            for name in names: setattr(apworlds,name,None)
            with self.client.application.app_context(), patch.object(apworlds,'parse_index_dir',return_value=[]), patch.object(apworlds,'_fetch_apworld_bytes',side_effect=AssertionError('must not fetch')):
                rows=apworlds.builder_schemas_for_pins([{'apworld_name':'game','version':'2'}])
            self.assertEqual(len(rows),1)
            self.assertIsNone(rows[0]['schema'])
            self.assertTrue(rows[0]['pending'])
        finally:
            for name,value in previous.items(): setattr(apworlds,name,value)

    def test_discovered_download_redirects_to_immutable_cache_without_fetching_package(self):
        (self.root/'index'/'index').mkdir(parents=True)
        names=['_index_cache','_index_worlds_cache','_index_lookup_cache','_review_stamp','_fuzz_stamp','_discovery_stamp']
        previous={name:getattr(apworlds,name) for name in names}
        try:
            for name in names: setattr(apworlds,name,None)
            with patch.object(apworlds,'parse_index_dir',return_value=[]), patch('tracker._resolve_ips',return_value=[ipaddress.ip_address('140.82.112.3')]), patch.object(apworlds.analytics,'record_event'):
                response=self.client.get('/api/apworlds/game/2/download')
            self.assertEqual(response.status_code,302)
            self.assertEqual(response.headers['Location'],'/api/apworlds/intake/releases/'+self.record['id']+'/download')
        finally:
            for name,value in previous.items(): setattr(apworlds,name,value)

    def test_raw_and_game_lookups_follow_replaced_discovery_snapshot(self):
        (self.root/'index'/'index').mkdir(parents=True)
        names=['_index_cache','_index_worlds_cache','_index_lookup_cache','_review_stamp','_fuzz_stamp','_discovery_stamp']
        previous={name:getattr(apworlds,name) for name in names}
        try:
            for name in names: setattr(apworlds,name,None)
            with self.client.application.app_context(), patch.object(apworlds,'parse_index_dir',return_value=[]):
                first=apworlds._get_index_worlds()
                self.assertEqual(first[0].versions[0].version,'2')
                updated={**self.record,'source':{'name':'Renamed Game'}}
                self.path.write_text(json.dumps({'schema':1,'releases':[updated]}))
                lookup=apworlds._get_game_lookup()
                self.assertIn('Renamed Game',lookup)
                self.assertNotIn('Game',lookup)
                self.assertEqual(apworlds._get_index_worlds()[0].display_name,'Renamed Game')
        finally:
            for name,value in previous.items(): setattr(apworlds,name,value)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.record=test_discovery.DiscoveryTests().record()
        self.path=self.root/'discovery.json'
        self.path.write_text(json.dumps({'schema':1,'releases':[self.record],
                                        'queue':{'sources':1,'jobs':{'queued':3}}}))
        app=Flask(__name__)
        app.config.update(TESTING=True,AP_INDEX_DIR=str(self.root/'index'))
        app.register_blueprint(apworlds.bp)
        self.client=app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_status_and_held_record_do_not_imply_a_review_pass(self):
        status=self.client.get('/api/apworlds/intake/status')
        self.assertEqual(status.status_code,200)
        self.assertEqual(status.json['queue']['jobs'],{'queued':3})
        record=self.client.get('/api/apworlds/intake/releases/'+self.record['id'])
        self.assertEqual(record.status_code,200)
        self.assertTrue(record.json['held'])
        self.assertNotIn('security_review',record.json)
        self.assertEqual(record.headers['Cache-Control'],'no-cache')

    def test_missing_and_malformed_identity_return_404(self):
        for digest in ['a'*64,'invalid']:
            self.assertEqual(self.client.get('/api/apworlds/intake/releases/'+digest).status_code,404)

    def test_invalid_replacement_retains_record_and_removal_resets_status(self):
        url='/api/apworlds/intake/releases/'+self.record['id']
        self.assertEqual(self.client.get(url).status_code,200)
        self.path.write_text('{invalid')
        self.assertEqual(self.client.get(url).status_code,200)
        self.path.unlink()
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.get('/api/apworlds/intake/status').json['available_releases'],0)
