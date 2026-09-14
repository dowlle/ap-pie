"""Run independent guide checks in a credential-free network sandbox."""
import argparse
import json
import math
import re
import subprocess
import tempfile
import urllib.parse
from pathlib import Path
from ledger import Ledger
from verify_queue import sandbox_command
from guide_worker import HOSTS


def validate_evidence(evidence, release, metadata):
    if not isinstance(evidence, dict) or set(evidence) != {'url', 'content_sha256', 'checked_at', 'kind'}:
        raise ValueError('Invalid guide worker fields')
    if not isinstance(evidence['url'], str) or len(evidence['url']) > 10000:
        raise ValueError('Invalid guide URL')
    url = urllib.parse.urlsplit(evidence['url'])
    if url.scheme != 'https' or url.hostname not in HOSTS or url.username or url.password or url.port not in (None, 443):
        raise ValueError('Invalid guide host')
    if not isinstance(evidence['content_sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', evidence['content_sha256']):
        raise ValueError('Invalid guide content digest')
    if type(evidence['checked_at']) not in (int, float) or not math.isfinite(evidence['checked_at']) or evidence['checked_at'] <= 0:
        raise ValueError('Invalid guide check date')
    existing = metadata.get('setup_guide')
    if existing:
        if evidence['url'] != existing or evidence['kind'] != 'existing-link-reachable':
            raise ValueError('Existing guide identity mismatch')
    else:
        repo = re.match(r'https://github\.com/([^/]+/[^/]+)/releases/download/', release['url'])
        if not repo or not evidence['url'].startswith('https://github.com/' + repo.group(1) + '/blob/HEAD/') or evidence['kind'] != 'repository-setup-document':
            raise ValueError('Discovered guide source mismatch')
        if url.query or url.fragment or '..' in url.path.split('/'):
            raise ValueError('Invalid discovered guide path')
    return evidence


def run(job):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'job.json'
        path.write_text(json.dumps(job))
        output = Path(tmp) / 'output'
        output.mkdir()
        args = sandbox_command(path, output)
        args[args.index(str(Path(__file__).with_name('artifact_worker.py').resolve()))] = str(Path(__file__).with_name('guide_worker.py').resolve())
        # The guide worker uses the same empty environment and public-network
        # sandbox mounts as the downloader; it receives metadata only.
        result = subprocess.run(args, capture_output=True, text=True, timeout=100, env={'PATH': '/usr/bin:/bin'})
        if result.returncode or len(result.stdout) > 20000:
            raise RuntimeError('Guide sandbox failed')
        return json.loads(result.stdout)


def process(ledger, limit=5):
    completed = 0
    for _ in range(limit):
        job = ledger.claim('guide', lease_seconds=150)
        if job is None:
            break
        row = ledger.db.execute('SELECT releases.*,sources.metadata FROM releases JOIN sources USING(module) WHERE releases.id=?', (job['release_id'],)).fetchone()
        metadata = json.loads(row['metadata'])
        try:
            result = run({'artifact_url': row['url'], 'setup_guide': metadata.get('setup_guide')})
            if result.get('error') or result.get('result') is None:
                ledger.finish(row['id'], 'guide', job['token'], None, error=result.get('error') or 'Guide discovery requires follow-up')
                continue
            evidence = validate_evidence(result['result'], row, metadata)
            if not metadata.get('setup_guide'):
                ledger.register(row['module'], {'setup_guide': evidence['url']})
                ledger.db.commit()
            ledger.finish(row['id'], 'guide', job['token'], evidence)
            completed += 1
        except Exception as exc:
            ledger.finish(row['id'], 'guide', job['token'], None, error=type(exc).__name__)
    return completed


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    a = p.parse_args()
    ledger = Ledger(a.db)
    try:
        print(json.dumps({'completed': process(ledger), 'queue': ledger.status()}))
    finally:
        ledger.db.close()
