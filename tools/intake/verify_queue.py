"""Verify discovery candidates with a credential-free artifact subprocess."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from ledger import Ledger


def sandbox_command(job, output):
    worker = Path(__file__).with_name('artifact_worker.py').resolve()
    args = ['/usr/bin/bwrap', '--die-with-parent', '--new-session', '--unshare-all',
            '--share-net', '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin',
            '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib',
            '--ro-bind', '/lib64', '/lib64', '--proc', '/proc', '--dev', '/dev',
            '--tmpfs', '/tmp', '--dir', '/etc', '--dir', '/etc/ssl',
            '--ro-bind', '/etc/ssl/certs', '/etc/ssl/certs']
    for name in ('resolv.conf', 'hosts', 'nsswitch.conf'):
        source = Path('/etc') / name
        if source.exists():
            args.extend(['--ro-bind', str(source), str(source)])
    args.extend(['--ro-bind', str(worker), '/worker.py', '--ro-bind', str(job), '/job.json',
                 '--bind', str(output), '/output', '--chdir', '/tmp',
                 '/usr/bin/python3', '-I', '/worker.py', '/job.json', '/output/artifact.apworld'])
    return args


def run_candidate(ledger, row, archives):
    with tempfile.TemporaryDirectory(prefix='ap-pie-artifact-') as tmp:
        root = Path(tmp)
        job = root / 'job.json'
        job.write_text(json.dumps({'url': row['url'], 'expected': row['expected']}))
        output = root / 'output'
        output.mkdir()
        process = subprocess.run(sandbox_command(job, output), capture_output=True,
                                 text=True, timeout=120, env={'PATH': '/usr/bin:/bin'})
        if process.returncode:
            # Sandbox startup failure is not an artifact defect. Fail closed.
            raise RuntimeError(f'Artifact sandbox failed, exit {process.returncode}: {process.stderr[:200]}')
        result = json.loads(process.stdout)
        if result['status'] != 'verified':
            ledger.retry_candidate(row['id'], result['error'], permanent=result['status'] == 'blocked')
            return result
        artifact = output / 'artifact.apworld'
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest != result['sha256']:
            raise RuntimeError('Worker output checksum mismatch')
        archives.mkdir(parents=True, exist_ok=True)
        target = archives / f'{digest}.apworld'
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError('Stored artifact checksum mismatch')
        else:
            # Keep the content-addressed file read-only for subsequent workers.
            artifact.chmod(0o444)
            artifact.replace(target)
        result['release_id'] = ledger.verified(row['id'], digest)
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--archives', type=Path, required=True)
    p.add_argument('--limit', type=int, default=5)
    p.add_argument('--module')
    p.add_argument('--version')
    a = p.parse_args()
    ledger = Ledger(a.db)
    try:
        query = "SELECT * FROM candidates WHERE state IN ('queued','retry') AND next_attempt<=?"
        values = [time.time()]
        if a.module:
            query += ' AND module=?'
            values.append(a.module)
        if a.version:
            query += ' AND version=?'
            values.append(a.version)
        # Release timestamps outrank ingestion order: paginated historical
        # releases must not push today's updates behind the oldest archives.
        order = " ORDER BY COALESCE((SELECT max(json_extract(detail,'$.published_at')) FROM origins WHERE candidate_id=candidates.id),'') DESC, discovered DESC LIMIT ?"
        rows = ledger.db.execute(query + order, [*values, a.limit]).fetchall()
        for row in rows:
            result = run_candidate(ledger, row, a.archives)
            print(json.dumps({'module': row['module'], 'version': row['version'], **result}), flush=True)
        print(json.dumps(ledger.status()), flush=True)
    finally:
        ledger.db.close()


if __name__ == '__main__':
    main()
