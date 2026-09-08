#!/usr/bin/env python3
"""Static, checksum-verified builder audit. Never imports APWorld code.

Input is a saved public /api/apworlds response. Archives and receipts remain
local; this does not call builder endpoints or change server caches.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ap-web'))
from apworld_options_parser import parse_apworld_options_bytes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('catalog', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--names', nargs='*')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = []
    for world in json.loads(args.catalog.read_text()):
        if world['disabled'] or (args.names and world['name'] not in args.names):
            continue
        downloadable = {v['version'] for v in world['downloadable_versions']}
        versions = [v for v in world['versions'] if v['version'] in downloadable]
        if not args.names:
            versions = versions[:1]
        jobs.extend((world, version) for version in versions)

    def audit(job):
        world, version = job
        row = {'name': world['name'], 'version': version['version']}
        key = hashlib.sha256(f"{world['name']}@{version['version']}".encode()).hexdigest()
        artifact = args.output / f'{key}.apworld'
        try:
            if artifact.exists():
                data = artifact.read_bytes()
            else:
                url = version.get('url')
                if not url:
                    url = ('https://raw.githubusercontent.com/dowlle/Archipelago-index/main/'
                           + version['local'])
                parsed = urlparse(url)
                if parsed.scheme != 'https' or parsed.hostname not in {'github.com', 'raw.githubusercontent.com', 'gitlab.com', 'codeberg.org', 'git.makuluni.com'}:
                    raise ValueError('Non-GitHub download needs separate review')
                with urllib.request.urlopen(url, timeout=30) as response:
                    data = response.read(50 * 1024 * 1024 + 1)
                if len(data) > 50 * 1024 * 1024:
                    raise ValueError('Archive exceeds 50 MiB audit cap')
                artifact.write_bytes(data)
            row['sha256'] = hashlib.sha256(data).hexdigest()
            if version.get('sha256') and version['sha256'].lower() != row['sha256']:
                raise ValueError('Index checksum mismatch')
            schema = parse_apworld_options_bytes(data, world['name'])
            row.update(status='null' if schema is None else 'empty' if not schema['options'] else 'parsed',
                       options=len(schema['options']) if schema else None,
                       game=schema['game'] if schema else None, artifact=str(artifact))
        except Exception as exc:
            row.update(status='error', error=f'{type(exc).__name__}: {exc}')
        return row

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(audit, jobs):
            rows.append(row)
            if len(rows) % 25 == 0 or row['status'] in ('null', 'error'):
                print(len(rows), '/', len(jobs), row['name'], row['status'], flush=True)
            (args.output / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
    print({status: sum(r['status'] == status for r in rows) for status in ('parsed', 'empty', 'null', 'error')})


if __name__ == '__main__':
    main()
