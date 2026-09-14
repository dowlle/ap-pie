"""Collect settled queued-PR fuzz matrices with exact run/source identities."""
import argparse
import base64
import importlib.util
import json
import re
import subprocess
import tomllib
import time
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
    identities = {}
    for row in ledger.db.execute('SELECT module,version,sha256 FROM releases'):
        identities.setdefault((row['module'], row['version']), set()).add(row['sha256'])
    relevant_prs = {row[0] for row in ledger.db.execute("SELECT DISTINCT substr(o.origin,4) FROM origins o JOIN candidates c ON c.id=o.candidate_id JOIN releases r ON r.module=c.module AND r.version=c.version WHERE o.origin LIKE 'pr:%'")}
    records = []
    for pr in prs:
        if str(pr['number']) not in relevant_prs:
            continue
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
            digest = lock.get(identity[0], {}).get(identity[1])
            if digest not in identities[identity]:
                continue
            result = producer._pull_pr_verdict_from_checks(pr['number'], checks)
            if result is None:
                continue
            records.append(dict(module=identity[0], version=identity[1], sha256=digest, report_url=url,
                                **{k: result[k] for k in ('verdict', 'default_rate', 'worst_hook', 'worst_hook_rate', 'seeds', 'fuzzed_at')}))
    return {'schema': 1, 'records': validate(records)}


def collect_incremental(ledger, prs, producer, cache, *, limit=5, ttl=21600):
    """Rotate bounded PR refreshes; preserve previously validated CI evidence."""
    if not 1<=limit<=20:raise ValueError('Invalid generation refresh limit')
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    entries=[];records=[];now=time.time()
    for pr in prs:
        head=pr['headRefOid']
        if not re.fullmatch('[a-f0-9]{40}',head):raise ValueError('Invalid PR head')
        path=cache/(str(int(pr['number']))+'-'+head+'.json')
        previous=[];updated=0;retry=False
        if path.exists():
            try:
                data=json.loads(path.read_text())
                if data.get('head')!=head:raise ValueError('Mismatched evidence cache head')
                previous=validate(data['records']);updated=path.stat().st_mtime
                retry=bool(data.get('retry'))
            except (ValueError,KeyError,TypeError):
                previous=[];updated=0
        records+=previous
        if now-updated>=(1800 if retry else ttl):entries.append((updated,pr,path,previous))
    for _,pr,path,previous in sorted(entries,key=lambda entry:(entry[0],entry[1]['number']))[:limit]:
        try:
            fresh=collect(ledger,[pr],producer)['records']
            # Old completed-run dispositions remain evidence after reruns.
            merged={json.dumps(r,sort_keys=True):r for r in previous+fresh}
            payload={'head':pr['headRefOid'],'records':validate(list(merged.values()))}
            write_atomic(path,payload)
            records+=fresh
        except Exception:
            # Keep prior evidence, retry this PR on a later bounded cycle.
            write_atomic(path,{'head':pr['headRefOid'],'records':previous,'retry':True})
            continue
    identities={(r['module'],r['version'],r['sha256']) for r in ledger.db.execute('SELECT module,version,sha256 FROM releases')}
    result={json.dumps(r,sort_keys=True):r for r in records if (r['module'],r['version'],r['sha256']) in identities}
    return {'schema':1,'records':validate(list(result.values()))}


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
