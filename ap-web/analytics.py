"""FEAT-31: cookieless, server-side product analytics.

Every privacy rule for the events log lives in this module. `db.insert_event`
is the storage layer and should not be called from anywhere else.

What this records
-----------------
Outcomes at the Flask layer that Cloudflare Web Analytics structurally cannot
see: why a YAML submission was rejected, whether an OAuth round-trip finished,
which games people open the YAML builder for, whether a guide reader goes on
to download anything. Server-rendered pages record themselves; the
client-postable kinds cover what only the browser knows (which SPA view is on
screen, how far someone got inside the builder modal, and the operational
signals of the Pokepelago SPA at pokepelago.ap-pie.com, which is static and
posts its events here).

What it never records
---------------------
- **No IP address.** The client IP is read for the per-IP rate-limit bucket on
  POST /api/events and for nothing else; it is never passed to the recorder
  and never reaches Postgres. Only `cf_country`, the two-letter country code
  Cloudflare supplies, is stored.
- **No User-Agent string.** Only a coarse class: desktop / mobile / bot,
  unknown, or synthetic when a secret verification header matches.
- **No cookie, no localStorage, no sessionStorage, no fingerprint.** The
  `visit_id` is a random value created in the page's JavaScript memory and
  passed along with client events; it is never written to the device and does
  not survive a reload, so it cannot link two visits or two devices.
- **No free-form content.** Props are validated against a per-kind allowlist
  below; unknown keys are dropped, strings are length-capped. Usernames,
  e-mail addresses, YAML contents and validator prose never enter an event.

GDPR posture
------------
- **Lawful basis:** legitimate interest, Art. 6(1)(f) - understanding how the
  site's own funnel performs, with minimised data and no third-party sharing.
  The balancing test is recorded in the vault design note.
- **Objection, Art. 21:** a request carrying `Sec-GPC: 1` or `DNT: 1` is
  recorded with `user_id` and `visit_id` forced to NULL, which reduces the
  event to an unlinkable counter. That is honoured on server-side events too,
  not just on the client endpoint.
- **Storage limitation, Art. 5(1)(e):** raw rows are pruned past
  `ANALYTICS_RETENTION_DAYS`; Builder rows with attempt ids expire after
  `ANALYTICS_ATTEMPT_RETENTION_DAYS`. The surviving daily rollups are counts
  only and relate to no identifiable person.
- **Erasure, Art. 17:** `db.delete_events_for_user` removes a logged-in
  user's rows outright. The public /privacy page documents how to ask.
- **Transparency, Art. 13:** the /privacy page describes this module in plain
  language. If a new kind or prop is added here, that page is part of the
  change, not a follow-up.

Failure posture
---------------
Recording is best-effort and asynchronous: events go onto a bounded in-memory
queue and a daemon thread writes them. A full queue drops the event, and a
database problem can never slow down or break a user's request. `record_event`
does not raise, ever.
"""

from __future__ import annotations

import queue
import secrets
import threading
import hmac
from typing import Any

import config

# ── Event taxonomy ───────────────────────────────────────────────
#
# `props` maps a prop name to its accepted type. `client` marks the kinds the
# public POST /api/events endpoint will accept; everything else is
# server-recorded only and is rejected if a browser tries to post it.
#
# Adding a kind means adding it here AND describing it on the /privacy page.

_STR = "str"
_INT = "int"
_BOOL = "bool"
_STR_LIST = "str_list"
_ATTEMPT_ID = "attempt_id"


def _enum(*values: str) -> frozenset[str]:
    return frozenset(values)

KIND_SPECS: dict[str, dict[str, Any]] = {
    # ── Client-postable: what only the browser can see ──
    # from_path is a same-origin bare path; entry_channel is a locally derived
    # coarse category for external/direct arrivals. The external hostname and
    # URL never reach the server. from_view is the previous coarse SPA view.
    "page_view": {
        "client": True,
        "props": {
            "view": _STR,
            "from_path": _STR,
            "from_view": _STR,
            "entry_channel": _enum(
                "direct", "internal", "search", "social", "community",
                "other_external", "unknown",
            ),
        },
    },
    "builder_opened": {
        "client": True,
        "props": {"game": _STR, "version": _STR, "surface": _STR, "attempt_id": _ATTEMPT_ID},
    },
    "builder_stage_reached": {
        "client": True,
        "props": {"game": _STR, "version": _STR,
                  "stage": _enum("preset", "options", "review"),
                  "attempt_id": _ATTEMPT_ID},
    },
    # `edited` marks a YAML that was hand-edited in the review step rather
    # than produced by the form alone. It is the demand signal for what the
    # form does not cover yet (weights, item links, plando, triggers).
    "builder_yaml_emitted": {
        "client": True,
        "props": {"game": _STR, "version": _STR,
                  "action": _enum("download", "submit", "add_to_room", "create_room"),
                  "edited": _BOOL, "attempt_id": _ATTEMPT_ID},
    },
    "builder_abandoned": {
        "client": True,
        "props": {"game": _STR, "version": _STR,
                  "stage": _enum("preset", "options", "review"),
                  "reason": _enum("page_closed", "navigated_away", "version_changed", "game_changed"),
                  "attempt_id": _ATTEMPT_ID},
    },
    "builder_failed": {
        "client": True,
        "props": {"game": _STR, "version": _STR,
                  "stage": _enum("preset", "options", "review"),
                  "reason": _enum("schema_load_failed", "schema_unsupported", "validation_blocked",
                                  "download_failed", "submit_failed"),
                  "attempt_id": _ATTEMPT_ID},
    },
    "builder_cta": {
        "client": True,
        "props": {"action": _enum("impression", "activation"), "surface": _STR},
    },
    "apworld_download_clicked": {
        "client": True,
        "props": {"name": _STR, "version": _STR, "surface": _STR},
    },

    # ── Pokepelago client (pokepelago.ap-pie.com) ──
    # Posted cross-site by the static Pokepelago SPA, which has no backend of
    # its own. These are operational signals only - no guesses, no gameplay
    # telemetry, no slot names, no server hostnames; props are canonical short
    # codes. `anonymous: True` strips the account id even when an apie_session
    # cookie rides along on the same-site request: playing Pokepelago is not
    # an action on this site, so it is never linked to an account.
    "pokepelago_connect_result": {
        "client": True,
        "anonymous": True,
        "props": {"outcome": _STR, "reason": _STR, "apworld_version": _STR},
    },
    "pokepelago_goal_reached": {
        "client": True,
        "anonymous": True,
        "props": {"goal_count": _INT},
    },
    # Emitted when the sprite diagnostic banner is shown (many sprite loads
    # failing while online, usually a content blocker). `layer` names the
    # sprite source layer that failed.
    "pokepelago_sprite_block_detected": {
        "client": True,
        "anonymous": True,
        "props": {"failures": _INT, "layer": _STR},
    },

    # ── Auth funnel ──
    "oauth_login_started": {"client": False, "props": {"next_path": _STR}},
    "oauth_callback_succeeded": {"client": False, "props": {"first_login": _BOOL}},
    "oauth_callback_failed": {"client": False, "props": {"reason": _STR}},

    # ── Submit funnel ──
    "submit_attempted": {
        "client": False,
        "props": {"has_session": _BOOL, "content_bytes": _INT},
    },
    "submit_succeeded": {"client": False, "props": {"game": _STR, "has_session": _BOOL}},
    "submit_rejected": {
        "client": False,
        "props": {"reason_code": _STR, "has_session": _BOOL},
    },
    "submit_rate_limited": {"client": False, "props": {"has_session": _BOOL}},

    # ── Rooms ──
    "room_public_view": {"client": False, "props": {"has_session": _BOOL}},
    "room_created": {"client": False, "props": {}},
    "room_settings_changed": {"client": False, "props": {"fields": _STR_LIST}},
    "claim_attempted": {"client": False, "props": {}},
    "claim_succeeded": {"client": False, "props": {}},
    "claim_raced": {"client": False, "props": {}},

    # ── APWorld index + builder ──
    "picker_pin_set": {
        "client": False,
        "props": {"game": _STR, "version": _STR, "in_index": _BOOL},
    },
    "apworld_downloaded": {
        "client": False,
        "props": {"name": _STR, "version": _STR, "via": _STR},
    },
    # FEAT-42 presets. `preset_applied` versus `builder_yaml_emitted` is the
    # measure that matters: does starting from someone else's configuration
    # make people more likely to finish a YAML at all.
    "preset_applied": {
        "client": False,
        "props": {"game": _STR, "version": _STR, "kind": _STR, "official": _BOOL},
    },
    "preset_published": {
        "client": False,
        "props": {"game": _STR, "version": _STR, "kind": _STR},
    },
    "preset_reported": {"client": False, "props": {}},

    "builder_schema_served": {
        "client": False,
        "props": {"game": _STR, "version": _STR, "cache": _STR, "derivable": _BOOL},
    },

    # ── Server-rendered content ──
    # `from_path` on these is what makes the guides-to-app journey visible:
    # the server-rendered pages are separate documents, so no client-side
    # value can span them.
    "guide_view": {"client": False, "props": {"slug": _STR, "from_path": _STR}},
    "ctr_view": {"client": False, "props": {"page": _STR, "from_path": _STR}},
    "ctr_download": {
        "client": False,
        "props": {"asset": _STR, "version": _STR, "from_path": _STR},
    },
    "machine_index_view": {"client": False, "props": {"surface": _STR}},

    # ── Security signals ──
    "admin_403": {"client": False, "props": {}},
    "auth_403": {"client": False, "props": {}},
}

CLIENT_KINDS = frozenset(k for k, spec in KIND_SPECS.items() if spec["client"])

# Kinds that must never carry an account id, even when the poster is signed
# in to ap-pie.com (the Pokepelago kinds - see their section above).
ANONYMOUS_KINDS = frozenset(
    k for k, spec in KIND_SPECS.items() if spec.get("anonymous")
)

# Props are metadata, never content. 120 characters is longer than any game
# name, version string, or reason code we emit, and short enough that a
# malformed caller cannot smuggle a YAML fragment into the table.
_MAX_STR = 120
_MAX_LIST = 25

# Bounded queue: at this traffic it never fills, and if it ever does the
# right answer is to drop analytics rather than slow the site down.
_QUEUE_MAX = 2000
_queue: queue.Queue[dict] = queue.Queue(maxsize=_QUEUE_MAX)
_writer_started = threading.Event()
_writer_lock = threading.Lock()
_dropped = 0
_dropped_lock = threading.Lock()

_logger = None


def _log(msg: str) -> None:
    if _logger is not None:
        try:
            _logger.warning(msg)
        except Exception:
            pass


def set_logger(logger) -> None:
    """Attach the Flask app logger (called once from create_app)."""
    global _logger
    _logger = logger


# ── Request-context extraction ───────────────────────────────────


def new_request_id() -> str:
    """Short correlation id, set per request in app.py's before_request."""
    return secrets.token_hex(8)


def _ua_class(ua: str) -> str:
    """Bucket a User-Agent into desktop / mobile / bot. The string itself is
    read here and discarded; only the bucket is ever stored."""
    if not ua:
        return "unknown"
    low = ua.lower()
    for marker in ("bot", "crawler", "spider", "slurp", "curl", "wget",
                   "python-requests", "headless", "monitor", "preview"):
        if marker in low:
            return "bot"
    for marker in ("android", "iphone", "ipad", "ipod", "mobile", "windows phone"):
        if marker in low:
            return "mobile"
    return "desktop"


def entry_path(req=None) -> str | None:
    """Where a server-rendered page was reached from, as a bare path.

    Makes cross-page journeys measurable ("readers of /guides/ctr go on to
    the index") without any identifier that survives a page load, which is
    the thing we deliberately do not have.

    Only same-origin paths are returned. An external referrer collapses to
    the literal string "external" and its URL is discarded: an external
    referrer can carry search terms and campaign parameters that say
    something about the person, and none of that is our business. Query
    strings and fragments are stripped from internal paths too.
    """
    req = _current_request(req)
    if req is None:
        return None
    try:
        ref = (req.headers.get("Referer") or "").strip()
        if not ref:
            return None
        from urllib.parse import urlparse

        parsed = urlparse(ref)
        if not parsed.netloc:
            return None
        if parsed.netloc != (req.host or ""):
            return "external"
        return (parsed.path or "/")[:120]
    except Exception:
        return None


def objection_signalled(req=None) -> bool:
    """True when the request carries a recognised opt-out signal.

    Defaults to the ambient Flask request, so callers cannot accidentally
    bypass an opt-out by omitting the argument.

    Global Privacy Control is a legally recognised objection signal in a
    growing number of jurisdictions, and Do Not Track is the older
    convention. Honouring both costs us nothing and is the cleanest way to
    respect Art. 21 without a consent banner.
    """
    req = _current_request(req)
    if req is None:
        return False
    try:
        if (req.headers.get("Sec-GPC") or "").strip() == "1":
            return True
        return (req.headers.get("DNT") or "").strip() == "1"
    except Exception:
        return False


def _current_request(req=None):
    """The request to read context from.

    Falls back to Flask's ambient request when the caller passes nothing.
    That default is load-bearing rather than a convenience: the objection
    check below lives on this path, so a recorder that forgets to pass
    `req=request` must still honour Sec-GPC / DNT. Failing open here would
    mean silently ignoring an opt-out.
    """
    if req is not None:
        return req
    try:
        from flask import has_request_context, request as flask_request

        return flask_request if has_request_context() else None
    except Exception:
        return None


def _request_context(req) -> dict:
    """Pull the (already minimised) request attributes we store.

    Runs in the request thread because the writer thread has no request
    context. Note what is absent: no IP, no UA string, no referrer, no
    query string - `path` is the route path only.
    """
    ctx = {
        "path": None,
        "cf_country": None,
        "ua_class": None,
        "request_id": None,
        "objection": False,
    }
    req = _current_request(req)
    if req is None:
        return ctx
    try:
        ctx["path"] = (req.path or "")[:200] or None
        country = (req.headers.get("CF-IPCountry") or "").strip().upper()
        # Cloudflare sends XX for unknown and T1 for Tor; neither is a country
        # and neither is worth storing.
        if len(country) == 2 and country not in ("XX", "T1"):
            ctx["cf_country"] = country
        synthetic = (req.headers.get("X-AP-Pie-Synthetic") or "").strip()
        expected = config.ANALYTICS_SYNTHETIC_TOKEN
        if expected and synthetic and hmac.compare_digest(synthetic, expected):
            ctx["ua_class"] = "synthetic"
        else:
            ctx["ua_class"] = _ua_class(req.headers.get("User-Agent") or "")
        ctx["objection"] = objection_signalled(req)
        from flask import g
        ctx["request_id"] = getattr(g, "request_id", None)
    except Exception:
        pass
    return ctx


# ── Props sanitising ─────────────────────────────────────────────


def sanitize_props(kind: str, props: dict | None) -> dict:
    """Keep only the props declared for `kind`, coerced to the declared type.

    Unknown keys are dropped silently rather than rejected: a caller passing
    something extra should lose the extra, not lose the event. Anything that
    cannot be coerced is dropped too.
    """
    spec = KIND_SPECS.get(kind)
    if not spec or not isinstance(props, dict):
        return {}
    allowed: dict[str, Any] = spec["props"]
    out: dict[str, Any] = {}
    for key, want in allowed.items():
        if key not in props:
            continue
        val = props[key]
        if val is None:
            continue
        try:
            if want == _STR:
                if isinstance(val, bool) or not isinstance(val, (str, int, float)):
                    continue
                out[key] = str(val)[:_MAX_STR]
            elif want == _INT:
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    continue
                out[key] = int(val)
            elif want == _BOOL:
                if not isinstance(val, bool):
                    continue
                out[key] = val
            elif want == _STR_LIST:
                if not isinstance(val, (list, tuple)):
                    continue
                out[key] = [
                    str(v)[:_MAX_STR] for v in val[:_MAX_LIST]
                    if isinstance(v, (str, int, float)) and not isinstance(v, bool)
                ]
            elif want == _ATTEMPT_ID:
                if isinstance(val, str) and len(val) == 16 and all(c in "0123456789abcdef" for c in val):
                    out[key] = val
            elif isinstance(want, frozenset):
                if isinstance(val, str) and val in want:
                    out[key] = val
        except Exception:
            continue
    return out


# ── Writer thread ────────────────────────────────────────────────


def _writer_loop() -> None:
    from db import insert_event

    while True:
        row = _queue.get()
        try:
            insert_event(
                row["kind"],
                user_id=row.get("user_id"),
                room_id=row.get("room_id"),
                path=row.get("path"),
                cf_country=row.get("cf_country"),
                ua_class=row.get("ua_class"),
                request_id=row.get("request_id"),
                visit_id=row.get("visit_id"),
                props=row.get("props"),
            )
        except Exception as e:
            # Best-effort by contract: a failed write is logged once and
            # forgotten. Never retried, never surfaced to the request.
            _log(f"analytics: event write failed ({row.get('kind')}): {e}")
        finally:
            _queue.task_done()


def start_writer() -> None:
    """Start the background writer once per process. Safe to call repeatedly."""
    with _writer_lock:
        if _writer_started.is_set():
            return
        t = threading.Thread(target=_writer_loop, name="analytics-writer", daemon=True)
        t.start()
        _writer_started.set()


# ── Public API ───────────────────────────────────────────────────


def record_event(
    kind: str,
    *,
    user_id: int | None = None,
    room_id: str | None = None,
    props: dict | None = None,
    req=None,
    visit_id: str | None = None,
) -> None:
    """Record one event. Never raises, never blocks on the database.

    `req` overrides which request the context is read from; it defaults to
    the ambient Flask request, which is what makes the objection check
    impossible to skip by forgetting an argument. `visit_id` is only ever
    supplied by the client-event endpoint; server-recorded events leave it
    NULL.
    """
    try:
        if not config.ANALYTICS_ENABLED:
            return
        if kind not in KIND_SPECS:
            _log(f"analytics: refusing unknown kind {kind!r}")
            return

        ctx = _request_context(req)
        if ctx["objection"]:
            # Art. 21 objection: keep the counter, drop everything that could
            # tie it to a person or a session.
            user_id = None
            visit_id = None
        if not config.ANALYTICS_VISIT_ID:
            visit_id = None

        clean_props = sanitize_props(kind, props)
        if ctx["objection"]:
            clean_props.pop("attempt_id", None)

        row = {
            "kind": kind,
            "user_id": user_id,
            "room_id": (str(room_id)[:64] if room_id else None),
            "path": ctx["path"],
            "cf_country": ctx["cf_country"],
            "ua_class": ctx["ua_class"],
            "request_id": ctx["request_id"],
            "visit_id": (str(visit_id)[:64] if visit_id else None),
            "props": clean_props,
        }

        start_writer()
        try:
            _queue.put_nowait(row)
        except queue.Full:
            global _dropped
            with _dropped_lock:
                _dropped += 1
                if _dropped % 100 == 1:
                    _log(f"analytics: queue full, dropped {_dropped} event(s)")
    except Exception as e:  # pragma: no cover - the whole point is not raising
        _log(f"analytics: record_event failed: {e}")


def queue_depth() -> int:
    """Current backlog, exposed on the admin summary for sanity checks."""
    try:
        return _queue.qsize()
    except Exception:
        return -1


def dropped_count() -> int:
    with _dropped_lock:
        return _dropped
