"""Read existing source-review dispositions for exact verified archive bytes."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from import_security import validate_catalog

STATUSES = {'PASS': 'pass', 'NEEDS_REVIEW': 'needs_review', 'FAIL': 'fail', 'POLICY_HOLD': 'held'}


def export(ledger, audit_db, summaries=()):
    records = []
    with sqlite3.connect(Path(audit_db).resolve().as_uri() + '?mode=ro', uri=True) as cache:
        for release in ledger.db.execute('SELECT module,version,sha256 FROM releases'):
            audit = cache.execute('SELECT verdict,report,audited_at FROM audits WHERE sha256=?', (release['sha256'],)).fetchone()
            if audit is None or audit[0] not in STATUSES or not isinstance(audit[1], str) or not audit[1].strip():
                continue
            date = datetime.fromisoformat(audit[2])
            date = date.replace(tzinfo=date.tzinfo or timezone.utc).astimezone(timezone.utc)
            records.append({'module': release['module'], 'version': release['version'], 'sha256': release['sha256'],
                            'status': STATUSES[audit[0]], 'reviewed_at': date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'method': 'automated-source-review', 'report_sha256': hashlib.sha256(audit[1].encode()).hexdigest()})
    identities = {(r['module'], r['version'], r['sha256']) for r in ledger.db.execute('SELECT module,version,sha256 FROM releases')}
    for summary in summaries:
        for item in json.loads(Path(summary).read_text())['results']:
            identity = (item.get('module'), item.get('version'), item.get('sha256'))
            if identity not in identities or item.get('status') not in STATUSES:
                continue
            report = Path(item['report'])
            if not report.is_file():
                continue
            date = datetime.fromtimestamp(report.stat().st_mtime, timezone.utc)
            records.append({'module': identity[0], 'version': identity[1], 'sha256': identity[2],
                            'status': STATUSES[item['status']], 'reviewed_at': date.strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'method': 'source-review-with-qa' if item.get('qa') else 'automated-source-review',
                            'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest()})
    return validate_catalog({'schema': 1, 'records': records})
