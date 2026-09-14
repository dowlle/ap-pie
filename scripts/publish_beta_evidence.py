#!/usr/bin/env python3
"""Publish public review metadata and verified test-run links to beta only."""
import argparse
import json
import shlex
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

REMOTE_PUBLISH = '''
import json, sys, time
from pathlib import Path
from security_reviews import load_catalog, record_id, validate_catalog
from fuzz_evidence import load_provenance
payload = json.load(sys.stdin)
root = Path('/app/.state')
security = validate_catalog(payload['security'])
security += load_catalog(root / 'security-evidence.json')
security = list({record_id(r): r for r in security}.values())
fuzz = payload['fuzz']['records']
existing = root / 'fuzz-evidence.json'
if existing.is_file():
    fuzz += load_provenance(str(existing), str(root / 'absent-fuzz-evidence.json'), (time.time_ns(),))
fuzz = list({json.dumps(r, sort_keys=True): r for r in fuzz}.values())
pending_review = root / 'security-evidence.json.pending'
pending_fuzz = root / 'fuzz-evidence.json.pending'
pending_review.write_text(json.dumps({'schema': 1, 'records': security}) + '\\n')
pending_fuzz.write_text(json.dumps({'schema': 1, 'records': fuzz}) + '\\n')
load_catalog(pending_review)
if len(load_provenance(str(pending_fuzz), str(root / 'absent-fuzz-evidence.json'), (time.time_ns(),))) != len(fuzz):
    raise ValueError('Invalid fuzz provenance')
pending_review.replace(root / 'security-evidence.json')
pending_fuzz.replace(root / 'fuzz-evidence.json')
print(json.dumps({'review_records': len(security), 'fuzz_links': len(fuzz)}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beta-url", required=True)
    parser.add_argument("--ssh-target", required=True)
    parser.add_argument("--container", default="ap-pie-beta-ap-web-1")
    parser.add_argument("--db", required=True)
    parser.add_argument("--summary", action="append", default=[])
    parser.add_argument("--holds", required=True)
    parser.add_argument("--emitter", required=True)
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    address = urlparse(args.beta_url)
    if address.scheme != "https" or not address.hostname or not address.hostname.startswith("beta.") or address.username or args.container != "ap-pie-beta-ap-web-1":
        parser.error("Publisher is restricted to the beta website and beta container")
    work = Path(args.work_dir); work.mkdir(parents=True, exist_ok=True)
    scripts = Path(__file__).resolve().parent
    app = scripts.parent / "ap-web"
    with urllib.request.urlopen(args.beta_url.rstrip("/") + "/api/apworlds", timeout=30) as response:
        content = response.read(6 * 1024 * 1024 + 1)
    if len(content) > 6 * 1024 * 1024:
        raise ValueError("Catalog exceeds budget")
    catalog = json.loads(content)
    (work / "catalog.json").write_bytes(content)
    lock = []
    for world in catalog:
        versions = [v for v in world["versions"] if v.get("sha256")]
        if versions:
            lock.append("[" + json.dumps(world["name"]) + "]")
            lock.extend(json.dumps(v["version"]) + " = " + json.dumps(v["sha256"]) for v in versions)
    (work / "index.lock").write_text("\n".join(lock) + "\n")
    if not lock:
        raise ValueError("Beta must expose pinned archive checksums before publishing evidence")
    review = work / "security-evidence.json"; fuzz = work / "fuzz-evidence.json"
    command = [sys.executable, str(scripts / "export_security_evidence.py"), "--db", args.db,
               "--lock", str(work / "index.lock"), "--holds", args.holds, "--out", str(review)]
    for source in (app / "security-evidence.json", review):
        if source.is_file():
            command.extend(["--previous", str(source)])
    for summary in args.summary:
        command.extend(["--summary", summary])
    subprocess.run(command, check=True, timeout=60)
    command = [sys.executable, str(scripts / "export_fuzz_provenance.py"), "--emitter", args.emitter,
               "--catalog", str(work / "catalog.json"), "--lock", str(work / "index.lock"),
               "--cache", str(work / "github-cache"), "--out", str(fuzz)]
    for source in (app / "fuzz-evidence.json", fuzz):
        if source.is_file():
            command.extend(["--previous", str(source)])
    subprocess.run(command, check=True, timeout=900)
    payload = json.dumps({"security": json.loads(review.read_text()), "fuzz": json.loads(fuzz.read_text())})
    remote = shlex.join(["docker", "exec", "--user", "1000", "-i", args.container, "python", "-c", REMOTE_PUBLISH])
    subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", args.ssh_target, remote],
                   input=payload, text=True, check=True, timeout=60)


if __name__ == "__main__":
    main()
