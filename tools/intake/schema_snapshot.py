"""Export only completed, hash-matched restricted schema results."""
import argparse
import json
import sys
from pathlib import Path
from ledger import Ledger
import snapshot
from snapshot import write_atomic
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ap-web'))
from apworld_options_parser import BUILDER_SCHEMA_FORMAT_VERSION

# Builder schemas are published for the newest version of each module only;
# ten versions of schemas measured 16.6 MiB against the 5 MiB budget.
SCHEMA_VERSIONS_PER_MODULE = 1


def export(ledger):
    published={r['id'] for r in snapshot.newest_versions(snapshot.export(ledger)['releases'], SCHEMA_VERSIONS_PER_MODULE)}
    records={}
    for row in ledger.db.execute("SELECT jobs.release_id,jobs.result,releases.sha256 FROM jobs JOIN releases ON releases.id=jobs.release_id WHERE kind='schema' AND state='completed'"):
        if row['release_id'] not in published:
            continue
        result=json.loads(row['result'])
        if result.get('sha256')!=row['sha256'] or not isinstance(result.get('schema'),(dict,type(None))):
            raise ValueError('Stored schema result does not match release')
        schema = result['schema']
        if schema is not None and schema.get('_format_version') != BUILDER_SCHEMA_FORMAT_VERSION:
            continue
        if schema is None and result.get('parser_version') != BUILDER_SCHEMA_FORMAT_VERSION:
            continue
        records[row['release_id']]=result
    return {'schema':1,'records':records}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    ledger=Ledger(a.db)
    try:
        write_atomic(a.out,export(ledger))
    finally:
        ledger.db.close()
