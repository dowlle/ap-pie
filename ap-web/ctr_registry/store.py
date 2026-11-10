"""Postgres access for the CTR track registry.

Every mutation is one transaction that takes an advisory lock, so two
reviewers promoting at once cannot get the same block_index. Functions take an
optional `conn` so tests and the CLI can pass their own connection.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Optional

from psycopg2.extras import Json

import db as appdb
from ctr_registry import rules
from ctr_registry.rules import RuleError

_LOCK_ID = 7_306_001  # advisory lock key for registry mutations

ENTRY_COLUMNS = (
    "id, track_key, block_index, state, ap_name, shipped_in, display_title, credits, links, "
    "provenance, saphi_track_id, source, reviewed_at, reviewed_by, superseded_by, "
    "report_count, created_at, updated_at, mint_status, maps_to"
)


def _conn(conn=None):
    return conn if conn is not None else appdb._get_conn()


def _rows(cur) -> list[dict]:
    return appdb._dictrow(cur)


def _lock(cur) -> None:
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_ID,))


def _run(conn, fn):
    """Run fn(cur) in one transaction under the registry lock."""
    try:
        with conn.cursor() as cur:
            _lock(cur)
            result = fn(cur)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise


def record_action(cur, action: str, *, entry_id: Optional[int] = None,
                  submission_id: Optional[int] = None, actor_id: Optional[int] = None,
                  detail: Optional[dict] = None) -> None:
    cur.execute(
        """INSERT INTO ctr_track_review_actions
               (entry_id, submission_id, actor_user_id, action, detail)
           VALUES (%s, %s, %s, %s, %s)""",
        (entry_id, submission_id, actor_id, action, Json(detail or {})),
    )


# ── Reads ────────────────────────────────────────────────────────

def get_entry(entry_id: Optional[int] = None, track_key: Optional[str] = None,
              conn=None, cur=None, for_update: bool = False) -> Optional[dict]:
    sql = f"SELECT {ENTRY_COLUMNS} FROM ctr_track_entries WHERE "
    sql += "id = %s" if entry_id is not None else "track_key = %s"
    if for_update:
        sql += " FOR UPDATE"
    arg = entry_id if entry_id is not None else track_key
    if cur is not None:
        cur.execute(sql, (arg,))
        rows = _rows(cur)
    else:
        with _conn(conn).cursor() as c:
            c.execute(sql, (arg,))
            rows = _rows(c)
    return rows[0] if rows else None


def list_entries(states: Optional[Iterable[str]] = None, conn=None,
                 saphi_only: bool = False) -> list[dict]:
    sql = f"SELECT {ENTRY_COLUMNS} FROM ctr_track_entries"
    where, args = [], []
    if states:
        where.append("state = ANY(%s)")
        args.append(list(states))
    if saphi_only:
        where.append("saphi_track_id IS NOT NULL")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(block_index, 1000000), lower(display_title), id"
    with _conn(conn).cursor() as cur:
        cur.execute(sql, args)
        return _rows(cur)


def revisions_for(entry_ids: list[int], conn=None, cur=None) -> dict[int, list[dict]]:
    if not entry_ids:
        return {}
    sql = ("SELECT * FROM ctr_track_revisions WHERE entry_id = ANY(%s) "
           "ORDER BY entry_id, created_at, id")
    if cur is not None:
        cur.execute(sql, (entry_ids,))
        rows = _rows(cur)
    else:
        with _conn(conn).cursor() as c:
            c.execute(sql, (entry_ids,))
            rows = _rows(c)
    out: dict[int, list[dict]] = {}
    for row in rows:
        out.setdefault(row["entry_id"], []).append(row)
    return out


def record_entries(conn=None) -> list[tuple[dict, list[dict]]]:
    """Everything the registry repository records, in block order then key."""
    entries = list_entries(rules.RECORD_STATES, conn=conn)
    revs = revisions_for([e["id"] for e in entries], conn=conn)
    return [(e, revs.get(e["id"], [])) for e in entries]


def get_submission(sub_id: int, conn=None, cur=None, for_update: bool = False) -> Optional[dict]:
    sql = "SELECT * FROM ctr_track_submissions WHERE id = %s" + (" FOR UPDATE" if for_update else "")
    if cur is not None:
        cur.execute(sql, (sub_id,))
        rows = _rows(cur)
    else:
        with _conn(conn).cursor() as c:
            c.execute(sql, (sub_id,))
            rows = _rows(c)
    return rows[0] if rows else None


def list_submissions(status: Optional[str] = None, user_id: Optional[int] = None,
                     conn=None, limit: int = 200) -> list[dict]:
    sql = ("SELECT s.*, u.discord_username AS submitter_name, "
           "e.track_key AS target_track_key, e.display_title AS target_title "
           "FROM ctr_track_submissions s "
           "LEFT JOIN users u ON u.id = s.submitter_user_id "
           "LEFT JOIN ctr_track_entries e ON e.id = s.target_entry_id")
    where, args = [], []
    if status:
        where.append("s.status = %s")
        args.append(status)
    if user_id is not None:
        where.append("s.submitter_user_id = %s")
        args.append(user_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.created_at DESC, s.id DESC LIMIT %s"
    args.append(limit)
    with _conn(conn).cursor() as cur:
        cur.execute(sql, args)
        return _rows(cur)


def count_pending(user_id: int, conn=None) -> int:
    with _conn(conn).cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM ctr_track_submissions "
            "WHERE submitter_user_id = %s AND status = 'pending'", (user_id,))
        return cur.fetchone()[0]


# ── Submissions ──────────────────────────────────────────────────

def clean_submission_payload(kind: str, body: dict) -> dict:
    """Validate a submission body into the stored payload. Raises RuleError."""
    if kind not in rules.SUBMISSION_KINDS:
        raise RuleError("kind", "kind must be new_track, new_revision or correction")
    payload: dict[str, Any] = {"note": rules.clean_note(body.get("note"))}
    if kind == "new_track":
        payload["title"] = rules.clean_title(body.get("title"))
        payload["credits"] = rules.clean_credits(body.get("credits"))
        payload["links"] = rules.clean_links(body.get("links"))
    if kind in ("new_track", "new_revision"):
        descriptor = body.get("descriptor")
        if descriptor is None and kind == "new_revision":
            raise RuleError("descriptor_required", "A new revision needs a descriptor")
        if descriptor is not None:
            payload["descriptor"] = rules.clean_descriptor(descriptor)
            rules.revision_fields(payload["descriptor"], body.get("revision"))
            if body.get("revision") is not None:
                payload["revision"] = str(body["revision"]).strip()
    if kind == "correction":
        changes = {}
        if body.get("title") is not None:
            changes["display_title"] = rules.clean_title(body["title"])
        if body.get("credits") is not None:
            changes["credits"] = rules.clean_credits(body["credits"])
        if body.get("links") is not None:
            changes["links"] = rules.clean_links(body["links"])
        if not changes:
            raise RuleError("empty_correction", "A correction needs a title, credits or links")
        payload["changes"] = changes
    return payload


def create_submission(user_id: Optional[int], kind: str, payload: dict,
                      target_entry_id: Optional[int] = None, source: str = "user",
                      conn=None) -> dict:
    conn = _conn(conn)

    def work(cur):
        if kind in ("new_revision", "correction"):
            target = get_entry(entry_id=target_entry_id, cur=cur) if target_entry_id else None
            if target is None or target["track_key"] is None:
                raise RuleError("target_not_found", "That track is not in the registry")
            if target["state"] in (rules.WITHDRAWN, rules.CANDIDATE):
                raise RuleError("target_not_open", "That track cannot take submissions right now")
        descriptor = payload.get("descriptor") or {}
        cid = descriptor.get("content_id")
        if cid:
            cur.execute("SELECT 1 FROM ctr_track_revisions WHERE content_id = %s", (cid,))
            if cur.fetchone():
                raise RuleError("content_id_exists", "That exact track version is already in the registry")
        cur.execute(
            """INSERT INTO ctr_track_submissions
                   (kind, source, submitter_user_id, target_entry_id, payload)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (kind, source, user_id, target_entry_id, Json(payload)),
        )
        row = _rows(cur)[0]
        record_action(cur, "submitted", entry_id=target_entry_id, submission_id=row["id"],
                      actor_id=user_id, detail={"kind": kind, "source": source})
        return row

    return _run(conn, work)


# ── Entry and revision writes (shared by approve and merge) ──────

def _insert_revision(cur, entry_id: int, payload: dict) -> dict:
    descriptor = payload.get("descriptor")
    label = None
    if descriptor is not None:
        fields = rules.revision_fields(descriptor, payload.get("revision"))
        label = fields["revision"]
        if fields["content_id"]:
            cur.execute("SELECT 1 FROM ctr_track_revisions WHERE content_id = %s", (fields["content_id"],))
            if cur.fetchone():
                raise RuleError("content_id_exists", "That exact track version is already in the registry")
    elif payload.get("saphi") is not None:
        saphi = payload["saphi"]
        label = str(payload.get("revision") or saphi.get("version") or saphi.get("download_id"))[: rules.REVISION_MAX_CHARS]
    if label is not None:
        cur.execute("SELECT 1 FROM ctr_track_revisions WHERE entry_id = %s AND revision = %s", (entry_id, label))
        if cur.fetchone():
            raise RuleError("revision_exists", f"This track already has a revision {label}")
    if descriptor is not None:
        cur.execute(
            """INSERT INTO ctr_track_revisions
                   (entry_id, revision, content_id, files, descriptor_schema, descriptor,
                    hash_state, provenance)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (entry_id, fields["revision"], fields["content_id"], Json(fields["files"]),
             fields["descriptor_schema"], Json(descriptor), fields["hash_state"],
             Json(payload.get("provenance") or {})),
        )
    elif payload.get("saphi") is not None:
        saphi = payload["saphi"]
        label = str(payload.get("revision") or saphi.get("version") or saphi.get("download_id"))
        cur.execute(
            """INSERT INTO ctr_track_revisions (entry_id, revision, hash_state, provenance)
               VALUES (%s, %s, 'pending', %s) RETURNING *""",
            (entry_id, label[: rules.REVISION_MAX_CHARS], Json({"saphi_downloads": saphi.get("downloads", [saphi])})),
        )
    else:
        raise RuleError("descriptor_required", "A revision needs a descriptor")
    return _rows(cur)[0]


def _assign_key(cur, title: str) -> str:
    cur.execute("SELECT track_key FROM ctr_track_entries WHERE track_key IS NOT NULL")
    return rules.slugify_key(title, {r[0] for r in cur.fetchall()})


def _apply_overrides(base: dict, overrides: Optional[dict]) -> dict:
    out = dict(base)
    for field, cleaner in (("display_title", rules.clean_title),
                           ("credits", rules.clean_credits),
                           ("links", rules.clean_links)):
        if overrides and overrides.get(field) is not None:
            out[field] = cleaner(overrides[field])
    return out


def _approve_entry_row(cur, entry: dict, actor_id: Optional[int], overrides: Optional[dict]) -> dict:
    if not rules.can_transition(entry["state"], rules.APPROVED) and entry["state"] != rules.APPROVED:
        raise RuleError("bad_state", f"A {entry['state']} entry cannot be approved")
    merged = _apply_overrides(entry, overrides)
    key = entry["track_key"] or _assign_key(cur, merged["display_title"])
    cur.execute(
        """UPDATE ctr_track_entries
              SET state = 'approved', track_key = %s, display_title = %s, credits = %s,
                  links = %s, reviewed_at = NOW(), reviewed_by = %s, updated_at = NOW()
            WHERE id = %s RETURNING *""",
        (key, merged["display_title"], Json(merged["credits"]), Json(merged["links"]),
         actor_id, entry["id"]),
    )
    return _rows(cur)[0]


# ── Review actions ───────────────────────────────────────────────

def approve_submission(sub_id: int, actor_id: int, overrides: Optional[dict] = None, conn=None) -> dict:
    conn = _conn(conn)

    def work(cur):
        sub = get_submission(sub_id, cur=cur, for_update=True)
        if sub is None:
            raise RuleError("not_found", "Submission not found")
        if sub["status"] != "pending":
            raise RuleError("already_decided", "That submission was already decided")
        payload = sub["payload"]
        kind = sub["kind"]
        if kind == "new_track":
            cur.execute(
                """INSERT INTO ctr_track_entries
                       (state, display_title, credits, links, source, provenance)
                   VALUES ('candidate', %s, %s, %s, 'submission', %s) RETURNING *""",
                (payload["title"], Json(payload.get("credits", [])), Json(payload.get("links", {})),
                 Json({"submission_id": sub_id})),
            )
            entry = _approve_entry_row(cur, _rows(cur)[0], actor_id, overrides)
            if payload.get("descriptor") is not None:
                _insert_revision(cur, entry["id"], payload)
        elif kind == "new_revision":
            entry = get_entry(entry_id=sub["target_entry_id"], cur=cur, for_update=True)
            if entry is None or entry["state"] in (rules.WITHDRAWN, rules.CANDIDATE):
                raise RuleError("target_not_open", "That track cannot take revisions right now")
            _insert_revision(cur, entry["id"], payload)
        else:  # correction
            entry = get_entry(entry_id=sub["target_entry_id"], cur=cur, for_update=True)
            if entry is None:
                raise RuleError("target_not_found", "That track is not in the registry")
            entry = _update_presentation_row(cur, entry, {**payload["changes"], **(overrides or {})}, actor_id)
        cur.execute(
            """UPDATE ctr_track_submissions
                  SET status = 'approved', result_entry_id = %s, decided_by = %s, decided_at = NOW()
                WHERE id = %s RETURNING *""",
            (entry["id"], actor_id, sub_id),
        )
        row = _rows(cur)[0]
        record_action(cur, "approve_submission", entry_id=entry["id"], submission_id=sub_id,
                      actor_id=actor_id, detail={"kind": kind})
        return row

    return _run(conn, work)


def reject_submission(sub_id: int, actor_id: int, reason: str, conn=None) -> dict:
    reason = (reason or "").strip()
    if len(reason) > 300:
        raise RuleError("reason_too_long", "Reasons are at most 300 characters")
    conn = _conn(conn)

    def work(cur):
        sub = get_submission(sub_id, cur=cur, for_update=True)
        if sub is None:
            raise RuleError("not_found", "Submission not found")
        if sub["status"] != "pending":
            raise RuleError("already_decided", "That submission was already decided")
        cur.execute(
            """UPDATE ctr_track_submissions
                  SET status = 'rejected', reject_reason = %s, decided_by = %s, decided_at = NOW()
                WHERE id = %s RETURNING *""",
            (reason, actor_id, sub_id),
        )
        row = _rows(cur)[0]
        record_action(cur, "reject_submission", entry_id=sub["target_entry_id"],
                      submission_id=sub_id, actor_id=actor_id, detail={"reason": reason})
        return row

    return _run(conn, work)


def merge_submission(sub_id: int, entry_id: int, actor_id: int, conn=None) -> dict:
    """Merge a submission into an existing entry. A new_track becomes a new
    revision of that entry (or just a note when it carries no descriptor); a
    correction applies to it."""
    conn = _conn(conn)

    def work(cur):
        sub = get_submission(sub_id, cur=cur, for_update=True)
        if sub is None:
            raise RuleError("not_found", "Submission not found")
        if sub["status"] != "pending":
            raise RuleError("already_decided", "That submission was already decided")
        entry = get_entry(entry_id=entry_id, cur=cur, for_update=True)
        if entry is None or entry["track_key"] is None or entry["state"] == rules.WITHDRAWN:
            raise RuleError("target_not_open", "That track cannot take a merge right now")
        payload = sub["payload"]
        if sub["kind"] == "correction":
            _update_presentation_row(cur, entry, payload["changes"], actor_id)
        elif payload.get("descriptor") is not None or payload.get("saphi") is not None:
            _insert_revision(cur, entry["id"], payload)
        cur.execute(
            """UPDATE ctr_track_submissions
                  SET status = 'merged', result_entry_id = %s, decided_by = %s, decided_at = NOW()
                WHERE id = %s RETURNING *""",
            (entry_id, actor_id, sub_id),
        )
        row = _rows(cur)[0]
        record_action(cur, "merge_submission", entry_id=entry_id, submission_id=sub_id,
                      actor_id=actor_id, detail={"kind": sub["kind"]})
        return row

    return _run(conn, work)


def approve_entry(entry_id: int, actor_id: int, overrides: Optional[dict] = None, conn=None) -> dict:
    """Approve a candidate entry directly (the Saphi batch path)."""
    conn = _conn(conn)

    def work(cur):
        entry = get_entry(entry_id=entry_id, cur=cur, for_update=True)
        if entry is None:
            raise RuleError("not_found", "Track not found")
        if entry["state"] != rules.CANDIDATE:
            raise RuleError("bad_state", f"Only candidates can be approved; this one is {entry['state']}")
        row = _approve_entry_row(cur, entry, actor_id, overrides)
        record_action(cur, "approve_entry", entry_id=entry_id, actor_id=actor_id,
                      detail={"track_key": row["track_key"]})
        return row

    return _run(conn, work)


def _update_presentation_row(cur, entry: dict, fields: dict, actor_id: Optional[int]) -> dict:
    allowed = {k: v for k, v in fields.items() if k in ("display_title", "credits", "links")}
    merged = _apply_overrides(entry, allowed)
    cur.execute(
        """UPDATE ctr_track_entries
              SET display_title = %s, credits = %s, links = %s, updated_at = NOW()
            WHERE id = %s RETURNING *""",
        (merged["display_title"], Json(merged["credits"]), Json(merged["links"]), entry["id"]),
    )
    row = _rows(cur)[0]
    record_action(cur, "edit_presentation", entry_id=entry["id"], actor_id=actor_id,
                  detail={"fields": sorted(allowed)})
    return row


def update_presentation(entry_id: int, actor_id: int, fields: dict, conn=None) -> dict:
    """Edit title, credits or links. Allowed in every state, shipped or not:
    presentation is never frozen. The shipped ap_name does not follow."""
    conn = _conn(conn)

    def work(cur):
        entry = get_entry(entry_id=entry_id, cur=cur, for_update=True)
        if entry is None:
            raise RuleError("not_found", "Track not found")
        return _update_presentation_row(cur, entry, fields, actor_id)

    return _run(conn, work)


def promote_entry(entry_id: int, actor_id: int, ap_name: Optional[str] = None, conn=None) -> dict:
    """Approved -> named. Assigns the next block_index and fixes ap_name.

    A given ap_name is only a reviewer's correction before the first release
    that ships the block; it still goes through the clash suffix rules."""
    conn = _conn(conn)

    def work(cur):
        entry = get_entry(entry_id=entry_id, cur=cur, for_update=True)
        if entry is None:
            raise RuleError("not_found", "Track not found")
        if entry["state"] == rules.NAMED:
            raise RuleError("already_named", "That track already has a named block")
        if entry["state"] != rules.APPROVED and not (
                entry["state"] in (rules.WITHDRAWN, rules.SOURCE_UNAVAILABLE)
                and entry["block_index"] is not None):
            raise RuleError("bad_state", "Only approved tracks can be promoted")
        cur.execute("SELECT block_index, ap_name FROM ctr_track_entries "
                    "WHERE block_index IS NOT NULL AND id <> %s", (entry_id,))
        others = cur.fetchall()
        index = entry["block_index"]
        if index is None:
            index = rules.next_block_index(r[0] for r in others)
        name = entry["ap_name"]
        if name is None or ap_name is not None:
            if entry["shipped_in"] is not None:
                raise RuleError("name_frozen", "A shipped name changes only through the unfreeze register")
            author = next((c["name"] for c in entry["credits"] if c.get("role") == "track"), None) \
                or next((c["name"] for c in entry["credits"]), None)
            name = rules.ap_name_for(ap_name or entry["display_title"], author,
                                     taken=(r[1] for r in others if r[1]))
        cur.execute(
            """UPDATE ctr_track_entries
                  SET state = 'named', block_index = %s, ap_name = %s, reviewed_at = NOW(),
                      reviewed_by = %s, updated_at = NOW()
                WHERE id = %s RETURNING *""",
            (index, name, actor_id, entry_id),
        )
        row = _rows(cur)[0]
        record_action(cur, "promote", entry_id=entry_id, actor_id=actor_id,
                      detail={"block_index": index, "ap_name": name})
        return row

    return _run(conn, work)


def set_state(entry_id: int, actor_id: Optional[int], action: str, conn=None) -> dict:
    """withdraw, restore or source_unavailable."""
    conn = _conn(conn)

    def work(cur):
        entry = get_entry(entry_id=entry_id, cur=cur, for_update=True)
        if entry is None:
            raise RuleError("not_found", "Track not found")
        if action == "withdraw":
            target = rules.WITHDRAWN
        elif action == "source_unavailable":
            target = rules.SOURCE_UNAVAILABLE
        elif action == "restore":
            target = rules.restored_state(entry)
        else:
            raise RuleError("action", "Unknown action")
        if entry["state"] == target:
            return entry
        if not rules.can_transition(entry["state"], target):
            raise RuleError("bad_state", f"A {entry['state']} entry cannot become {target}")
        cur.execute("UPDATE ctr_track_entries SET state = %s, updated_at = NOW() WHERE id = %s RETURNING *",
                    (target, entry_id))
        row = _rows(cur)[0]
        record_action(cur, action, entry_id=entry_id, actor_id=actor_id,
                      detail={"from": entry["state"], "to": target})
        return row

    return _run(conn, work)


def set_minting(entry_id: int, actor_id: Optional[int], status: str,
                maps_to: Optional[str] = None, conn=None) -> dict:
    """Set what the apworld build does with this entry's block.

    `reserved`: keep the block_index, mint nothing until set back to `mint`.
    `builtin`: the entry is an existing in-game named block (`maps_to` names it);
    permanent. The block_index stays assigned and is never reused."""
    if status not in rules.MINT_STATUSES:
        raise RuleError("mint_status", "mint_status must be mint, reserved or builtin")
    maps_to = (maps_to or "").strip() or None
    if status == "builtin" and not maps_to:
        raise RuleError("maps_to", "A builtin entry needs maps_to, the existing named block")
    if status == "mint":
        maps_to = None
    conn = _conn(conn)

    def work(cur):
        entry = get_entry(entry_id=entry_id, cur=cur, for_update=True)
        if entry is None:
            raise RuleError("not_found", "Track not found")
        if entry["block_index"] is None:
            raise RuleError("not_named", "Only a track with a block_index has a minting status")
        bad = rules.freeze_violations(entry, {**entry, "mint_status": status, "maps_to": maps_to})
        if bad:
            raise RuleError("frozen", "Frozen fields: " + ", ".join(bad))
        cur.execute("UPDATE ctr_track_entries SET mint_status = %s, maps_to = %s, updated_at = NOW() "
                    "WHERE id = %s RETURNING *", (status, maps_to, entry_id))
        row = _rows(cur)[0]
        record_action(cur, "set_minting", entry_id=entry_id, actor_id=actor_id,
                      detail={"from": entry["mint_status"], "to": status, "maps_to": maps_to})
        return row

    return _run(conn, work)


def mark_shipped(version: str, track_keys: list[str], actor_id: Optional[int], conn=None) -> list[dict]:
    """Record the first apworld release that minted these blocks. From then on
    their ap_name is frozen (database trigger and rules.freeze_violations)."""
    if rules.parse_version(version) is None:
        raise RuleError("version", "Give the apworld version, such as 0.3.0")
    conn = _conn(conn)

    def work(cur):
        out = []
        for key in track_keys:
            entry = get_entry(track_key=key, cur=cur, for_update=True)
            if entry is None or entry["block_index"] is None:
                raise RuleError("not_named", f"{key} has no named block")
            if entry["shipped_in"] is not None:
                continue
            if entry["mint_status"] != "mint":
                raise RuleError("not_minted", f"{key} is {entry['mint_status']} and was not minted")
            cur.execute("UPDATE ctr_track_entries SET shipped_in = %s, updated_at = NOW() "
                        "WHERE id = %s RETURNING *", (version, entry["id"]))
            row = _rows(cur)[0]
            record_action(cur, "mark_shipped", entry_id=entry["id"], actor_id=actor_id,
                          detail={"version": version})
            out.append(row)
        return out

    return _run(conn, work)


def add_report(entry_id: int, user_id: int, reason: str, conn=None) -> bool:
    """True when this was a new report from this user."""
    reason = (reason or "").strip()
    if len(reason) > rules.REPORT_REASON_MAX:
        raise RuleError("reason_too_long", f"Reasons are at most {rules.REPORT_REASON_MAX} characters")
    conn = _conn(conn)

    def work(cur):
        cur.execute(
            """INSERT INTO ctr_track_reports (entry_id, user_id, reason) VALUES (%s, %s, %s)
               ON CONFLICT DO NOTHING""", (entry_id, user_id, reason))
        if cur.rowcount == 0:
            return False
        cur.execute("UPDATE ctr_track_entries SET report_count = report_count + 1 WHERE id = %s", (entry_id,))
        record_action(cur, "report", entry_id=entry_id, actor_id=user_id, detail={"reason": reason})
        return True

    return _run(conn, work)


# ── Hashing hook (the later Atlas verifier step) ─────────────────

def attach_evidence(revision_id: int, *, content_id: str, files: dict, evidence: dict,
                    modes: list, apworld_min: Optional[str] = None,
                    apworld_max: Optional[str] = None, conn=None) -> dict:
    """Store verifier output on a revision and mark it verified.

    Called by hashing.attach_from_file(), never from a web route. Refuses to
    change hashes that are already verified."""
    if not (isinstance(content_id, str) and len(content_id) == 64
            and all(c in "0123456789abcdef" for c in content_id)):
        raise RuleError("content_id", "content_id must be 64 lowercase hex characters")
    conn = _conn(conn)

    def work(cur):
        cur.execute("SELECT * FROM ctr_track_revisions WHERE id = %s FOR UPDATE", (revision_id,))
        rows = _rows(cur)
        if not rows:
            raise RuleError("not_found", "Revision not found")
        old = rows[0]
        new = {**old, "content_id": content_id, "files": files, "hash_state": "verified"}
        bad = rules.revision_violations(old, new)
        if bad:
            raise RuleError("frozen", "Frozen revision fields: " + ", ".join(bad))
        cur.execute(
            """UPDATE ctr_track_revisions
                  SET content_id = %s, files = %s, evidence = %s, modes = %s,
                      apworld_min = %s, apworld_max = %s, hash_state = 'verified'
                WHERE id = %s RETURNING *""",
            (content_id, Json(files), Json(evidence), Json(modes), apworld_min, apworld_max, revision_id),
        )
        row = _rows(cur)[0]
        record_action(cur, "attach_evidence", entry_id=old["entry_id"], actor_id=None,
                      detail={"revision": old["revision"], "content_id": content_id})
        return row

    return _run(conn, work)


def pending_hash_revisions(conn=None) -> list[dict]:
    """Revisions still waiting for the verifier, with their Saphi locators."""
    with _conn(conn).cursor() as cur:
        cur.execute(
            """SELECT r.id, r.entry_id, r.revision, r.hash_state, r.provenance, e.track_key,
                      e.saphi_track_id
                 FROM ctr_track_revisions r JOIN ctr_track_entries e ON e.id = r.entry_id
                WHERE r.hash_state <> 'verified' AND e.state IN ('approved','named')
                ORDER BY r.id""")
        return _rows(cur)


def json_safe(value: Any) -> Any:
    """Round-trip through JSON so datetimes become strings for API output."""
    return json.loads(json.dumps(value, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o)))


def set_superseded(entry_id: int, superseded_by_id: Optional[int], actor_id: int, conn=None) -> dict:
    """Link an entry to the entry that replaces it (or clear the link)."""
    if superseded_by_id == entry_id:
        raise RuleError("self_supersede", "A track cannot supersede itself")
    conn = _conn(conn)

    def work(cur):
        entry = get_entry(entry_id=entry_id, cur=cur, for_update=True)
        if entry is None:
            raise RuleError("not_found", "Track not found")
        if superseded_by_id is not None and get_entry(entry_id=superseded_by_id, cur=cur) is None:
            raise RuleError("not_found", "Replacement track not found")
        cur.execute("UPDATE ctr_track_entries SET superseded_by = %s, updated_at = NOW() "
                    "WHERE id = %s RETURNING *", (superseded_by_id, entry_id))
        row = _rows(cur)[0]
        record_action(cur, "supersede", entry_id=entry_id, actor_id=actor_id,
                      detail={"superseded_by": superseded_by_id})
        return row

    return _run(conn, work)
