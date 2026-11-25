"""Read and normalize public CTR registry snapshots."""

from collections import defaultdict
import json
import logging
import re
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

import requests

from tracker import is_safe_outbound_host


MODE_LABELS = {
    "arcade": "Race against AI",
    "time_trial": "Time Trial",
    "relic_race": "Relic Race",
    "ctr_challenge": "CTR letters",
    "wumpa": "Wumpa",
    "crystal_challenge": "Crystal Challenge",
}
SOURCE_LABELS = {"saphi": "Project Saphi", "xdelta": "xdelta patch"}

_REPOSITORY = "dowlle/ctr-track-registry"
_REF_URL = f"https://api.github.com/repos/{_REPOSITORY}/git/ref/heads/main"
_RAW_BASE = f"https://raw.githubusercontent.com/{_REPOSITORY}"
_HOSTS = {"api.github.com", "raw.githubusercontent.com"}
_REF_LIMIT = 16 * 1024
_FILE_LIMIT = 2 * 1024 * 1024
_REFRESH_SECONDS = 15 * 60
_COMMIT = re.compile(r"[a-f0-9]{40}")
_HASH = re.compile(r"[a-f0-9]{64}")
_TRACK_KEY = re.compile(r"[a-z0-9][a-z0-9-]*")
_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(.*)")
_LOG = logging.getLogger(__name__)


def _fetch_json(session, url, limit, *, optional=False):
    host = urlsplit(url).hostname
    if not url.startswith("https://") or host not in _HOSTS or not is_safe_outbound_host(host):
        raise ValueError("Registry host is not allowed")
    with session.get(url, timeout=(3, 5), stream=True, allow_redirects=False) as response:
        if optional and response.status_code == 404:
            return None
        if response.status_code != 200:
            raise ValueError(f"Registry returned HTTP {response.status_code}")
        if int(response.headers.get("Content-Length", 0)) > limit:
            raise ValueError("Registry response exceeds size limit")
        body = bytearray()
        for chunk in response.iter_content(chunk_size=16384):
            body.extend(chunk)
            if len(body) > limit:
                raise ValueError("Registry response exceeds size limit")
        document = json.loads(body)
        if not isinstance(document, dict):
            raise ValueError("Registry response must be an object")
        return document


def _rows(document, key):
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("Unsupported CTR registry schema")
    return _list(document[key])


def _list(value):
    if not isinstance(value, list):
        raise ValueError("Expected a registry list")
    return value


def _string(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected a registry string")
    return value


def _publication_url(value):
    if not isinstance(value, str) or any(char.isspace() or char == "\\" for char in value):
        return None
    try:
        url = urlsplit(value)
        if url.scheme == "https" and url.hostname and not url.username and url.password is None:
            return value
    except ValueError:
        pass
    return None


def _saphi_url(track):
    saphi = track.get("provenance", {}).get("saphi")
    if saphi is None:
        return None
    track_id = saphi.get("track_id")
    return _publication_url(saphi.get("url")) or (
        f"https://www.projectsaphi.com/tracks/{track_id}"
        if type(track_id) is int and track_id > 0 else None
    )


def _revision_order(revision):
    # Pack labels have no comparable release number. Keep them after numbered
    # versions, preserving registry order among equally ranked revisions.
    match = _VERSION.fullmatch(revision["revision"])
    if not match:
        return (0, 0, 0, 0, False)
    major, minor, patch, suffix = match.groups()
    return (1, int(major), int(minor), int(patch), not suffix)


def make_catalog(commit, registry, sources):
    patches = defaultdict(list)
    if sources is not None:
        for patch in _rows(sources, "patches"):
            file_name = _string(patch["file_name"])
            sha = _string(patch["patch_sha256"])
            if not _HASH.fullmatch(sha):
                raise ValueError("Invalid CTR patch hash")
            url = _publication_url(patch.get("source_url"))
            for slot in _list(patch["slots"]):
                pair = (slot["lev_sha256"], slot["vrm_sha256"])
                index = slot["bigfile_index"]
                if not all(_HASH.fullmatch(value) for value in pair) or type(index) is not int or not 0 <= index <= 4095:
                    raise ValueError("Invalid CTR patch slot")
                patches[pair].append({
                    "kind": "xdelta",
                    "file_name": file_name,
                    "patch_sha256": sha,
                    "bigfile_index": index,
                    "url": url,
                })

    tracks = {}
    matched = set()
    for entry in _rows(registry, "tracks"):
        key = _string(entry["track_key"])
        if not _TRACK_KEY.fullmatch(key) or key in tracks:
            raise ValueError("Invalid or duplicate CTR track key")
        saphi_url = _saphi_url(entry)
        revisions = []
        for revision in _list(entry["revisions"]):
            files = revision.get("files", {})
            pair = tuple((files.get(kind) or {}).get("sha256") for kind in ("lev", "vrm"))
            revision_sources = list(patches.get(pair, ()))
            if revision_sources:
                matched.add(pair)
            downloads = _list(revision.get("provenance", {}).get("saphi_downloads", []))
            if saphi_url and downloads:
                revision_sources.insert(0, {"kind": "saphi", "url": saphi_url})
            modes = {_string(mode) for mode in _list(revision.get("modes", []))}
            content_id = revision["content_id"]
            if content_id is not None and not _HASH.fullmatch(_string(content_id)):
                raise ValueError("Invalid CTR revision content ID")
            revisions.append({
                "revision": _string(revision["revision"]),
                "content_id": content_id,
                "hash_state": _string(revision["hash_state"]),
                "modes": [mode for mode in MODE_LABELS if mode in modes],
                "sources": revision_sources,
            })
        revisions.sort(key=_revision_order, reverse=True)
        tracks[key] = {
            "track_key": key,
            "display_title": _string(entry["display_title"]),
            "credits": [
                {"name": _string(credit["name"]), "role": _string(credit["role"])}
                for credit in _list(entry["credits"])
            ],
            "state": _string(entry["state"]),
            "saphi_url": saphi_url,
            "revisions": revisions,
        }

    unmatched = defaultdict(list)
    for pair, locations in patches.items():
        if pair not in matched:
            for location in locations:
                key = (location["file_name"], location["patch_sha256"], location["url"])
                unmatched[key].append(location["bigfile_index"])

    return {
        "schema_version": 1,
        "registry_commit": commit,
        "tracks": sorted(tracks.values(), key=lambda track: track["display_title"].casefold()),
        "unmatched_patches": [
            {"file_name": name, "patch_sha256": sha, "url": url, "slots": sorted(slots)}
            for (name, sha, url), slots in sorted(unmatched.items(), key=lambda item: item[0][0].casefold())
        ],
    }


def _load_catalog():
    with requests.Session() as session:
        # Keep this public fetch independent of ambient proxy and netrc credentials.
        session.trust_env = False
        ref = _fetch_json(session, _REF_URL, _REF_LIMIT)
        commit = ref["object"]["sha"]
        if not _COMMIT.fullmatch(commit):
            raise ValueError("Invalid CTR registry commit")
        base = f"{_RAW_BASE}/{commit}"
        registry = _fetch_json(session, f"{base}/registry.json", _FILE_LIMIT)
        sources = _fetch_json(session, f"{base}/sources.json", _FILE_LIMIT, optional=True)
    return make_catalog(commit, registry, sources)


class RegistryCache:
    """Keep one validated snapshot and throttle refresh attempts per worker."""

    def __init__(self, load=_load_catalog, clock=monotonic):
        self._load = load
        self._clock = clock
        self._lock = Lock()
        self._next_attempt = float("-inf")
        self._catalog = None

    def get(self):
        with self._lock:
            now = self._clock()
            if now >= self._next_attempt:
                self._next_attempt = now + _REFRESH_SECONDS
                try:
                    self._catalog = self._load()
                except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
                    _LOG.warning("CTR track registry refresh failed (%s)", type(error).__name__)
            return self._catalog


registry_cache = RegistryCache()
