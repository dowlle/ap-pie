"""Read public audit metadata; never load private reports into the web tier."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from functools import lru_cache
import logging

STATUSES = {"pass", "needs_review", "fail", "held", "human_accepted"}
METHODS = {"automated-source-review", "source-review-with-qa", "maintainer-decision"}
MAX_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 10000
_last_valid_overlay = {}
SUMMARIES = {
    "pass": "The automated source review reported no issues for these exact archive bytes. This is a bounded review, not a safety guarantee or gameplay test.",
    "needs_review": "The source review flagged behavior requiring human assessment. This archive has not received a passing review disposition.",
    "fail": "The source review did not clear this archive. A failed review does not by itself establish malicious intent.",
    "held": "This release is held for a maintainer decision. A passing automated result cannot clear the hold.",
    "human_accepted": "A human explicitly accepted the recorded concerns for these exact archive bytes. This does not erase the original review findings.",
}


def record_id(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_catalog(payload):
    if not isinstance(payload, dict) or set(payload) != {"schema", "records"} or type(payload["schema"]) is not int or payload["schema"] != 1:
        raise ValueError("Invalid evidence schema")
    records = payload["records"]
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError("Invalid record count")
    allowed = {"module", "version", "sha256", "status", "reviewed_at", "method", "report_sha256"}
    for record in records:
        if not isinstance(record, dict) or set(record) not in (allowed, allowed | {"rationale"}):
            raise ValueError("Invalid public record fields")
        if "rationale" in record:
            text = record["rationale"]
            if (not isinstance(text, str) or not 20 <= len(text) <= 600 or
                    any(ord(c) < 32 for c in text) or
                    len(re.findall(r"[.!?](?:\s|$)", text)) not in (1, 2) or
                    re.search(r"https?://|/home/|/root/|/tmp/|[<>`]|api[_ -]?key|Bearer\s", text, re.I)):
                raise ValueError("Invalid public rationale")
        if not isinstance(record["module"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", record["module"]):
            raise ValueError("Invalid module")
        if not isinstance(record["version"], str) or not 0 < len(record["version"]) <= 160 or any(ord(c) < 32 for c in record["version"]):
            raise ValueError("Invalid version")
        for field in ("sha256", "report_sha256"):
            if not isinstance(record[field], str) or not re.fullmatch(r"[0-9a-f]{64}", record[field]):
                raise ValueError("Invalid digest")
        if not isinstance(record["status"], str) or not isinstance(record["method"], str) or record["status"] not in STATUSES or record["method"] not in METHODS:
            raise ValueError("Invalid review state")
        if not isinstance(record["reviewed_at"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", record["reviewed_at"]):
            raise ValueError("Invalid review date")
        datetime.strptime(record["reviewed_at"], "%Y-%m-%dT%H:%M:%SZ")
    return records


def load_catalog(path):
    path = Path(path)
    if not path.is_file():
        return []
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Evidence file exceeds budget")
    return validate_catalog(json.loads(path.read_text()))


def fingerprint(path):
    try:
        stat = Path(path).stat()
        return (stat.st_ino, stat.st_size, stat.st_mtime_ns)
    except FileNotFoundError:
        return None


@lru_cache(maxsize=4)
def load_snapshot(seed, overlay, stamp):
    # The stamp is part of the cache key; publisher uses atomic file replace.
    records = load_catalog(seed)
    try:
        extra = load_catalog(overlay)
        _last_valid_overlay[overlay] = extra
    except (ValueError, OSError):
        logging.getLogger(__name__).warning("Invalid runtime review evidence; retaining previous dispositions")
        extra = _last_valid_overlay.get(overlay)
        if extra is None:
            # Without a previous snapshot, unseen holds must not become PASS.
            records = [r for r in records if r["status"] not in {"pass", "human_accepted"}]
            extra = []
    records += extra
    return list({record_id(r): r for r in records}.values())


def public_record(record):
    return {**record, "id": record_id(record), "summary": SUMMARIES[record["status"]],
            "report_public": False}


def join_reviews(world_dict, records):
    """Require module, version and full digest; never inherit earlier clearance."""
    ranking = {"pass": 0, "human_accepted": 1, "needs_review": 2, "fail": 3, "held": 4}
    for version in world_dict["versions"]:
        candidates = [r for r in records if r["module"] == world_dict["name"] and
                      r["version"] == version["version"] and r["sha256"] == version.get("sha256")]
        # A hold or QA concern remains effective until an explicit accepted
        # decision supersedes it. Routine automated PASS never erases it.
        accepted = [r for r in candidates if r["status"] == "human_accepted" and r["method"] == "maintainer-decision"]
        if accepted:
            decision = max(accepted, key=lambda r: r["reviewed_at"])
            candidates = [r for r in candidates if r["reviewed_at"] >= decision["reviewed_at"]]
        chosen = max(candidates, key=lambda r: (ranking[r["status"]], r["reviewed_at"], bool(r.get("rationale")))) if candidates else None
        version["security_review"] = public_record(chosen) if chosen else None
    return world_dict
