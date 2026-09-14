import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'ap-web'),str(ROOT/'ap-lib')]
from flask import Flask
from api import apworlds
import test_discovery


class IntakeAPITests(unittest.TestCase):
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
