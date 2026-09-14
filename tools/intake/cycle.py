"""Run intake phases with discovery publication preceding evidence work."""
import argparse
import fcntl
import json
import time
import uuid
import sys
from pathlib import Path
from ledger import Ledger
import snapshot
import schema_snapshot
import security_snapshot
import generation_snapshot
import schema_queue
import guide_queue
import import_security
import import_generation
import cached_security
from scan_sources import scan
from verify_queue import run_candidate
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ap-lib'))
import discovery as discovery_loader
from publish_beta_discovery import publish as publish_beta_discovery
from publish_beta_discovery import publish_schemas
from publish_beta_evidence import publish as publish_beta_evidence


def cycle(ledger, *, scan_sources, verify, publish_discovery, evidence_steps):
    run_id = uuid.uuid4().hex
    with ledger.db:
        ledger.db.execute('INSERT INTO runs(id,started,status) VALUES(?,?,?)', (run_id, time.time(), 'running'))
    phases = {}
    try:
        phases['scan'] = scan_sources()
        phases['verification'] = verify()
        # This callback must finish publication before any evidence worker runs.
        publish_discovery()
        phases['discovery'] = 'published'
        for name, action in evidence_steps:
            try:
                phases[name] = action()
            except Exception as exc:
                phases[name] = {'error': type(exc).__name__}
        publish_discovery()  # Refresh job states independently of verdicts.
        status = 'partial' if any(isinstance(v, dict) and 'error' in v for v in phases.values()) else 'completed'
    except Exception as exc:
        phases['fatal'] = {'error': type(exc).__name__}
        status = 'failed'
    with ledger.db:
        ledger.db.execute('UPDATE runs SET finished=?,status=?,summary=? WHERE id=?',
                          (time.time(), status, json.dumps(phases), run_id))
    return {'run_id': run_id, 'status': status, 'phases': phases, 'queue': ledger.status()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--archives', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--security', type=Path, required=True)
    p.add_argument('--generation', type=Path, required=True)
    p.add_argument('--limit', type=int, default=5)
    p.add_argument('--beta-ssh-target', help='Publish discovery before evidence work to the fixed beta container')
    p.add_argument('--audit-db', type=Path, help='Read-only existing source-review cache')
    a = p.parse_args()
    if not 1 <= a.limit <= 50:
        p.error('limit must be between 1 and 50')
    a.out_dir.mkdir(parents=True, exist_ok=True)
    with a.db.with_suffix('.cycle.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({'status': 'already-running'}))
            return
        ledger = Ledger(a.db)
        try:
            def verify():
                rows = ledger.pending_candidates(limit=a.limit)
                return [run_candidate(ledger, row, a.archives)['status'] for row in rows]

            def discovery():
                path = a.out_dir / 'discovery.json'
                snapshot.write_atomic(path, snapshot.export(ledger), validate=discovery_loader.load)
                if a.beta_ssh_target:
                    publish_beta_discovery(a.beta_ssh_target, path)

            def security():
                records = security_snapshot.load_catalog(a.security)
                if a.audit_db:
                    records += cached_security.export(ledger, a.audit_db)
                completed = import_security.process(ledger, records, limit=a.limit)
                snapshot.write_atomic(a.out_dir / 'security-evidence.json', security_snapshot.export(ledger, records))
                return completed

            def generation():
                records = import_generation.validate(json.loads(a.generation.read_text())['records'])
                completed = import_generation.process(ledger, records, limit=a.limit)
                snapshot.write_atomic(a.out_dir / 'fuzz-evidence.json', generation_snapshot.export(ledger, records))
                return completed

            def schemas():
                completed = schema_queue.process(ledger, a.archives, limit=a.limit)
                snapshot.write_atomic(a.out_dir / 'discovery-schemas.json', schema_snapshot.export(ledger))
                if a.beta_ssh_target:
                    publish_schemas(a.beta_ssh_target, a.out_dir / 'discovery-schemas.json')
                return completed

            steps = [('security', security), ('generation', generation), ('schema', schemas),
                     ('guide', lambda: guide_queue.process(ledger, a.limit))]
            if a.beta_ssh_target:
                steps.append(('evidence_publication', lambda: publish_beta_evidence(a.beta_ssh_target,
                              a.out_dir / 'security-evidence.json', a.out_dir / 'fuzz-evidence.json')))
            result = cycle(ledger, scan_sources=lambda: scan(ledger, a.cache), verify=verify,
                           publish_discovery=discovery, evidence_steps=steps)
            print(json.dumps(result))
            if result['status'] == 'failed':
                raise SystemExit(1)
        finally:
            ledger.db.close()


if __name__ == '__main__':
    main()
