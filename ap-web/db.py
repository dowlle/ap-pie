"""PostgreSQL database for persistent features (market, rooms, future: claims, users)."""

from __future__ import annotations

import os
import re
import secrets
import threading

import psycopg2
import psycopg2.extras


# SEC-22: scrub the password out of any string that may contain a Postgres
# connection URL before it gets logged. psycopg2's OperationalError text
# routinely echoes the DSN in the form "postgresql://user:password@host/db",
# and Caddy/gunicorn access logs may pick it up on healthcheck failures.
# Defensive against both URL forms ("postgres://" and "postgresql://") and
# tolerant of empty / non-string input.
_DB_URL_PASSWORD_RE = re.compile(r"(postgres(?:ql)?://[^:/\s@]+:)[^@/\s]+(@)")


def scrub_db_url(text: object) -> str:
    """Return `text` with any embedded Postgres-URL passwords replaced by ***.

    Use anywhere an exception with a possible DSN gets logged. Idempotent
    on already-scrubbed text. Stringifies non-str input so callers don't
    need to wrap exceptions themselves.
    """
    return _DB_URL_PASSWORD_RE.sub(r"\1***\2", str(text))

_db_url: str | None = None
_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    discord_id TEXT UNIQUE NOT NULL,
    discord_username TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    is_approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trackers (
    id TEXT PRIMARY KEY,
    tracker_url TEXT NOT NULL UNIQUE,
    display_name TEXT,
    host TEXT,
    port INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_synced TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS listings (
    id SERIAL PRIMARY KEY,
    seed TEXT,
    tracker_id TEXT REFERENCES trackers(id) ON DELETE CASCADE,
    slot INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    item_name TEXT NOT NULL,
    listing_type TEXT NOT NULL CHECK(listing_type IN ('offer', 'request')),
    quantity INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'fulfilled', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_listings_seed ON listings(seed);
CREATE INDEX IF NOT EXISTS idx_listings_active ON listings(seed, status, listing_type);
CREATE INDEX IF NOT EXISTS idx_listings_tracker ON listings(tracker_id);
CREATE INDEX IF NOT EXISTS idx_listings_tracker_active ON listings(tracker_id, status, listing_type);

CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    host_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    seed TEXT,
    generation_log TEXT,
    spoiler_level INTEGER DEFAULT 3,
    race_mode BOOLEAN DEFAULT FALSE,
    max_players INTEGER DEFAULT 0,
    max_yamls_per_user INTEGER DEFAULT 0,
    external_host TEXT,
    external_port INTEGER,
    tracker_url TEXT,
    submit_deadline TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rooms_seed ON rooms(seed);

CREATE TABLE IF NOT EXISTS room_yamls (
    id SERIAL PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    player_name TEXT NOT NULL,
    game TEXT NOT NULL,
    yaml_content TEXT NOT NULL,
    filename TEXT NOT NULL,
    validation_status TEXT DEFAULT 'unknown'
        CHECK(validation_status IN ('validated', 'manually_validated', 'unsupported', 'failed', 'unknown')),
    validation_error TEXT,
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_room_yamls_room ON room_yamls(room_id);

-- FEAT-30 Phase 0a: structured request flow for proposing new APWorld
-- versions to dowlle/Archipelago-index. Two entry points (room hosts +
-- linked maintainers) funnel into a single queue that Stef triages.
-- The Eijebong fuzzer + Claude security audit gates are tracked as
-- separate status fields so each can be ticked off independently.
CREATE TABLE IF NOT EXISTS apworld_maintainers (
    apworld_name    TEXT NOT NULL,
    discord_user_id TEXT NOT NULL,
    granted_by      INTEGER NOT NULL REFERENCES users(id),
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes           TEXT,
    PRIMARY KEY (apworld_name, discord_user_id)
);

CREATE TABLE IF NOT EXISTS apworld_index_requests (
    id                SERIAL PRIMARY KEY,
    apworld_name      TEXT NOT NULL,
    display_name      TEXT NOT NULL,
    requested_version TEXT NOT NULL,
    source_url        TEXT NOT NULL,
    notes             TEXT,
    requester_user_id INTEGER NOT NULL REFERENCES users(id),
    requester_role    TEXT NOT NULL CHECK (requester_role IN ('room_host', 'maintainer')),
    source_room_id    TEXT REFERENCES rooms(id) ON DELETE SET NULL,
    status            TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'audited', 'approved', 'pr_opened', 'merged', 'rejected', 'failed')),
    fuzzer_status     TEXT CHECK (fuzzer_status IN ('pass', 'fail') OR fuzzer_status IS NULL),
    fuzzer_url        TEXT,
    audit_status      TEXT CHECK (audit_status IN ('pass', 'needs_review', 'fail') OR audit_status IS NULL),
    audit_url         TEXT,
    pr_url            TEXT,
    reject_reason     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at       TIMESTAMPTZ,
    -- SEC-21-style length caps so a hostile submitter can't bloat the queue.
    CONSTRAINT apworld_request_url_length CHECK (length(source_url) <= 1024),
    CONSTRAINT apworld_request_version_length CHECK (length(requested_version) <= 64),
    CONSTRAINT apworld_request_notes_length CHECK (length(COALESCE(notes, '')) <= 2000),
    CONSTRAINT apworld_request_apworld_length CHECK (length(apworld_name) <= 128)
);

CREATE INDEX IF NOT EXISTS idx_apworld_requests_status ON apworld_index_requests(status);
CREATE INDEX IF NOT EXISTS idx_apworld_requests_requester ON apworld_index_requests(requester_user_id);
CREATE INDEX IF NOT EXISTS idx_apworld_maintainers_user ON apworld_maintainers(discord_user_id);

CREATE TABLE IF NOT EXISTS room_activity (
    id SERIAL PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_room_activity_room ON room_activity(room_id);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id SERIAL PRIMARY KEY,
    room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK(status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    seed TEXT,
    log TEXT DEFAULT '',
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_generation_jobs_room ON generation_jobs(room_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_generation_jobs_status ON generation_jobs(status, created_at) WHERE status = 'queued';
"""


def init_db(db_url: str) -> None:
    global _db_url
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
        # Migration: add is_approved column if missing
        cur.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS is_approved BOOLEAN DEFAULT FALSE
        """)
        # Migration: external server pointer for rooms that run on the host's own machine
        cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS external_host TEXT")
        cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS external_port INTEGER")
        # Migration: 5-state validation enum (was 'valid'/'invalid'/'pending').
        # Drop the old CHECK constraint if it exists, rename values, re-add the
        # new constraint. UPDATE statements are no-ops if the table is already
        # on the new vocabulary, so this is safe to run repeatedly.
        cur.execute("UPDATE room_yamls SET validation_status = 'validated' WHERE validation_status = 'valid'")
        cur.execute("UPDATE room_yamls SET validation_status = 'failed' WHERE validation_status = 'invalid'")
        cur.execute("UPDATE room_yamls SET validation_status = 'unknown' WHERE validation_status = 'pending'")
        # The column default on tables created before this migration is still
        # 'pending', which now violates the new CHECK. Update the default so
        # INSERTs that omit validation_status get the new vocabulary.
        cur.execute("ALTER TABLE room_yamls ALTER COLUMN validation_status SET DEFAULT 'unknown'")
        cur.execute("ALTER TABLE room_yamls DROP CONSTRAINT IF EXISTS room_yamls_validation_status_check")
        cur.execute(
            "ALTER TABLE room_yamls ADD CONSTRAINT room_yamls_validation_status_check "
            "CHECK(validation_status IN ('validated', 'manually_validated', 'unsupported', 'failed', 'unknown'))"
        )
        # Migration: optional Discord-login gating per room.
        cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS require_discord_login BOOLEAN DEFAULT FALSE")
        # Migration: capture submitter Discord identity on each YAML row when the
        # uploader is logged in. Nullable so legacy rows + anonymous public submits
        # still work; ON DELETE SET NULL so deleting a user doesn't cascade-delete
        # the YAML.
        cur.execute(
            "ALTER TABLE room_yamls ADD COLUMN IF NOT EXISTS "
            "submitter_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
        )
        # Migration: room ownership FK so /rooms can filter to the current user.
        # Nullable so legacy rows are visible to admins; the route layer treats
        # null-owner rooms as admin-only. Backfill matches host_name → discord_username
        # for any room whose host name equals exactly one user's display name.
        cur.execute(
            "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS "
            "host_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
        )
        cur.execute("""
            UPDATE rooms r SET host_user_id = u.id
            FROM users u
            WHERE r.host_user_id IS NULL
              AND u.discord_username = r.host_name
              AND (SELECT COUNT(*) FROM users WHERE discord_username = r.host_name) = 1
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rooms_host_user ON rooms(host_user_id)")
        # Migration: optional auto-close deadline. NULL = no scheduled close,
        # manual "Close Room" still works regardless. The sweeper closes any
        # open room whose deadline has passed; writes to open rooms also do
        # a lazy check so a request right after the deadline gets the right
        # behaviour without waiting for the next sweep tick.
        cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS submit_deadline TIMESTAMPTZ")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_rooms_deadline_open "
            "ON rooms(submit_deadline) WHERE status = 'open' AND submit_deadline IS NOT NULL"
        )
        # Migration: FEAT-07 per-user submission cap. 0 = unlimited (matches
        # the existing max_players semantics). Enforced server-side only on
        # logged-in submits - anonymous submits are subject to max_players
        # alone, since there's no identity to attribute repeats to.
        cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS max_yamls_per_user INTEGER DEFAULT 0")
        # Migration: FEAT-08 host-supplied public tracker URL. The host
        # pastes an Archipelago tracker link (e.g. archipelago.gg/tracker/xyz)
        # and /r/<id> surfaces it as a "Live tracker" link out. We never
        # iframe the tracker - cross-origin + ugly nesting.
        cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS tracker_url TEXT")
        # Migration: FEAT-17 host-supplied override for which slot the
        # WebSocket TrackerConnection should authenticate as. NULL =
        # auto-discover (prefer host's own first-uploaded slot, fall back
        # to first slot scraped from the tracker page). Any non-null
        # value is used verbatim. The host sets this via the room
        # Settings modal when they want a specific slot (e.g., a slot
        # they "own" semantically that wasn't auto-detected because the
        # YAML predates Discord-submitter tracking).
        cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS tracker_slot_name TEXT")
        # Migration: FEAT-20 claim-mode rooms. When TRUE, the host pre-loads
        # YAMLs as anonymous (submitter_user_id stays NULL even on host upload)
        # and players claim them via the public lobby. Default FALSE so every
        # existing room behaves exactly as before - feature is opt-in per
        # room via the Settings modal.
        cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS claim_mode BOOLEAN DEFAULT FALSE")
        # Migration: FEAT-21 per-room APWorld version pins. The host picks
        # which version of each game's APWorld players should install
        # locally; the public room page surfaces those as install links.
        # `apworld_name` is the index key (TOML filename stem, e.g. "alttp"),
        # `version` matches the index entry. Composite PK so a room has at
        # most one pin per APWorld; ON DELETE CASCADE so killing a room
        # cleans the pins. We DO NOT FK apworld_name -> any catalog table:
        # the index lives in a git repo, not the DB, and we want pins to
        # survive an index entry being temporarily renamed/dropped.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS room_apworlds (
                room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                apworld_name TEXT NOT NULL,
                version TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (room_id, apworld_name)
            )
        """)
        # Migration: FEAT-21 room-level APWorld policy toggles.
        #   allow_mixed_apworld_versions: softens the "you need exactly this
        #     version" copy on the public room page to "suggested version"
        #     so groups that don't strictly enforce match-up don't scare
        #     players who already have a different release installed.
        #   force_latest_apworld_versions: ignores stored per-game pins and
        #     always surfaces the latest version from the index. Auto-bumps
        #     as the index updates. The picker UI disables the dropdowns
        #     when this is on so the host can't leave stale pins behind.
        cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS allow_mixed_apworld_versions BOOLEAN DEFAULT FALSE")
        cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS force_latest_apworld_versions BOOLEAN DEFAULT FALSE")
        # FEAT-28 v2: when True (default), auto-pin upgrades the room's
        # pin to the highest indexed APWorld version any YAML in the
        # room declares via `requires.game.<Name>`. Hosts who want to
        # lock pins flip this off. Default TRUE so new rooms get the
        # smart behaviour without setup; existing rows backfill TRUE on
        # the ALTER.
        cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS auto_upgrade_apworld_pins BOOLEAN DEFAULT TRUE")
        # FEAT-28 v2: cached `{game_name: version}` map extracted from
        # each YAML's requires.game block at upload time. NULL means
        # "not yet extracted" (predates this column or save) and is
        # backfilled lazily by the room-wide auto-pin button.
        cur.execute("ALTER TABLE room_yamls ADD COLUMN IF NOT EXISTS apworld_versions JSONB DEFAULT NULL")
        # SEC-21: schema-level CHECK constraints on the `rooms` string columns.
        # Caps match the server-side validation in `api/rooms.py`
        # (_ROOM_STRING_LIMITS). The validation rejects with a clean 400; this
        # is a backstop so any path that bypasses the route layer (direct DB
        # writes, future blueprints, migrations) still can't push a multi-MB
        # value that would bloat the activity log (room name is denormalised
        # into every event row) or saturate request memory. Idempotent via
        # the pg_constraint pre-check pattern - PostgreSQL doesn't support
        # `ADD CONSTRAINT IF NOT EXISTS` for CHECK constraints natively.
        # Existing-data audit on 2026-05-05 confirmed the live max for each
        # column is well under its cap (e.g. desc_max=410 vs cap 8000).
        for cname, expr in (
            ("rooms_name_length",              "length(name) <= 200"),
            ("rooms_description_length",       "length(description) <= 8000"),
            ("rooms_host_name_length",         "length(host_name) <= 64"),
            ("rooms_tracker_url_length",       "length(tracker_url) <= 1024"),
            ("rooms_tracker_slot_name_length", "length(tracker_slot_name) <= 64"),
            ("rooms_external_host_length",     "length(external_host) <= 256"),
        ):
            cur.execute(f"""
                DO $$ BEGIN
                  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{cname}') THEN
                    ALTER TABLE rooms ADD CONSTRAINT {cname} CHECK ({expr});
                  END IF;
                END $$;
            """)
        # FEAT-33: per-user room creation templates. Logged-in hosts save
        # reusable room shapes (description, login requirement, deadline-as-
        # time+offset, claim mode, per-user cap, APWorld policy + auto-upgrade)
        # and apply them via a "Select template..." dropdown at the top of
        # CreateRoomModal. Payload is a JSONB blob owned by the API layer so
        # the templatable field set can evolve without schema migrations.
        # The partial unique index enforces "at most one default per user"
        # without blocking multiple non-defaults.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_room_templates (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name       TEXT NOT NULL,
                payload    JSONB NOT NULL,
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT user_room_templates_name_length CHECK (length(name) <= 80),
                CONSTRAINT user_room_templates_name_nonempty CHECK (length(name) > 0)
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_room_templates_user "
            "ON user_room_templates(user_id)"
        )
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_room_templates_default "
            "ON user_room_templates(user_id) WHERE is_default = TRUE"
        )
        # FEAT-38: Tier-1 builder schema cache. One row per distinct .apworld
        # artifact, keyed on the sha256 of the zip bytes (matches index.lock's
        # per-version sha when present) so a re-tagged upstream release can't
        # serve a stale schema. `schema` is the parse_apworld_options_bytes()
        # output; NULL means "parse attempted, nothing derivable" - a cached
        # negative so Tier-0 worlds don't get re-downloaded on every
        # builder-schemas request. (apworld_name, version) is a secondary
        # lookup path for index entries that have no lock sha.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS apworld_builder_schemas (
                sha256       TEXT PRIMARY KEY,
                apworld_name TEXT NOT NULL,
                version      TEXT NOT NULL,
                schema       JSONB,
                parsed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_apworld_builder_schemas_name_version "
            "ON apworld_builder_schemas(apworld_name, version)"
        )
    conn.autocommit = False
    conn.close()
    _db_url = db_url


def _get_conn():
    global _db_url
    # Self-heal if init_db() failed at boot (e.g., postgres not yet reachable
    # after a host reboot raced ap-web ahead of the db container). Without this
    # _db_url stays None and psycopg2.connect(None) silently falls back to a
    # local Unix socket, producing a misleading "No such file or directory"
    # error long after postgres recovers.
    if _db_url is None:
        _db_url = os.environ.get("DATABASE_URL")
    if not hasattr(_local, "conn") or _local.conn is None or _local.conn.closed:
        _local.conn = psycopg2.connect(_db_url)
    return _local.conn


def _dictrow(cur) -> list[dict]:
    cols = [d[0] for d in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _serialize(row: dict) -> dict:
    """Make datetimes JSON-safe."""
    out = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _gen_id() -> str:
    return secrets.token_urlsafe(6)


# ── Listings (Market) ────────────────────────────────────────────


def create_listing(seed: str, slot: int, player_name: str, item_name: str,
                   listing_type: str, quantity: int = 1) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO listings (seed, slot, player_name, item_name, listing_type, quantity)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
            (seed, slot, player_name, item_name, listing_type, quantity),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize(row)


def get_listing(listing_id: int) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM listings WHERE id = %s", (listing_id,))
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else {}


def get_listings(seed: str, status: str = "active") -> list[dict]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM listings WHERE seed = %s AND status = %s ORDER BY created_at DESC",
            (seed, status),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def get_matches(seed: str) -> list[dict]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT
                o.id AS offer_id, o.player_name AS offer_player, o.slot AS offer_slot,
                r.id AS request_id, r.player_name AS request_player, r.slot AS request_slot,
                o.item_name, o.quantity AS offer_qty, r.quantity AS request_qty
            FROM listings o
            JOIN listings r ON LOWER(o.item_name) = LOWER(r.item_name)
                AND o.seed = r.seed
                AND o.slot != r.slot
            WHERE o.seed = %s
                AND o.listing_type = 'offer' AND r.listing_type = 'request'
                AND o.status = 'active' AND r.status = 'active'
            ORDER BY o.item_name""",
            (seed,),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def update_listing(listing_id: int, **kwargs) -> dict:
    conn = _get_conn()
    allowed = {"status", "quantity"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_listing(listing_id)

    set_parts = [f"{k} = %s" for k in updates]
    set_parts.append("updated_at = NOW()")
    set_clause = ", ".join(set_parts)
    values = list(updates.values()) + [listing_id]

    with conn.cursor() as cur:
        cur.execute(f"UPDATE listings SET {set_clause} WHERE id = %s RETURNING *", values)
        rows = _dictrow(cur)
    conn.commit()
    return _serialize(rows[0]) if rows else {}


def delete_listing(listing_id: int) -> bool:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM listings WHERE id = %s", (listing_id,))
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted


# ── Rooms ────────────────────────────────────────────────────────


def create_room(name: str, host_name: str, description: str = "",
                spoiler_level: int = 3, race_mode: bool = False,
                max_players: int = 0, require_discord_login: bool = False,
                host_user_id: int | None = None,
                submit_deadline: str | None = None,
                max_yamls_per_user: int = 0,
                tracker_url: str | None = None,
                allow_mixed_apworld_versions: bool = False,
                force_latest_apworld_versions: bool = False,
                auto_upgrade_apworld_pins: bool = True,
                claim_mode: bool = False) -> dict:
    conn = _get_conn()
    room_id = _gen_id()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO rooms (id, name, host_name, description, spoiler_level, race_mode, max_players, require_discord_login, host_user_id, submit_deadline, max_yamls_per_user, tracker_url, allow_mixed_apworld_versions, force_latest_apworld_versions, auto_upgrade_apworld_pins, claim_mode)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (room_id, name, host_name, description, spoiler_level, race_mode, max_players, require_discord_login, host_user_id, submit_deadline, max_yamls_per_user, tracker_url, allow_mixed_apworld_versions, force_latest_apworld_versions, auto_upgrade_apworld_pins, claim_mode),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize(row)


def get_room(room_id: str) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM rooms WHERE id = %s", (room_id,))
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else {}


def get_room_by_seed(seed: str) -> dict:
    """Return the room whose generated seed matches, or {} if none."""
    if not seed:
        return {}
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM rooms WHERE seed = %s LIMIT 1", (seed,))
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else {}


def list_rooms(status: str | None = None, host_user_id: int | None = None) -> list[dict]:
    """List rooms, optionally filtered by status and/or owner.

    host_user_id semantics:
      - None: returns ALL rooms (admin view)
      - int : returns only rooms whose host_user_id matches (the user's own rooms)

    The route layer in api/rooms.py decides which to pass based on the caller's
    is_admin flag (admins get all by default, non-admins are pinned to their own).
    """
    conn = _get_conn()
    where = []
    args: list = []
    if status:
        where.append("status = %s")
        args.append(status)
    if host_user_id is not None:
        where.append("host_user_id = %s")
        args.append(host_user_id)
    # Include a yaml_count subquery so the rooms list can render slot counts
    # without an N+1 round-trip per row. Cheap because room_yamls.room_id
    # is indexed (`idx_room_yamls_room`).
    sql = (
        "SELECT rooms.*, "
        "  (SELECT COUNT(*) FROM room_yamls WHERE room_yamls.room_id = rooms.id) "
        "    AS yaml_count "
        "FROM rooms"
    )
    if where:
        sql += " WHERE " + " AND ".join(["rooms." + w if not w.startswith("rooms.") else w for w in where])
    sql += " ORDER BY rooms.created_at DESC"
    with conn.cursor() as cur:
        cur.execute(sql, args)
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def update_room(room_id: str, **kwargs) -> dict:
    conn = _get_conn()
    allowed = {"name", "description", "status", "seed", "generation_log",
               "spoiler_level", "race_mode", "max_players",
               "external_host", "external_port", "require_discord_login",
               "host_user_id", "submit_deadline",
               "max_yamls_per_user", "tracker_url", "tracker_slot_name",
               "claim_mode",
               "allow_mixed_apworld_versions", "force_latest_apworld_versions",
               "auto_upgrade_apworld_pins"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_room(room_id)

    set_parts = [f"{k} = %s" for k in updates]
    set_parts.append("updated_at = NOW()")
    set_clause = ", ".join(set_parts)
    values = list(updates.values()) + [room_id]

    with conn.cursor() as cur:
        cur.execute(f"UPDATE rooms SET {set_clause} WHERE id = %s RETURNING *", values)
        rows = _dictrow(cur)
    conn.commit()
    return _serialize(rows[0]) if rows else {}


def delete_room(room_id: str) -> bool:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM rooms WHERE id = %s", (room_id,))
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted


def auto_close_expired_rooms() -> list[dict]:
    """Close any open room whose submit_deadline has passed.

    Atomic UPDATE ... RETURNING so the sweeper and a concurrent request can't
    both react to the same expiry. Returns the rows that flipped to 'closed'
    so the caller can write a row_activity entry per close. NOW() in Postgres
    is the transaction's start time, which is fine here - we only care about
    "did the deadline pass at least a moment ago".
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE rooms
               SET status = 'closed', updated_at = NOW()
               WHERE status = 'open'
                 AND submit_deadline IS NOT NULL
                 AND submit_deadline <= NOW()
               RETURNING *"""
        )
        rows = _dictrow(cur)
    conn.commit()
    return [_serialize(r) for r in rows]


def maybe_auto_close_room(room_id: str) -> dict:
    """Lazy-close a single room if its deadline has passed.

    Returns the (possibly updated) room. Cheaper than a full sweep when a
    request only cares about one room (e.g. on read of /api/rooms/<id> or on
    a public submit). Idempotent on already-closed rooms.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE rooms
               SET status = 'closed', updated_at = NOW()
               WHERE id = %s
                 AND status = 'open'
                 AND submit_deadline IS NOT NULL
                 AND submit_deadline <= NOW()
               RETURNING *""",
            (room_id,),
        )
        rows = _dictrow(cur)
    conn.commit()
    if rows:
        return _serialize(rows[0])
    # No close happened - return current state.
    return get_room(room_id)


# ── Room YAMLs ───────────────────────────────────────────────────


def add_yaml(room_id: str, player_name: str, game: str,
             yaml_content: str, filename: str,
             submitter_user_id: int | None = None,
             apworld_versions: dict[str, str] | None = None) -> dict:
    """Insert a YAML row. Caller is expected to call update_yaml_validation
    immediately after to set the real status; we explicitly insert 'unknown'
    here rather than relying on the column default so a partial migration
    can't surface a 'pending' that violates the CHECK constraint.

    submitter_user_id captures the logged-in Discord user when present;
    null for host bulk uploads and anonymous public submits.

    apworld_versions caches the YAML's `requires.game` map so room views
    can render per-YAML version warnings without re-parsing on every
    request. None means "not extracted" (e.g. caller passed nothing -
    legacy path); the room-wide auto-pin button backfills these lazily.
    """
    import json
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO room_yamls (
                 room_id, player_name, game, yaml_content, filename,
                 validation_status, submitter_user_id, apworld_versions
               )
               VALUES (%s, %s, %s, %s, %s, 'unknown', %s, %s) RETURNING *""",
            (
                room_id, player_name, game, yaml_content, filename,
                submitter_user_id,
                json.dumps(apworld_versions) if apworld_versions is not None else None,
            ),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize(row)


def update_yaml_apworld_versions(yaml_id: int, apworld_versions: dict[str, str] | None) -> None:
    """FEAT-28 v2 backfill helper: cache the parsed `requires.game` map on
    an existing YAML row. Idempotent. Used by the auto-pin-all button to
    populate the column lazily for YAMLs that pre-date the schema."""
    import json
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE room_yamls SET apworld_versions = %s WHERE id = %s",
            (
                json.dumps(apworld_versions) if apworld_versions is not None else None,
                yaml_id,
            ),
        )
    conn.commit()


def get_yamls(room_id: str) -> list[dict]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM room_yamls WHERE room_id = %s ORDER BY uploaded_at",
            (room_id,),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def count_yamls_by_submitter(room_id: str, submitter_user_id: int) -> int:
    """FEAT-07: how many YAMLs has this Discord user submitted to this room?
    Anonymous submits (submitter_user_id IS NULL) are NOT counted - they can't
    be attributed to anyone, so the per-user cap can't enforce against them.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM room_yamls WHERE room_id = %s AND submitter_user_id = %s",
            (room_id, submitter_user_id),
        )
        return cur.fetchone()[0]


def get_yamls_with_submitters(room_id: str) -> list[dict]:
    """Host-only view: each YAML row + the submitter's Discord username when
    available. LEFT JOIN keeps anonymous (no-submitter) rows intact with
    submitter_username = None.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT y.*, u.discord_username AS submitter_username
               FROM room_yamls y
               LEFT JOIN users u ON u.id = y.submitter_user_id
               WHERE y.room_id = %s
               ORDER BY y.uploaded_at""",
            (room_id,),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def remove_yaml(yaml_id: int) -> bool:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM room_yamls WHERE id = %s", (yaml_id,))
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted


def get_yaml(yaml_id: int) -> dict | None:
    """Fetch one YAML row by id. Used by the FEAT-18 update flow to verify
    ownership before mutating, since the public route uses the YAML id
    (not the room id) as the addressable handle."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM room_yamls WHERE id = %s", (yaml_id,))
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else None


def update_yaml_content(yaml_id: int, player_name: str, game: str,
                        yaml_content: str, filename: str,
                        apworld_versions: dict[str, str] | None = None) -> dict:
    """FEAT-18: mutate an existing YAML's content in place. Preserves id,
    uploaded_at, room_id, and submitter_user_id - caller is expected to
    call update_yaml_validation immediately after to set the real status,
    same shape as add_yaml. Reset to 'unknown' here so a partially-failed
    update can't leave a stale 'validated' on a YAML whose new content
    doesn't pass.

    apworld_versions: re-extracted from the new content by the caller,
    refreshes the cached requires.game map. Pass None to leave the
    cached map untouched (rare - normally the caller re-extracts since
    the YAML body changed).
    """
    import json
    conn = _get_conn()
    with conn.cursor() as cur:
        # When apworld_versions is None we deliberately overwrite with NULL
        # too - if the new content doesn't have a requires.game block the
        # cached map shouldn't keep the old one around.
        cur.execute(
            """UPDATE room_yamls
               SET player_name = %s, game = %s, yaml_content = %s,
                   filename = %s, validation_status = 'unknown',
                   validation_error = NULL,
                   apworld_versions = %s
               WHERE id = %s
               RETURNING *""",
            (
                player_name, game, yaml_content, filename,
                json.dumps(apworld_versions) if apworld_versions is not None else None,
                yaml_id,
            ),
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize(rows[0]) if rows else {}


def claim_yaml(yaml_id: int, user_id: int) -> dict | None:
    """FEAT-20: a logged-in player atomically claims an unclaimed YAML.

    Race-safe: the WHERE clause requires submitter_user_id IS NULL, so two
    simultaneous claims resolve to one winner (rowcount=1) and one loser
    (rowcount=0 -> returns None). The route layer translates None to 409
    so the second claimer learns the slot was taken.

    Returns the updated row when the claim succeeded, None otherwise.
    Caller is expected to gate on room.claim_mode + room.status before
    invoking; this function only enforces the atomic write itself.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE room_yamls
               SET submitter_user_id = %s
               WHERE id = %s AND submitter_user_id IS NULL
               RETURNING *""",
            (user_id, yaml_id),
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize(rows[0]) if rows else None


def release_yaml(yaml_id: int, user_id: int) -> dict | None:
    """FEAT-20: the current claimer releases their claim, returning the
    YAML to the unclaimed pool. Atomic on submitter_user_id=user_id so a
    user can only release their own claim, never someone else's.

    Returns the updated row when the release succeeded, None otherwise."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE room_yamls
               SET submitter_user_id = NULL
               WHERE id = %s AND submitter_user_id = %s
               RETURNING *""",
            (yaml_id, user_id),
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize(rows[0]) if rows else None


VALID_VALIDATION_STATUSES = (
    "validated",
    "manually_validated",
    "unsupported",
    "failed",
    "unknown",
)

# Statuses that allow a YAML into a generation. ManuallyValidated is the
# escape hatch: an admin trusts a player whose YAML the validator can't
# reason about (custom apworld, version skew, etc.) so we let it through.
GENERATION_READY_STATUSES = ("validated", "manually_validated")


def update_yaml_validation(yaml_id: int, status: str, error: str | None = None) -> dict:
    if status not in VALID_VALIDATION_STATUSES:
        raise ValueError(f"Unknown validation status: {status}")
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE room_yamls SET validation_status = %s, validation_error = %s
               WHERE id = %s RETURNING *""",
            (status, error, yaml_id),
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize(rows[0]) if rows else {}


# ── Room Activity ────────────────────────────────────────────────


def add_activity(room_id: str, event_type: str, message: str) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO room_activity (room_id, event_type, message)
               VALUES (%s, %s, %s) RETURNING *""",
            (room_id, event_type, message),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize(row)


def get_activity(room_id: str, limit: int = 50) -> list[dict]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM room_activity WHERE room_id = %s ORDER BY created_at DESC LIMIT %s",
            (room_id, limit),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


# ── Per-room APWorld pins (FEAT-21) ──────────────────────────────


def get_room_apworlds(room_id: str) -> list[dict]:
    """Return the host's APWorld version pins for a room.

    Shape: [{apworld_name, version, created_at, updated_at}]. The picker
    UI overlays these onto the index entries to render dropdowns; the
    public room page joins them against the index to surface install
    links. Returns [] for rooms without any pins.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT apworld_name, version, created_at, updated_at "
            "FROM room_apworlds WHERE room_id = %s ORDER BY apworld_name",
            (room_id,),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def set_room_apworld(room_id: str, apworld_name: str, version: str) -> dict:
    """Upsert a single APWorld pin. Idempotent - resaving the same
    version just bumps updated_at."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO room_apworlds (room_id, apworld_name, version)
               VALUES (%s, %s, %s)
               ON CONFLICT (room_id, apworld_name) DO UPDATE
                 SET version = EXCLUDED.version, updated_at = NOW()
               RETURNING apworld_name, version, created_at, updated_at""",
            (room_id, apworld_name, version),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize(row)


def clear_room_apworld(room_id: str, apworld_name: str) -> bool:
    """Drop a single pin. Returns True if a row was deleted."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM room_apworlds WHERE room_id = %s AND apworld_name = %s",
            (room_id, apworld_name),
        )
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted


# ── Builder schema cache (FEAT-38) ────────────────────────────────


def _serialize_builder_schema(row: dict) -> dict:
    """Normalize the JSONB `schema` column to a dict (or None). Same
    driver-variance guard as _serialize_template."""
    out = _serialize(row)
    schema = out.get("schema")
    if isinstance(schema, str):
        import json as _json
        try:
            out["schema"] = _json.loads(schema)
        except Exception:
            out["schema"] = None
    return out


def get_builder_schema(sha256: str) -> dict | None:
    """Look up a cached Tier-1 builder schema by artifact sha256.

    Returns the full row ({sha256, apworld_name, version, schema, parsed_at})
    or None on cache miss. A returned row with schema=None is a cached
    NEGATIVE (parse attempted, nothing derivable) - callers must distinguish
    "no row" (fetch + parse needed) from "row with null schema" (Tier 0,
    don't re-fetch).
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sha256, apworld_name, version, schema, parsed_at "
            "FROM apworld_builder_schemas WHERE sha256 = %s",
            (sha256,),
        )
        rows = _dictrow(cur)
    return _serialize_builder_schema(rows[0]) if rows else None


def get_builder_schema_by_version(apworld_name: str, version: str) -> dict | None:
    """Fallback lookup for index entries without a lock sha. Newest row wins
    if multiple artifacts ever claimed the same (name, version)."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sha256, apworld_name, version, schema, parsed_at "
            "FROM apworld_builder_schemas "
            "WHERE apworld_name = %s AND version = %s "
            "ORDER BY parsed_at DESC LIMIT 1",
            (apworld_name, version),
        )
        rows = _dictrow(cur)
    return _serialize_builder_schema(rows[0]) if rows else None


def set_builder_schema(
    sha256: str, apworld_name: str, version: str, schema: dict | None
) -> None:
    """Upsert a parsed schema (or a null negative) for an artifact.
    Idempotent - re-parsing the same bytes refreshes parsed_at."""
    import json
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO apworld_builder_schemas (sha256, apworld_name, version, schema)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (sha256) DO UPDATE
                 SET apworld_name = EXCLUDED.apworld_name,
                     version = EXCLUDED.version,
                     schema = EXCLUDED.schema,
                     parsed_at = NOW()""",
            (
                sha256, apworld_name, version,
                json.dumps(schema) if schema is not None else None,
            ),
        )
    conn.commit()


# ── APWorld index requests + maintainers (FEAT-30 Phase 0a) ──────


def create_apworld_index_request(
    *,
    apworld_name: str,
    display_name: str,
    requested_version: str,
    source_url: str,
    notes: str | None,
    requester_user_id: int,
    requester_role: str,
    source_room_id: str | None,
) -> dict:
    """Insert a new request and return the row. Caller is responsible for
    permission checks (room host vs maintainer). Status starts at 'pending'."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO apworld_index_requests (
                 apworld_name, display_name, requested_version, source_url,
                 notes, requester_user_id, requester_role, source_room_id
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (
                apworld_name, display_name, requested_version, source_url,
                notes, requester_user_id, requester_role, source_room_id,
            ),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize(row)


def list_apworld_index_requests(status: str | None = None) -> list[dict]:
    """List all requests joined with the requester's discord username for
    the admin queue UI. Newest first."""
    conn = _get_conn()
    where = ""
    args: tuple = ()
    if status:
        where = "WHERE r.status = %s"
        args = (status,)
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT r.*, u.discord_username AS requester_username
                FROM apworld_index_requests r
                LEFT JOIN users u ON u.id = r.requester_user_id
                {where}
                ORDER BY r.created_at DESC""",
            args,
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def get_apworld_index_request(request_id: int) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM apworld_index_requests WHERE id = %s",
            (request_id,),
        )
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else {}


def update_apworld_index_request(request_id: int, **kwargs) -> dict:
    """Update mutable fields on a request. Same allowlist pattern as
    update_room (SEC-21): user-supplied keys filtered against a hardcoded
    set before being interpolated into the SET clause; values still go
    through %s. Touches updated_at unconditionally; sets resolved_at when
    transitioning to a terminal status (merged/rejected/failed)."""
    allowed = {
        "status", "fuzzer_status", "fuzzer_url",
        "audit_status", "audit_url", "pr_url", "reject_reason",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_apworld_index_request(request_id)

    set_parts = [f"{k} = %s" for k in updates]
    set_parts.append("updated_at = NOW()")
    if updates.get("status") in ("merged", "rejected", "failed"):
        set_parts.append("resolved_at = NOW()")
    set_clause = ", ".join(set_parts)
    values = list(updates.values()) + [request_id]

    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE apworld_index_requests SET {set_clause} WHERE id = %s RETURNING *",
            values,
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize(rows[0]) if rows else {}


def list_apworld_maintainers(apworld_name: str | None = None) -> list[dict]:
    """List maintainer assignments. If apworld_name is given, scoped to one
    APWorld; otherwise returns all (admin admin UI use)."""
    conn = _get_conn()
    where = ""
    args: tuple = ()
    if apworld_name:
        where = "WHERE m.apworld_name = %s"
        args = (apworld_name,)
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT m.*, u.discord_username, u.id AS user_id
                FROM apworld_maintainers m
                LEFT JOIN users u ON u.discord_id = m.discord_user_id
                {where}
                ORDER BY m.apworld_name, m.granted_at""",
            args,
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def list_maintained_apworlds(discord_user_id: str) -> list[str]:
    """Return the list of apworld_name strings the given Discord user
    maintains. Used to gate the maintainer-side submit endpoint and to
    populate the 'My APWorlds' nav surface."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT apworld_name FROM apworld_maintainers WHERE discord_user_id = %s ORDER BY apworld_name",
            (discord_user_id,),
        )
        return [r[0] for r in cur.fetchall()]


def is_apworld_maintainer(discord_user_id: str, apworld_name: str) -> bool:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM apworld_maintainers WHERE discord_user_id = %s AND apworld_name = %s",
            (discord_user_id, apworld_name),
        )
        return cur.fetchone() is not None


def add_apworld_maintainer(apworld_name: str, discord_user_id: str,
                           granted_by: int, notes: str | None = None) -> dict:
    """Idempotent: if the (apworld, user) pair already exists, returns the
    existing row instead of erroring (Postgres ON CONFLICT DO NOTHING)."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO apworld_maintainers (apworld_name, discord_user_id, granted_by, notes)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (apworld_name, discord_user_id) DO NOTHING
               RETURNING *""",
            (apworld_name, discord_user_id, granted_by, notes),
        )
        rows = _dictrow(cur)
    conn.commit()
    if rows:
        return _serialize(rows[0])
    # Existed already - fetch + return current row
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM apworld_maintainers WHERE apworld_name = %s AND discord_user_id = %s",
            (apworld_name, discord_user_id),
        )
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else {}


def remove_apworld_maintainer(apworld_name: str, discord_user_id: str) -> bool:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM apworld_maintainers WHERE apworld_name = %s AND discord_user_id = %s",
            (apworld_name, discord_user_id),
        )
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted


# ── Generation jobs ──────────────────────────────────────────────


def enqueue_generation_job(room_id: str) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO generation_jobs (room_id, status)
               VALUES (%s, 'queued') RETURNING *""",
            (room_id,),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize(row)


def get_generation_job(job_id: int) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM generation_jobs WHERE id = %s", (job_id,))
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else {}


def get_latest_generation_job(room_id: str) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM generation_jobs WHERE room_id = %s ORDER BY created_at DESC LIMIT 1",
            (room_id,),
        )
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else {}


def claim_pending_job() -> dict:
    """Atomically pick the oldest queued job and flip it to 'running'.

    Uses SELECT ... FOR UPDATE SKIP LOCKED so multiple workers (if we ever
    scale gunicorn past one worker) won't race for the same row. Returns the
    claimed row in its new running state, or {} if the queue is empty.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE generation_jobs
               SET status = 'running', started_at = NOW()
               WHERE id = (
                   SELECT id FROM generation_jobs
                   WHERE status = 'queued'
                   ORDER BY created_at ASC
                   FOR UPDATE SKIP LOCKED
                   LIMIT 1
               )
               RETURNING *"""
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize(rows[0]) if rows else {}


def mark_job_succeeded(job_id: int, seed: str, log: str) -> None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE generation_jobs
               SET status = 'succeeded', seed = %s, log = %s, finished_at = NOW()
               WHERE id = %s""",
            (seed, log, job_id),
        )
    conn.commit()


def mark_job_failed(job_id: int, error: str, log: str) -> None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE generation_jobs
               SET status = 'failed', error = %s, log = %s, finished_at = NOW()
               WHERE id = %s""",
            (error, log, job_id),
        )
    conn.commit()


def reset_orphaned_running_jobs() -> int:
    """Recover jobs left in 'running' when the worker process died.

    Anything 'running' that started more than GENERATION_TIMEOUT * 3 seconds ago
    is presumed lost (worker crashed mid-generation, container restarted, etc.)
    and gets flipped back to 'queued' so a new worker can pick it up. Called
    once at worker startup.
    """
    import config
    conn = _get_conn()
    cutoff_secs = config.GENERATION_TIMEOUT * 3
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE generation_jobs
               SET status = 'queued', started_at = NULL
               WHERE status = 'running'
                 AND started_at < NOW() - (%s || ' seconds')::interval""",
            (str(cutoff_secs),),
        )
        affected = cur.rowcount
    conn.commit()
    return affected


# ── Users ─────────────────────────────────────────────────────────


def create_or_update_user(discord_id: str, discord_username: str) -> dict:
    import config
    is_owner = discord_id == config.OWNER_DISCORD_ID
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO users (discord_id, discord_username, is_admin, is_approved)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (discord_id)
               DO UPDATE SET discord_username = EXCLUDED.discord_username,
                             is_admin = users.is_admin OR EXCLUDED.is_admin,
                             is_approved = users.is_approved OR EXCLUDED.is_approved
               RETURNING *""",
            (discord_id, discord_username, is_owner, is_owner),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize(row)


def get_user(user_id: int) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else {}


def list_users() -> list[dict]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users ORDER BY created_at")
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def set_user_approved(user_id: int, approved: bool) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET is_approved = %s WHERE id = %s RETURNING *",
            (approved, user_id),
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize(rows[0]) if rows else {}


# ── Room creation templates (FEAT-33) ─────────────────────────────
#
# Per-user reusable room shapes applied via the "Select template..." dropdown
# at the top of CreateRoomModal. Payload is an opaque JSONB blob owned by the
# API layer (api/room_templates.py) so the templatable field set can evolve
# without schema migrations. Default-template flip is mutually exclusive per
# user via a partial unique index in init_db.


def _serialize_template(row: dict) -> dict:
    """Pull the JSONB payload out as a dict before json.dumps in jsonify."""
    out = _serialize(row)
    payload = out.get("payload")
    # psycopg2 returns JSONB as a Python dict by default, but some drivers
    # return raw text. Normalize to dict either way.
    if isinstance(payload, str):
        import json as _json
        try:
            out["payload"] = _json.loads(payload)
        except Exception:
            out["payload"] = {}
    return out


def list_room_templates(user_id: int) -> list[dict]:
    """All templates owned by this user, default first then alphabetical."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT * FROM user_room_templates
               WHERE user_id = %s
               ORDER BY is_default DESC, lower(name) ASC, id ASC""",
            (user_id,),
        )
        rows = _dictrow(cur)
    return [_serialize_template(r) for r in rows]


def count_room_templates(user_id: int) -> int:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM user_room_templates WHERE user_id = %s", (user_id,))
        return cur.fetchone()[0]


def get_room_template(user_id: int, template_id: int) -> dict | None:
    """Scoped read: returns None for templates the user doesn't own (so the
    route layer can return 404 without leaking existence to other users)."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM user_room_templates WHERE id = %s AND user_id = %s",
            (template_id, user_id),
        )
        rows = _dictrow(cur)
    return _serialize_template(rows[0]) if rows else None


def create_room_template(user_id: int, name: str, payload: dict,
                         is_default: bool = False) -> dict:
    """Insert a new template. If is_default=True, atomically clears the flag
    on any existing template owned by this user before setting it on the new
    row, so the partial unique index never trips mid-statement."""
    import json as _json
    conn = _get_conn()
    with conn.cursor() as cur:
        if is_default:
            cur.execute(
                "UPDATE user_room_templates SET is_default = FALSE, updated_at = NOW() "
                "WHERE user_id = %s AND is_default = TRUE",
                (user_id,),
            )
        cur.execute(
            """INSERT INTO user_room_templates (user_id, name, payload, is_default)
               VALUES (%s, %s, %s::jsonb, %s) RETURNING *""",
            (user_id, name, _json.dumps(payload), is_default),
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize_template(rows[0])


def update_room_template(user_id: int, template_id: int, *,
                         name: str | None = None,
                         payload: dict | None = None,
                         is_default: bool | None = None) -> dict | None:
    """Patch the named fields. Scoped by user_id so cross-user writes are
    impossible. Returns None when the row doesn't exist or isn't owned by
    this user. Default-flip semantics match create_room_template."""
    import json as _json
    conn = _get_conn()
    with conn.cursor() as cur:
        # Pre-flight: confirm the row belongs to this user.
        cur.execute(
            "SELECT id FROM user_room_templates WHERE id = %s AND user_id = %s",
            (template_id, user_id),
        )
        if not cur.fetchone():
            return None

        if is_default is True:
            cur.execute(
                "UPDATE user_room_templates SET is_default = FALSE, updated_at = NOW() "
                "WHERE user_id = %s AND is_default = TRUE AND id != %s",
                (user_id, template_id),
            )

        sets = []
        params: list = []
        if name is not None:
            sets.append("name = %s")
            params.append(name)
        if payload is not None:
            sets.append("payload = %s::jsonb")
            params.append(_json.dumps(payload))
        if is_default is not None:
            sets.append("is_default = %s")
            params.append(is_default)
        if not sets:
            # Nothing to change — return the current row unchanged.
            cur.execute(
                "SELECT * FROM user_room_templates WHERE id = %s AND user_id = %s",
                (template_id, user_id),
            )
            rows = _dictrow(cur)
            return _serialize_template(rows[0]) if rows else None

        sets.append("updated_at = NOW()")
        params.extend([template_id, user_id])
        cur.execute(
            f"UPDATE user_room_templates SET {', '.join(sets)} "
            f"WHERE id = %s AND user_id = %s RETURNING *",
            tuple(params),
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize_template(rows[0]) if rows else None


def delete_room_template(user_id: int, template_id: int) -> bool:
    """Returns True when the row existed and was deleted, False otherwise.
    Scoped by user_id so users can't delete each other's templates."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_room_templates WHERE id = %s AND user_id = %s",
            (template_id, user_id),
        )
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted


# ── Trackers ──────────────────────────────────────────────────────


def create_tracker(tracker_url: str, display_name: str = "",
                   host: str = "", port: int | None = None) -> dict:
    conn = _get_conn()
    tracker_id = _gen_id()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO trackers (id, tracker_url, display_name, host, port)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (tracker_url)
               DO UPDATE SET display_name = COALESCE(NULLIF(EXCLUDED.display_name, ''), trackers.display_name),
                            last_synced = NOW()
               RETURNING *""",
            (tracker_id, tracker_url, display_name, host, port),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize(row)


def get_tracker(tracker_id: str) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM trackers WHERE id = %s", (tracker_id,))
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else {}


def get_tracker_by_url(tracker_url: str) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM trackers WHERE tracker_url = %s", (tracker_url,))
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else {}


def list_trackers(limit: int = 20) -> list[dict]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM trackers ORDER BY last_synced DESC NULLS LAST, created_at DESC LIMIT %s",
            (limit,),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def update_tracker_sync(tracker_id: str) -> None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("UPDATE trackers SET last_synced = NOW() WHERE id = %s", (tracker_id,))
    conn.commit()


# ── Tracker-based Listings ────────────────────────────────────────


def create_tracker_listing(tracker_id: str, slot: int, player_name: str,
                           item_name: str, listing_type: str,
                           quantity: int = 1) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO listings (tracker_id, slot, player_name, item_name, listing_type, quantity)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
            (tracker_id, slot, player_name, item_name, listing_type, quantity),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize(row)


def get_tracker_listings(tracker_id: str, status: str = "active") -> list[dict]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM listings WHERE tracker_id = %s AND status = %s ORDER BY created_at DESC",
            (tracker_id, status),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def get_tracker_matches(tracker_id: str) -> list[dict]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT
                o.id AS offer_id, o.player_name AS offer_player, o.slot AS offer_slot,
                r.id AS request_id, r.player_name AS request_player, r.slot AS request_slot,
                o.item_name, o.quantity AS offer_qty, r.quantity AS request_qty
            FROM listings o
            JOIN listings r ON LOWER(o.item_name) = LOWER(r.item_name)
                AND o.tracker_id = r.tracker_id
                AND o.slot != r.slot
            WHERE o.tracker_id = %s
                AND o.listing_type = 'offer' AND r.listing_type = 'request'
                AND o.status = 'active' AND r.status = 'active'
            ORDER BY o.item_name""",
            (tracker_id,),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]
