"""Verify discovery candidates with a credential-free artifact subprocess."""
from __future__ import annotations
import argparse
import concurrent.futures
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


def download_candidate(row, archives):
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
            return result
        if result['status'] != 'verified':
            return result
        artifact = output / 'artifact.apworld'
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest != result['sha256']:
            raise RuntimeError('Worker output checksum mismatch')
        store_artifact(artifact, archives, digest)
        return result


def record_result(ledger, row, result):
    if result['status'] == 'checksum_mismatch':
        ledger.record_checksum_mismatch(row['id'], result['observed_sha256'])
    elif result['status'] == 'verified':
        result['release_id'] = ledger.verified(row['id'], result['sha256'])
    else:
        ledger.retry_candidate(row['id'], result['error'], permanent=result['status'] == 'blocked')
    return result


def run_candidate(ledger, row, archives):
    return record_result(ledger, row, download_candidate(row, archives))


def batch_rows(ledger, limit):
    """Spread work across sources and skip equivalent observations in a batch."""
    pending = ledger.pending_candidates(limit=max(1000, limit * 20))
    first, rest, modules, identities = [], [], set(), set()
    for row in pending:
        key = (row['module'], row['version'], row['url'], row['expected'])
        if key in identities:
            continue
        identities.add(key)
        target = rest if row['module'] in modules else first
        target.append(dict(row))
        modules.add(row['module'])
    return (first + rest)[:limit]


def run_batch(ledger, rows, archives, *, workers=4, download=download_candidate):
    if not 1 <= workers <= 8:
        raise ValueError('workers must be between 1 and 8')
    results = []
    # Workers touch only public downloads and the hash-addressed archive cache.
    # All SQLite updates happen on the coordinator thread.
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(download, row, archives): row for row in rows}
        for future in concurrent.futures.as_completed(futures):
            row = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {'status': 'retry', 'error': type(exc).__name__}
            result = record_result(ledger, row, result)
            results.append({'candidate_id':row['id'],'module': row['module'], 'version': row['version'], **result})
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--archives', type=Path, required=True)
    p.add_argument('--limit', type=int, default=5)
    p.add_argument('--module')
    p.add_argument('--version')
    p.add_argument('--workers', type=int, default=4)
    a = p.parse_args()
    if not 1 <= a.limit <= 500 or not 1 <= a.workers <= 8:
        p.error('limit must be 1..500 and workers 1..8')
    ledger = Ledger(a.db)
    try:
        rows = ledger.pending_candidates(limit=a.limit, module=a.module, version=a.version) if a.module or a.version else batch_rows(ledger, a.limit)
        for result in run_batch(ledger, rows, a.archives, workers=a.workers):
            print(json.dumps(result), flush=True)
        print(json.dumps(ledger.status()), flush=True)
    finally:
        ledger.db.close()


if __name__ == '__main__':
    main()
