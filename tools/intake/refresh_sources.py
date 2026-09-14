"""Refresh only the canonical public index and immutable open-PR observations."""
import json
import re
import subprocess
from pathlib import Path
from reconcile import reconcile
from snapshot import write_atomic

REPO = 'https://github.com/dowlle/Archipelago-index.git'


def command(args, timeout=120):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode or len(result.stdout.encode()) > 10 * 1024 * 1024:
        raise RuntimeError('Canonical source refresh failed')
    return result.stdout


def refresh(ledger, repo, holds):
    repo = Path(repo)
    if not repo.exists():
        command(['git', 'clone', '--no-checkout', REPO, str(repo)], timeout=600)
    origin = command(['git', '-C', str(repo), 'remote', 'get-url', 'origin']).strip()
    if origin != REPO:
        raise ValueError('Source checkout is not the canonical index')
    prs = json.loads(command(['gh', 'pr', 'list', '--repo', 'dowlle/Archipelago-index', '--state', 'open',
                             '--limit', '1000', '--json', 'number,title,headRefOid']))
    if not isinstance(prs, list) or len(prs) >= 1000:
        raise ValueError('Queued source listing requires pagination')
    for pr in prs:
        if not isinstance(pr, dict) or set(pr) != {'number', 'title', 'headRefOid'} or type(pr['number']) is not int or pr['number'] <= 0:
            raise ValueError('Invalid queued source record')
        if not isinstance(pr['headRefOid'], str) or not re.fullmatch('[0-9a-f]{40}', pr['headRefOid']) or not isinstance(pr['title'], str):
            raise ValueError('Invalid queued commit identity')
    heads = sorted({pr['headRefOid'] for pr in prs})
    command(['git', '-C', str(repo), 'fetch', '--no-tags', 'origin',
             'main:refs/remotes/origin/main', *heads], timeout=600)
    # PR head hashes from the listing remain immutable even if a PR changes
    # while fetching. Missing/unreachable commits fail the refresh and retry.
    for head in heads:
        command(['git', '-C', str(repo), 'cat-file', '-e', head + '^{commit}'])
    policy = json.loads(Path(holds).read_text()) if holds else {}
    result = reconcile(ledger, repo, 'refs/remotes/origin/main', prs, policy)
    write_atomic(repo.parent / 'queued-prs.json', prs)
    return result
