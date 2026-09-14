"""Run intake phases with discovery publication preceding evidence work."""
import argparse
import importlib.util
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
import uncached_security
import collect_generation
from refresh_sources import refresh
from scan_sources import scan
from verify_queue import batch_rows, run_batch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ap-lib'))
import discovery as discovery_loader
from publish_beta_discovery import publish as publish_beta_discovery
from publish_beta_discovery import publish_schemas
from publish_beta_evidence import publish as publish_beta_evidence
from publish_beta_archives import publish as publish_beta_archives


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
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--evidence-limit', type=int, help='Independent bounded evidence work per cycle')
    p.add_argument('--beta-ssh-target', help='Publish discovery before evidence work to the fixed beta container')
    p.add_argument('--audit-db', type=Path, help='Read-only existing source-review cache')
    p.add_argument('--review-summary', type=Path, action='append', default=[], help='Existing exact-checksum QA summary')
    p.add_argument('--index-source', type=Path, help='Dedicated canonical-index source checkout')
    p.add_argument('--holds', type=Path, help='Existing policy holds, retained independently')
    p.add_argument('--generation-emitter', type=Path, help='Trusted existing Actions evidence parser; never starts tests')
    p.add_argument('--review-runner', type=Path, help='Trusted existing source extractor and audit prompt')
    p.add_argument('--review-runtime', type=Path, help='Native headless review runtime directory')
    p.add_argument('--review-auth', type=Path, help='Provider-only login file; never application credentials')
    p.add_argument('--review-limit', type=int, default=1, help='Maximum uncached model reviews per cycle')
    a = p.parse_args()
    if not 1 <= a.limit <= 500 or not 1 <= a.workers <= 8:
        p.error('limit must be 1..500 and workers 1..8')
    evidence_limit = a.limit if a.evidence_limit is None else a.evidence_limit
    if not 1 <= evidence_limit <= 500:
        p.error('evidence-limit must be 1..500')
    if not 1 <= a.review_limit <= 4:
        p.error('review-limit must be 1..4')
    if a.review_runner and not (a.review_runtime and a.review_auth):
        p.error('review-runner requires review-runtime and review-auth')
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
                rows = batch_rows(ledger, a.limit)
                return [r['status'] for r in run_batch(ledger, rows, a.archives, workers=a.workers)]

            def discovery():
                path = a.out_dir / 'discovery.json'
                snapshot.write_atomic(path, snapshot.export(ledger), validate=discovery_loader.load)
                if a.beta_ssh_target:
                    publish_beta_archives(a.beta_ssh_target, json.loads(path.read_text()), a.archives)
                    publish_beta_discovery(a.beta_ssh_target, path)

            def security():
                records = security_snapshot.load_catalog(a.security)
                if a.audit_db:
                    records += cached_security.export(ledger, a.audit_db, a.review_summary)
                completed = import_security.process(ledger, records, limit=evidence_limit, cached_only=bool(a.review_runner))
                if a.review_runner:
                    completed += uncached_security.process(ledger, a.archives, a.out_dir.parent/'private-reviews',
                        uncached_security.load_runner(a.review_runner), a.review_runtime, a.review_auth, limit=a.review_limit)
                snapshot.write_atomic(a.out_dir / 'security-evidence.json', security_snapshot.export(ledger, records))
                return completed

            def generation():
                records = import_generation.validate(json.loads(a.generation.read_text())['records'])
                if a.generation_emitter and a.index_source:
                    spec = importlib.util.spec_from_file_location('intake_actions_parser', a.generation_emitter)
                    producer = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(producer)
                    producer.gh_text, producer.gh_json = collect_generation.gh_text, collect_generation.gh_json
                    prs = json.loads((a.index_source.parent / 'queued-prs.json').read_text())
                    records += collect_generation.collect(ledger, prs, producer)['records']
                completed = import_generation.process(ledger, records, limit=evidence_limit)
                snapshot.write_atomic(a.out_dir / 'fuzz-evidence.json', generation_snapshot.export(ledger, records))
                return completed

            def schemas():
                completed = schema_queue.process(ledger, a.archives, limit=evidence_limit)
                snapshot.write_atomic(a.out_dir / 'discovery-schemas.json', schema_snapshot.export(ledger))
                if a.beta_ssh_target:
                    publish_schemas(a.beta_ssh_target, a.out_dir / 'discovery-schemas.json')
                return completed

            steps = [('security', security), ('generation', generation), ('schema', schemas),
                     ('guide', lambda: guide_queue.process(ledger, evidence_limit))]
            if a.beta_ssh_target:
                steps.append(('evidence_publication', lambda: publish_beta_evidence(a.beta_ssh_target,
                              a.out_dir / 'security-evidence.json', a.out_dir / 'fuzz-evidence.json')))
            def scan_sources():
                if a.index_source:
                    refresh(ledger, a.index_source, a.holds)
                return scan(ledger, a.cache)

            result = cycle(ledger, scan_sources=scan_sources, verify=verify,
                           publish_discovery=discovery, evidence_steps=steps)
            print(json.dumps(result))
            if result['status'] == 'failed':
                raise SystemExit(1)
        finally:
            ledger.db.close()


if __name__ == '__main__':
    main()
