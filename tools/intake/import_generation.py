"""Reuse checksum-matched Actions generation evidence in independent jobs."""
import argparse
import json
import sys
import tempfile
from pathlib import Path
from ledger import Ledger

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ap-web'))
from fuzz_evidence import load_provenance


def validate(records):
    if not isinstance(records, list):
        raise ValueError('Invalid generation records')
    body = json.dumps({'schema': 1, 'records': records})
    if len(body.encode()) > 5 * 1024 * 1024:
        raise ValueError('Generation evidence exceeds budget')
    # The web validator accepts or rejects an entire file. Check its result
    # before leasing any jobs, since it otherwise logs invalid input and skips.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'evidence.json'
        path.write_text(body)
        checked = load_provenance(str(path), str(Path(tmp) / 'absent.json'), path.stat().st_mtime_ns)
    if checked != records:
        raise ValueError('Invalid generation evidence')
    return checked


def process(ledger, records, limit=20):
    lookup = {}
    for record in validate(records):
        lookup.setdefault((record['module'], record['version'], record['sha256']), []).append(record)
    completed = 0
    for _ in range(limit):
        job = ledger.claim('generation')
        if job is None:
            break
        release = ledger.db.execute('SELECT * FROM releases WHERE id=?', (job['release_id'],)).fetchone()
        matching = lookup.get((release['module'], release['version'], release['sha256']), [])
        if not matching:
            ledger.finish(release['id'], 'generation', job['token'], None, error='Exact-release generation evidence required')
            continue
        ledger.finish(release['id'], 'generation', job['token'], {'records': matching})
        completed += 1
    return completed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    a = p.parse_args()
    records = json.loads(a.evidence.read_text())['records']
    ledger = Ledger(a.db)
    try:
        print(json.dumps({'completed': process(ledger, records), 'queue': ledger.status()}))
    finally:
        ledger.db.close()
