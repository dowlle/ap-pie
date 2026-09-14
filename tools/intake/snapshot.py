"""Export bounded public discovery metadata, without private queue details."""
import argparse
import json
import os
import tempfile
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
    policies = [dict(r) for r in ledger.db.execute('SELECT module,version FROM holds ORDER BY module,version')]
    observations=[]
    for row in ledger.db.execute("SELECT DISTINCT c.* FROM candidates c JOIN origins o ON o.candidate_id=c.id WHERE o.origin IN ('archived-audit','recorded-audit') AND c.state!='verified' AND NOT EXISTS(SELECT 1 FROM releases r WHERE r.module=c.module AND r.version=c.version AND r.url=c.url AND (c.expected IS NULL OR c.expected=r.sha256)) ORDER BY c.module,c.version,c.id"):
        reason=('checksum_mismatch' if row['error']=='Artifact checksum mismatch' else
                'archive_verification_rejected' if row['state']=='blocked' else
                'source_unreachable' if row['error']=='HTTPError' else 'verification_pending')
        observations.append({'id':row['id'],'module':row['module'],'version':row['version'],'url':row['url'],
                             'expected_sha256':row['expected'],'state':row['state'],'reason':reason,'verified':False})
    snapshot = {'schema': 1, 'releases': releases, 'observations':observations,
                'queue': ledger.status(), 'policies': policies}
    if len(json.dumps(snapshot).encode()) > MAX_BYTES:
        raise ValueError('Discovery snapshot exceeds public metadata budget')
    return snapshot


def write_atomic(path, snapshot, *, validate=None):
    body = (json.dumps(snapshot, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if len(body) > MAX_BYTES:
        raise ValueError('Discovery snapshot exceeds public metadata budget')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as f:
            temporary = Path(f.name)
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        if validate is not None:
            validate(temporary)
        temporary.replace(path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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
