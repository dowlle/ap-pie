from __future__ import annotations

import threading
from functools import wraps
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, redirect, request, send_file

from typing import Iterator

from auth import requires_admin

from ap_lib.apworld_index import (
    APWorldInfo,
    build_game_lookup,
    download_apworld,
    fetch_index,
    list_installed,
    parse_index_dir,
    resolve_local_path,
)

import config

bp = Blueprint("apworlds", __name__)


def _requires_generation(f):
    """Per-route gate for the AP-server-side install/remove flow. The browse
    + per-room-pin surface (FEAT-21) is intentionally NOT gated - it's useful
    on `ap-pie.com` (where generation is off) for surfacing install links to
    players who run AP locally. Only the `install` / `remove` / `installed`
    endpoints actually touch the AP install dir."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not config.FEATURES.get("generation", False):
            return jsonify({
                "error": "The 'generation' feature is currently disabled on this server.",
                "feature": "generation",
                "enabled": False,
            }), 403
        return f(*args, **kwargs)
    return wrapper


_index_cache: list | None = None
_index_worlds_cache: list | None = None  # raw APWorldInfo objects, parallel to _index_cache
_index_lookup_cache: dict | None = None  # game_name -> APWorldInfo
_index_lock = threading.Lock()


def _get_index_dir() -> Path:
    return Path(current_app.config.get("AP_INDEX_DIR", ".state/archipelago-index"))


def _get_worlds_dir() -> Path:
    return Path(current_app.config["AP_WORLDS_DIR"])


def _load_index_into_cache():
    """Populate all three index caches in one parse pass. Caller holds the
    lock. Cache is invalidated by `refresh_index` and on first read."""
    global _index_cache, _index_worlds_cache, _index_lookup_cache
    index_dir = _get_index_dir()
    if (index_dir / "index").is_dir():
        worlds = parse_index_dir(index_dir)
        _index_worlds_cache = worlds
        _index_cache = [w.to_dict() for w in worlds]
        _index_lookup_cache = build_game_lookup(worlds)
    else:
        _index_worlds_cache = []
        _index_cache = []
        _index_lookup_cache = {}


def _get_index() -> list:
    global _index_cache
    with _index_lock:
        if _index_cache is None:
            _load_index_into_cache()
        return _index_cache


def _get_index_worlds() -> list[APWorldInfo]:
    """Get the raw APWorldInfo objects (not dicts) for URL resolution."""
    global _index_worlds_cache
    with _index_lock:
        if _index_worlds_cache is None:
            _load_index_into_cache()
        return _index_worlds_cache or []


def _get_game_lookup() -> dict[str, APWorldInfo]:
    """Get the `game_name -> APWorldInfo` map (FEAT-21 picker uses this to
    resolve YAML.game strings into index entries)."""
    global _index_lookup_cache
    with _index_lock:
        if _index_lookup_cache is None:
            _load_index_into_cache()
        return _index_lookup_cache or {}


def _compare_versions(a: str, b: str) -> int:
    """Tuple-compare semver-ish version strings. Numeric segments
    compared as ints, alpha segments as strings, mixed segments by
    string ordering. Mirrors the frontend's `compareVersions` in
    APWorlds.tsx so backend and frontend agree on "which version is
    newest".

    Returns negative if a<b, zero if equal, positive if a>b.
    """
    import re
    pa = re.split(r"[.\-]", a)
    pb = re.split(r"[.\-]", b)
    for i in range(max(len(pa), len(pb))):
        x = pa[i] if i < len(pa) else "0"
        y = pb[i] if i < len(pb) else "0"
        try:
            xi, yi = int(x), int(y)
        except ValueError:
            xi = yi = None
        if xi is not None and yi is not None:
            if xi != yi:
                return xi - yi
            continue
        if x != y:
            return -1 if x < y else 1
    return 0


def select_pin_version(world, requested_versions: list[str] | None) -> str | None:
    """Pick the version to pin for a world.

    Preference order:
      1. Highest version in `requested_versions` that exists in the
         world's `versions` list (i.e. the YAMLs in the room asked for
         a specific version and the index has it - perfect match).
      2. World's latest version (`world.versions[0].version` - the
         existing FEAT-21 v2 default).
      3. None if the world has no versions at all.

    `requested_versions` may include duplicates and entries that don't
    exist in the index; both are filtered.
    """
    if not world or not world.versions:
        return None
    if requested_versions:
        available = {v.version for v in world.versions}
        matched = [v for v in requested_versions if v in available]
        if matched:
            # Highest matched, by the same comparator the index uses.
            return sorted(matched, key=__import__("functools").cmp_to_key(_compare_versions))[-1]
    return world.versions[0].version


def split_yaml_games(game_string: str) -> list[str]:
    """Split a YAML's `game:` field into individual game names.

    BUG-03's `extract_player_info` joins dict and list `game:` keys with
    " / " for display purposes (weighted-random + uniform-list random
    pools). Each game in the joined string is a standalone APWorld that
    the host needs pinned independently - "Yacht Dice Bliss / VVVVVV /
    Refunct" is three different APWorlds, not one mega-world.

    Single-game YAMLs return a one-element list. Empty input returns [].
    No real Archipelago game name contains " / " (validated against the
    full dowlle/Archipelago-index display_name set), so the split is
    unambiguous.
    """
    if not game_string:
        return []
    return [g.strip() for g in game_string.split(" / ") if g.strip()]


def auto_pin_for_room_game(
    room_id: str,
    game_string: str,
    yaml_content: str | None = None,
) -> None:
    """Pin (or upgrade) the room's APWorld pins based on this YAML.

    Version selection per game:
      1. The YAML's `requires.game.<Name>` declaration, if it exists in
         the dowlle index.
      2. The index's latest version, when the YAML doesn't declare a
         version or its declared version isn't indexed.

    Pin write decision (FEAT-28 v2):
      - No existing pin -> write the target version.
      - Existing pin and `room.auto_upgrade_apworld_pins` is FALSE
        -> respect it, no-op (host opted out of auto-upgrades).
      - Existing pin and the flag is TRUE:
          - target > current pin (per `_compare_versions`) -> upgrade.
          - target <= current -> no-op (never downgrade auto-pins).

    Multi-game random-pool YAMLs (`Game A / Game B / Game C`) split via
    `split_yaml_games` and each component is processed independently.

    Silent on all errors - YAML upload should never fail because a pin
    write blew up.
    """
    games = split_yaml_games(game_string)
    if not games:
        return
    try:
        from db import get_room, get_room_apworlds, set_room_apworld
    except Exception:
        return

    # Parse the YAML's `requires.game` block once. May be empty (YAMLs
    # are not required to declare versions; many don't).
    required: dict[str, str] = {}
    if yaml_content:
        try:
            from validation import extract_required_apworld_versions
            required = extract_required_apworld_versions(yaml_content)
        except Exception:
            required = {}

    room = get_room(room_id) or {}
    auto_upgrade = bool(room.get("auto_upgrade_apworld_pins", True))

    lookup = _get_game_lookup()
    pins = get_room_apworlds(room_id)
    pin_versions: dict[str, str] = {p["apworld_name"]: p["version"] for p in pins}
    for g in games:
        world = lookup.get(g)
        if not world or not world.versions:
            continue
        requested = [required[g]] if g in required else None
        target = select_pin_version(world, requested)
        if not target:
            continue
        current = pin_versions.get(world.name)
        if current is not None:
            if not auto_upgrade:
                # Host opted out of auto-upgrades for this room.
                continue
            if _compare_versions(target, current) <= 0:
                # Target equals or is older than current pin - never
                # downgrade auto-pins; equal is a no-op for write
                # efficiency too.
                continue
        try:
            set_room_apworld(room_id, world.name, target)
            pin_versions[world.name] = target  # reflect for subsequent loop iterations
        except Exception:
            pass


def iter_pinned_apworld_files(
    yamls: list[dict],
    pins: list[dict],
    *,
    force_latest: bool = False,
) -> Iterator[tuple[str, bytes]]:
    """FEAT-25: yield (filename, bytes) for every downloadable APWorld pin
    in this room.

    Mirrors the per-version resolution in `apworld_download_proxy`, but
    fetches bytes instead of redirecting so callers can stream them into
    a zip. Skips:
      - games not in the index (no pinnable APWorld to surface)
      - pins with neither `url` nor `local` source (built-in worlds ship
        with AP itself; nothing to bundle)
      - pins that 404 upstream (silently dropped, not fatal - one bad
        upstream shouldn't sabotage the rest of the bundle)

    `force_latest` mirrors the room policy flag: when True, every pin
    resolves to the index's latest downloadable version regardless of
    what was stored.

    Filename format `<world.name>.apworld` (no version suffix) matches
    how AP itself loads APWorlds and how upstream GitHub release assets
    name them, so the zip's contents drop straight into a `worlds/`
    directory without renames. The schema (`room_apworlds` PK on
    `(room_id, apworld_name)`) plus `seen_apworlds` dedup guarantees
    one yield per apworld name, so version collisions in the zip are
    unreachable.
    """
    lookup = _get_game_lookup()
    pin_map = {p["apworld_name"]: p["version"] for p in pins}

    seen_apworlds: set[str] = set()
    index_dir = _get_index_dir()
    for y in yamls:
        for game in split_yaml_games(y.get("game") or ""):
            world = lookup.get(game)
            if not world:
                continue
            if world.name in seen_apworlds:
                continue
            seen_apworlds.add(world.name)

            if force_latest:
                ver = next(
                    (v for v in world.versions if v.url or v.local),
                    None,
                )
            else:
                version_str = pin_map.get(world.name)
                if not version_str:
                    continue
                ver = next(
                    (v for v in world.versions if v.version == version_str),
                    None,
                )
            if not ver:
                continue

            filename = f"{world.name}.apworld"
            if ver.local:
                local_path = resolve_local_path(index_dir, world, ver)
                if local_path and local_path.is_file():
                    try:
                        yield filename, local_path.read_bytes()
                    except Exception:
                        continue
            elif ver.url:
                # SEC-03 (SEC-07 sibling): gate the upstream fetch on the same
                # scheme + outbound-host check `tracker.py` uses. `ver.url`
                # comes from the dowlle/Archipelago-index TOML manifest (PR-
                # reviewed + FEAT-19 audited) so the trust level is high, but
                # `urlopen` honours `file://` and any other scheme urllib
                # supports - a single bad PR could turn this into an arbitrary-
                # file-read primitive on the prod box. Skip on reject, same
                # shape as the existing per-pin upstream-failure path.
                from tracker import is_safe_tracker_url
                if not is_safe_tracker_url(ver.url):
                    current_app.logger.warning(
                        f"apworlds: rejected unsafe ver.url for "
                        f"{world.name} {ver.version}: {ver.url[:80]!r}"
                    )
                    continue
                try:
                    from urllib.request import Request, urlopen
                    req = Request(ver.url, headers={"User-Agent": "archipelago-pie/1.0"})
                    with urlopen(req, timeout=30) as resp:
                        yield filename, resp.read()
                except Exception:
                    continue


def apworlds_for_room(
    yamls: list[dict],
    pins: list[dict],
    host: bool,
    *,
    force_latest: bool = False,
    allow_mixed: bool = False,
) -> list[dict]:
    """Resolve a room's YAML game list against the index + per-room pins.

    yamls: room.yamls (each carrying a `game` field)
    pins:  rows from db.get_room_apworlds(room_id) (one per apworld_name)
    host:  True if the caller is the room host (gets full version list +
           install URL preview); False is the public/player view (gets the
           selected-version download URL only).

    Returns one entry per distinct INDIVIDUAL game from the YAMLs, in
    stable first-seen order. Multi-game random-pool YAMLs (`Game A /
    Game B / Game C`) split into separate rows via `split_yaml_games` -
    each game in the pool is a standalone APWorld the host needs ready,
    so each gets its own picker row.

        [{
            game,                # individual game string (post-split)
            apworld_name,        # index key, or null if no match in the index
            display_name,        # pretty name from the index, falls back to game
            home,                # discord/github link from the index, may be ""
            tags,                # index tags (["ad"] for after-dark)
            yaml_count,          # how many YAMLs in this room could roll this game
            in_index,            # bool
            selected_version,    # the host's pinned version, or null
            download_url,        # for the pinned version, or null
            available_versions,  # full version list (host view) or [] (public)
        }]

    `yaml_count` semantics post-split: counts every YAML where this
    game *could* be selected at generation time. A single-game YAML
    contributes 1 to its game's count; a 5-game random-pool YAML
    contributes 1 to each of its 5 games' counts. Useful for the host
    to see "this game is in the pool of 3 different YAMLs" at a glance.

    Players see only games that have a pin set (otherwise we don't know
    what URL to surface). Hosts see every game so they can pin missing
    ones.
    """
    lookup = _get_game_lookup()
    pin_map = {p["apworld_name"]: p["version"] for p in pins}

    counts: dict[str, int] = {}
    order: list[str] = []
    for y in yamls:
        for g in split_yaml_games(y.get("game") or ""):
            if g not in counts:
                order.append(g)
                counts[g] = 0
            counts[g] += 1

    out = []
    for game in order:
        world = lookup.get(game)
        entry: dict = {
            "game": game,
            "yaml_count": counts[game],
            "in_index": world is not None,
            "apworld_name": world.name if world else None,
            "display_name": world.display_name if world else game,
            "home": world.home if world else "",
            "tags": world.tags if world else [],
            "selected_version": None,
            "download_url": None,
            "available_versions": [],
            # Public-facing copy is steered by these two flags; surfacing
            # them per-row keeps the frontend ignorant of room policy.
            "policy": "suggested" if allow_mixed else "required",
            "auto_latest": force_latest,
        }
        if world is None:
            # Unknown game - host sees a "no index entry" badge; public view
            # filters this out (see `host` check below).
            if host:
                out.append(entry)
            continue

        # force_latest overrides any stored pin: always use the index's
        # latest downloadable version (built-in-only worlds still resolve
        # to None since there's no download to surface).
        if force_latest:
            downloadable_latest = next(
                (v for v in world.versions if v.url or v.local),
                None,
            )
            selected = downloadable_latest.version if downloadable_latest else None
        else:
            selected = pin_map.get(world.name)
        entry["selected_version"] = selected
        if selected:
            # Both host and public benefit from the resolved download URL,
            # but the public version uses the proxy endpoint so we can
            # serve `local`-only versions too.
            entry["download_url"] = f"/api/apworlds/{world.name}/{selected}/download"

        if host:
            entry["available_versions"] = [
                {
                    "version": v.version,
                    "source": "url" if v.url else ("local" if v.local else "builtin"),
                    "sha256": v.sha256,
                    "url": v.url,  # raw upstream URL (host-only - public uses /download proxy)
                }
                for v in world.versions
            ]
            out.append(entry)
        elif selected:
            # Public view: only games with a pin set get surfaced. Don't
            # leak the host's "needs picking" backlog to players.
            out.append(entry)

    return out


@bp.route("/api/apworlds")
def list_apworlds():
    search = request.args.get("search", "").lower()
    supported_only = request.args.get("supported") == "true"

    worlds = _get_index()
    if search:
        worlds = [
            w for w in worlds
            if search in w["display_name"].lower() or search in w["name"].lower()
        ]
    if supported_only:
        worlds = [w for w in worlds if w["supported"] and not w["disabled"]]

    return jsonify(worlds)


@bp.route("/api/apworlds/installed")
@_requires_generation
def installed_apworlds():
    worlds_dir = _get_worlds_dir()
    return jsonify(list_installed(worlds_dir))


@bp.route("/api/apworlds/<name>/<version>/download")
def apworld_download_proxy(name: str, version: str):
    """Single download URL the public room page can hand to players,
    regardless of whether the index entry is `url`- or `local`-backed.

    For `url` versions: 302 to the upstream. For `local` versions: serve
    the file from the cloned index repo. For unknown name/version pairs:
    404. Authenticated only by knowing the index's name+version pair -
    no rate-limit beyond the upstream's own.
    """
    worlds = _get_index_worlds()
    world = next((w for w in worlds if w.name == name), None)
    if not world:
        abort(404, description=f"APWorld '{name}' not in index")
    ver = next((v for v in world.versions if v.version == version), None)
    if not ver:
        abort(404, description=f"Version '{version}' not in index for '{name}'")

    if ver.url:
        return redirect(ver.url, code=302)

    local_path = resolve_local_path(_get_index_dir(), world, ver)
    if local_path:
        # name + version aren't user-controlled paths (they're matched
        # against the index), so the filename here is safe. Filename
        # drops the version to match upstream URL-backed pins (whose
        # GitHub release assets are named without version) and the
        # bulk-zip filenames in `iter_pinned_apworld_files`.
        return send_file(
            local_path,
            download_name=f"{world.name}.apworld",
            as_attachment=True,
        )
    abort(404, description=f"No download source for '{name}' v{version}")


@bp.route("/api/apworlds/install", methods=["POST"])
@_requires_generation
@requires_admin
def install_apworld():
    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "name is required"}), 400

    name = data["name"]
    version = data.get("version")

    # Find the world in the index
    worlds = _get_index_worlds()
    world = next((w for w in worlds if w.name == name), None)
    if not world:
        return jsonify({"error": f"APWorld '{name}' not found in index"}), 404

    # Resolve version
    if not version and world.latest_version:
        version = world.latest_version.version
    if not version:
        return jsonify({"error": "No version available"}), 400

    url = world.get_download_url(version)
    if not url:
        return jsonify({"error": f"No download URL for {name} v{version}"}), 400

    # Audit-2026-05-04 #5: pass through the index-pinned SHA-256 so
    # download_apworld can verify the bytes match. None when the index
    # didn't ship a sha for this version (older entries pre-lockfile).
    ver_obj = next((v for v in world.versions if v.version == version), None)
    expected_sha = ver_obj.sha256 if ver_obj else None

    # Download
    worlds_dir = _get_worlds_dir()
    worlds_dir.mkdir(parents=True, exist_ok=True)
    dest = worlds_dir / f"{name}.apworld"

    try:
        download_apworld(url, dest, expected_sha=expected_sha)
    except Exception as e:
        return jsonify({"error": f"Download failed: {e}"}), 500

    # Store version metadata alongside the apworld file
    (worlds_dir / f"{name}.version").write_text(version)

    return jsonify({
        "status": "installed",
        "name": name,
        "version": version,
        "path": str(dest),
    })


@bp.route("/api/apworlds/<name>", methods=["DELETE"])
@_requires_generation
@requires_admin
def remove_apworld(name: str):
    worlds_dir = _get_worlds_dir()
    target = worlds_dir / f"{name}.apworld"
    if not target.exists():
        return jsonify({"error": f"APWorld '{name}' not installed"}), 404

    target.unlink()
    version_file = worlds_dir / f"{name}.version"
    if version_file.exists():
        version_file.unlink()
    return jsonify({"status": "removed", "name": name})


@bp.route("/api/apworlds/refresh", methods=["POST"])
@requires_admin
def refresh_index():
    """Pull the latest index from the configured repo. NOT gated on
    the generation feature - the per-room picker (FEAT-21) needs a
    fresh index even when this server doesn't run AP itself.

    Admin-only because the refresh is global state and any approved
    user could otherwise spam pulls or sync in untrusted upstream
    state if the host hasn't reviewed it yet (2026-05-03 policy).
    The /apworlds page itself stays visible to all approved hosts;
    only the Refresh button hides for non-admins (gated client-side
    via FeaturesContext / AuthContext - see APWorlds.tsx)."""
    global _index_cache, _index_worlds_cache, _index_lookup_cache
    index_dir = _get_index_dir()
    repo_url = current_app.config.get("AP_INDEX_REPO", "https://github.com/dowlle/Archipelago-index.git")

    try:
        fetch_index(index_dir, repo_url)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch index: {e}"}), 500

    with _index_lock:
        _index_cache = None  # Force re-parse on next request
        _index_worlds_cache = None
        _index_lookup_cache = None

    worlds = _get_index()
    return jsonify({"status": "refreshed", "count": len(worlds)})
