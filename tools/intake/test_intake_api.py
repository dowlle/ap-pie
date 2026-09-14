import json
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
    def test_discovered_download_redirects_to_recorded_source_without_fetching_package(self):
        (self.root/'index'/'index').mkdir(parents=True)
        names=['_index_cache','_index_worlds_cache','_index_lookup_cache','_review_stamp','_fuzz_stamp','_discovery_stamp']
        previous={name:getattr(apworlds,name) for name in names}
        try:
            for name in names: setattr(apworlds,name,None)
            with patch.object(apworlds,'parse_index_dir',return_value=[]), patch('tracker._resolve_ips',return_value=[ipaddress.ip_address('140.82.112.3')]), patch.object(apworlds.analytics,'record_event'):
                response=self.client.get('/api/apworlds/game/2/download')
            self.assertEqual(response.status_code,302)
            self.assertEqual(response.headers['Location'],self.record['url'])
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
