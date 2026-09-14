"""Coverage manifest for every registered source, PR origin and standing hold.

This is an operational report, not publication evidence. Equivalent candidates
count as verified only when their version, URL and declared digest match a
verified release. Missing scans and missing PR origins remain explicit gaps.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import time
from snapshot import write_atomic


def export(db, expected_prs=()):
    sources = [dict(r) for r in db.execute('SELECT * FROM sources ORDER BY module')]
    releases = [dict(r) for r in db.execute('SELECT * FROM releases')]
    candidates = [dict(r) for r in db.execute('SELECT * FROM candidates')]
    release_ids = {r['id']:r for r in releases}
    candidate_ids = {c['id']:c for c in candidates}
    holds = {(r['module'],r['version']) for r in db.execute('SELECT module,version FROM holds')}
    quarantined = set()
    for row in db.execute("SELECT candidate_id,origin FROM origins WHERE origin LIKE 'checksum-mismatch:%'"):
        original=candidate_ids.get(row['origin'].split(':',1)[1])
        observed=candidate_ids[row['candidate_id']]
        release=release_ids.get(observed['release_id']) or next((r for r in releases if (
            r['module'],r['version'],r['url'],r['sha256']) == (
            observed['module'],observed['version'],observed['url'],observed['expected'])),None)
        if original and release and (
                release['module'],release['version'],release['url']) == (
                original['module'],original['version'],original['url']) and release['sha256']!=original['expected'] and (
                (original['module'],original['version']) in holds or (original['module'],'*') in holds):
            quarantined.add((original['module'],original['version'],original['url'],original['expected']))
    verified = defaultdict(list)
    for release in releases:
        verified[(release['module'], release['version'], release['url'])].append(release)
    by_module = defaultdict(list)
    by_id = {}
    for candidate in candidates:
        matches = verified[(candidate['module'], candidate['version'], candidate['url'])]
        exact = [r for r in matches if candidate['expected'] is None or candidate['expected'] == r['sha256']]
        # A later asset revision must be downloaded again even at the same URL.
        direct = release_ids.get(candidate['release_id'])
        directly_verified = candidate['state']=='verified' and direct is not None and (
            direct['module'],direct['version'],direct['sha256']) == (
            candidate['module'],candidate['version'],candidate['expected'] or direct['sha256'])
        state = ('quarantined' if (candidate['module'],candidate['version'],candidate['url'],candidate['expected']) in quarantined else 'verified' if directly_verified or
                 any(r['verified'] >= candidate['discovered'] for r in exact) else candidate['state'])
        item = {'id': candidate['id'], 'version': candidate['version'], 'state': state,
                'attempts': candidate['attempts']}
        by_module[candidate['module']].append(item)
        by_id[candidate['id']] = item
    scans = {r['module']: r['state'] for r in db.execute('SELECT module,state FROM scans')}
    report = []
    for source in sources:
        metadata = json.loads(source['metadata'])
        items = by_module[source['module']]
        classification = ('retired' if metadata.get('disabled') else 'builtin' if metadata.get('supported')
                          else scans.get(source['module'], 'not_scanned'))
        states = dict(Counter(item['state'] for item in items))
        gap = None if classification in ('retired', 'builtin') else (
            'missing_source_mapping' if classification == 'needs_source_mapping' else
            'scan_retry' if classification in ('retry', 'not_scanned') else
            'no_artifact_observation' if not items else
            'artifact_verification_pending' if not states.get('verified') else None)
        report.append({'module': source['module'], 'classification': classification,
                       'candidate_states': states, 'gap': gap})
    prs = defaultdict(list)
    for row in db.execute("SELECT candidate_id,origin FROM origins WHERE origin LIKE 'pr:%'"):
        prs[row['origin'][3:]].append(by_id[row['candidate_id']])
    pr_numbers = set(prs) | {str(p['number']) for p in expected_prs}
    pr_report = []
    for number in sorted(pr_numbers, key=int):
        items = prs[number]
        states = dict(Counter(item['state'] for item in items))
        pr_report.append({'number': int(number), 'candidate_states': states,
                          'gap': 'no_candidate_origin' if not items else
                          'artifact_verification_pending' if any(i['state'] not in ('verified','quarantined') for i in items) else None})
    held = []
    for row in db.execute('SELECT module,version FROM holds ORDER BY module,version'):
        matches = [r for r in releases if r['module'] == row['module'] and
                   (row['version'] == '*' or r['version'] == row['version'])]
        held.append({'module': row['module'], 'version': row['version'],
                     'verified_releases': len(matches),
                     'gap': None if matches else 'held_artifact_verification_pending'})
    jobs = dict(Counter((r['kind'] + ':' + r['state']) for r in db.execute('SELECT kind,state FROM jobs')))
    return {'schema': 1, 'generated_at': time.time(), 'sources': report, 'prs': pr_report,
            'holds': held, 'jobs': jobs,
            'summary': {'registered_sources': len(report), 'pr_origins': len(pr_report),
                        'verified_releases': len(releases),
                        'source_gaps': dict(Counter(r['gap'] for r in report if r['gap'])),
                        'pr_gaps': sum(bool(r['gap']) for r in pr_report),
                        'hold_gaps': sum(bool(r['gap']) for r in held)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--prs', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    db = sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute('BEGIN')  # One consistent view, including committed WAL data.
        result = export(db, json.loads(args.prs.read_text()) if args.prs else [])
        write_atomic(args.out, result)
        print(json.dumps(result['summary']))
    finally:
        db.close()


if __name__ == '__main__':
    main()
