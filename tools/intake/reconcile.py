"""Register immutable index/PR observations and held audit candidates.

Reconciliation queues artifact verification. It never treats an index checksum,
security PASS or successful CI job as proof of a freshly downloaded artifact.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import tomllib
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit, unquote
import yaml
from ledger import Ledger, HASH


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True)


def read(repo, ref, path):
    return git(repo, 'show', f'{ref}:{path}')


def add_world(ledger, module, data, lock, origin, detail):
    ledger.register(module, {k: data[k] for k in
                            ('name', 'home', 'tags', 'supported', 'disabled', 'stability',
                             'setup_guide', 'tracker', 'default_url') if k in data})
    count = 0
    for version, spec in data.get('versions', {}).items():
        url = spec.get('url') or data.get('default_url')
        if not url:
            continue  # Built-in/local sources remain represented in the registry.
        digest = lock.get(module, {}).get(version)
        ledger.discover(module, version, url.replace('{{version}}', version),
                        digest.lower() if isinstance(digest, str) and HASH.fullmatch(digest.lower()) else None,
                        origin=origin, detail=detail)
        count += 1
    return count


def archived_audit_observations(directory):
    """Extract only bounded source metadata, never report bodies or paths.

    Historical verdicts remain observations, not current dispositions. An
    unknown historical checksum must never be joined to newly downloaded bytes.
    """
    result = []
    for path in sorted(directory.rglob('*Audit.md')):
        text = path.read_text()
        if not text.startswith('---\n'):
            continue
        meta = yaml.safe_load(text.split('---', 2)[1])
        if not isinstance(meta, dict) or meta.get('verdict') not in ('FAIL', 'NEEDS_REVIEW', 'POLICY_HOLD'):
            continue
        module, version = meta.get('apworld'), str(meta.get('version', ''))
        if not isinstance(module, str) or not version:
            continue
        digest = meta.get('sha256') or meta.get('archive_sha256')
        digest = digest.lower() if isinstance(digest, str) and HASH.fullmatch(digest.lower()) else None
        urls = re.findall(r'https://github\.com/[^\s<>\]\)"`]+/releases/download/[^\s<>\]\)"`]+', text)
        for raw in dict.fromkeys(urls):
            u = urlsplit(raw)
            parts = u.path.rsplit('/', 2)
            if len(parts) != 3 or not parts[-1].endswith('.apworld'):
                continue
            tag = unquote(parts[-2])
            if tag != version and tag != 'v' + version:
                continue
            url = urlunsplit((u.scheme, u.netloc, u.path, '', ''))
            result.append({'module': module, 'version': version, 'url': url,
                           'sha256': digest, 'verdict': meta['verdict'],
                           'historical_checksum_known': digest is not None})
    return result


def standing_holds(watch_list):
    section = watch_list.read_text().split('## Blocked at the audit gate', 1)[1].split('## Process when filing', 1)[0]
    result = []
    for line in section.splitlines():
        if not line.startswith('| '):
            continue
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if len(cells) >= 3 and cells[2].startswith(('FAIL', 'NEEDS_REVIEW', 'POLICY_HOLD')):
            result.append((cells[0], cells[1]))
    return result


def reconcile(ledger, repo, ref, prs, policy, audit_results=()):
    ref = git(repo, 'rev-parse', ref).strip()
    lock = tomllib.loads(read(repo, ref, 'index.lock'))
    paths = [p for p in git(repo, 'ls-tree', '-r', '--name-only', ref, 'index').splitlines()
             if p.endswith('.toml')]
    counts = {'index_sources': len(paths), 'index_candidates': 0, 'prs': 0,
              'pr_candidates': 0, 'held_audit_candidates': 0}
    with ledger.db:
        for path in paths:
            counts['index_candidates'] += add_world(
                ledger, Path(path).stem, tomllib.loads(read(repo, ref, path)), lock,
                'index:' + ref, {'commit': ref})
        for pr in prs:
            head = pr['headRefOid']
            # Diff against main's merge base so an older PR cannot overwrite
            # unrelated newer metadata or omit the batch's reviewed guide links.
            base = git(repo, 'merge-base', head, ref).strip()
            changed = git(repo, 'diff', '--name-only', '--diff-filter=AM', base, head, '--', 'index').splitlines()
            pr_lock = tomllib.loads(read(repo, head, 'index.lock'))
            for path in changed:
                if path.endswith('.toml'):
                    counts['pr_candidates'] += add_world(
                        ledger, Path(path).stem, tomllib.loads(read(repo, head, path)), pr_lock,
                        'pr:' + str(pr['number']), {'number': pr['number'], 'commit': head,
                                                  'url': f"https://github.com/dowlle/Archipelago-index/pull/{pr['number']}"})
            counts['prs'] += 1
        for module, versions in policy.get('version_holds', {}).items():
            for version, reason in versions.items():
                ledger.hold(module, version, reason)
        for module, rejected in policy.get('rejected', {}).items():
            for record in rejected:
                reason = record.get('reason', '')
                if reason.startswith(('security-', 'policy-')):
                    ledger.hold(module, record['version'], reason)
        # Preserve every recorded non-PASS exact artifact as a discovery
        # observation, regardless of whether accepted intake opened a PR.
        for result in audit_results:
            module, version = result.get('module'), result.get('version')
            url, digest = result.get('url'), result.get('sha256')
            verdict = result.get('verdict')
            if verdict not in ('NEEDS_REVIEW', 'FAIL', 'POLICY_HOLD'):
                continue
            if not all(isinstance(x, str) and x for x in (module, version, url)):
                continue
            if not ledger.db.execute('SELECT 1 FROM sources WHERE module=?', (module,)).fetchone():
                ledger.register(module, {'name': module, 'home': '', 'supported': False})
            ledger.discover(module, version, url, digest,
                            origin='archived-audit' if 'historical_checksum_known' in result else 'recorded-audit',
                            detail={'status': verdict, 'historical_checksum_known': digest is not None})
            counts['held_audit_candidates'] += 1
        for module, reason in policy.get('security_holds', {}).items():
            if not module.startswith('_') and isinstance(reason, str):
                # Module-wide policy holds apply to future versions as well.
                ledger.hold(module, '*', reason)
    return {**counts, **ledger.status(), 'index_commit': ref}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--index', type=Path, required=True)
    p.add_argument('--ref', required=True)
    p.add_argument('--prs', type=Path, required=True)
    p.add_argument('--holds', type=Path, required=True)
    p.add_argument('--audit-results', type=Path)
    p.add_argument('--audit-notes', type=Path)
    p.add_argument('--watch-list', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    audit_results = [json.loads(line) for line in a.audit_results.read_text().splitlines() if line.strip()] if a.audit_results else []
    if a.audit_notes:
        audit_results.extend(archived_audit_observations(a.audit_notes))
    ledger = Ledger(a.db)
    try:
        if a.watch_list:
            with ledger.db:
                for module, version in standing_holds(a.watch_list):
                    if not ledger.db.execute('SELECT 1 FROM holds WHERE module=? AND version=?', (module, version)).fetchone():
                        ledger.hold(module, version, 'Active recorded security disposition requires explicit resolution')
        result = reconcile(ledger, a.index, a.ref, json.loads(a.prs.read_text()),
                           json.loads(a.holds.read_text()), audit_results)
        a.out.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
    finally:
        ledger.db.close()


if __name__ == '__main__':
    main()
