"""FEAT-30 Phase 0a: structured request flow for proposing new APWorld
versions to dowlle/Archipelago-index.

Two entry points funnel into a single queue:
  - room hosts (host of a room where the apworld is referenced by a YAML)
  - linked maintainers (Discord identity in apworld_maintainers for that apworld)

The Eijebong runtime fuzzer + Claude security audit gates are tracked as
separate status fields on the request row so each can be ticked off
independently. Phase 0a captures the workflow only; later phases automate the audit
+ PR open via an off-server worker. No GitHub credentials are used in
this blueprint - everything is queue-only.

Permission model:
  - Submit (room_host): user must be the host of the room AND the apworld
    must be referenced by a YAML in that room or already pinned. Prevents
    "I host a room, let me submit any apworld" abuse.
  - Submit (maintainer): user's Discord ID must appear in apworld_maintainers
    for the requested apworld. Maintainer assignments are admin-only.
  - All admin endpoints require is_admin (enforced by the auth middleware
    via the /api/admin/* prefix + the per-route requires_admin decorator
    as belt-and-suspenders, per SEC-10).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, session

from ap_lib.apworld_index import parse_index_dir
from auth import requires_admin
from db import (
    _db_url,
    add_apworld_maintainer,
    create_apworld_index_request,
    get_apworld_index_request,
    get_room,
    get_yamls,
    get_room_apworlds,
    is_apworld_maintainer,
    list_apworld_index_requests,
    list_apworld_maintainers,
    list_maintained_apworlds,
    remove_apworld_maintainer,
    update_apworld_index_request,
)


bp = Blueprint("apworld_requests", __name__)


# Length caps mirror the schema CHECK constraints. Reject early with a
# clean 400 instead of letting psycopg2 bubble up a generic 500.
_FIELD_LIMITS = {
    "requested_version": 64,
    "source_url": 1024,
    "notes": 2000,
    "apworld_name": 128,
    "display_name": 256,
}


def _current_user() -> dict | None:
    user = getattr(g, "user", None)
    if user is not None:
        return user
    # The /api/apworlds prefix skips the auth middleware since the index
    # went public (FEAT-39), so g.user is never populated on these routes.
    # Read the session directly, the same way requires_auth does; without
    # this fallback the maintainer routes fail closed even for logged-in
    # users (found by the 2026-07-22 branch security audit).
    user_id = session.get("user_id")
    if not user_id:
        return None
    from db import get_user
    return get_user(user_id)


def _validate_lengths(data: dict) -> tuple | None:
    for field, limit in _FIELD_LIMITS.items():
        v = data.get(field)
        if isinstance(v, str) and len(v) > limit:
            return jsonify({"error": f"{field} is too long (max {limit} characters)"}), 400
    return None


def _requires_db():
    if _db_url is None:
        return jsonify({"error": "Database not available"}), 503
    return None


def _apworld_referenced_by_room(room_id: str, apworld_name: str, display_name: str) -> bool:
    """Check whether the apworld appears in the room's YAML pool or pins.

    Match shape: an apworld is referenced if (a) it's in room_apworlds,
    or (b) any YAML in the room declares its display_name in
    apworld_versions, or (c) any YAML's `game` field matches the
    display_name. This catches both the auto-pinned and manually-pinned
    cases without requiring the host to have already pinned the world.
    """
    pinned = get_room_apworlds(room_id)
    if any(p.get("apworld_name") == apworld_name for p in pinned):
        return True
    yamls = get_yamls(room_id)
    for y in yamls:
        if y.get("game") == display_name:
            return True
        versions = y.get("apworld_versions") or {}
        if display_name in versions:
            return True
    return False


# ── Submit endpoints ─────────────────────────────────────────────


@bp.route("/api/rooms/<room_id>/apworlds/<path:apworld_name>/request-update", methods=["POST"])
def request_update_from_room(room_id: str, apworld_name: str):
    """Room-host path: host of `room_id` proposes a new index version for
    an apworld that is actually referenced by a YAML in their room."""
    err = _requires_db()
    if err: return err
    user = _current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
    is_admin = bool(user.get("is_admin"))
    is_host = room.get("host_user_id") == user.get("id")
    if not (is_admin or is_host):
        return jsonify({"error": "Only the room host can request APWorld updates from this room"}), 403

    data = request.get_json(silent=True) or {}
    err = _validate_lengths(data)
    if err: return err
    requested_version = (data.get("requested_version") or "").strip()
    source_url = (data.get("source_url") or "").strip()
    display_name = (data.get("display_name") or "").strip()
    notes = (data.get("notes") or "").strip() or None
    if not (requested_version and source_url and display_name):
        return jsonify({"error": "requested_version, source_url, and display_name are required"}), 400
    if not source_url.lower().startswith(("https://", "http://")):
        return jsonify({"error": "source_url must be an http(s) URL"}), 400

    if not _apworld_referenced_by_room(room_id, apworld_name, display_name):
        return jsonify({
            "error": f"This room does not reference {display_name}. Submit from a room where it's used, or ask a maintainer.",
        }), 400

    row = create_apworld_index_request(
        apworld_name=apworld_name,
        display_name=display_name,
        requested_version=requested_version,
        source_url=source_url,
        notes=notes,
        requester_user_id=user["id"],
        requester_role="room_host",
        source_room_id=room_id,
    )
    return jsonify(row), 201


@bp.route("/api/apworlds/<path:apworld_name>/request-update", methods=["POST"])
def request_update_from_maintainer(apworld_name: str):
    """Maintainer path: any user linked to `apworld_name` in
    apworld_maintainers proposes a new index version. Doesn't require
    a room context - meant for the dev who maintains the apworld."""
    err = _requires_db()
    if err: return err
    user = _current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    discord_id = user.get("discord_id")
    if not discord_id:
        return jsonify({"error": "Discord identity required"}), 403
    is_admin = bool(user.get("is_admin"))
    if not (is_admin or is_apworld_maintainer(discord_id, apworld_name)):
        return jsonify({"error": "You are not a registered maintainer of this APWorld"}), 403

    data = request.get_json(silent=True) or {}
    err = _validate_lengths(data)
    if err: return err
    requested_version = (data.get("requested_version") or "").strip()
    source_url = (data.get("source_url") or "").strip()
    display_name = (data.get("display_name") or "").strip()
    notes = (data.get("notes") or "").strip() or None
    if not (requested_version and source_url and display_name):
        return jsonify({"error": "requested_version, source_url, and display_name are required"}), 400
    if not source_url.lower().startswith(("https://", "http://")):
        return jsonify({"error": "source_url must be an http(s) URL"}), 400

    row = create_apworld_index_request(
        apworld_name=apworld_name,
        display_name=display_name,
        requested_version=requested_version,
        source_url=source_url,
        notes=notes,
        requester_user_id=user["id"],
        requester_role="maintainer",
        source_room_id=None,
    )
    return jsonify(row), 201


# ── Index-candidate detection (compare GitHub releases vs index) ─


# Owner/repo segments are alnum + hyphen + dot + underscore per GitHub's
# rules; capping length keeps a malicious / weird TOML from blowing up
# the API URL.
_GH_RELEASE_URL_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9._-]{1,100})/([A-Za-z0-9._-]{1,100})/releases/download/"
)
_GH_API_TIMEOUT = 8.0
_GH_USER_AGENT = "ap-pie-index-candidate-checker"


def _resolve_index_dir() -> Path:
    return Path(current_app.config.get("AP_INDEX_DIR", ".state/archipelago-index"))


def _strip_v_prefix(s: str) -> str:
    return s[1:] if s.startswith("v") and len(s) > 1 and s[1].isdigit() else s


@bp.route("/api/apworlds/<path:apworld_name>/index-candidates")
def index_candidates(apworld_name: str):
    """Surface upstream releases that aren't yet in the index.

    Reads the apworld's TOML for its `default_url` template, parses out
    the GitHub `owner/repo`, fetches `/releases?per_page=20` (unauth GitHub
    API; rate-limited 60/hr/IP), and diffs the release tags against the
    versions already declared in the index. The modal uses this to
    suggest "v3.6.0 is on GitHub but not yet in the index" quick-picks
    so the host doesn't have to hand-paste version + URL.

    Auth: requires a logged-in user (any session). Read-only, low blast
    radius - the response only contains data the index TOML itself
    points at. Bounded request body, bounded URL parsing, hardcoded
    api.github.com (not a fetch of arbitrary user input).
    """
    err = _requires_db()
    if err: return err
    user = _current_user()
    if not user:
        return jsonify({"error": "Authentication required"}), 401

    index_dir = _resolve_index_dir()
    worlds = parse_index_dir(index_dir)
    world = next((w for w in worlds if w.name == apworld_name), None)
    if not world:
        return jsonify({"error": f"APWorld {apworld_name} is not in the index"}), 404

    indexed_versions = [v.version for v in world.versions]
    response = {
        "apworld_name": apworld_name,
        "display_name": world.display_name,
        "indexed_versions": indexed_versions,
        "github_releases": [],
        "candidates": [],
        "error": None,
    }

    if not world.default_url:
        response["error"] = "This APWorld has no default_url; manual entry only."
        return jsonify(response)

    repo_match = _GH_RELEASE_URL_RE.match(world.default_url)
    if not repo_match:
        response["error"] = "default_url is not a GitHub releases URL; manual entry only."
        return jsonify(response)
    owner, repo = repo_match.group(1), repo_match.group(2)

    fn_match = re.search(r"/([^/]+\.apworld)$", world.default_url)
    expected_filename_template = fn_match.group(1) if fn_match else None

    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=20"
    req = urllib.request.Request(api_url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": _GH_USER_AGENT,
    })
    try:
        with urllib.request.urlopen(req, timeout=_GH_API_TIMEOUT) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        response["error"] = f"GitHub API returned {e.code}; try again later (rate limit is 60/hr per source IP)."
        return jsonify(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        response["error"] = f"GitHub API call failed: {type(e).__name__}"
        return jsonify(response)

    if not isinstance(payload, list):
        response["error"] = "GitHub API returned an unexpected shape."
        return jsonify(response)

    indexed_set = set(indexed_versions)
    seen_versions: set[str] = set()

    for release in payload:
        if not isinstance(release, dict):
            continue
        if release.get("draft") or release.get("prerelease"):
            # We still surface prereleases - many APworlds use beta tags
            # for actual usable releases. Skip pure drafts only.
            if release.get("draft"):
                continue
        tag = (release.get("tag_name") or "").strip()
        if not tag:
            continue
        version = _strip_v_prefix(tag)
        if not version or version in seen_versions:
            continue
        seen_versions.add(version)

        # Find the matching .apworld asset URL. Prefer an exact filename
        # match against the default_url template if we extracted one;
        # otherwise fall back to the first asset ending in .apworld.
        asset_url = None
        assets = release.get("assets") or []
        if expected_filename_template:
            wanted = expected_filename_template.replace("{{version}}", version)
            for a in assets:
                if isinstance(a, dict) and a.get("name") == wanted:
                    asset_url = a.get("browser_download_url")
                    break
        if not asset_url:
            for a in assets:
                if isinstance(a, dict) and isinstance(a.get("name"), str) and a["name"].endswith(".apworld"):
                    asset_url = a.get("browser_download_url")
                    break
        if not asset_url:
            # Last-ditch: synthesise the URL from the default_url template.
            # This is what the index resolver would do anyway, so it's
            # consistent with what gets stored.
            asset_url = world.default_url.replace("{{version}}", version)

        entry = {
            "tag": tag,
            "version": version,
            "asset_url": asset_url,
            "published_at": release.get("published_at"),
        }
        response["github_releases"].append(entry)
        if version not in indexed_set:
            response["candidates"].append(entry)

    return jsonify(response)


# ── Maintainer-facing read endpoint ─────────────────────────────


@bp.route("/api/apworlds/maintained")
def my_maintained_apworlds():
    """Return the list of apworld_name strings the current user maintains.
    Frontend uses this to decide whether to render the 'My APWorlds' nav
    link and to populate the page itself."""
    err = _requires_db()
    if err: return err
    user = _current_user()
    if not user or not user.get("discord_id"):
        return jsonify([])
    return jsonify(list_maintained_apworlds(user["discord_id"]))


# ── Admin endpoints ─────────────────────────────────────────────


@bp.route("/api/admin/apworld-requests")
@requires_admin
def admin_list_requests():
    status = request.args.get("status") or None
    return jsonify(list_apworld_index_requests(status=status))


@bp.route("/api/admin/apworld-requests/<int:request_id>", methods=["PATCH"])
@requires_admin
def admin_update_request(request_id: int):
    """Flexible PATCH so the admin UI can set any subset of:
      fuzzer_status, fuzzer_url, audit_status, audit_url, pr_url,
      status, reject_reason
    The DB layer's allowlist drops anything else."""
    existing = get_apworld_index_request(request_id)
    if not existing:
        return jsonify({"error": "Request not found"}), 404
    data = request.get_json(silent=True) or {}
    updated = update_apworld_index_request(request_id, **data)
    return jsonify(updated)


@bp.route("/api/admin/apworld-maintainers")
@requires_admin
def admin_list_maintainers():
    apworld_name = request.args.get("apworld_name") or None
    return jsonify(list_apworld_maintainers(apworld_name=apworld_name))


@bp.route("/api/admin/apworld-maintainers", methods=["POST"])
@requires_admin
def admin_add_maintainer():
    data = request.get_json(silent=True) or {}
    apworld_name = (data.get("apworld_name") or "").strip()
    discord_user_id = (data.get("discord_user_id") or "").strip()
    notes = (data.get("notes") or "").strip() or None
    if not (apworld_name and discord_user_id):
        return jsonify({"error": "apworld_name and discord_user_id are required"}), 400
    if len(apworld_name) > 128 or len(discord_user_id) > 64:
        return jsonify({"error": "field length out of bounds"}), 400
    granted_by = _current_user()["id"]
    row = add_apworld_maintainer(apworld_name, discord_user_id, granted_by, notes)
    return jsonify(row), 201


@bp.route("/api/admin/apworld-maintainers/<path:apworld_name>/<discord_user_id>", methods=["DELETE"])
@requires_admin
def admin_remove_maintainer(apworld_name: str, discord_user_id: str):
    ok = remove_apworld_maintainer(apworld_name, discord_user_id)
    if not ok:
        return jsonify({"error": "Maintainer link not found"}), 404
    return jsonify({"removed": True})
