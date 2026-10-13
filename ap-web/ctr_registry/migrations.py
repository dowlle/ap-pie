"""Postgres schema for the CTR track registry.

UP is append-only and idempotent: it runs on every boot from db.init_db(), the
same as every other migration in this app, so a shipped statement is never
edited, only followed by a new one. DOWN removes everything UP created and is
run by hand (`python -m ctr_registry.cli migrate-down --yes`); it drops the
five registry tables and so loses their rows. Nothing else in the database
references them.

Identity is guarded twice: rules.freeze_violations() in Python and the
triggers below in the database, so a stray UPDATE cannot move a shipped name.
"""

UP = [
    # Entries: one per logical track. track_key is NULL until first approval.
    """
    CREATE TABLE IF NOT EXISTS ctr_track_entries (
        id             SERIAL PRIMARY KEY,
        track_key      TEXT UNIQUE,
        block_index    INTEGER UNIQUE,
        state          TEXT NOT NULL DEFAULT 'candidate'
                       CHECK (state IN ('candidate','approved','named','withdrawn','source-unavailable')),
        ap_name        TEXT,
        shipped_in     TEXT,
        display_title  TEXT NOT NULL,
        credits        JSONB NOT NULL DEFAULT '[]'::jsonb,
        links          JSONB NOT NULL DEFAULT '{}'::jsonb,
        provenance     JSONB NOT NULL DEFAULT '{}'::jsonb,
        saphi_track_id INTEGER UNIQUE,
        source         TEXT NOT NULL DEFAULT 'submission'
                       CHECK (source IN ('submission','saphi_import','admin')),
        reviewed_at    TIMESTAMPTZ,
        reviewed_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
        superseded_by  INTEGER REFERENCES ctr_track_entries(id) ON DELETE SET NULL,
        report_count   INTEGER NOT NULL DEFAULT 0,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT ctr_entry_block_range CHECK (block_index IS NULL OR (block_index >= 0 AND block_index < 10000)),
        CONSTRAINT ctr_entry_named_needs_block CHECK (
            state <> 'named' OR (block_index IS NOT NULL AND ap_name IS NOT NULL AND track_key IS NOT NULL)),
        CONSTRAINT ctr_entry_shipped_needs_name CHECK (shipped_in IS NULL OR ap_name IS NOT NULL),
        CONSTRAINT ctr_entry_title_length CHECK (length(display_title) <= 80),
        CONSTRAINT ctr_entry_key_shape CHECK (track_key IS NULL OR track_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$')
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ctr_entries_state ON ctr_track_entries(state)",
    # Revisions: one per file version. content_id is NULL until hashed.
    """
    CREATE TABLE IF NOT EXISTS ctr_track_revisions (
        id                SERIAL PRIMARY KEY,
        entry_id          INTEGER NOT NULL REFERENCES ctr_track_entries(id) ON DELETE RESTRICT,
        revision          TEXT NOT NULL,
        content_id        TEXT UNIQUE,
        files             JSONB NOT NULL DEFAULT '{}'::jsonb,
        descriptor_schema INTEGER,
        descriptor        JSONB,
        evidence          JSONB NOT NULL DEFAULT '{}'::jsonb,
        modes             JSONB NOT NULL DEFAULT '[]'::jsonb,
        apworld_min       TEXT,
        apworld_max       TEXT,
        hash_state        TEXT NOT NULL DEFAULT 'pending'
                          CHECK (hash_state IN ('pending','claimed','verified')),
        provenance        JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT ctr_revision_unique UNIQUE (entry_id, revision),
        CONSTRAINT ctr_revision_label CHECK (length(revision) <= 32),
        CONSTRAINT ctr_revision_content_id CHECK (content_id IS NULL OR content_id ~ '^[0-9a-f]{64}$')
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ctr_revisions_entry ON ctr_track_revisions(entry_id)",
    # Submissions: the intake queue.
    """
    CREATE TABLE IF NOT EXISTS ctr_track_submissions (
        id                SERIAL PRIMARY KEY,
        kind              TEXT NOT NULL CHECK (kind IN ('new_track','new_revision','correction')),
        source            TEXT NOT NULL DEFAULT 'user' CHECK (source IN ('user','saphi_import')),
        submitter_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        target_entry_id   INTEGER REFERENCES ctr_track_entries(id) ON DELETE RESTRICT,
        payload           JSONB NOT NULL,
        status            TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','approved','rejected','merged')),
        result_entry_id   INTEGER REFERENCES ctr_track_entries(id) ON DELETE RESTRICT,
        reject_reason     TEXT,
        decided_by        INTEGER REFERENCES users(id) ON DELETE SET NULL,
        decided_at        TIMESTAMPTZ,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT ctr_submission_payload_bytes CHECK (octet_length(payload::text) <= 32768)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ctr_submissions_status ON ctr_track_submissions(status, created_at)",
    """CREATE INDEX IF NOT EXISTS idx_ctr_submissions_user ON ctr_track_submissions(submitter_user_id, created_at DESC)
       WHERE submitter_user_id IS NOT NULL""",
    # Review actions: the audit trail of every decision.
    """
    CREATE TABLE IF NOT EXISTS ctr_track_review_actions (
        id            SERIAL PRIMARY KEY,
        entry_id      INTEGER REFERENCES ctr_track_entries(id) ON DELETE RESTRICT,
        submission_id INTEGER REFERENCES ctr_track_submissions(id) ON DELETE RESTRICT,
        actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        action        TEXT NOT NULL,
        detail        JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ctr_actions_entry ON ctr_track_review_actions(entry_id, created_at)",
    # Reports: one per signed-in user and entry.
    """
    CREATE TABLE IF NOT EXISTS ctr_track_reports (
        entry_id   INTEGER NOT NULL REFERENCES ctr_track_entries(id) ON DELETE CASCADE,
        user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        reason     TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (entry_id, user_id),
        CONSTRAINT ctr_report_reason_length CHECK (length(reason) <= 200)
    )
    """,
    # Freeze triggers. Identity cannot move once set; a shipped name is final.
    """
    CREATE OR REPLACE FUNCTION ctr_track_entries_freeze() RETURNS trigger AS $$
    BEGIN
        IF OLD.track_key IS NOT NULL AND NEW.track_key IS DISTINCT FROM OLD.track_key THEN
            RAISE EXCEPTION 'ctr registry: track_key is frozen' USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.block_index IS NOT NULL AND NEW.block_index IS DISTINCT FROM OLD.block_index THEN
            RAISE EXCEPTION 'ctr registry: block_index is frozen' USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.shipped_in IS NOT NULL AND (NEW.shipped_in IS DISTINCT FROM OLD.shipped_in
                                           OR NEW.ap_name IS DISTINCT FROM OLD.ap_name) THEN
            RAISE EXCEPTION 'ctr registry: a shipped ap_name is frozen' USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS ctr_track_entries_freeze ON ctr_track_entries",
    """CREATE TRIGGER ctr_track_entries_freeze BEFORE UPDATE ON ctr_track_entries
       FOR EACH ROW EXECUTE FUNCTION ctr_track_entries_freeze()""",
    """
    CREATE OR REPLACE FUNCTION ctr_track_revisions_freeze() RETURNS trigger AS $$
    BEGIN
        IF OLD.content_id IS NOT NULL AND NEW.content_id IS DISTINCT FROM OLD.content_id THEN
            RAISE EXCEPTION 'ctr registry: content_id is frozen' USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.hash_state = 'verified' AND (NEW.files IS DISTINCT FROM OLD.files
                                            OR NEW.hash_state <> 'verified') THEN
            RAISE EXCEPTION 'ctr registry: verified hashes are frozen' USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS ctr_track_revisions_freeze ON ctr_track_revisions",
    """CREATE TRIGGER ctr_track_revisions_freeze BEFORE UPDATE ON ctr_track_revisions
       FOR EACH ROW EXECUTE FUNCTION ctr_track_revisions_freeze()""",
]

# Reverse order of dependency. Triggers go with their tables; the functions
# are dropped explicitly.
DOWN = [
    "DROP TABLE IF EXISTS ctr_track_reports",
    "DROP TABLE IF EXISTS ctr_track_review_actions",
    "DROP TABLE IF EXISTS ctr_track_submissions",
    "DROP TABLE IF EXISTS ctr_track_revisions",
    "DROP TABLE IF EXISTS ctr_track_entries",
    "DROP FUNCTION IF EXISTS ctr_track_revisions_freeze()",
    "DROP FUNCTION IF EXISTS ctr_track_entries_freeze()",
]

TABLES = (
    "ctr_track_entries", "ctr_track_revisions", "ctr_track_submissions",
    "ctr_track_review_actions", "ctr_track_reports",
)


def apply_up(cur) -> None:
    for statement in UP:
        cur.execute(statement)


def apply_down(cur) -> None:
    for statement in DOWN:
        cur.execute(statement)
