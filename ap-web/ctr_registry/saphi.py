"""Candidate import from Project Saphi's public v2 track endpoints.

What it reads: the track list (`/api/v2/tracks`) and each track's download
listing (`/api/v2/tracks/{id}/downloads`). What it keeps: titles, authors,
versions, download ids, CRC32 values and the page link when the API gives one.
What it never does: call the file download endpoint, store or serve a track
file. Hashing the real bytes is a separate later step on Atlas
(ctr_registry.hashing); this job only leaves `pending` revisions for it.

Courtesy: one identified User-Agent, https to a single host, a pause between
requests, a size cap and a timeout on every response. Run it by hand or from an
Atlas timer, never from a web request.

The field mapping is tolerant (several spellings per field) because the live
response shape was recorded in notes rather than pinned by a schema. The first
live run should be checked against `normalize_track` output before batch
approval.
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Callable, Optional
from urllib.parse import urlparse

from psycopg2.extras import Json

from ctr_registry import notify, rules, store

SAPHI_HOST = "www.projectsaphi.com"
BASE = f"https://{SAPHI_HOST}/api/v2"
USER_AGENT = "AP-Pie-registry-import/1 (+https://ap-pie.com)"
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = 20
PAUSE_SECONDS = 1.0
#: Refuse to flip more than this share of known Saphi entries to
#: source-unavailable in one run: a truncated list must not hide the catalogue.
MAX_MISSING_SHARE = 0.2


class SaphiError(RuntimeError):
    pass


def http_get_json(url: str) -> object:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != SAPHI_HOST:
        raise SaphiError("Only https://%s is allowed" % SAPHI_HOST)
    if "/downloads/" in parsed.path:
        raise SaphiError("The file download endpoint is never called")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 (host pinned above)
        body = resp.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise SaphiError("Response too large")
    return json.loads(body)


def _first(raw: dict, *names, default=None):
    for name in names:
        if raw.get(name) not in (None, ""):
            return raw[name]
    return default


def _items(doc: object, *keys: str) -> list:
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        for key in keys:
            if isinstance(doc.get(key), list):
                return doc[key]
    raise SaphiError("Unexpected response shape")


def normalize_track(raw: dict, downloads: Optional[list] = None) -> Optional[dict]:
    """A Saphi track as the importer uses it, or None when it has no id/title."""
    if not isinstance(raw, dict):
        return None
    track_id = _first(raw, "id", "track_id")
    title = _first(raw, "title", "name")
    if type(track_id) is not int or not isinstance(title, str) or not title.strip():
        return None
    authors = _first(raw, "authors", "author", "creator", "creators", default=[])
    if isinstance(authors, str):
        authors = [authors]
    names = []
    for a in authors if isinstance(authors, list) else []:
        name = a.get("name") or a.get("username") if isinstance(a, dict) else a
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    url = _first(raw, "url", "page_url", "link")
    groups: dict[str, list] = {}
    for d in downloads or []:
        if not isinstance(d, dict):
            continue
        did = _first(d, "id", "download_id")
        if type(did) is not int:
            continue
        version = str(_first(d, "version", "name", default=did))
        crc = _first(d, "crc32", "crc", "checksum")
        groups.setdefault(version, []).append({
            "download_id": did,
            "kind": str(_first(d, "type", "file_type", "kind", "format", default="")).lower() or None,
            "crc32": str(crc).lower() if crc is not None else None,
        })
    return {
        "saphi_id": track_id,
        "title": title.strip(),
        "authors": names,
        "category": _first(raw, "type", "category", "kind"),
        "url": url if isinstance(url, str) and url.startswith("https://") else None,
        "versions": groups,
    }


def _entry_fields(track: dict) -> tuple[str, list, dict, dict]:
    title = rules.clean_title(track["title"], strict=False)
    credits = rules.clean_credits([{"name": n, "role": "track"} for n in track["authors"]], strict=False)
    links = {}
    if track["url"]:
        try:
            links = rules.clean_links({"saphi": track["url"]})
        except rules.RuleError:
            links = {}
    provenance = {"saphi": {"track_id": track["saphi_id"], "title": track["title"],
                            "category": track["category"], "url": track["url"]}}
    return title, credits, links, provenance


def _group_label(version: str) -> str:
    return version[: rules.REVISION_MAX_CHARS]


def import_track(cur, track: dict, queue: list) -> str:
    """Apply one normalized track. Returns created, refreshed, unchanged or drift.

    Approved entries are never edited: a new version or changed CRC32 becomes a
    pending submission and an alert in `queue` for the caller to push."""
    cur.execute("SELECT id, state FROM ctr_track_entries WHERE saphi_track_id = %s FOR UPDATE",
                (track["saphi_id"],))
    found = cur.fetchone()
    title, credits, links, provenance = _entry_fields(track)
    if found is None:
        cur.execute(
            """INSERT INTO ctr_track_entries
                   (state, display_title, credits, links, provenance, saphi_track_id, source)
               VALUES ('candidate', %s, %s, %s, %s, %s, 'saphi_import') RETURNING id""",
            (title, Json(credits), Json(links), Json(provenance), track["saphi_id"]),
        )
        entry_id = cur.fetchone()[0]
        for version, downloads in track["versions"].items():
            cur.execute(
                """INSERT INTO ctr_track_revisions (entry_id, revision, hash_state, provenance)
                   VALUES (%s, %s, 'pending', %s) ON CONFLICT DO NOTHING""",
                (entry_id, _group_label(version), Json({"saphi_downloads": downloads})),
            )
        store.record_action(cur, "saphi_import", entry_id=entry_id,
                            detail={"saphi_id": track["saphi_id"]})
        return "created"

    entry_id, state = found
    cur.execute("SELECT id, revision, hash_state, provenance FROM ctr_track_revisions WHERE entry_id = %s",
                (entry_id,))
    existing = {r[1]: r for r in cur.fetchall()}
    outcome = "unchanged"
    for version, downloads in track["versions"].items():
        label = _group_label(version)
        known = existing.get(label)
        if known is None:
            if state == rules.CANDIDATE:
                cur.execute(
                    """INSERT INTO ctr_track_revisions (entry_id, revision, hash_state, provenance)
                       VALUES (%s, %s, 'pending', %s)""",
                    (entry_id, label, Json({"saphi_downloads": downloads})))
                outcome = "refreshed" if outcome == "unchanged" else outcome
            elif _queue_submission(cur, entry_id, label, downloads, drift=False):
                queue.append(("new_version", track["title"], label))
                outcome = "drift"
            continue
        old_downloads = {d["download_id"]: d.get("crc32")
                         for d in (known[3] or {}).get("saphi_downloads", [])}
        changed = any(old_downloads.get(d["download_id"], d.get("crc32")) != d.get("crc32")
                      for d in downloads)
        if not changed:
            continue
        if state == rules.CANDIDATE and known[2] != "verified":
            cur.execute("UPDATE ctr_track_revisions SET provenance = %s WHERE id = %s",
                        (Json({"saphi_downloads": downloads}), known[0]))
            outcome = "refreshed" if outcome == "unchanged" else outcome
        else:
            crc = next((d.get("crc32") for d in downloads if d.get("crc32")), "x")
            drift_label = _group_label(f"{version}+{str(crc)[:8]}")
            if _queue_submission(cur, entry_id, drift_label, downloads, drift=True):
                queue.append(("crc_changed", track["title"], label))
                outcome = "drift"
    if outcome == "refreshed" and state == rules.CANDIDATE:
        cur.execute("UPDATE ctr_track_entries SET provenance = provenance || %s, updated_at = NOW() WHERE id = %s",
                    (Json(provenance), entry_id))
    return outcome


def _queue_submission(cur, entry_id: int, label: str, downloads: list, *, drift: bool) -> bool:
    cur.execute(
        """SELECT 1 FROM ctr_track_submissions
            WHERE target_entry_id = %s AND status = 'pending' AND source = 'saphi_import'
              AND payload->>'revision' = %s""", (entry_id, label))
    if cur.fetchone():
        return False
    payload = {"revision": label, "saphi": {"version": label, "downloads": downloads},
               "drift": drift,
               "note": "Saphi serves different bytes for a known version" if drift
               else "Saphi lists a new version"}
    cur.execute(
        """INSERT INTO ctr_track_submissions (kind, source, target_entry_id, payload)
           VALUES ('new_revision', 'saphi_import', %s, %s) RETURNING id""",
        (entry_id, Json(payload)))
    sub_id = cur.fetchone()[0]
    store.record_action(cur, "saphi_drift" if drift else "saphi_new_version", entry_id=entry_id,
                        submission_id=sub_id, detail={"revision": label})
    return True


def run_import(fetch: Callable[[str], object] = http_get_json, *, conn=None,
               sleep: Callable[[float], None] = time.sleep, pause: float = PAUSE_SECONDS,
               notifier=notify.push, limit: Optional[int] = None) -> dict:
    """Import the whole catalogue. Returns a summary dict.

    Only reads list and downloads-listing endpoints. A track whose download
    listing fails is skipped this run (counted under `errors`), not lost."""
    conn = store._conn(conn)
    listing = _items(fetch(f"{BASE}/tracks"), "tracks", "data", "results")
    summary = {"seen": 0, "created": 0, "refreshed": 0, "unchanged": 0, "drift": 0,
               "errors": 0, "missing": 0, "skipped": 0}
    queue: list = []
    seen_ids: set[int] = set()
    for raw in listing[: limit if limit else None]:
        base = normalize_track(raw)
        if base is None:
            summary["skipped"] += 1
            continue
        sleep(pause)
        try:
            downloads = _items(fetch(f"{BASE}/tracks/{base['saphi_id']}/downloads"), "downloads", "data", "results")
        except Exception:  # noqa: BLE001 - one bad track must not stop the run
            summary["errors"] += 1
            continue
        track = normalize_track(raw, downloads)
        seen_ids.add(track["saphi_id"])
        summary["seen"] += 1

        def work(cur, track=track):
            return import_track(cur, track, queue)

        summary[store._run(conn, work)] += 1

    if limit is None and summary["errors"] == 0 and seen_ids:
        summary["missing"] = mark_missing(conn, seen_ids, queue)
    if queue:
        notifier("CTR registry: Saphi changes", "; ".join(f"{k}: {t} {v}" for k, t, v in queue[:8]))
    elif summary["created"]:
        notifier("CTR registry: Saphi import", f"{summary['created']} new candidates to review")
    return summary


def mark_missing(conn, seen_ids: set[int], queue: list) -> int:
    """Flip entries Saphi no longer lists to source-unavailable, unless that
    would flip an implausible share (a truncated list)."""
    def work(cur):
        cur.execute("""SELECT id, display_title, saphi_track_id FROM ctr_track_entries
                        WHERE saphi_track_id IS NOT NULL
                          AND state IN ('candidate','approved','named')""")
        gone = [r for r in cur.fetchall() if r[2] not in seen_ids]
        cur.execute("SELECT COUNT(*) FROM ctr_track_entries WHERE saphi_track_id IS NOT NULL")
        total = cur.fetchone()[0]
        if not gone:
            return 0
        if total and len(gone) / total > MAX_MISSING_SHARE:
            queue.append(("missing_skipped", f"{len(gone)} of {total}", "list looks truncated"))
            return 0
        for entry_id, title, _ in gone:
            cur.execute("UPDATE ctr_track_entries SET state = 'source-unavailable', updated_at = NOW() WHERE id = %s",
                        (entry_id,))
            store.record_action(cur, "source_unavailable", entry_id=entry_id, detail={"by": "saphi_import"})
            queue.append(("source_unavailable", title, ""))
        return len(gone)

    return store._run(conn, work)
