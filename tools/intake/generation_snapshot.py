"""Export completed checksum-matched generation evidence for beta overlay."""
import argparse
import json
from pathlib import Path
from ledger import Ledger
from import_generation import validate
from snapshot import write_atomic


def export(ledger, previous=()):
    records = {json.dumps(r, sort_keys=True): r for r in validate(list(previous))}
    for row in ledger.db.execute("SELECT jobs.result,releases.module,releases.version,releases.sha256 FROM jobs JOIN releases ON releases.id=jobs.release_id WHERE kind='generation' AND state='completed'"):
        for record in validate(json.loads(row['result'])['records']):
            if (record['module'], record['version'], record['sha256']) != (row['module'], row['version'], row['sha256']):
                raise ValueError('Stored generation evidence does not match release')
            records[json.dumps(record, sort_keys=True)] = record
    return {'schema': 1, 'records': validate(list(records.values()))}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--previous', type=Path, action='append', default=[])
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    ledger = Ledger(a.db)
    try:
        previous = [r for path in a.previous for r in json.loads(path.read_text())['records']]
        write_atomic(a.out, export(ledger, previous))
    finally:
        ledger.db.close()
