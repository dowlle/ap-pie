#!/usr/bin/env python3
"""Match saved fuzz results to public Actions runs without changing the index.

Uses the existing badge producer to reconstruct its result from source PR
checks. Requires the archive hash at that run's source commit and all saved
result fields to match. Cached public metadata stays outside the web tier.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path

FIELDS = ("verdict", "default_rate", "worst_hook", "worst_hook_rate", "seeds", "fuzzed_at")
REPO = "dowlle/Archipelago-index"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emitter", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--lock", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--previous", action="append", default=[])
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()
    cache = Path(args.cache); cache.mkdir(parents=True, exist_ok=True)

    def gh_text(*arguments):
        key = hashlib.sha256(json.dumps(arguments).encode()).hexdigest()
        path = cache / (key + ".txt")
        mutable = arguments[:2] in (("pr", "list"), ("pr", "view"))
        if path.is_file() and (not mutable or time.time() - path.stat().st_mtime < 1800):
            return path.read_text()
        completed = subprocess.run(["gh", *arguments], text=True, capture_output=True, timeout=60)
        if completed.returncode:
            raise RuntimeError("Public GitHub evidence request failed")
        pending = path.with_suffix(".pending"); pending.write_text(completed.stdout); pending.replace(path)
        return completed.stdout

    def gh_json(*arguments):
        return json.loads(gh_text(*arguments))

    spec = importlib.util.spec_from_file_location("badge_producer", args.emitter)
    producer = importlib.util.module_from_spec(spec); spec.loader.exec_module(producer)
    producer.gh_json = gh_json
    producer.gh_text = gh_text
    catalog = json.loads(Path(args.catalog).read_text())
    lock = tomllib.loads(Path(args.lock).read_text())
    existing = {(w["name"], v["version"]): v["fuzz_result"] for w in catalog for v in w["versions"] if v.get("fuzz_result")}
    records = []
    for previous in args.previous:
        records.extend(json.loads(Path(previous).read_text())["records"])
    prs = gh_json("pr", "list", "--repo", REPO, "--state", "merged", "--limit", str(args.limit), "--json", "number,title")
    for pr in prs:
        if not pr["title"].startswith("Add ") or "badge" in pr["title"].lower():
            continue
        data = gh_json("pr", "view", str(pr["number"]), "--repo", REPO, "--json", "headRefOid,statusCheckRollup")
        groups = {}
        for check in data["statusCheckRollup"]:
            parsed = producer.parse_check_name(check.get("name", ""))
            if parsed and (parsed[0], parsed[1]) in existing:
                groups.setdefault(parsed[:2], []).append(check)
        for (module, version), checks in groups.items():
            if any(check.get("conclusion") not in {"SUCCESS", "FAILURE"} for check in checks):
                continue
            run_urls = {match.group(1) for check in checks if (match := re.fullmatch(
                r"(https://github\.com/dowlle/Archipelago-index/actions/runs/[0-9]+)/job/[0-9]+", check.get("detailsUrl", "")))}
            if len(run_urls) != 1:
                continue
            result = producer._pull_pr_verdict_from_checks(pr["number"], checks)
            if not result or not all(result[field] == existing[(module, version)][field] for field in FIELDS):
                continue
            url = run_urls.pop(); run_id = url.rsplit("/", 1)[-1]
            run = gh_json("run", "view", run_id, "--repo", REPO, "--json", "headSha,status")
            if run["status"] != "completed" or run["headSha"] != data["headRefOid"]:
                continue
            content = gh_json("api", f"repos/{REPO}/contents/index.lock?ref={run['headSha']}")
            source_lock = tomllib.loads(base64.b64decode(content["content"]).decode())
            digest = lock.get(module, {}).get(version)
            if not digest or digest != source_lock.get(module, {}).get(version):
                continue
            record = {"module": module, "version": version, "sha256": digest, "report_url": url,
                      **{field: result[field] for field in FIELDS}}
            records.append(record)
            print(json.dumps({"module": module, "version": version, "run": run_id}), flush=True)
    unique = {json.dumps(r, sort_keys=True): r for r in records}
    payload = {"schema": 1, "records": sorted(unique.values(), key=lambda r: (r["module"], r["version"], r["fuzzed_at"]))}
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ap-web"))
    from fuzz_evidence import load_provenance
    destination = Path(args.out); pending = destination.with_suffix(".pending")
    pending.write_text(json.dumps(payload, indent=2) + "\n")
    if len(load_provenance(str(pending), str(cache / "absent.json"), (time.time_ns(),))) != len(payload["records"]):
        raise ValueError("Invalid generated provenance")
    pending.replace(destination)
    print(json.dumps({"records": len(payload["records"])}))


if __name__ == "__main__":
    main()
