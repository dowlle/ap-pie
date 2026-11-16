"""Seed a database from a registry directory (the public repository's files).

The repository is the record. This loads it into an empty database, or one
that already matches, keeping every identity value exactly: track_key,
block_index, a frozen ap_name, shipped_in, revision strings, content_id, file
hashes and descriptors. It runs the registry checker and the DIGEST.json
comparison first, and it refuses to write anything if one track conflicts
with a row already present.

Rules:
- A track already in the database that equals its file (compared as the same
  canonical export document) is skipped: re-running is a no-op.
- A track whose key, block_index, Saphi id or content_id is held by a
  different row, or whose stored values differ from the file, is a conflict.
  Nothing is written when any conflict exists.
- Rows in the database that are not in the directory are left alone and
  reported. They only matter if they hold a block_index the directory needs.
- Submitter identities and review history are not in the directory, so the
  seeded rows have none. Each new row gets one `seed` review action carrying
  the directory digest.

The whole load is one transaction under the registry lock.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from psycopg2.extras import Json

from ctr_registry import check, export, rules, store


class SeedError(Exception):
    """The directory is invalid or conflicts with the database."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems[:5]) + (f" (+{len(problems) - 5} more)" if len(problems) > 5 else ""))
        self.problems = problems


def _load_tracks(root: Path) -> list[dict]:
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / "tracks").glob("*.json"))]
    docs.sort(key=lambda d: (d.get("block_index") is None, d.get("block_index") or 0, d["track_key"]))
    return docs


def _validate_directory(root: Path) -> str:
    if not (root / "registry.json").is_file() or not (root / "tracks").is_dir():
        raise SeedError([f"{root} is not a registry directory"])
    problems = check.check(root)
    digest_file = root / export.DIGEST_FILE
    if digest_file.is_file():
        stated = json.loads(digest_file.read_text("utf-8")).get("digest")
        actual = check.digest_of(root)
        if stated != actual:
            problems.append(f"DIGEST.json says {stated} but the files hash to {actual}")
    else:
        problems.append("DIGEST.json is missing")
    if problems:
        raise SeedError(problems)
    return check.digest_of(root)


def _stored_doc(entry: dict, revisions: list[dict], keys_by_id: dict) -> bytes:
    return export.canonical(export.entry_doc(entry, revisions, keys_by_id, True))


def _entry_values(doc: dict) -> dict:
    saphi = (doc.get("provenance") or {}).get("saphi") or {}
    reviewed = doc.get("review", {}).get("reviewed_at")
    # Noon UTC keeps the stored date stable in any session time zone.
    reviewed_at = (datetime.fromisoformat(reviewed).replace(hour=12, tzinfo=timezone.utc)
                   if reviewed else None)
    return {
        "track_key": doc["track_key"], "state": doc["state"], "display_title": doc["display_title"],
        "credits": doc.get("credits") or [], "links": doc.get("links") or {},
        "provenance": doc.get("provenance") or {}, "block_index": doc.get("block_index"),
        "ap_name": doc.get("ap_name"), "shipped_in": doc.get("shipped_in"),
        "mint_status": doc.get("mint_status") or "mint", "maps_to": doc.get("maps_to"),
        "saphi_track_id": saphi.get("track_id"), "source": "saphi_import" if saphi else "admin",
        "reviewed_at": reviewed_at,
    }


def seed_from_directory(directory: str, *, dry_run: bool = False, conn=None) -> dict:
    root = Path(directory)
    digest = _validate_directory(root)
    docs = _load_tracks(root)
    conn = store._conn(conn)

    def work(cur):
        cur.execute(f"SELECT {store.ENTRY_COLUMNS} FROM ctr_track_entries")
        rows = store._rows(cur)
        by_key = {r["track_key"]: r for r in rows if r["track_key"]}
        by_block = {r["block_index"]: r for r in rows if r["block_index"] is not None}
        by_saphi = {r["saphi_track_id"]: r for r in rows if r["saphi_track_id"] is not None}
        keys_by_id = {r["id"]: r["track_key"] for r in rows if r["track_key"]}
        revs_by_entry = store.revisions_for([r["id"] for r in rows], cur=cur)
        cur.execute("SELECT content_id FROM ctr_track_revisions WHERE content_id IS NOT NULL")
        used_content = {r[0] for r in cur.fetchall()}

        problems: list[str] = []
        todo: list[dict] = []
        skipped = 0
        wanted_keys = {d["track_key"] for d in docs}
        for doc in docs:
            key = doc["track_key"]
            row = by_key.get(key)
            if row is not None:
                stored = _stored_doc(row, revs_by_entry.get(row["id"], []), keys_by_id)
                wanted = export.canonical(doc)
                if stored == wanted:
                    skipped += 1
                else:
                    a, b = json.loads(stored), doc
                    fields = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
                    problems.append(f"{key}: database row differs from the file in {', '.join(fields)}")
                continue
            vals = _entry_values(doc)
            holder = by_block.get(vals["block_index"]) if vals["block_index"] is not None else None
            if holder is not None:
                problems.append(f"{key}: block_index {vals['block_index']} is held by {holder['track_key'] or 'entry ' + str(holder['id'])}")
            holder = by_saphi.get(vals["saphi_track_id"]) if vals["saphi_track_id"] is not None else None
            if holder is not None:
                problems.append(f"{key}: Saphi track {vals['saphi_track_id']} is held by {holder['track_key'] or 'entry ' + str(holder['id'])}")
            for rev in doc.get("revisions", []):
                if rev.get("content_id") and rev["content_id"] in used_content:
                    problems.append(f"{key}: content_id {rev['content_id'][:12]} already exists in the database")
            todo.append(doc)
        if problems:
            raise SeedError(problems)

        extra = sorted(k for k in by_key if k not in wanted_keys)
        if dry_run:
            return {"would_insert": len(todo), "skipped": skipped, "extra_in_database": extra}

        inserted_ids: dict[str, int] = {}
        for doc in todo:
            v = _entry_values(doc)
            cur.execute(
                """INSERT INTO ctr_track_entries
                       (track_key, block_index, state, ap_name, shipped_in, display_title, credits,
                        links, provenance, saphi_track_id, source, reviewed_at, mint_status, maps_to)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (v["track_key"], v["block_index"], v["state"], v["ap_name"], v["shipped_in"],
                 v["display_title"], Json(v["credits"]), Json(v["links"]), Json(v["provenance"]),
                 v["saphi_track_id"], v["source"], v["reviewed_at"], v["mint_status"], v["maps_to"]))
            entry_id = cur.fetchone()[0]
            inserted_ids[doc["track_key"]] = entry_id
            for rev in doc.get("revisions", []):
                cur.execute(
                    """INSERT INTO ctr_track_revisions
                           (entry_id, revision, content_id, files, descriptor_schema, descriptor,
                            evidence, modes, apworld_min, apworld_max, hash_state, provenance)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (entry_id, rev["revision"], rev.get("content_id"), Json(rev.get("files") or {}),
                     rev.get("descriptor_schema"),
                     Json(rev["descriptor"]) if rev.get("descriptor") is not None else None,
                     Json(rev.get("evidence") or {}), Json(rev.get("modes") or []),
                     rev.get("apworld_min"), rev.get("apworld_max"), rev.get("hash_state", "pending"),
                     Json(rev.get("provenance") or {})))
            store.record_action(cur, "seed", entry_id=entry_id, detail={"registry_digest": digest})
        for doc in todo:
            target = (doc.get("review") or {}).get("superseded_by")
            if target:
                target_id = inserted_ids.get(target) or by_key.get(target, {}).get("id")
                if target_id is None:
                    raise SeedError([f"{doc['track_key']}: superseded_by {target} is not in the directory or database"])
                cur.execute("UPDATE ctr_track_entries SET superseded_by = %s WHERE id = %s",
                            (target_id, inserted_ids[doc["track_key"]]))
        return {"inserted": len(todo), "skipped": skipped, "extra_in_database": extra}

    out = store._run(conn, work)
    out["digest"] = digest
    out["dry_run"] = dry_run
    return out
