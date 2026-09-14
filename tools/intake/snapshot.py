"""Export bounded public discovery metadata, without private queue details."""
import argparse
import json
import os
from pathlib import Path
from ledger import Ledger

MAX_BYTES = 5 * 1024 * 1024
SOURCE_KEYS = ('name', 'home', 'supported', 'disabled', 'stability', 'setup_guide', 'tracker')


def export(ledger):
    releases = []
    for row in ledger.db.execute('SELECT * FROM releases ORDER BY module,version,verified,id'):
        metadata = json.loads(ledger.db.execute('SELECT metadata FROM sources WHERE module=?',
                                               (row['module'],)).fetchone()[0])
        held = bool(ledger.db.execute('SELECT 1 FROM holds WHERE module=? AND version IN (?,?)',
                                      (row['module'], row['version'], '*')).fetchone())
        jobs = {j['kind']: j['state'] for j in ledger.db.execute(
            'SELECT kind,state FROM jobs WHERE release_id=?', (row['id'],))}
        # Raw policy reasons, errors, source paths and model reports are not
        # public output. Actual findings will arrive through exact-hash evidence.
        releases.append({'id': row['id'], 'module': row['module'], 'version': row['version'],
                         'sha256': row['sha256'], 'url': row['url'], 'verified_at': row['verified'],
                         'source': {k: metadata[k] for k in SOURCE_KEYS if k in metadata},
                         'held': held, 'jobs': jobs})
    snapshot = {'schema': 1, 'releases': releases, 'queue': ledger.status()}
    if len(json.dumps(snapshot).encode()) > MAX_BYTES:
        raise ValueError('Discovery snapshot exceeds public metadata budget')
    return snapshot


def write_atomic(path, snapshot):
    body = (json.dumps(snapshot, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if len(body) > MAX_BYTES:
        raise ValueError('Discovery snapshot exceeds public metadata budget')
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('wb') as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    temporary.replace(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    ledger = Ledger(args.db)
    try:
        write_atomic(args.out, export(ledger))
    finally:
        ledger.db.close()
