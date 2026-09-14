"""Scan every registered source, without accepted-index or audit filtering."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote
from ledger import Ledger

REPO = re.compile(r'^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)(?:/|$)')


def repository(url):
    match = REPO.match(url or '')
    return '/'.join(match.groups()) if match else None


def pages(raw):
    decoder = json.JSONDecoder()
    result = []
    raw = raw.strip()
    while raw:
        page, end = decoder.raw_decode(raw)
        if not isinstance(page, list):
            raise ValueError('Unexpected GitHub release shape')
        result.extend(page)
        raw = raw[end:].lstrip()
    return result


def fetch_releases(repo, cache, *, ttl=1800):
    filename = cache / (hashlib.sha256(repo.lower().encode()).hexdigest() + '.json')
    if filename.exists() and time.time() - filename.stat().st_mtime < ttl:
        return json.loads(filename.read_text())
    fields = '[.[]|{tag_name,published_at,draft,prerelease,assets:[.assets[]|{id,name,browser_download_url,size,digest,updated_at}]}]'
    p = subprocess.run(['gh', 'api', '--paginate', f'repos/{repo}/releases?per_page=100', '--jq', fields],
                       capture_output=True, text=True, timeout=180)
    if p.returncode:
        raise RuntimeError('GitHub release request failed')
    if len(p.stdout) > 10 * 1024 * 1024:
        raise RuntimeError('GitHub release metadata budget exceeded')
    releases = pages(p.stdout)
    cache.mkdir(parents=True, exist_ok=True)
    tmp = filename.with_suffix('.tmp')
    tmp.write_text(json.dumps(releases))
    tmp.replace(filename)
    return releases


def asset_matches(module, urls, filename):
    if not isinstance(filename, str) or not filename.endswith('.apworld'):
        return False
    for url in urls:
        pattern = unquote(url.rsplit('/', 1)[-1])
        if pattern.endswith('.apworld'):
            regex = re.escape(pattern).replace(re.escape('{{version}}'), '.+')
            if re.fullmatch(regex, filename):
                return True
    normalize = lambda value: re.sub('[^a-z0-9]', '', value.lower())
    return normalize(filename[:-8]) == normalize(module)


def observations(module, metadata, existing, releases):
    urls = [r['url'] for r in existing]
    if metadata.get('default_url'):
        urls.append(metadata['default_url'])
    aliases = {r['url']: r['version'] for r in existing}
    result = []
    unmatched = []
    for release in releases:
        if release.get('draft') or not release.get('tag_name'):
            continue
        tag = release['tag_name']
        version = tag[1:] if tag.startswith('v') and len(tag) > 1 and tag[1].isdigit() else tag
        assets = [a for a in release.get('assets', []) if isinstance(a, dict)]
        for asset in assets:
            filename = asset.get('name')
            if not isinstance(filename, str) or not filename.endswith('.apworld'):
                continue
            if not asset_matches(module, urls, filename):
                unmatched.append({'tag': tag, 'asset': filename})
                continue
            url = asset.get('browser_download_url')
            if not isinstance(url, str):
                continue
            digest = asset.get('digest')
            expected = digest[7:].lower() if isinstance(digest, str) and re.fullmatch('sha256:[a-fA-F0-9]{64}', digest) else None
            result.append({'version': aliases.get(url, version), 'url': url, 'expected': expected,
                           'revision': f"{asset.get('id')}:{asset.get('updated_at')}",
                           'published_at': release.get('published_at'),
                           'prerelease': bool(release.get('prerelease'))})
    return result, unmatched


def scan(ledger, cache, *, workers=6, ttl=1800):
    sources = [dict(row) for row in ledger.db.execute('SELECT * FROM sources ORDER BY module')]
    grouped = {}
    summary = {'registered': len(sources), 'scanned': 0, 'unsupported': 0, 'errors': 0, 'observations': 0}
    for source in sources:
        metadata = json.loads(source['metadata'])
        candidates = [dict(row) for row in ledger.db.execute('SELECT * FROM candidates WHERE module=?', (source['module'],))]
        repo = next((r for u in [metadata.get('default_url'), *[c['url'] for c in candidates], metadata.get('home')]
                     if (r := repository(u))), None)
        if repo:
            grouped.setdefault(repo.lower(), []).append((source['module'], metadata, candidates))
        else:
            summary['unsupported'] += 1
            state = 'builtin' if metadata.get('supported') else 'needs_source_mapping'
            ledger.db.execute('INSERT INTO scans VALUES (?,?,?,?) ON CONFLICT(module) DO UPDATE '
                              'SET state=excluded.state,detail=excluded.detail,updated=excluded.updated',
                              (source['module'], state, '{}', time.time()))
    ledger.db.commit()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_releases, repo, cache, ttl=ttl): repo for repo in grouped}
        for future in concurrent.futures.as_completed(futures):
            repo = futures[future]
            try:
                releases = future.result()
                error = None
            except Exception as e:
                releases, error = [], type(e).__name__
            with ledger.db:
                for module, metadata, candidates in grouped[repo]:
                    found, unmatched = observations(module, metadata, candidates, releases)
                    for record in found:
                        ledger.discover(module, record['version'], record['url'], record['expected'],
                                        origin='github:' + repo, detail=record, revision=record['revision'])
                    summary['observations'] += len(found)
                    summary['errors' if error else 'scanned'] += 1
                    detail = {'repository': repo, 'observations': len(found),
                              'unmatched_assets': unmatched[:100], 'error': error}
                    ledger.db.execute('INSERT INTO scans VALUES (?,?,?,?) ON CONFLICT(module) DO UPDATE '
                                      'SET state=excluded.state,detail=excluded.detail,updated=excluded.updated',
                                      (module, 'retry' if error else 'scanned', json.dumps(detail), time.time()))
            print(json.dumps({'repository': repo, 'sources': len(grouped[repo]), 'error': error}), flush=True)
    assert summary['scanned'] + summary['errors'] + summary['unsupported'] == summary['registered']
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--ttl', type=int, default=1800)
    a = p.parse_args()
    ledger = Ledger(a.db)
    try:
        result = scan(ledger, a.cache, workers=a.workers, ttl=a.ttl)
        a.out.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    finally:
        ledger.db.close()


if __name__ == '__main__':
    main()
