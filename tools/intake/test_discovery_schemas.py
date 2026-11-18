import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ap-web'))
import discovery_schemas
from apworld_options_parser import BUILDER_SCHEMA_FORMAT_VERSION as FORMAT


class DiscoverySchemaVersionTests(unittest.TestCase):
    def test_stale_positive_and_negative_results_require_worker_refresh(self):
        version = SimpleNamespace(discovery_id='a'*64, sha256='b'*64)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'schemas.json'
            for schema, parser_version, accepted in [
                ({'game': 'Game', 'options': [], '_format_version': FORMAT}, None, True),
                ({'game': 'Game', 'options': [], '_format_version': 7}, None, False),
                ({'game': 'Game', 'options': []}, None, False),
                (None, None, False), (None, 7, False), (None, FORMAT, True),
            ]:
                with self.subTest(schema=schema, parser_version=parser_version):
                    record = {'sha256': version.sha256, 'schema': schema}
                    if parser_version is not None:
                        record['parser_version'] = parser_version
                    path.write_text(json.dumps({'schema': 1, 'records': {version.discovery_id: record}}))
                    result = discovery_schemas.lookup(path, version)
                    self.assertEqual(result is not None, accepted)
