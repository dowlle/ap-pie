"""Durable discovery state, independent of accepted-index merge eligibility.

No archive code is imported here. Evidence belongs to immutable release bytes;
source/guide metadata and queue progress can change independently.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

KINDS = ('security', 'generation', 'guide', 'schema')
HASH = re.compile(r'^[0-9a-f]{64}$')
MODULE = re.compile(r'^[A-Za-z0-9_ .-]{1,160}$')


def identity(*parts):
    return hashlib.sha256(json.dumps(parts, separators=(',', ':')).encode()).hexdigest()


class Ledger:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS sources (
            module TEXT PRIMARY KEY, metadata TEXT NOT NULL, updated REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY, module TEXT NOT NULL REFERENCES sources(module),
            version TEXT NOT NULL, url TEXT NOT NULL, expected TEXT,
            state TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt REAL NOT NULL DEFAULT 0, error TEXT, release_id TEXT,
            discovered REAL NOT NULL, updated REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS origins (
            candidate_id TEXT NOT NULL REFERENCES candidates(id), origin TEXT NOT NULL,
            detail TEXT NOT NULL, PRIMARY KEY(candidate_id,origin));
          CREATE TABLE IF NOT EXISTS releases (
            id TEXT PRIMARY KEY, module TEXT NOT NULL REFERENCES sources(module),
            version TEXT NOT NULL, sha256 TEXT NOT NULL, url TEXT NOT NULL,
            verified REAL NOT NULL, UNIQUE(module,version,sha256));
          CREATE TABLE IF NOT EXISTS holds (
            module TEXT NOT NULL, version TEXT NOT NULL, reason TEXT NOT NULL,
            PRIMARY KEY(module,version));
          CREATE TABLE IF NOT EXISTS jobs (
            release_id TEXT NOT NULL REFERENCES releases(id), kind TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt REAL NOT NULL DEFAULT 0, lease_until REAL,
            token TEXT, error TEXT, result TEXT,
            PRIMARY KEY(release_id,kind));
          CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, started REAL NOT NULL, finished REAL,
            status TEXT NOT NULL, summary TEXT);
          CREATE TABLE IF NOT EXISTS scans (
            module TEXT PRIMARY KEY REFERENCES sources(module), state TEXT NOT NULL,
            detail TEXT NOT NULL, updated REAL NOT NULL);
        ''')
        # Existing verified releases also acquire the independent schema job.
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO jobs (release_id,kind) SELECT id,'schema' FROM releases")

    def register(self, module, metadata):
        if not MODULE.fullmatch(module):
            raise ValueError('Invalid module key')
        old = self.db.execute('SELECT metadata FROM sources WHERE module=?', (module,)).fetchone()
        prior = json.loads(old[0]) if old else {}
        # An upstream observation never removes a reviewed guide or source identity.
        if prior.get('setup_guide'):
            metadata = {**metadata, 'setup_guide': prior['setup_guide']}
        self.db.execute('INSERT INTO sources VALUES (?,?,?) ON CONFLICT(module) '
                        'DO UPDATE SET metadata=excluded.metadata,updated=excluded.updated',
                        (module, json.dumps({**prior, **metadata}), time.time()))

    def hold(self, module, version, reason):
        self.db.execute('INSERT INTO holds VALUES (?,?,?) ON CONFLICT(module,version) '
                        'DO UPDATE SET reason=excluded.reason', (module, version, reason))

    def discover(self, module, version, url, expected=None, *, origin, detail=None, revision=None):
        if not isinstance(version, str) or not 0 < len(version) <= 200:
            raise ValueError('Invalid version')
        if expected is not None and not HASH.fullmatch(expected):
            raise ValueError('Invalid expected checksum')
        cid = identity(module, version, url, expected) if revision is None else identity(module, version, url, expected, revision)
        now = time.time()
        self.db.execute('INSERT OR IGNORE INTO candidates '
                        '(id,module,version,url,expected,discovered,updated) VALUES (?,?,?,?,?,?,?)',
                        (cid, module, version, url, expected, now, now))
        self.db.execute('INSERT INTO origins VALUES (?,?,?) ON CONFLICT(candidate_id,origin) '
                        'DO UPDATE SET detail=excluded.detail', (cid, origin, json.dumps(detail or {})))
        return cid

    def verified(self, candidate_id, digest):
        if not HASH.fullmatch(digest):
            raise ValueError('Invalid verified checksum')
        with self.db:
            c = self.db.execute('SELECT * FROM candidates WHERE id=?', (candidate_id,)).fetchone()
            if c is None:
                raise KeyError(candidate_id)
            if c['expected'] and c['expected'] != digest:
                raise ValueError('Checksum mismatch')
            rid = identity(c['module'], c['version'], digest)
            self.db.execute('INSERT OR IGNORE INTO releases VALUES (?,?,?,?,?,?)',
                            (rid, c['module'], c['version'], digest, c['url'], time.time()))
            self.db.execute("UPDATE candidates SET state='verified',release_id=?,error=NULL,updated=? WHERE id=?",
                            (rid, time.time(), candidate_id))
            for kind in KINDS:
                self.db.execute('INSERT OR IGNORE INTO jobs (release_id,kind) VALUES (?,?)', (rid, kind))
        return rid

    def retry_candidate(self, candidate_id, error, *, permanent=False):
        with self.db:
            row = self.db.execute('SELECT attempts FROM candidates WHERE id=?', (candidate_id,)).fetchone()
            attempts = row[0] + 1
            delay = min(86400, 60 * 2 ** min(attempts, 10))
            self.db.execute('UPDATE candidates SET state=?,attempts=?,next_attempt=?,error=?,updated=? WHERE id=?',
                            ('blocked' if permanent else 'retry', attempts, time.time() + delay,
                             str(error)[:300], time.time(), candidate_id))

    def claim(self, kind, *, now=None, lease_seconds=300):
        if kind not in KINDS:
            raise ValueError('Unknown job kind')
        now = time.time() if now is None else now
        token = identity(kind, now, time.monotonic_ns())
        self.db.execute('BEGIN IMMEDIATE')
        try:
            job = self.db.execute("SELECT * FROM jobs WHERE kind=? AND "
                                  "((state IN ('queued','retry') AND next_attempt<=?) OR "
                                  "(state='running' AND lease_until<=?)) ORDER BY next_attempt,release_id LIMIT 1",
                                  (kind, now, now)).fetchone()
            if job is None:
                self.db.commit()
                return None
            self.db.execute("UPDATE jobs SET state='running',lease_until=?,token=?,attempts=attempts+1 "
                            'WHERE release_id=? AND kind=?', (now + lease_seconds, token, job['release_id'], kind))
            self.db.commit()
            return {**dict(job), 'token': token}
        except BaseException:
            self.db.rollback()
            raise

    def finish(self, release_id, kind, token, result, *, error=None, blocked=False, now=None):
        now = time.time() if now is None else now
        state = 'blocked' if blocked else 'retry' if error else 'completed'
        with self.db:
            changed = self.db.execute('UPDATE jobs SET state=?,result=?,error=?,next_attempt=?,lease_until=NULL '
                                      "WHERE release_id=? AND kind=? AND token=? AND state='running' AND lease_until>?",
                                      (state, json.dumps(result), str(error)[:300] if error else None,
                                       now + 300 if error else 0, release_id, kind, token, now)).rowcount
            if changed != 1:
                raise ValueError('Expired or stale worker lease')

    def status(self):
        def counts(table):
            return {r['state']: r['n'] for r in self.db.execute(
                f'SELECT state,count(*) n FROM {table} GROUP BY state')}
        return {'sources': self.db.execute('SELECT count(*) FROM sources').fetchone()[0],
                'releases': self.db.execute('SELECT count(*) FROM releases').fetchone()[0],
                'holds': self.db.execute('SELECT count(*) FROM holds').fetchone()[0],
                'candidates': counts('candidates'), 'jobs': counts('jobs')}
