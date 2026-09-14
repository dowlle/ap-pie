"""Collect settled queued-PR fuzz matrices with exact run/source identities."""
import argparse
import base64
import importlib.util
import json
import re
import subprocess
import tomllib
from pathlib import Path
from ledger import Ledger
from import_generation import validate
from snapshot import write_atomic

REPO = 'dowlle/Archipelago-index'


def gh_text(*args):
    result = subprocess.run(['gh', *args], capture_output=True, text=True, timeout=90)
    if result.returncode or len(result.stdout.encode()) > 10 * 1024 * 1024:
        raise RuntimeError('Public generation evidence request failed')
    return result.stdout


def gh_json(*args):
    return json.loads(gh_text(*args))


def collect(ledger, prs, producer):
    identities = {(r['module'], r['version']): r['sha256'] for r in ledger.db.execute('SELECT * FROM releases')}
    records = []
    for pr in prs:
        data = gh_json('pr', 'view', str(pr['number']), '--repo', REPO, '--json', 'headRefOid,statusCheckRollup')
        if data['headRefOid'] != pr['headRefOid']:
            continue
        groups = {}
        for check in data['statusCheckRollup']:
            parsed = producer.parse_check_name(check.get('name', ''))
            if parsed and parsed[:2] in identities:
                groups.setdefault(parsed[:2], []).append(check)
        for identity, checks in groups.items():
            if any(c.get('conclusion') not in {'SUCCESS', 'FAILURE'} for c in checks):
                continue
            urls = {m.group(1) for c in checks if (m := re.fullmatch(r'(https://github\.com/dowlle/Archipelago-index/actions/runs/[0-9]+)/job/[0-9]+', c.get('detailsUrl', '')))}
            if len(urls) != 1 or any(not re.fullmatch(r'https://github\.com/dowlle/Archipelago-index/actions/runs/[0-9]+/job/[0-9]+', c.get('detailsUrl', '')) for c in checks):
                continue
            url = urls.pop()
            run = gh_json('run', 'view', url.rsplit('/', 1)[-1], '--repo', REPO, '--json', 'headSha,status')
            if run['status'] != 'completed' or run['headSha'] != data['headRefOid']:
                continue
            source = gh_json('api', f"repos/{REPO}/contents/index.lock?ref={run['headSha']}")
            lock = tomllib.loads(base64.b64decode(source['content']).decode())
            digest = identities[identity]
            if lock.get(identity[0], {}).get(identity[1]) != digest:
                continue
            result = producer._pull_pr_verdict_from_checks(pr['number'], checks)
            if result is None:
                continue
            records.append(dict(module=identity[0], version=identity[1], sha256=digest, report_url=url,
                                **{k: result[k] for k in ('verdict', 'default_rate', 'worst_hook', 'worst_hook_rate', 'seeds', 'fuzzed_at')}))
    return {'schema': 1, 'records': validate(records)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--prs', type=Path, required=True)
    p.add_argument('--emitter', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    spec = importlib.util.spec_from_file_location('badge_producer', a.emitter)
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    producer.gh_text, producer.gh_json = gh_text, gh_json
    ledger = Ledger(a.db)
    try:
        payload = collect(ledger, json.loads(a.prs.read_text()), producer)
        write_atomic(a.out, payload)
        print(json.dumps({'records': len(payload['records'])}))
    finally:
        ledger.db.close()
