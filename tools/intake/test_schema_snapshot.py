import json
import tempfile
import unittest
from pathlib import Path
from ledger import Ledger
import schema_snapshot
from apworld_options_parser import BUILDER_SCHEMA_FORMAT_VERSION as FORMAT


class SchemaSnapshotTests(unittest.TestCase):
    def test_only_newest_published_version_carries_a_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            l=Ledger(Path(tmp)/'state.db')
            l.register('game',{'name':'Game'})
            for minor in range(3):
                cid=l.discover('game',f'0.{minor}.0',f'https://github.com/o/r/releases/download/0.{minor}.0/game.apworld',origin='source')
                l.db.commit()
                l.verified(cid,f'{minor:064x}')
            with l.db:
                for row in l.db.execute('SELECT id,sha256 FROM releases').fetchall():
                    l.db.execute("INSERT OR REPLACE INTO jobs(release_id,kind,state,result) VALUES(?,?,?,?)",
                                 (row['id'],'schema','completed',json.dumps({'sha256':row['sha256'],'schema':{'_format_version':FORMAT}})))
            newest=l.db.execute("SELECT id FROM releases WHERE version='0.2.0'").fetchone()['id']
            self.assertEqual(set(schema_snapshot.export(l)['records']),{newest})
            checksum=l.db.execute('SELECT sha256 FROM releases WHERE id=?',(newest,)).fetchone()['sha256']
            for schema, parser_version, expected in [
                ({'_format_version':7}, None, set()), (None, None, set()),
                (None, FORMAT, {newest}),
            ]:
                with self.subTest(schema=schema, parser_version=parser_version), l.db:
                    result={'sha256':checksum,'schema':schema}
                    if parser_version is not None:
                        result['parser_version']=parser_version
                    l.db.execute("UPDATE jobs SET result=? WHERE release_id=? AND kind='schema'",
                                 (json.dumps(result),newest))
                    self.assertEqual(set(schema_snapshot.export(l)['records']),expected)
            l.db.close()


if __name__=='__main__':
    unittest.main()
