"""Pure rules for the CTR custom-track name registry. No database, no Flask.

Everything that decides identity lives here so it can be tested without a
server: block ids, the frozen-field rules, the title clash suffixes, the
submission caps and the sliding-window rate limit.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from collections import defaultdict, deque
from typing import Iterable, Mapping, Optional

# ── Id scheme (ruled 2026-10-13) ─────────────────────────────────
# location = LOCATION_BASE + block_index * LOCATIONS_PER_TRACK + offset
# item     = ITEM_BASE     + block_index * ITEMS_PER_TRACK     + offset
LOCATION_BASE = 35_200_000
ITEM_BASE = 35_100_000
LOCATIONS_PER_TRACK = 200
ITEMS_PER_TRACK = 5
MAX_BLOCKS = 10_000  # block_index 0..9999

SCHEMA_VERSION = 1  # of the published registry document and the read API

# ── States ───────────────────────────────────────────────────────
CANDIDATE = "candidate"
APPROVED = "approved"
NAMED = "named"
WITHDRAWN = "withdrawn"
SOURCE_UNAVAILABLE = "source-unavailable"
STATES = (CANDIDATE, APPROVED, NAMED, WITHDRAWN, SOURCE_UNAVAILABLE)
#: Shown by the picker and the manager.
PUBLIC_STATES = (APPROVED, NAMED)
#: Written to the registry repository: everything that ever got a track_key,
#: because the repository is the record and withdrawn blocks stay frozen.
RECORD_STATES = (APPROVED, NAMED, WITHDRAWN, SOURCE_UNAVAILABLE)

_TRANSITIONS = {
    CANDIDATE: {APPROVED, WITHDRAWN, SOURCE_UNAVAILABLE},
    APPROVED: {NAMED, WITHDRAWN, SOURCE_UNAVAILABLE},
    NAMED: {WITHDRAWN, SOURCE_UNAVAILABLE},
    WITHDRAWN: {CANDIDATE, APPROVED, NAMED},
    SOURCE_UNAVAILABLE: {CANDIDATE, APPROVED, NAMED, WITHDRAWN},
}

SUBMISSION_KINDS = ("new_track", "new_revision", "correction")
HASH_STATES = ("pending", "claimed", "verified")

# ── Caps ─────────────────────────────────────────────────────────
TITLE_MAX_CHARS = 40  # matches the apworld's title sanitizer
TITLE_MAX_BYTES = 60
AUTHOR_MAX_CHARS = 24
AUTHOR_MAX_BYTES = 30
ROOM_TITLE_MAX_BYTES = 105
CREDIT_NAME_MAX = 48
CREDITS_MAX = 8
CREDIT_ROLES = ("track", "music", "ap_boxes", "other")
LINKS_MAX = 5
LINK_MAX_CHARS = 300
NOTE_MAX_CHARS = 300
REVISION_MAX_CHARS = 32
DESCRIPTOR_MAX_BYTES = 16 * 1024
DESCRIPTOR_STRING_MAX = 2000
DESCRIPTOR_DEPTH_MAX = 6
SUBMISSIONS_PER_USER_PER_HOUR = 5
PENDING_PER_USER_MAX = 10
REPORTS_PER_USER_PER_HOUR = 20
REPORT_REASON_MAX = 200
LINK_KINDS = ("creator", "saphi", "source", "other")

#: track_key values that would shadow a static route under /api/ctr/tracks/.
RESERVED_KEYS = frozenset({"submissions", "publication", "mine", "report", "revisions"})

#: Stems a custom title must not reuse (retail tracks, cups, garages, Wumpa).
#: A copy of the apworld's registered location stems; refresh it from the
#: apworld at the minting step. A title equal to one of these gets "(Custom)".
RETAIL_STEMS = frozenset(s.casefold() for s in (
    "Blizzard Bluff", "Blue Gem Cup", "Coco Park", "Cortex Castle", "Crash Cove",
    "Dingo Canyon", "Dragon Mines", "Green Gem Cup", "Hot Air Skyway",
    "Komodo Joe Garage", "Mystery Caves", "N. Gin Labs", "N. Oxide Garage",
    "Nitro Court", "Oxide Station", "Papu Papu Garage", "Papu's Pyramid",
    "Pinstripe Garage", "Polar Pass", "Purple Gem Cup", "Rampage Ruins",
    "Red Gem Cup", "Ripper Roo Garage", "Rocky Road", "Roo's Tubes",
    "Sewer Speedway", "Skull Rock", "Slide Coliseum", "Tiger Temple",
    "Tiny Arena", "Turbo Track", "Yellow Gem Cup", "Wumpa",
))

_GENERIC = re.compile(r"custom track \d+")
_BRACKETS = str.maketrans({"[": "(", "]": ")", "{": "(", "}": ")"})
_HEX64 = re.compile(r"[0-9a-f]{64}")
_KEY_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class RuleError(ValueError):
    """A rule was broken. `code` is stable for API callers; str() is for people."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# ── Ids ──────────────────────────────────────────────────────────

def check_block_index(index: int) -> int:
    if type(index) is not int or not 0 <= index < MAX_BLOCKS:
        raise RuleError("block_range", f"block_index must be 0 to {MAX_BLOCKS - 1}")
    return index


def location_code(block_index: int, offset: int) -> int:
    check_block_index(block_index)
    if type(offset) is not int or not 0 <= offset < LOCATIONS_PER_TRACK:
        raise RuleError("offset_range", f"location offset must be 0 to {LOCATIONS_PER_TRACK - 1}")
    return LOCATION_BASE + block_index * LOCATIONS_PER_TRACK + offset


def item_code(block_index: int, offset: int) -> int:
    check_block_index(block_index)
    if type(offset) is not int or not 0 <= offset < ITEMS_PER_TRACK:
        raise RuleError("offset_range", f"item offset must be 0 to {ITEMS_PER_TRACK - 1}")
    return ITEM_BASE + block_index * ITEMS_PER_TRACK + offset


def id_ranges() -> dict:
    return {
        "locations": {"first": LOCATION_BASE,
                      "last": LOCATION_BASE + MAX_BLOCKS * LOCATIONS_PER_TRACK - 1,
                      "per_track": LOCATIONS_PER_TRACK},
        "items": {"first": ITEM_BASE,
                  "last": ITEM_BASE + MAX_BLOCKS * ITEMS_PER_TRACK - 1,
                  "per_track": ITEMS_PER_TRACK},
        "max_blocks": MAX_BLOCKS,
    }


def next_block_index(used: Iterable[int]) -> int:
    """The next block_index: one past the highest ever used. Indexes are never
    reused, so gaps stay gaps, and withdrawn entries keep theirs."""
    highest = max(used, default=-1)
    nxt = highest + 1
    if nxt >= MAX_BLOCKS:
        raise RuleError("blocks_exhausted", "All 10,000 named blocks are used")
    return nxt


# ── Titles and clash suffixes ────────────────────────────────────

def sanitize_title(raw, max_chars: int = TITLE_MAX_CHARS,
                   max_bytes: int = TITLE_MAX_BYTES) -> Optional[str]:
    """Clean community text into a safe title, or None when nothing is left.

    Same steps as the apworld's sanitizer: NFC, no control or format
    characters, brackets turned round (Universal Tracker renders Kivy
    markup), whitespace collapsed, character and byte caps.
    """
    if not isinstance(raw, str):
        return None
    text = unicodedata.normalize("NFC", raw).translate(_BRACKETS)
    kept = []
    for ch in text:
        category = unicodedata.category(ch)
        if ch.isspace() or category.startswith("Z"):
            kept.append(" ")
        elif not category.startswith("C"):
            kept.append(ch)
    text = " ".join("".join(kept).split()).strip(" :")
    text = text[:max_chars]
    while len(text.encode("utf-8")) > max_bytes:
        text = text[:-1]
    text = text.rstrip(" :")
    return text or None


def ap_name_for(title, author=None, *, taken: Iterable[str] = (),
                reserved: Optional[Iterable[str]] = None) -> str:
    """The frozen datapackage name for a promoted track.

    A title equal to a retail stem (or `Custom Track N`) gets "(Custom)". A
    result another named track already uses gets the author:
    "Crash Cove (Custom, Author)", then a number if that is taken too. Names
    already taken keep their place; the later track gets the suffix. Compares
    casefolded, like the apworld.
    """
    base = sanitize_title(title)
    if base is None:
        raise RuleError("empty_title", "A track needs a usable title")
    reserved_set = RETAIL_STEMS if reserved is None else {r.casefold() for r in reserved}
    taken_set = {t.casefold() for t in taken}
    candidate = base
    if base.casefold() in reserved_set or _GENERIC.fullmatch(base.casefold()):
        candidate = f"{base} (Custom)"
    if candidate.casefold() in taken_set:
        who = sanitize_title(author, AUTHOR_MAX_CHARS, AUTHOR_MAX_BYTES) or "Unknown"
        candidate = f"{base} (Custom, {who})"
        number = 2
        while candidate.casefold() in taken_set:
            candidate = f"{base} (Custom, {who} {number})"
            number += 1
    if len(candidate.encode("utf-8")) > ROOM_TITLE_MAX_BYTES:
        raise RuleError("name_too_long", "That name is too long once suffixes are added")
    return candidate


def slugify_key(title: str, taken: Iterable[str] = ()) -> str:
    """ASCII track_key from a title. Never reuses a key in `taken` (which must
    include withdrawn entries) and never returns a reserved route word."""
    text = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48].strip("-") or "track"
    used = set(taken) | RESERVED_KEYS
    key, n = text, 2
    while key in used:
        key = f"{text}-{n}"
        n += 1
    return key


def valid_key(key: object) -> bool:
    return isinstance(key, str) and len(key) <= 60 and bool(_KEY_RE.fullmatch(key))


# ── Freeze rules ─────────────────────────────────────────────────

def freeze_violations(old: Mapping, new: Mapping) -> list[str]:
    """Which frozen fields an update would change.

    Identity is `track_key` once set, `block_index` once set, `ap_name` once
    shipped, and `shipped_in` once set. Presentation (title, credits, links,
    provenance) is never frozen. A name may still be corrected between
    promotion and the first release that ships it.
    """
    problems = []
    if old.get("track_key") is not None and new.get("track_key") != old["track_key"]:
        problems.append("track_key")
    if old.get("block_index") is not None and new.get("block_index") != old["block_index"]:
        problems.append("block_index")
    if old.get("shipped_in") is not None:
        if new.get("shipped_in") != old["shipped_in"]:
            problems.append("shipped_in")
        if new.get("ap_name") != old.get("ap_name"):
            problems.append("ap_name")
    return problems


def revision_violations(old: Mapping, new: Mapping) -> list[str]:
    """A revision's hashes never change; content_id may be filled in once."""
    problems = []
    if old.get("content_id") is not None and new.get("content_id") != old["content_id"]:
        problems.append("content_id")
    if old.get("hash_state") == "verified":
        if new.get("files") != old.get("files"):
            problems.append("files")
        if new.get("hash_state") != "verified":
            problems.append("hash_state")
    return problems


def can_transition(old: str, new: str) -> bool:
    return new in _TRANSITIONS.get(old, set())


def restored_state(entry: Mapping) -> str:
    """Where a withdrawn or source-unavailable entry returns to."""
    if entry.get("block_index") is not None:
        return NAMED
    if entry.get("track_key") is not None:
        return APPROVED
    return CANDIDATE


# ── Version compare (apworld filter) ─────────────────────────────

def parse_version(text: object) -> Optional[tuple]:
    if not isinstance(text, str):
        return None
    m = re.match(r"^v?(\d+(?:\.\d+){0,3})", text.strip())
    if not m:
        return None
    parts = [int(p) for p in m.group(1).split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def revision_compatible(rev: Mapping, apworld: Optional[str]) -> bool:
    """A revision with no apworld range fits every apworld. An unparseable
    request version filters nothing, matching how the picker treats a YAML
    with no pinned version."""
    want = parse_version(apworld)
    if want is None:
        return True
    lo, hi = parse_version(rev.get("apworld_min")), parse_version(rev.get("apworld_max"))
    if lo is not None and want < lo:
        return False
    if hi is not None and want > hi:
        return False
    return True


# ── Validation of submitted text ─────────────────────────────────

def clean_title(raw, *, strict: bool = True) -> str:
    """A submitted display title. Strict mode refuses a title longer than the
    cap rather than silently cutting it; importers pass strict=False."""
    if not isinstance(raw, str) or not raw.strip():
        raise RuleError("title_required", "A track needs a title")
    if strict and len(raw.strip()) > TITLE_MAX_CHARS:
        raise RuleError("title_too_long", f"Titles are at most {TITLE_MAX_CHARS} characters")
    title = sanitize_title(raw)
    if title is None:
        raise RuleError("title_required", "A track needs a usable title")
    return title


def clean_credits(raw, *, strict: bool = True) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise RuleError("credits_shape", "Credits must be a list")
    if len(raw) > CREDITS_MAX:
        if strict:
            raise RuleError("credits_too_many", f"At most {CREDITS_MAX} credits")
        raw = raw[:CREDITS_MAX]
    out = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise RuleError("credits_shape", "Each credit needs a name and a role")
        name = item.get("name")
        role = item.get("role", "track")
        if role not in CREDIT_ROLES:
            raise RuleError("credit_role", f"Credit role must be one of {', '.join(CREDIT_ROLES)}")
        if isinstance(name, str) and strict and len(name.strip()) > CREDIT_NAME_MAX:
            raise RuleError("credit_too_long", f"Credit names are at most {CREDIT_NAME_MAX} characters")
        cleaned = sanitize_title(name, CREDIT_NAME_MAX, CREDIT_NAME_MAX * 4)
        if cleaned is None:
            raise RuleError("credit_name", "A credit needs a name")
        out.append({"name": cleaned, "role": role})
    return out


def clean_links(raw) -> dict:
    """Locators only: https URLs, no credentials, a closed set of kinds."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise RuleError("links_shape", "Links must be an object")
    if len(raw) > LINKS_MAX:
        raise RuleError("links_too_many", f"At most {LINKS_MAX} links")
    out = {}
    for kind, url in raw.items():
        if kind not in LINK_KINDS:
            raise RuleError("link_kind", f"Link kind must be one of {', '.join(LINK_KINDS)}")
        if not isinstance(url, str) or len(url) > LINK_MAX_CHARS:
            raise RuleError("link_url", f"Links are at most {LINK_MAX_CHARS} characters")
        if not url.startswith("https://") or any(c.isspace() or ord(c) < 32 for c in url):
            raise RuleError("link_url", "Links must be plain https URLs")
        host = url[len("https://"):].split("/", 1)[0]
        if not host or "@" in host:
            raise RuleError("link_url", "Links must be plain https URLs")
        out[kind] = url
    return out


def clean_note(raw) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, str) or len(raw) > NOTE_MAX_CHARS:
        raise RuleError("note_too_long", f"Notes are at most {NOTE_MAX_CHARS} characters")
    return " ".join(raw.split())


def _descriptor_walk(value, depth: int = 0) -> None:
    if depth > DESCRIPTOR_DEPTH_MAX:
        raise RuleError("descriptor_depth", "That descriptor is nested too deeply")
    if isinstance(value, Mapping):
        for k, v in value.items():
            if not isinstance(k, str) or len(k) > 100:
                raise RuleError("descriptor_shape", "Descriptor keys must be short strings")
            _descriptor_walk(v, depth + 1)
    elif isinstance(value, list):
        if len(value) > 200:
            raise RuleError("descriptor_shape", "Descriptor lists are too long")
        for v in value:
            _descriptor_walk(v, depth + 1)
    elif isinstance(value, str):
        if len(value) > DESCRIPTOR_STRING_MAX:
            raise RuleError("descriptor_shape", "A descriptor value is too long")
    elif not (value is None or isinstance(value, (bool, int, float))):
        raise RuleError("descriptor_shape", "Descriptors are plain JSON")


def clean_descriptor(raw) -> dict:
    """Shape-check a descriptor exported by the in-game manager.

    The registry stores it verbatim for the picker. Hashes it claims are kept
    as `claimed` until the Atlas verifier confirms them; any `modes` it
    carries are ignored because modes come from the verifier, not a submitter.
    """
    import json
    if not isinstance(raw, Mapping):
        raise RuleError("descriptor_shape", "A descriptor must be a JSON object")
    try:
        size = len(json.dumps(raw, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):
        raise RuleError("descriptor_shape", "Descriptors are plain JSON") from None
    if size > DESCRIPTOR_MAX_BYTES:
        raise RuleError("descriptor_size", "That descriptor is too large")
    _descriptor_walk(raw)
    content_id = raw.get("content_id")
    if content_id is not None and not (isinstance(content_id, str) and _HEX64.fullmatch(content_id)):
        raise RuleError("descriptor_content_id", "content_id must be 64 lowercase hex characters")
    files = raw.get("files")
    if files is not None:
        if not isinstance(files, Mapping) or len(files) > 8:
            raise RuleError("descriptor_files", "files must be an object of at most 8 roles")
        for role, info in files.items():
            sha = info.get("sha256") if isinstance(info, Mapping) else None
            if not isinstance(sha, str) or not _HEX64.fullmatch(sha):
                raise RuleError("descriptor_files", f"files.{role}.sha256 must be 64 lowercase hex characters")
    return dict(raw)


def revision_fields(descriptor: Mapping, revision: Optional[str] = None) -> dict:
    """Pull the identity fields out of a cleaned descriptor."""
    rev = revision if revision is not None else descriptor.get("revision")
    if not isinstance(rev, str) or not rev.strip() or len(rev.strip()) > REVISION_MAX_CHARS:
        raise RuleError("revision_required", f"A revision label of at most {REVISION_MAX_CHARS} characters is required")
    files = {}
    for role, info in (descriptor.get("files") or {}).items():
        size = info.get("size")
        files[role] = {"sha256": info["sha256"],
                       **({"size": size} if type(size) is int and size >= 0 else {})}
    content_id = descriptor.get("content_id")
    return {
        "revision": rev.strip(),
        "content_id": content_id,
        "files": files,
        "descriptor_schema": descriptor.get("schema_version") if type(descriptor.get("schema_version")) is int else None,
        "hash_state": "claimed" if content_id else "pending",
    }


# ── Rate limiting ────────────────────────────────────────────────

class SlidingWindowLimiter:
    """Per-key sliding window, in process. Same shape as the presets limiter;
    each gunicorn worker keeps its own window, so the DB-backed pending cap is
    the hard ceiling and this is the courtesy limit."""

    def __init__(self, limit: int, window_seconds: float = 3600.0, clock=time.time):
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._buckets: dict = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key) -> bool:
        now = self._clock()
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
