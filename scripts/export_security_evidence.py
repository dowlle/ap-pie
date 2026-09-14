#!/usr/bin/env python3
"""Export public dispositions from a read-only audit cache outside the web tier.

Private reports are hashed locally and never included in the output.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sqlite3
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ap-web"))
from security_reviews import load_catalog, record_id, validate_catalog

VERDICTS = {"PASS": "pass", "NEEDS_REVIEW": "needs_review", "FAIL": "fail", "POLICY_HOLD": "held"}


def utc_date(value):
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def export(db, lock, summaries=(), holds=None, previous=()):
    records = {record_id(r): r for r in previous}
    with sqlite3.connect(f"{Path(db).resolve().as_uri()}?mode=ro", uri=True) as connection:
        audits = {sha: (verdict, report, date) for sha, verdict, report, date in connection.execute(
            "SELECT sha256, verdict, report, audited_at FROM audits")}
    identities = [(module, version, digest.lower()) for module, versions in lock.items()
                  if isinstance(versions, dict) for version, digest in versions.items()
                  if isinstance(digest, str) and re.fullmatch(r"[0-9a-fA-F]{64}", digest)]
    identity_set = set(identities)

    def add(module, version, digest, status, date, method, report_hash):
        record = dict(module=module, version=version, sha256=digest, status=status,
                      reviewed_at=utc_date(date), method=method, report_sha256=report_hash)
        validate_catalog({"schema": 1, "records": [record]})
        records[record_id(record)] = record

    for module, version, digest in identities:
        audit = audits.get(digest)
        if not audit or audit[0] not in VERDICTS or not isinstance(audit[1], str) or not audit[1].strip():
            continue
        verdict, report, date = audit
        add(module, version, digest, VERDICTS[verdict], date, "automated-source-review",
            hashlib.sha256(report.encode()).hexdigest())
    for summary in summaries:
        for item in json.loads(Path(summary).read_text())["results"]:
            identity = (item.get("module"), item.get("version"), item.get("sha256"))
            if identity not in identity_set or item.get("status") not in VERDICTS:
                continue
            report = Path(item["report"])
            if not report.is_file():
                continue
            date = datetime.fromtimestamp(report.stat().st_mtime, timezone.utc).isoformat()
            add(*identity, VERDICTS[item["status"]], date,
                "source-review-with-qa" if item.get("qa") else "automated-source-review",
                hashlib.sha256(report.read_bytes()).hexdigest())
    # Holds augment the underlying audit and cannot be erased by PASS.
    held_versions = set()
    if holds:
        policy = json.loads(Path(holds).read_text())
        held_versions.update((module, version) for module, versions in policy.get("version_holds", {}).items()
                             for version in versions)
        for module, reason in policy.get("security_holds", {}).items():
            if module.startswith("_") or not isinstance(reason, str):
                continue
            match = re.match(r"^(\S+)\s+bundles\b", reason)
            if match:
                held_versions.add((module, match[1]))
    for record in list(records.values()):
        if (record["module"], record["version"]) in held_versions:
            held = {**record, "status": "held"}
            records[record_id(held)] = held
    result = {"schema": 1, "records": sorted(records.values(), key=lambda r: (
        r["module"], r["version"], r["sha256"], r["reviewed_at"], r["status"]))}
    validate_catalog(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--lock", required=True)
    parser.add_argument("--summary", action="append", default=[])
    parser.add_argument("--holds")
    parser.add_argument("--previous", action="append", default=[])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    previous = [r for path in args.previous for r in load_catalog(path)]
    result = export(args.db, tomllib.loads(Path(args.lock).read_text()), args.summary, args.holds, previous)
    destination = Path(args.out)
    pending = destination.with_suffix(destination.suffix + ".pending")
    pending.write_text(json.dumps(result, indent=2) + "\n")
    pending.replace(destination)
    print(json.dumps({"records": len(result["records"])}))


if __name__ == "__main__":
    main()
