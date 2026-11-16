import json
import tempfile
import unittest
from pathlib import Path
from ledger import Ledger
import schema_snapshot


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
                                 (row['id'],'schema','completed',json.dumps({'sha256':row['sha256'],'schema':{}})))
            newest=l.db.execute("SELECT id FROM releases WHERE version='0.2.0'").fetchone()['id']
            self.assertEqual(set(schema_snapshot.export(l)['records']),{newest})
            l.db.close()


if __name__=='__main__':
    unittest.main()
