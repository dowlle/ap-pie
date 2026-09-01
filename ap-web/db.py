"""PostgreSQL database for persistent features (market, rooms, future: claims, users)."""

from __future__ import annotations

import os
import re
import secrets
import threading
from datetime import datetime, timezone

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


def rollback_request_transaction() -> None:
    """Close any read-only/request transaction left on this thread.

    Helpers use a thread-local persistent connection and many SELECT helpers
    intentionally do not commit. Flask calls this after every request so those
    reads cannot hold snapshots or relation locks between requests.
    """
    conn = getattr(_local, "conn", None)
    if conn is not None and not conn.closed:
        conn.rollback()

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
        # Open-room access keeps a separate abuse switch from the legacy
        # approval bit. Approval still controls the older host-only surfaces;
        # this flag lets an admin stop new room creation without erasing a
        # user's rooms or preventing them from downloading existing work.
        cur.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
            "room_creation_blocked BOOLEAN DEFAULT FALSE"
        )
        # Account lifecycle: a scheduled deletion locks the account immediately
        # but preserves every row until deletion_due_at so the same Discord
        # identity can cancel an accidental request during the grace period.
        cur.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS deletion_requested_at TIMESTAMPTZ"
        )
        cur.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS deletion_due_at TIMESTAMPTZ"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_deletion_due "
            "ON users(deletion_due_at) WHERE deletion_due_at IS NOT NULL"
        )
        cur.execute("""
            CREATE TABLE IF NOT EXISTS account_deletion_tokens (
                user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS account_deletion_rate_limits (
                user_id           INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                window_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                attempts          INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS room_creation_blocks (
                discord_id_hmac TEXT PRIMARY KEY,
                blocked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                review_after    TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '180 days')
            )
        """)
        # Operational grants issued by an account can outlive that account;
        # preserve the grant while removing its person-level attribution.
        cur.execute(
            "ALTER TABLE apworld_maintainers "
            "DROP CONSTRAINT IF EXISTS apworld_maintainers_granted_by_fkey"
        )
        cur.execute(
            "ALTER TABLE apworld_maintainers ALTER COLUMN granted_by DROP NOT NULL"
        )
        cur.execute(
            "ALTER TABLE apworld_maintainers ADD CONSTRAINT "
            "apworld_maintainers_granted_by_fkey FOREIGN KEY (granted_by) "
            "REFERENCES users(id) ON DELETE SET NULL"
        )
        # Structured attribution makes future account erasure exact. Legacy
        # rows remain nullable and are handled by the permanent-delete scrub.
        cur.execute(
            "ALTER TABLE room_activity ADD COLUMN IF NOT EXISTS "
            "actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
        )
        cur.execute(
            "ALTER TABLE room_activity ADD COLUMN IF NOT EXISTS "
            "subject_yaml_id INTEGER REFERENCES room_yamls(id) ON DELETE SET NULL"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_room_activity_actor "
            "ON room_activity(actor_user_id) WHERE actor_user_id IS NOT NULL"
        )
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
        # Room coordination slices A+B: bind a collection room to its generated
        # tracker roster, then keep ownership and self-reported state against
        # stable Archipelago (team, slot) coordinates. Display names remain
        # mutable labels and are deliberately not part of any primary key.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS room_generated_rooms (
                room_id TEXT PRIMARY KEY REFERENCES rooms(id) ON DELETE CASCADE,
                tracker_url TEXT NOT NULL,
                tracker_room_id TEXT,
                associated_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                associated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT generated_room_tracker_url_length CHECK (length(tracker_url) <= 1024)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS room_slots (
                room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                team INTEGER NOT NULL DEFAULT 0 CHECK (team >= 0),
                slot INTEGER NOT NULL CHECK (slot > 0),
                player_name TEXT NOT NULL,
                game TEXT NOT NULL DEFAULT '',
                source_yaml_id INTEGER REFERENCES room_yamls(id) ON DELETE SET NULL,
                owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                owner_source TEXT CHECK (owner_source IN ('yaml', 'claim', 'host') OR owner_source IS NULL),
                ownership_locked BOOLEAN NOT NULL DEFAULT FALSE,
                claimed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (room_id, team, slot),
                CONSTRAINT room_slots_player_name_length CHECK (length(player_name) <= 64),
                CONSTRAINT room_slots_game_length CHECK (length(game) <= 200)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_room_slots_owner ON room_slots(room_id, owner_user_id)")
        cur.execute("ALTER TABLE room_slots ADD COLUMN IF NOT EXISTS ownership_locked BOOLEAN NOT NULL DEFAULT FALSE")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS room_slot_ownership_events (
                id BIGSERIAL PRIMARY KEY,
                room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                team INTEGER NOT NULL,
                slot INTEGER NOT NULL,
                event_type TEXT NOT NULL CHECK (event_type IN ('yaml_bound', 'claimed', 'released', 'host_assigned', 'host_cleared')),
                previous_owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                owner_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_room_slot_events ON room_slot_ownership_events(room_id, team, slot, created_at DESC)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS room_slot_state (
                room_id TEXT NOT NULL,
                team INTEGER NOT NULL,
                slot INTEGER NOT NULL,
                bk_since TIMESTAMPTZ,
                bk_confirmed_at TIMESTAMPTZ,
                go_mode_since TIMESTAMPTZ,
                slot_note TEXT NOT NULL DEFAULT '',
                updated_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (room_id, team, slot),
                FOREIGN KEY (room_id, team, slot) REFERENCES room_slots(room_id, team, slot) ON DELETE CASCADE,
                CONSTRAINT room_slot_note_length CHECK (length(slot_note) <= 280)
            )
        """)
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

        # FEAT-42: community YAML presets.
        #
        # A preset is a named configuration someone publishes so a newcomer
        # can start from a working setup instead of 26 options they cannot
        # evaluate. Two kinds (design D5): `simple` stores option values and
        # fills the builder form; `advanced` stores a full YAML document and
        # opens in the review step's editor, which is how plando, triggers,
        # item links and weights stay shareable.
        #
        # Column is `option_values`, not `values`: VALUES is a reserved word
        # in SQL and every query touching it would need quoting.
        #
        # status starts at `private` (design D6): saving is cheap and
        # personal, publishing is a separate deliberate act from the My
        # presets page. That private tier is what FEAT-23 asked for.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS apworld_presets (
                id             SERIAL PRIMARY KEY,
                apworld_name   TEXT NOT NULL,
                version        TEXT NOT NULL,
                name           TEXT NOT NULL,
                description    TEXT NOT NULL DEFAULT '',
                kind           TEXT NOT NULL DEFAULT 'simple'
                               CHECK (kind IN ('simple', 'advanced')),
                option_values  JSONB,
                yaml_content   TEXT,
                author_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                is_official    BOOLEAN NOT NULL DEFAULT FALSE,
                status         TEXT NOT NULL DEFAULT 'private'
                               CHECK (status IN ('private', 'published', 'hidden')),
                uses           INTEGER NOT NULL DEFAULT 0,
                score          INTEGER NOT NULL DEFAULT 0,
                reports        INTEGER NOT NULL DEFAULT 0,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT preset_name_length CHECK (length(name) <= 80),
                CONSTRAINT preset_desc_length CHECK (length(description) <= 500),
                CONSTRAINT preset_yaml_length CHECK (length(COALESCE(yaml_content, '')) <= 65536),
                CONSTRAINT preset_payload CHECK (
                    (kind = 'simple' AND option_values IS NOT NULL AND yaml_content IS NULL)
                    OR (kind = 'advanced' AND yaml_content IS NOT NULL AND option_values IS NULL)
                )
            )
        """)
        for stmt in (
            "CREATE INDEX IF NOT EXISTS idx_presets_apworld ON apworld_presets"
            "(apworld_name, status)",
            "CREATE INDEX IF NOT EXISTS idx_presets_author ON apworld_presets"
            "(author_user_id, created_at DESC) WHERE author_user_id IS NOT NULL",
        ):
            cur.execute(stmt)

        # One upvote per user per preset. No downvotes (decision 2026-08-17):
        # in a community this size a negative vote reads as a personal remark
        # rather than a data point, and report + admin hide already covers
        # junk. `value` is constrained to 1 so widening it later is a
        # deliberate migration rather than an accident.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS apworld_preset_votes (
                preset_id  INTEGER NOT NULL REFERENCES apworld_presets(id) ON DELETE CASCADE,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                value      SMALLINT NOT NULL DEFAULT 1 CHECK (value IN (1)),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (preset_id, user_id)
            )
        """)
        # SEC-44: reporting is idempotent per signed-in user and preset.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS apworld_preset_reports (
                preset_id  INTEGER NOT NULL REFERENCES apworld_presets(id) ON DELETE CASCADE,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (preset_id, user_id)
            )
        """)
        # SEC-45: API validation gives a friendly response; these append-only
        # migration backstops prevent later writers bypassing the same cap.
        cur.execute("""
            DO $$ BEGIN
                ALTER TABLE apworld_presets
                    ADD CONSTRAINT preset_option_values_bytes
                    CHECK (option_values IS NULL OR octet_length(option_values::text) <= 65536);
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$
        """)

        # FEAT-43: a player's own YAML library.
        #
        # Separate from apworld_presets on purpose: presets are public
        # content with publish / report / vote lifecycles, a saved YAML is a
        # private artifact with a slot name and a submission history. Same
        # payload shape, different lives.
        #
        # kind mirrors the preset split (design D2): a form-built YAML is
        # stored as option values so it survives version bumps and can be
        # re-validated, a hand-edited one is kept verbatim because rewriting
        # someone's plando block would be worse than not storing it.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_yamls (
                id            SERIAL PRIMARY KEY,
                user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                apworld_name  TEXT NOT NULL,
                version       TEXT NOT NULL,
                player_name   TEXT NOT NULL,
                label         TEXT NOT NULL DEFAULT '',
                kind          TEXT NOT NULL DEFAULT 'simple'
                              CHECK (kind IN ('simple', 'advanced')),
                option_values JSONB,
                yaml_content  TEXT,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT user_yaml_label_length CHECK (length(label) <= 120),
                CONSTRAINT user_yaml_payload CHECK (
                    (kind = 'simple' AND option_values IS NOT NULL AND yaml_content IS NULL)
                    OR (kind = 'advanced' AND yaml_content IS NOT NULL AND option_values IS NULL)
                )
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_yamls_user ON user_yamls"
            "(user_id, updated_at DESC)"
        )
        cur.execute("""
            DO $$ BEGIN
                ALTER TABLE user_yamls
                    ADD CONSTRAINT user_yaml_option_values_bytes
                    CHECK (option_values IS NULL OR octet_length(option_values::text) <= 65536);
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$
        """)
        # Additive link so a submission can point back at the library row it
        # came from. Nullable: every existing submission predates the library,
        # and anonymous submits never have one.
        cur.execute(
            "ALTER TABLE room_yamls ADD COLUMN IF NOT EXISTS source_user_yaml_id "
            "INTEGER REFERENCES user_yamls(id) ON DELETE SET NULL"
        )
        # FEAT-31 gap 2: option-level validation results. validate_yaml only
        # ever checked structure, so a bad option value surfaced at generation
        # time in the host's lap. Warnings are advisory and never block a
        # submission - a custom fork or a triggers block is legitimately not
        # schema-checkable.
        cur.execute(
            "ALTER TABLE room_yamls ADD COLUMN IF NOT EXISTS option_warnings JSONB"
        )

        # FEAT-31: cookieless server-side analytics.
        #
        # Privacy shape is load-bearing, not incidental (see analytics.py and
        # the public /privacy page): no raw IP, no User-Agent string, no
        # persistent or device-stored identifier. `cf_country` is a 2-letter
        # code, `ua_class` is one of desktop/mobile/bot, and `visit_id` is a
        # per-page-load random id held only in the browser's memory, so it
        # dies on reload and links nothing across visits or devices.
        #
        # `room_id` is deliberately NOT a foreign key: rooms get deleted and
        # we want the historical event to survive. `user_id` IS a foreign key
        # with ON DELETE SET NULL so deleting a user anonymises their history
        # instead of orphaning it (GDPR Art. 17 via db.delete_events_for_user
        # for the narrower "erase my analytics" request).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id         BIGSERIAL PRIMARY KEY,
                ts         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                kind       TEXT NOT NULL,
                user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
                room_id    TEXT,
                path       TEXT,
                cf_country TEXT,
                ua_class   TEXT,
                request_id TEXT,
                visit_id   TEXT,
                props      JSONB NOT NULL DEFAULT '{}'::jsonb
            )
        """)
        for stmt in (
            "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC)",
            "CREATE INDEX IF NOT EXISTS idx_events_kind_ts ON events(kind, ts DESC)",
            "CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events(user_id, ts DESC) "
            "WHERE user_id IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_events_room_ts ON events(room_id, ts DESC) "
            "WHERE room_id IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_events_visit_ts ON events(visit_id, ts DESC) "
            "WHERE visit_id IS NOT NULL",
        ):
            cur.execute(stmt)

        # Daily rollup. Written by the retention sweeper BEFORE raw rows are
        # pruned, so long-term trend survives the retention window. Contains
        # counts only - no user_id, no room_id, no visit_id, nothing that
        # relates to an identifiable person - which is why it has no
        # expiry of its own.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events_daily (
                day         DATE NOT NULL,
                kind        TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                PRIMARY KEY (day, kind)
            )
        """)
        # SEC-43: a DB-shared ceiling covers every server-side recorder and
        # remains global if gunicorn later gains more workers.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS analytics_write_buckets (
                minute      TIMESTAMPTZ PRIMARY KEY,
                event_count INTEGER NOT NULL CHECK (event_count >= 0)
            )
        """)
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


def get_room_creation_counts(host_user_id: int) -> dict[str, int]:
    """Return the three quota counters used by open room creation.

    `active` means a collector that is still accepting submissions. Closing a
    room frees active quota; deleting it also frees retained-room quota. The
    query is one indexed pass over that user's rooms.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status = 'open') AS active,
                   COUNT(*) FILTER (
                       WHERE created_at >= NOW() - INTERVAL '1 hour'
                   ) AS recent
               FROM rooms
               WHERE host_user_id = %s""",
            (host_user_id,),
        )
        row = _dictrow(cur)[0]
    return {key: int(row.get(key) or 0) for key in ("total", "active", "recent")}


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


def add_activity(
    room_id: str,
    event_type: str,
    message: str,
    *,
    actor_user_id: int | None = None,
    subject_yaml_id: int | None = None,
) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO room_activity
                      (room_id, event_type, message, actor_user_id, subject_yaml_id)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (room_id, event_type, message, actor_user_id, subject_yaml_id),
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


# ── Generated-room slots and coordination state ─────────────────


def get_generated_room(room_id: str) -> dict | None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM room_generated_rooms WHERE room_id = %s", (room_id,))
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else None


def list_room_slots(room_id: str) -> list[dict]:
    """Return the generated roster with owner display data and state."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT s.*, u.discord_username AS owner_username,
                      st.bk_since, st.bk_confirmed_at, st.go_mode_since,
                      COALESCE(st.slot_note, '') AS slot_note, st.updated_at AS state_updated_at
               FROM room_slots s
               LEFT JOIN users u ON u.id = s.owner_user_id
               LEFT JOIN room_slot_state st
                 ON st.room_id = s.room_id AND st.team = s.team AND st.slot = s.slot
               WHERE s.room_id = %s
               ORDER BY s.team, s.slot""",
            (room_id,),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def get_room_slot(room_id: str, team: int, slot: int) -> dict | None:
    rows = [s for s in list_room_slots(room_id) if s["team"] == team and s["slot"] == slot]
    return rows[0] if rows else None


def associate_generated_room(
    room_id: str,
    tracker_url: str,
    tracker_room_id: str | None,
    actor_user_id: int | None,
    slots: list[dict],
) -> list[dict]:
    """Persist a reviewed generated roster without overwriting explicit claims.

    Each slot dict contains team, slot, player_name, game and optional yaml_id,
    yaml_owner_user_id. Existing claim/host ownership wins over a refreshed
    automatic YAML mapping. YAML ownership initializes only an unowned row.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO room_generated_rooms
                 (room_id, tracker_url, tracker_room_id, associated_by_user_id)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (room_id) DO UPDATE SET
                 tracker_url = EXCLUDED.tracker_url,
                 tracker_room_id = EXCLUDED.tracker_room_id,
                 associated_by_user_id = EXCLUDED.associated_by_user_id,
                 updated_at = NOW()""",
            (room_id, tracker_url, tracker_room_id, actor_user_id),
        )
        seen: set[tuple[int, int]] = set()
        for item in slots:
            team = int(item.get("team", 0))
            slot = int(item["slot"])
            seen.add((team, slot))
            yaml_owner = item.get("yaml_owner_user_id")
            cur.execute(
                """INSERT INTO room_slots
                     (room_id, team, slot, player_name, game, source_yaml_id,
                      owner_user_id, owner_source, claimed_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s,
                           CASE WHEN %s IS NULL THEN NULL ELSE 'yaml' END,
                           CASE WHEN %s IS NULL THEN NULL ELSE NOW() END)
                   ON CONFLICT (room_id, team, slot) DO UPDATE SET
                     player_name = EXCLUDED.player_name,
                     game = EXCLUDED.game,
                     source_yaml_id = EXCLUDED.source_yaml_id,
                     owner_user_id = CASE
                       WHEN NOT room_slots.ownership_locked THEN EXCLUDED.owner_user_id
                       ELSE room_slots.owner_user_id END,
                     owner_source = CASE
                       WHEN NOT room_slots.ownership_locked THEN EXCLUDED.owner_source
                       ELSE room_slots.owner_source END,
                     claimed_at = CASE
                       WHEN NOT room_slots.ownership_locked THEN EXCLUDED.claimed_at
                       ELSE room_slots.claimed_at END,
                     updated_at = NOW()
                   RETURNING owner_user_id, owner_source""",
                (
                    room_id, team, slot, item["player_name"], item.get("game", ""),
                    item.get("yaml_id"), yaml_owner, yaml_owner, yaml_owner,
                ),
            )
            persisted = cur.fetchone()
            if yaml_owner is not None and persisted and persisted[1] == "yaml":
                cur.execute(
                    """INSERT INTO room_slot_ownership_events
                         (room_id, team, slot, event_type, owner_user_id, actor_user_id)
                       SELECT %s, %s, %s, 'yaml_bound', %s, %s
                       WHERE NOT EXISTS (
                         SELECT 1 FROM room_slot_ownership_events
                         WHERE room_id = %s AND team = %s AND slot = %s
                           AND event_type = 'yaml_bound' AND owner_user_id = %s
                       )""",
                    (room_id, team, slot, yaml_owner, actor_user_id,
                     room_id, team, slot, yaml_owner),
                )
        # Drop roster entries no longer present only when they have no explicit
        # owner/state. Claimed or coordinated historical slots stay reviewable.
        cur.execute("SELECT team, slot FROM room_slots WHERE room_id = %s", (room_id,))
        for team, slot in cur.fetchall():
            if (team, slot) not in seen:
                cur.execute(
                    """DELETE FROM room_slots s
                       WHERE s.room_id = %s AND s.team = %s AND s.slot = %s
                         AND s.owner_user_id IS NULL
                         AND NOT EXISTS (
                           SELECT 1 FROM room_slot_state st
                           WHERE st.room_id=s.room_id AND st.team=s.team AND st.slot=s.slot
                         )""",
                    (room_id, team, slot),
                )
    conn.commit()
    return list_room_slots(room_id)


def claim_room_slot(room_id: str, team: int, slot: int, user_id: int) -> dict | None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE room_slots SET owner_user_id=%s, owner_source='claim', ownership_locked=TRUE,
                      claimed_at=NOW(), updated_at=NOW()
               WHERE room_id=%s AND team=%s AND slot=%s AND owner_user_id IS NULL
               RETURNING *""",
            (user_id, room_id, team, slot),
        )
        rows = _dictrow(cur)
        if rows:
            cur.execute(
                """INSERT INTO room_slot_ownership_events
                     (room_id, team, slot, event_type, owner_user_id, actor_user_id)
                   VALUES (%s, %s, %s, 'claimed', %s, %s)""",
                (room_id, team, slot, user_id, user_id),
            )
    conn.commit()
    return _serialize(rows[0]) if rows else None


def release_room_slot(room_id: str, team: int, slot: int, user_id: int) -> dict | None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE room_slots SET owner_user_id=NULL, owner_source=NULL, ownership_locked=TRUE,
                      claimed_at=NULL, updated_at=NOW()
               WHERE room_id=%s AND team=%s AND slot=%s AND owner_user_id=%s
               RETURNING *""",
            (room_id, team, slot, user_id),
        )
        rows = _dictrow(cur)
        if rows:
            cur.execute(
                """INSERT INTO room_slot_ownership_events
                     (room_id, team, slot, event_type, previous_owner_user_id, actor_user_id)
                   VALUES (%s, %s, %s, 'released', %s, %s)""",
                (room_id, team, slot, user_id, user_id),
            )
    conn.commit()
    return _serialize(rows[0]) if rows else None


def assign_room_slot_owner(
    room_id: str, team: int, slot: int, owner_user_id: int | None, actor_user_id: int | None,
) -> dict | None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT owner_user_id FROM room_slots WHERE room_id=%s AND team=%s AND slot=%s FOR UPDATE",
            (room_id, team, slot),
        )
        prior = cur.fetchone()
        if not prior:
            conn.commit()
            return None
        cur.execute(
            """UPDATE room_slots SET owner_user_id=%s, ownership_locked=TRUE,
                      owner_source=CASE WHEN %s IS NULL THEN NULL ELSE 'host' END,
                      claimed_at=CASE WHEN %s IS NULL THEN NULL ELSE NOW() END,
                      updated_at=NOW()
               WHERE room_id=%s AND team=%s AND slot=%s RETURNING *""",
            (owner_user_id, owner_user_id, owner_user_id, room_id, team, slot),
        )
        rows = _dictrow(cur)
        cur.execute(
            """INSERT INTO room_slot_ownership_events
                 (room_id, team, slot, event_type, previous_owner_user_id, owner_user_id, actor_user_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (room_id, team, slot, "host_assigned" if owner_user_id else "host_cleared",
             prior[0], owner_user_id, actor_user_id),
        )
    conn.commit()
    return _serialize(rows[0]) if rows else None


def update_room_slot_state(
    room_id: str, team: int, slot: int, actor_user_id: int,
    *, bk_action: str | None = None, go_mode: bool | None = None,
    slot_note: str | None = None,
) -> dict:
    """Apply a partial self-state update. BK actions are set/confirm/clear."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO room_slot_state (room_id, team, slot, updated_by_user_id)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (room_id, team, slot) DO NOTHING""",
            (room_id, team, slot, actor_user_id),
        )
        updates = ["updated_by_user_id=%s", "updated_at=NOW()"]
        values: list = [actor_user_id]
        if bk_action == "set":
            updates += ["bk_since=COALESCE(bk_since, NOW())", "bk_confirmed_at=NOW()"]
        elif bk_action == "confirm":
            updates += ["bk_since=COALESCE(bk_since, NOW())", "bk_confirmed_at=NOW()"]
        elif bk_action == "clear":
            updates += ["bk_since=NULL", "bk_confirmed_at=NULL"]
        if go_mode is not None:
            updates.append("go_mode_since=CASE WHEN %s THEN COALESCE(go_mode_since, NOW()) ELSE NULL END")
            values.append(go_mode)
        if slot_note is not None:
            updates.append("slot_note=%s")
            values.append(slot_note)
        values += [room_id, team, slot]
        cur.execute(
            f"""UPDATE room_slot_state SET {', '.join(updates)}
                WHERE room_id=%s AND team=%s AND slot=%s""",
            values,
        )
    conn.commit()
    return get_room_slot(room_id, team, slot) or {}


# ── FEAT-43 personal YAML library ────────────────────────────────


def _serialize_user_yaml(row: dict) -> dict:
    d = _serialize(row)
    d["values"] = d.pop("option_values", None)
    return d


def create_user_yaml(
    *,
    user_id: int,
    apworld_name: str,
    version: str,
    player_name: str,
    label: str,
    kind: str,
    option_values: dict | None,
    yaml_content: str | None,
) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO user_yamls
                   (user_id, apworld_name, version, player_name, label,
                    kind, option_values, yaml_content)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (user_id, apworld_name, version, player_name, label, kind,
             psycopg2.extras.Json(option_values) if option_values is not None else None,
             yaml_content),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize_user_yaml(row)


def list_user_yamls(user_id: int) -> list[dict]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM user_yamls WHERE user_id = %s ORDER BY updated_at DESC LIMIT 200",
            (user_id,),
        )
        rows = _dictrow(cur)
    return [_serialize_user_yaml(r) for r in rows]


def get_user_yaml(yaml_id: int) -> dict | None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM user_yamls WHERE id = %s", (yaml_id,))
        rows = _dictrow(cur)
    return _serialize_user_yaml(rows[0]) if rows else None


def update_user_yaml(yaml_id: int, **fields) -> dict | None:
    allowed = {"label", "player_name", "option_values", "yaml_content", "version"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_user_yaml(yaml_id)
    if "option_values" in updates and updates["option_values"] is not None:
        updates["option_values"] = psycopg2.extras.Json(updates["option_values"])
    sets = ", ".join(f"{k} = %s" for k in updates)
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE user_yamls SET {sets}, updated_at = NOW() WHERE id = %s RETURNING *",
            (*updates.values(), yaml_id),
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize_user_yaml(rows[0]) if rows else None


def delete_user_yaml(yaml_id: int) -> bool:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM user_yamls WHERE id = %s", (yaml_id,))
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted


def list_submissions_by_user(user_id: int) -> list[dict]:
    """Every YAML this account has submitted, across all rooms.

    Derived from room_yamls rather than from the library, so it works
    retroactively for everything submitted before the library existed. Room
    name and status ride along because "where is this in use" is the whole
    question the Submitted view answers.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT y.id, y.room_id, y.player_name, y.game, y.filename,
                      y.validation_status, y.validation_error, y.option_warnings,
                      y.apworld_versions, y.uploaded_at, y.source_user_yaml_id,
                      r.name AS room_name, r.status AS room_status
                 FROM room_yamls y
                 JOIN rooms r ON r.id = y.room_id
                WHERE y.submitter_user_id = %s
             ORDER BY y.uploaded_at DESC
                LIMIT 200""",
            (user_id,),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def set_yaml_option_warnings(yaml_id: int, warnings: list | None) -> None:
    """Advisory option-level findings from the submit-time schema check."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE room_yamls SET option_warnings = %s WHERE id = %s",
            (psycopg2.extras.Json(warnings) if warnings else None, yaml_id),
        )
    conn.commit()


# ── FEAT-42 community presets ────────────────────────────────────


def _serialize_preset(row: dict) -> dict:
    d = _serialize(row)
    # option_values is the storage name (VALUES is reserved in SQL); the API
    # speaks `values`, which is what the builder and the design note use.
    d["values"] = d.pop("option_values", None)
    return d


def create_preset(
    *,
    apworld_name: str,
    version: str,
    name: str,
    description: str,
    kind: str,
    option_values: dict | None,
    yaml_content: str | None,
    author_user_id: int,
    is_official: bool = False,
    status: str = "private",
) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO apworld_presets
                   (apworld_name, version, name, description, kind,
                    option_values, yaml_content, author_user_id,
                    is_official, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (apworld_name, version, name, description, kind,
             psycopg2.extras.Json(option_values) if option_values is not None else None,
             yaml_content, author_user_id, is_official, status),
        )
        row = _dictrow(cur)[0]
    conn.commit()
    return _serialize_preset(row)


def list_presets_for_apworld(apworld_name: str, viewer_user_id: int | None = None) -> list[dict]:
    """Published presets for a world, plus the viewer's own private ones.

    Order is the design's: official first, then by upvote score, then by
    usage, then newest. Ties break on newest so a fresh preset is not buried
    behind an old one with the same score forever.

    Capped at 200. A single game accumulating more than that says something
    has gone wrong (or the feature has succeeded far past what this UI was
    built for), and either way the answer is paging rather than shipping a
    thousand rows to a browser. The cap is deliberate and noted here rather
    than silent.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT p.*, u.discord_username AS author_username
                 FROM apworld_presets p
            LEFT JOIN users u ON u.id = p.author_user_id
                WHERE p.apworld_name = %s
                  AND (p.status = 'published'
                       OR (p.status = 'private' AND p.author_user_id = %s))
             ORDER BY p.is_official DESC, p.score DESC, p.uses DESC, p.created_at DESC
                LIMIT 200""",
            (apworld_name, viewer_user_id),
        )
        rows = _dictrow(cur)
    return [_serialize_preset(r) for r in rows]


def list_presets_by_author(user_id: int) -> list[dict]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM apworld_presets WHERE author_user_id = %s "
            "ORDER BY created_at DESC",
            (user_id,),
        )
        rows = _dictrow(cur)
    return [_serialize_preset(r) for r in rows]


def get_preset(preset_id: int) -> dict | None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT p.*, u.discord_username AS author_username
                 FROM apworld_presets p
            LEFT JOIN users u ON u.id = p.author_user_id
                WHERE p.id = %s""",
            (preset_id,),
        )
        rows = _dictrow(cur)
    return _serialize_preset(rows[0]) if rows else None


_PRESET_UPDATABLE = {"name", "description", "status"}


def update_preset(preset_id: int, **fields) -> dict | None:
    """Rename, re-describe, publish or unpublish. Ignores anything else, so a
    caller cannot flip is_official or rewrite the payload through this path."""
    updates = {k: v for k, v in fields.items() if k in _PRESET_UPDATABLE}
    if not updates:
        return get_preset(preset_id)
    sets = ", ".join(f"{k} = %s" for k in updates)
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE apworld_presets SET {sets}, updated_at = NOW() "
            f"WHERE id = %s RETURNING *",
            (*updates.values(), preset_id),
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize_preset(rows[0]) if rows else None


def delete_preset(preset_id: int) -> bool:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM apworld_presets WHERE id = %s", (preset_id,))
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted


def record_preset_use(preset_id: int) -> None:
    """Bump the visible usage counter. Best-effort: a lost increment is not
    worth failing a user's action over."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE apworld_presets SET uses = uses + 1 WHERE id = %s AND status != 'hidden'",
            (preset_id,),
        )
    conn.commit()


def vote_preset(preset_id: int, user_id: int) -> dict | None:
    """Toggle this user's upvote. Returns the preset with its new score.

    The votes table is the source of truth; `score` is denormalised so the
    listing can order without a join.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM apworld_preset_votes WHERE preset_id = %s AND user_id = %s",
            (preset_id, user_id),
        )
        removed = cur.rowcount > 0
        if not removed:
            cur.execute(
                "INSERT INTO apworld_preset_votes (preset_id, user_id) VALUES (%s, %s)",
                (preset_id, user_id),
            )
        cur.execute(
            """UPDATE apworld_presets
                  SET score = (SELECT COALESCE(SUM(value), 0)
                                 FROM apworld_preset_votes WHERE preset_id = %s)
                WHERE id = %s RETURNING *""",
            (preset_id, preset_id),
        )
        rows = _dictrow(cur)
    conn.commit()
    if not rows:
        return None
    out = _serialize_preset(rows[0])
    out["voted"] = not removed
    return out


def has_voted(preset_ids: list[int], user_id: int | None) -> set[int]:
    if not preset_ids or user_id is None:
        return set()
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT preset_id FROM apworld_preset_votes "
            "WHERE user_id = %s AND preset_id = ANY(%s)",
            (user_id, preset_ids),
        )
        return {r["preset_id"] for r in _dictrow(cur)}


def report_preset(preset_id: int, user_id: int) -> bool:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO apworld_preset_reports (preset_id, user_id)
               VALUES (%s, %s)
               ON CONFLICT DO NOTHING
               RETURNING preset_id""",
            (preset_id, user_id),
        )
        inserted = cur.fetchone() is not None
        if inserted:
            cur.execute(
                "UPDATE apworld_presets SET reports = reports + 1 WHERE id = %s",
                (preset_id,),
            )
    conn.commit()
    return inserted


def list_reported_presets(limit: int = 100) -> list[dict]:
    """Admin view: anything reported at least once, or recently published."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT p.*, u.discord_username AS author_username
                 FROM apworld_presets p
            LEFT JOIN users u ON u.id = p.author_user_id
                WHERE p.reports > 0 OR p.status = 'published'
             ORDER BY p.reports DESC, p.created_at DESC
                LIMIT %s""",
            (max(1, min(int(limit), 500)),),
        )
        rows = _dictrow(cur)
    return [_serialize_preset(r) for r in rows]


# ── FEAT-31 analytics events ─────────────────────────────────────
#
# Storage layer only. Every privacy rule (what may be passed in, what gets
# dropped, how objection signals are honoured) lives in analytics.py, which
# is the only module that should call insert_event directly.


def insert_event(
    kind: str,
    *,
    user_id: int | None = None,
    room_id: str | None = None,
    path: str | None = None,
    cf_country: str | None = None,
    ua_class: str | None = None,
    request_id: str | None = None,
    visit_id: str | None = None,
    props: dict | None = None,
) -> None:
    """Append one event under the shared, per-minute writer ceiling."""
    import config

    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """WITH bucket AS (
                   INSERT INTO analytics_write_buckets (minute, event_count)
                   VALUES (date_trunc('minute', NOW()), 1)
                   ON CONFLICT (minute) DO UPDATE
                       SET event_count = analytics_write_buckets.event_count + 1
                       WHERE analytics_write_buckets.event_count < %s
                   RETURNING 1
               )
               INSERT INTO events
                   (kind, user_id, room_id, path, cf_country, ua_class,
                    request_id, visit_id, props)
               SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s FROM bucket""",
            (max(1, config.ANALYTICS_EVENTS_GLOBAL_PER_MINUTE),
             kind, user_id, room_id, path, cf_country, ua_class,
             request_id, visit_id, psycopg2.extras.Json(props or {})),
        )
        cur.execute(
            "DELETE FROM analytics_write_buckets WHERE minute < NOW() - INTERVAL '2 hours'"
        )
    conn.commit()


def query_events(
    *,
    kind: str | None = None,
    since: str | None = None,
    until: str | None = None,
    room_id: str | None = None,
    user_id: int | None = None,
    visit_id: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Filtered read for the admin endpoint. Newest first, hard-capped."""
    limit = max(1, min(int(limit), 1000))
    where: list[str] = []
    params: list = []
    if kind:
        where.append("kind = %s")
        params.append(kind)
    if since:
        where.append("ts >= %s")
        params.append(since)
    if until:
        where.append("ts < %s")
        params.append(until)
    if room_id:
        where.append("room_id = %s")
        params.append(room_id)
    if user_id is not None:
        where.append("user_id = %s")
        params.append(user_id)
    if visit_id:
        where.append("visit_id = %s")
        params.append(visit_id)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM events {clause} ORDER BY ts DESC, id DESC LIMIT %s",
            (*params, limit),
        )
        rows = _dictrow(cur)
    return [_serialize(r) for r in rows]


def events_counts_by_kind(days: int = 7) -> list[dict]:
    """Event volume per kind over a trailing window."""
    days = max(1, min(int(days), 3650))
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT kind, COUNT(*) AS event_count
                 FROM events
                WHERE ts > NOW() - make_interval(days => %s)
             GROUP BY kind
             ORDER BY event_count DESC""",
            (days,),
        )
        rows = _dictrow(cur)
    return [{"kind": r["kind"], "count": int(r["event_count"])} for r in rows]


def events_funnel(days: int = 7) -> dict:
    """The four questions the design note exists to answer.

    Visit-scoped conversion uses visit_id, which only client-side events
    carry, so anonymous funnel rates are 'of visits we could observe' -
    a visitor who blocks the events endpoint or sends Sec-GPC counts in
    the server-side totals but not in the visit-scoped ones.
    """
    days = max(1, min(int(days), 3650))
    conn = _get_conn()
    out: dict = {"window_days": days}
    with conn.cursor() as cur:
        cur.execute(
            """SELECT
                   COUNT(*) FILTER (WHERE kind = 'page_view') AS page_views,
                   COUNT(DISTINCT visit_id) FILTER (WHERE visit_id IS NOT NULL) AS visits,
                   COUNT(*) FILTER (WHERE kind = 'oauth_login_started') AS login_started,
                   COUNT(*) FILTER (WHERE kind = 'oauth_callback_succeeded') AS login_succeeded,
                   COUNT(*) FILTER (WHERE kind = 'builder_opened') AS builder_opened,
                   COUNT(*) FILTER (WHERE kind = 'builder_yaml_emitted') AS builder_emitted,
                   COUNT(*) FILTER (WHERE kind = 'submit_succeeded') AS submit_succeeded,
                   COUNT(*) FILTER (WHERE kind = 'submit_rejected') AS submit_rejected,
                   COUNT(*) FILTER (WHERE kind = 'room_created') AS room_created,
                   COUNT(*) FILTER (WHERE kind = 'guide_view') AS guide_views,
                   COUNT(*) FILTER (WHERE kind = 'ctr_download') AS ctr_downloads
                 FROM events
                WHERE ts > NOW() - make_interval(days => %s)""",
            (days,),
        )
        out["totals"] = {k: int(v or 0) for k, v in _dictrow(cur)[0].items()}

        cur.execute(
            """SELECT props->>'reason_code' AS reason, COUNT(*) AS n
                 FROM events
                WHERE kind = 'submit_rejected'
                  AND ts > NOW() - make_interval(days => %s)
             GROUP BY reason ORDER BY n DESC LIMIT 15""",
            (days,),
        )
        out["rejection_reasons"] = [
            {"reason_code": r["reason"], "count": int(r["n"])} for r in _dictrow(cur)
        ]

        cur.execute(
            """SELECT props->>'game' AS game, COUNT(*) AS n
                 FROM events
                WHERE kind IN ('builder_opened', 'builder_schema_served', 'picker_pin_set')
                  AND props->>'game' IS NOT NULL
                  AND ts > NOW() - make_interval(days => %s)
             GROUP BY game ORDER BY n DESC LIMIT 20""",
            (days,),
        )
        out["top_games"] = [
            {"game": r["game"], "count": int(r["n"])} for r in _dictrow(cur)
        ]

        # Server-rendered pages: `path` is the page itself.
        cur.execute(
            """SELECT path, COUNT(*) AS n
                 FROM events
                WHERE kind IN ('guide_view', 'ctr_view')
                  AND path IS NOT NULL
                  AND ts > NOW() - make_interval(days => %s)
             GROUP BY path ORDER BY n DESC LIMIT 20""",
            (days,),
        )
        out["top_paths"] = [
            {"path": r["path"], "count": int(r["n"])} for r in _dictrow(cur)
        ]

        # SPA views arrive on the shared /api/events path by design - the
        # browser sends a coarse view name instead of the URL, so room ids
        # and query strings never reach the log. Group on that name.
        cur.execute(
            """SELECT props->>'view' AS view, COUNT(*) AS n
                 FROM events
                WHERE kind = 'page_view'
                  AND props->>'view' IS NOT NULL
                  AND ts > NOW() - make_interval(days => %s)
             GROUP BY view ORDER BY n DESC LIMIT 20""",
            (days,),
        )
        out["top_views"] = [
            {"view": r["view"], "count": int(r["n"])} for r in _dictrow(cur)
        ]

        # Journey edges. Because no identifier survives a page load, a
        # journey across documents (a guide, then the app) can only be seen
        # in aggregate: "N arrivals at X came from Y". That is what this is.
        cur.execute(
            """SELECT props->>'from_path' AS from_path,
                      kind,
                      coalesce(props->>'view', props->>'slug', props->>'page') AS landed_on,
                      COUNT(*) AS n
                 FROM events
                WHERE props->>'from_path' IS NOT NULL
                  AND ts > NOW() - make_interval(days => %s)
             GROUP BY from_path, kind, landed_on
             ORDER BY n DESC LIMIT 25""",
            (days,),
        )
        out["entry_edges"] = [
            {
                "from_path": r["from_path"],
                "kind": r["kind"],
                "landed_on": r["landed_on"],
                "count": int(r["n"]),
            }
            for r in _dictrow(cur)
        ]

        # In-app edges: view-to-view moves inside one document.
        cur.execute(
            """SELECT props->>'from_view' AS from_view,
                      props->>'view' AS to_view,
                      COUNT(*) AS n
                 FROM events
                WHERE kind = 'page_view'
                  AND props->>'from_view' IS NOT NULL
                  AND ts > NOW() - make_interval(days => %s)
             GROUP BY from_view, to_view
             ORDER BY n DESC LIMIT 25""",
            (days,),
        )
        out["view_edges"] = [
            {"from_view": r["from_view"], "to_view": r["to_view"], "count": int(r["n"])}
            for r in _dictrow(cur)
        ]
    return out


def rollup_and_prune_events(retention_days: int = 180) -> dict:
    """Fold expiring rows into events_daily, then delete them.

    Rollup runs over the WHOLE table (idempotent upsert) so a day is never
    missed if the sweeper skips a tick; the delete only touches rows past
    the retention horizon. Returns {'days_rolled': n, 'rows_pruned': n}.
    """
    retention_days = max(1, int(retention_days))
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO events_daily (day, kind, event_count)
               SELECT (ts AT TIME ZONE 'UTC')::date AS day, kind, COUNT(*)
                 FROM events
             GROUP BY day, kind
               ON CONFLICT (day, kind)
               DO UPDATE SET event_count = GREATEST(
                   events_daily.event_count, EXCLUDED.event_count)"""
        )
        days_rolled = cur.rowcount
        cur.execute(
            "DELETE FROM events WHERE ts < NOW() - make_interval(days => %s)",
            (retention_days,),
        )
        pruned = cur.rowcount
    conn.commit()
    return {"days_rolled": max(days_rolled, 0), "rows_pruned": max(pruned, 0)}


def delete_events_for_user(user_id: int) -> int:
    """Erase one user's analytics rows outright (GDPR Art. 17 request).

    Deletes rather than anonymises: a request to erase should not leave
    behind rows that are still linkable via visit_id within a session.
    Returns the number of rows removed.
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM events WHERE user_id = %s", (user_id,))
        n = cur.rowcount
    conn.commit()
    return max(n, 0)


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


def discord_id_hmac(discord_id: str) -> str:
    """Pseudonymous key for the separate room-creation denylist."""
    import hashlib
    import hmac
    import config

    return hmac.new(
        config.ABUSE_HMAC_KEY.encode("utf-8"),
        discord_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def is_discord_room_creation_blocked(discord_id: str) -> bool:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM room_creation_blocks WHERE review_after <= NOW()")
        cur.execute(
            """SELECT 1 FROM room_creation_blocks
                WHERE discord_id_hmac = %s AND review_after > NOW()""",
            (discord_id_hmac(discord_id),),
        )
        blocked = cur.fetchone() is not None
    conn.commit()
    return blocked


def prune_expired_room_creation_blocks() -> int:
    """Enforce the denylist retention ceiling even when nobody signs in."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM room_creation_blocks WHERE review_after <= NOW()")
        removed = cur.rowcount
    conn.commit()
    return removed


def create_or_update_user(discord_id: str, discord_username: str) -> dict:
    import config
    is_owner = discord_id == config.OWNER_DISCORD_ID
    blocked = is_discord_room_creation_blocked(discord_id)
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            # `xmax = 0` is the standard way to tell an upsert's INSERT from
            # its UPDATE: a freshly inserted tuple has no update transaction
            # id. Surfaced as is_new_user so the OAuth callback can record
            # first-login vs returning (FEAT-31) without a second query.
            """INSERT INTO users
                      (discord_id, discord_username, is_admin, is_approved,
                       room_creation_blocked)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (discord_id)
               DO UPDATE SET discord_username = EXCLUDED.discord_username,
                             is_admin = users.is_admin OR EXCLUDED.is_admin,
                             is_approved = users.is_approved OR EXCLUDED.is_approved,
                             room_creation_blocked = users.room_creation_blocked
                                 OR EXCLUDED.room_creation_blocked
               RETURNING *, (xmax = 0) AS is_new_user""",
            (discord_id, discord_username, is_owner, is_owner, blocked),
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


def get_user_by_discord_id(discord_id: str) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE discord_id = %s", (discord_id,))
        rows = _dictrow(cur)
    return _serialize(rows[0]) if rows else {}


def get_account_summary(user_id: int) -> dict:
    """Identity plus the exact counts shown before scheduled deletion."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT u.*,
                      (SELECT COUNT(*) FROM rooms r
                        WHERE r.host_user_id = u.id) AS rooms,
                      (SELECT COUNT(*) FROM room_yamls y
                        JOIN rooms r ON r.id = y.room_id
                       WHERE r.host_user_id = u.id) AS hosted_submissions,
                      (SELECT COUNT(*) FROM user_yamls y
                        WHERE y.user_id = u.id) AS saved_yamls,
                      (SELECT COUNT(*) FROM room_yamls y
                        WHERE y.submitter_user_id = u.id) AS submissions,
                      (SELECT COUNT(*) FROM apworld_presets p
                        WHERE p.author_user_id = u.id) AS presets,
                      (SELECT COUNT(*) FROM user_room_templates t
                        WHERE t.user_id = u.id) AS room_templates,
                      (SELECT COUNT(*) FROM apworld_index_requests q
                        WHERE q.requester_user_id = u.id) AS apworld_requests
                 FROM users u WHERE u.id = %s""",
            (user_id,),
        )
        rows = _dictrow(cur)
    if not rows:
        return {}
    row = _serialize(rows[0])
    count_keys = (
        "rooms", "hosted_submissions", "saved_yamls", "submissions",
        "presets", "room_templates", "apworld_requests",
    )
    return {
        "account": {k: v for k, v in row.items() if k not in count_keys},
        "counts": {k: int(row[k]) for k in count_keys},
    }


def create_account_deletion_token(user_id: int, token_hash: str, minutes: int = 10) -> None:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO account_deletion_tokens (user_id, token_hash, expires_at)
               VALUES (%s, %s, NOW() + make_interval(mins => %s))
               ON CONFLICT (user_id) DO UPDATE
                  SET token_hash = EXCLUDED.token_hash,
                      expires_at = EXCLUDED.expires_at,
                      created_at = NOW()""",
            (user_id, token_hash, minutes),
        )
    conn.commit()


def consume_account_deletion_reauth_limit(
    user_id: int,
    *,
    max_attempts: int = 5,
    window_minutes: int = 15,
) -> tuple[bool, int]:
    """Database-wide limit for destructive OAuth initiation.

    Returns ``(allowed, retry_after_seconds)``. Completion is separately
    bounded by the ten-minute, single-use token and the pending-account lock.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT attempts, window_started_at
                     FROM account_deletion_rate_limits
                    WHERE user_id = %s FOR UPDATE""",
                (user_id,),
            )
            row = cur.fetchone()
            now = datetime.now(timezone.utc)
            if not row:
                cur.execute(
                    """INSERT INTO account_deletion_rate_limits
                              (user_id, window_started_at, attempts)
                       VALUES (%s, NOW(), 1)""",
                    (user_id,),
                )
                conn.commit()
                return True, 0

            attempts, started_at = row
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            elapsed = (now - started_at).total_seconds()
            window_seconds = max(1, int(window_minutes)) * 60
            if elapsed >= window_seconds:
                cur.execute(
                    """UPDATE account_deletion_rate_limits
                          SET window_started_at = NOW(), attempts = 1
                        WHERE user_id = %s""",
                    (user_id,),
                )
                conn.commit()
                return True, 0
            if attempts >= max(1, int(max_attempts)):
                conn.commit()
                return False, max(1, int(window_seconds - elapsed) + 1)
            cur.execute(
                """UPDATE account_deletion_rate_limits
                      SET attempts = attempts + 1 WHERE user_id = %s""",
                (user_id,),
            )
        conn.commit()
        return True, 0
    except Exception:
        conn.rollback()
        raise


def schedule_account_deletion(
    user_id: int,
    token_hash: str,
    grace_days: int,
) -> dict:
    """Consume a reauth token and atomically schedule the reversible stage."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """DELETE FROM account_deletion_tokens
                    WHERE user_id = %s AND token_hash = %s AND expires_at > NOW()
                RETURNING user_id""",
                (user_id, token_hash),
            )
            if not cur.fetchone():
                conn.rollback()
                return {}
            cur.execute(
                """UPDATE users
                      SET deletion_requested_at = NOW(),
                          deletion_due_at = NOW() + make_interval(days => %s)
                    WHERE id = %s AND deletion_due_at IS NULL
                RETURNING *""",
                (grace_days, user_id),
            )
            rows = _dictrow(cur)
        conn.commit()
        return _serialize(rows[0]) if rows else {}
    except Exception:
        conn.rollback()
        raise


def cancel_account_deletion(user_id: int) -> dict:
    """Restore access only while the grace deadline is still in the future."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE users
                  SET deletion_requested_at = NULL, deletion_due_at = NULL
                WHERE id = %s AND deletion_due_at > NOW()
            RETURNING *""",
            (user_id,),
        )
        rows = _dictrow(cur)
    conn.commit()
    return _serialize(rows[0]) if rows else {}


def list_due_account_deletions(limit: int = 25) -> list[dict]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, deletion_due_at
                 FROM users
                WHERE deletion_due_at IS NOT NULL AND deletion_due_at <= NOW()
             ORDER BY deletion_due_at
                LIMIT %s""",
            (max(1, min(int(limit), 100)),),
        )
        rows = _dictrow(cur)
    # psycopg2 begins a transaction even for SELECT. This helper runs forever
    # on the background sweeper thread, so close the read transaction rather
    # than holding a relation lock and old snapshot until something is due.
    conn.rollback()
    return [_serialize(row) for row in rows]


def get_account_erasure_targets(user_id: int) -> dict:
    """Minimal pre-delete material needed for the off-database receipt."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id FROM users
                WHERE id = %s AND deletion_due_at IS NOT NULL
                  AND deletion_due_at <= NOW()
                FOR UPDATE""",
            (user_id,),
        )
        if not cur.fetchone():
            conn.rollback()
            return {}
        cur.execute(
            """SELECT DISTINCT owned.seed
                 FROM rooms owned
                WHERE owned.host_user_id = %s
                  AND owned.seed IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM rooms other
                       WHERE other.seed = owned.seed
                         AND other.host_user_id IS DISTINCT FROM %s
                  )""",
            (user_id, user_id),
        )
        seeds = sorted({row[0] for row in cur.fetchall() if row[0]})
    conn.rollback()
    return {"user_id": user_id, "seeds": seeds}


def export_account_data(user_id: int) -> dict:
    """Return only this account's identity/content; never other players' YAMLs."""
    conn = _get_conn()

    def query(cur, sql: str, args: tuple) -> list[dict]:
        cur.execute(sql, args)
        return [_serialize(row) for row in _dictrow(cur)]

    with conn.cursor() as cur:
        account = query(cur, "SELECT * FROM users WHERE id = %s", (user_id,))
        if not account:
            return {}
        discord_id = account[0]["discord_id"]
        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "account": account[0],
            "hosted_rooms": query(
                cur, "SELECT * FROM rooms WHERE host_user_id = %s ORDER BY created_at", (user_id,)
            ),
            "saved_yamls": query(
                cur, "SELECT * FROM user_yamls WHERE user_id = %s ORDER BY created_at", (user_id,)
            ),
            "submissions": query(
                cur,
                "SELECT * FROM room_yamls WHERE submitter_user_id = %s ORDER BY uploaded_at",
                (user_id,),
            ),
            "presets": query(
                cur,
                "SELECT * FROM apworld_presets WHERE author_user_id = %s ORDER BY created_at",
                (user_id,),
            ),
            "room_templates": query(
                cur,
                "SELECT * FROM user_room_templates WHERE user_id = %s ORDER BY created_at",
                (user_id,),
            ),
            "apworld_requests": query(
                cur,
                "SELECT * FROM apworld_index_requests WHERE requester_user_id = %s ORDER BY created_at",
                (user_id,),
            ),
            "maintainer_grants": query(
                cur,
                "SELECT * FROM apworld_maintainers WHERE discord_user_id = %s ORDER BY granted_at",
                (discord_id,),
            ),
            "analytics_events": query(
                cur, "SELECT * FROM events WHERE user_id = %s ORDER BY ts", (user_id,)
            ),
            "room_activity": query(
                cur,
                "SELECT * FROM room_activity WHERE actor_user_id = %s ORDER BY created_at",
                (user_id,),
            ),
            "deletion_security": query(
                cur,
                "SELECT window_started_at, attempts "
                "FROM account_deletion_rate_limits WHERE user_id = %s",
                (user_id,),
            ),
        }


def permanently_delete_account(user_id: int, *, receipt_replay: bool = False) -> dict:
    """Irreversibly erase one account's live database graph in one transaction.

    Normal callers may only purge an expired scheduled deletion. A durable
    erasure receipt may set receipt_replay=True after a backup restore, where
    the restored user row can predate the schedule columns entirely.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            if receipt_replay:
                cur.execute("SELECT * FROM users WHERE id = %s FOR UPDATE", (user_id,))
            else:
                cur.execute(
                    """SELECT * FROM users
                        WHERE id = %s AND deletion_due_at <= NOW()
                        FOR UPDATE""",
                    (user_id,),
                )
            user_rows = _dictrow(cur)
            if not user_rows:
                conn.rollback()
                return {"user_id": user_id, "already_absent": True, "seeds": []}
            user = user_rows[0]
            cur.execute(
                "SELECT id, seed FROM rooms WHERE host_user_id = %s FOR UPDATE",
                (user_id,),
            )
            owned_rooms = _dictrow(cur)
            room_ids = [row["id"] for row in owned_rooms]
            seeds = sorted({row["seed"] for row in owned_rooms if row.get("seed")})

            cur.execute(
                "SELECT id, player_name FROM room_yamls WHERE submitter_user_id = %s",
                (user_id,),
            )
            submitted = _dictrow(cur)
            yaml_ids = [row["id"] for row in submitted]

            if user.get("room_creation_blocked"):
                cur.execute(
                    """INSERT INTO room_creation_blocks (discord_id_hmac)
                       VALUES (%s) ON CONFLICT (discord_id_hmac) DO NOTHING""",
                    (discord_id_hmac(user["discord_id"]),),
                )

            if room_ids:
                cur.execute(
                    "DELETE FROM events WHERE user_id = %s OR room_id = ANY(%s)",
                    (user_id, room_ids),
                )
            else:
                cur.execute("DELETE FROM events WHERE user_id = %s", (user_id,))

            if yaml_ids:
                cur.execute(
                    """DELETE FROM room_activity
                        WHERE actor_user_id = %s OR subject_yaml_id = ANY(%s)""",
                    (user_id, yaml_ids),
                )
            else:
                cur.execute("DELETE FROM room_activity WHERE actor_user_id = %s", (user_id,))

            # Legacy activity predates structured actor/subject ids. Delete
            # only user-action event kinds whose message contains a known name.
            legacy_names = {
                user.get("discord_username"),
                *(row.get("player_name") for row in submitted),
            }
            legacy_names = [
                value.strip() for value in legacy_names
                if isinstance(value, str) and len(value.strip()) >= 3
            ]
            if legacy_names:
                cur.execute(
                    """DELETE FROM room_activity
                        WHERE actor_user_id IS NULL
                          AND event_type IN (
                              'yaml_submitted', 'yaml_submitted_invalid',
                              'yaml_uploaded', 'yaml_preloaded', 'yaml_created',
                              'yaml_invalid', 'yaml_updated', 'yaml_deleted',
                              'yaml_claimed', 'yaml_released'
                          )
                          AND EXISTS (
                              SELECT 1 FROM unnest(%s::text[]) AS legacy_name
                               WHERE position(lower(legacy_name) in lower(message)) > 0
                          )""",
                    (legacy_names,),
                )

            cur.execute(
                "DELETE FROM apworld_index_requests WHERE requester_user_id = %s",
                (user_id,),
            )
            cur.execute(
                "DELETE FROM apworld_maintainers WHERE discord_user_id = %s",
                (user["discord_id"],),
            )
            cur.execute(
                "DELETE FROM apworld_presets WHERE author_user_id = %s",
                (user_id,),
            )
            cur.execute(
                "DELETE FROM room_yamls WHERE submitter_user_id = %s",
                (user_id,),
            )
            cur.execute("DELETE FROM rooms WHERE host_user_id = %s", (user_id,))
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return {
            "user_id": user_id,
            "already_absent": False,
            "rooms_deleted": len(room_ids),
            "submissions_deleted": len(yaml_ids),
            "seeds": seeds,
        }
    except Exception:
        conn.rollback()
        raise


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


def set_user_room_creation_blocked(user_id: int, blocked: bool) -> dict:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET room_creation_blocked = %s WHERE id = %s RETURNING *",
            (blocked, user_id),
        )
        rows = _dictrow(cur)
        if rows and not blocked:
            cur.execute(
                "DELETE FROM room_creation_blocks WHERE discord_id_hmac = %s",
                (discord_id_hmac(rows[0]["discord_id"]),),
            )
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
