import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'ap-web'),
                str(Path(__file__).resolve().parents[1] / 'ap-lib')]
from flask import Flask
from ap_lib.apworld_index import APWorldInfo
from api import apworlds
from builtin_builder import builtin_record, build_versions

class BuiltinBuilderTests(unittest.TestCase):
    def setUp(self):
        self.world = APWorldInfo(name='sm', display_name='Super Metroid', game_name='Super Metroid', supported=True)
        self.app = Flask(__name__)
        self.app.secret_key = 'test-only'
        self.app.register_blueprint(apworlds.bp)

    def test_builtin_endpoint_returns_frozen_options_without_fetch_or_cache(self):
        with patch.object(apworlds, '_get_index_worlds', return_value=[self.world]), \
             patch.object(apworlds, '_fetch_apworld_bytes', side_effect=AssertionError('No remote fetch')), \
             patch('db.get_builder_schema', side_effect=AssertionError('No DB schema lookup')), \
             patch.object(apworlds.analytics, 'record_event'):
            result = self.app.test_client().get('/api/apworlds/sm/builder-schema')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['version'], '0.6.7')
        self.assertEqual(result.json['source'], 'builtin')
        self.assertEqual(result.json['schema']['ap_version'], '0.6.7')
        options = {o['name']: o for o in result.json['schema']['options']}
        self.assertEqual(options['custom_preset']['type'], 'dict')
        self.assertEqual(options['custom_preset']['default'], {'controller': {}, 'knows': {}, 'settings': {}})
        self.assertNotIn('accessibility', options)
        self.assertEqual(self.world.versions, [])

    def test_wrong_version_disabled_and_identity_mismatch_do_not_use_bundle(self):
        self.assertIsNone(builtin_record(self.world, '0.6.6'))
        self.world.disabled = True
        self.assertIsNone(builtin_record(self.world))
        self.world.disabled = False
        self.world.game_name = 'Another game'
        self.assertIsNone(builtin_record(self.world))

    def test_explicit_wrong_version_is_404(self):
        with patch.object(apworlds, '_get_index_worlds', return_value=[self.world]):
            self.assertEqual(self.app.test_client().get('/api/apworlds/sm/builder-schema?version=0.6.6').status_code, 404)

    def test_catalog_build_versions_do_not_invent_downloads(self):
        self.assertEqual(build_versions(self.world), [{'version': '0.6.7'}])
        self.assertEqual(self.world.to_dict()['downloadable_versions'], [])

if __name__ == '__main__':
    unittest.main()
