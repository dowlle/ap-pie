"""Export completed security evidence without weakening prior dispositions."""
import argparse
import json
import sys
from pathlib import Path
from ledger import Ledger
from snapshot import write_atomic

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ap-web'))
from security_reviews import load_catalog, record_id, validate_catalog


def export(ledger, previous=()):
    records = {record_id(r): r for r in validate_catalog({'schema': 1, 'records': list(previous)})}
    for row in ledger.db.execute("SELECT jobs.result,releases.module,releases.version,releases.sha256 FROM jobs JOIN releases ON releases.id=jobs.release_id WHERE kind='security' AND state='completed'"):
        result = json.loads(row['result'])
        batch = validate_catalog({'schema': 1, 'records': result['records']})
        for record in batch:
            if (record['module'], record['version'], record['sha256']) != (row['module'], row['version'], row['sha256']):
                raise ValueError('Stored security result does not match release')
            records[record_id(record)] = record
    payload = {'schema': 1, 'records': sorted(records.values(), key=record_id)}
    validate_catalog(payload)
    return payload


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--previous', type=Path, action='append', default=[])
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    ledger = Ledger(a.db)
    try:
        previous = [r for path in a.previous for r in load_catalog(path)]
        write_atomic(a.out, export(ledger, previous))
    finally:
        ledger.db.close()
