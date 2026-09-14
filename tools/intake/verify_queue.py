"""Verify discovery candidates with a credential-free artifact subprocess."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from ledger import Ledger


def store_artifact(artifact, archives, digest):
    archives.mkdir(parents=True, exist_ok=True)
    target = archives / f'{digest}.apworld'
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Stored artifact checksum mismatch')
        return target
    staged = None
    try:
        # Stage on the destination filesystem; /tmp may be a separate mount.
        with tempfile.NamedTemporaryFile(dir=archives, prefix=digest + '.', delete=False) as output:
            staged = Path(output.name)
            with artifact.open('rb') as source:
                shutil.copyfileobj(source, output, length=65536)
            output.flush()
            os.fsync(output.fileno())
        if hashlib.sha256(staged.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Stored artifact checksum mismatch')
        staged.chmod(0o444)
        staged.replace(target)
        directory = os.open(archives, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return target
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


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
        if result['status']=='checksum_mismatch':
            if result['expected_sha256'] != row['expected']:
                raise RuntimeError('Worker checksum identity mismatch')
            ledger.record_checksum_mismatch(row['id'],result['observed_sha256'])
            return result
        if result['status'] != 'verified':
            ledger.retry_candidate(row['id'], result['error'], permanent=result['status'] == 'blocked')
            return result
        artifact = output / 'artifact.apworld'
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest != result['sha256']:
            raise RuntimeError('Worker output checksum mismatch')
        store_artifact(artifact, archives, digest)
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
        rows = ledger.pending_candidates(limit=a.limit, module=a.module, version=a.version)
        for row in rows:
            result = run_candidate(ledger, row, a.archives)
            print(json.dumps({'module': row['module'], 'version': row['version'], **result}), flush=True)
        print(json.dumps(ledger.status()), flush=True)
    finally:
        ledger.db.close()


if __name__ == '__main__':
    main()
