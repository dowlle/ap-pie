"""Hook for the later hashing step (CTR verifier on Atlas).

The plan: an Atlas job downloads a Saphi file to a temporary directory, runs
the CTR verifier on it, deletes the bytes, and hands only the result here.
Nothing in AP-Pie downloads, stores or serves track files, and this module does
not either. It exposes the two calls that job needs:

- `pending()` lists revisions waiting for a verdict, with their Saphi locators
- `attach_from_file(path)` reads a verifier result JSON and stores it

Result file shape (one revision per file):

    {"revision_id": 12,
     "content_id": "<64 hex>",
     "files": {"lev": {"sha256": "<64 hex>", "size": 12345}, "vrm": {...}},
     "modes": ["time_trial"],
     "evidence": {"verifier_version": "...", "verifier_artifact_sha256": "<64 hex>",
                  "level": "static" | "runtime"},
     "apworld_min": "0.3.0", "apworld_max": null}

Hashes already verified never change (database trigger plus
rules.revision_violations). Nothing here runs as part of the web app.
"""

from __future__ import annotations

import json
from pathlib import Path

from ctr_registry import store


def pending(conn=None) -> list[dict]:
    return store.pending_hash_revisions(conn=conn)


def attach_from_file(path: str, conn=None) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return store.attach_evidence(
        int(data["revision_id"]),
        content_id=data["content_id"],
        files=data["files"],
        evidence=data.get("evidence", {}),
        modes=data.get("modes", []),
        apworld_min=data.get("apworld_min"),
        apworld_max=data.get("apworld_max"),
        conn=conn,
    )
