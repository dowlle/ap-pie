"""APWorld index management - browse, download, and manage APWorld packages."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.request import urlopen, Request

logger = logging.getLogger(__name__)

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

DEFAULT_INDEX_REPO = "https://github.com/dowlle/Archipelago-index.git"


@dataclass
class FuzzResult:
    """Per-version empirical fuzz verdict from dowlle/Archipelago-index.

    FEAT-35: each world TOML may carry a top-level `[[fuzz_results]]`
    array-of-tables with one record per (version, fuzz-run). The reader
    groups records by `version`, sorts by `fuzzed_at` descending, and picks
    `[0]` as the active result per version (OPS-18 schema take-2, Option B).
    Absent records for a version mean "no data yet" -- treat as unknown in
    the UI; never render as clean. `*_rate` fields are decimals
    (0.004 = 0.4%); the UI multiplies by 100 for display. Verdict is one of
    "clean" | "flaky" | "broken" per thresholds locked in PR #113 of the
    index repo.
    """
    verdict: str
    default_rate: float
    worst_hook: str
    worst_hook_rate: float
    seeds: int
    fuzzed_at: str  # ISO date

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "default_rate": self.default_rate,
            "worst_hook": self.worst_hook,
            "worst_hook_rate": self.worst_hook_rate,
            "seeds": self.seeds,
            "fuzzed_at": self.fuzzed_at,
        }


@dataclass
class APWorldVersion:
    version: str
    url: str | None = None
    local: str | None = None
    sha256: str | None = None
    fuzz_result: FuzzResult | None = None


@dataclass
class APWorldInfo:
    name: str  # internal key (e.g. "hollow_knight"), == TOML filename stem
    display_name: str  # human-readable (e.g. "Hollow Knight")
    # The TOML's `name` field, which is what shows up as `game:` in player
    # YAMLs. Distinct from `name` (which is the apworld key / filename stem)
    # and from `display_name` (which is `Manual: Pretty Name` for manuals).
    # FEAT-21 uses this to map YAML.game -> APWorld entry.
    game_name: str = ""
    home: str = ""
    tags: list[str] = field(default_factory=list)
    supported: bool = False
    disabled: bool = False
    default_url: str | None = None
    versions: list[APWorldVersion] = field(default_factory=list)
    # OPS-16 fields backfilled from the unofficial AP APWorld sheet, all
    # optional. `stability` is stable/unstable/alpha/beta; `setup_guide`
    # and `tracker` are URLs.
    stability: str | None = None
    setup_guide: str | None = None
    tracker: str | None = None

    @property
    def latest_version(self) -> APWorldVersion | None:
        return self.versions[0] if self.versions else None

    def get_download_url(self, version: str) -> str | None:
        for v in self.versions:
            if v.version == version:
                if v.url:
                    return v.url
                if self.default_url:
                    return self.default_url.replace("{{version}}", version)
                return None
        return None

    @property
    def is_builtin(self) -> bool:
        """A supported world with no downloadable versions ships with AP."""
        return self.supported and not self.disabled and not any(
            v.url or self.default_url for v in self.versions
        )

    @property
    def has_update(self) -> bool:
        """A supported built-in world that also has downloadable versions."""
        return self.supported and not self.disabled and any(
            v.url or self.default_url for v in self.versions
        )

    def to_dict(self) -> dict:
        downloadable = [v for v in self.versions if v.url or self.default_url]
        return {
            "name": self.name,
            "display_name": self.display_name,
            "game_name": self.game_name,
            "home": self.home,
            "tags": self.tags,
            "supported": self.supported,
            "disabled": self.disabled,
            "is_builtin": self.is_builtin,
            "has_update": self.has_update,
            # Full per-version detail. `source` is what the FEAT-21 picker
            # surfaces ("download from URL" vs "ships in the index repo");
            # `sha256` comes from index.lock and lets the picker badge
            # checksum-pinned versions.
            "versions": [
                {
                    "version": v.version,
                    "url": v.url,
                    "local": v.local,
                    "sha256": v.sha256,
                    "source": "url" if v.url else ("local" if v.local else "builtin"),
                    # FEAT-35: per-version fuzz verdict. None when the index has
                    # no data for this (apworld, version) pair; the UI must
                    # render that as nothing (not "clean").
                    "fuzz_result": v.fuzz_result.to_dict() if v.fuzz_result else None,
                }
                for v in self.versions
            ],
            "downloadable_versions": [
                {"version": v.version} for v in downloadable
            ],
            "stability": self.stability,
            "setup_guide": self.setup_guide,
            "tracker": self.tracker,
        }


def _version_sort_key(ver_str: str) -> tuple:
    """Parse a version string into a tuple for proper semver-like sorting.

    Handles versions like "0.6.4", "1.0", "0.4.2", and non-numeric suffixes.
    """
    parts = []
    for part in re.split(r"[.\-]", ver_str):
        if part.isdigit():
            parts.append((0, int(part)))
        else:
            parts.append((1, part))
    return tuple(parts)


def parse_world_toml(key: str, data: dict) -> APWorldInfo:
    """Parse a single APWorld TOML file into an APWorldInfo."""
    default_url = data.get("default_url")
    versions_raw = data.get("versions", {})

    # FEAT-35 / OPS-18: build {version: FuzzResult} from the top-level
    # `[[fuzz_results]]` array-of-tables. The schema (Option B) places
    # fuzz records OUTSIDE the [versions] table so [versions] stays
    # byte-for-byte upstream-compatible with mooinglemur/ionium-ap and so
    # multiple records per version (re-fuzz, different AP versions, hook
    # suite changes) are natively expressible. The reader collapses to one
    # active record per version by latest-`fuzzed_at`-wins. Records missing
    # `version` or any required field are dropped silently -- CI lints the
    # schema, so a real corruption surfaces there, not here.
    fuzz_by_version: dict[str, FuzzResult] = {}
    fuzz_results_raw = data.get("fuzz_results", [])
    if isinstance(fuzz_results_raw, list):
        groups: dict[str, list[dict]] = {}
        for entry in fuzz_results_raw:
            if not isinstance(entry, dict):
                continue
            ver = entry.get("version")
            if not isinstance(ver, str):
                continue
            groups.setdefault(ver, []).append(entry)
        for ver, entries in groups.items():
            entries.sort(key=lambda e: str(e.get("fuzzed_at", "")), reverse=True)
            for entry in entries:
                try:
                    fuzz_by_version[ver] = FuzzResult(
                        verdict=entry["verdict"],
                        default_rate=float(entry["default_rate"]),
                        worst_hook=entry["worst_hook"],
                        worst_hook_rate=float(entry["worst_hook_rate"]),
                        seeds=int(entry["seeds"]),
                        fuzzed_at=str(entry["fuzzed_at"]),
                    )
                    break
                except (KeyError, TypeError, ValueError):
                    continue

    versions = []
    for ver_str, ver_data in versions_raw.items():
        if isinstance(ver_data, dict):
            url = ver_data.get("url")
            local = ver_data.get("local")
        else:
            url = None
            local = None

        # If no explicit URL but default_url exists, resolve it
        if not url and default_url:
            url = default_url.replace("{{version}}", ver_str)

        versions.append(
            APWorldVersion(
                version=ver_str,
                url=url,
                local=local,
                fuzz_result=fuzz_by_version.get(ver_str),
            )
        )

    # Sort versions descending so versions[0] is the latest
    versions.sort(key=lambda v: _version_sort_key(v.version), reverse=True)

    game_name = data.get("name", key)
    return APWorldInfo(
        name=key,
        display_name=data.get("display_name", game_name),
        game_name=game_name,
        home=data.get("home", ""),
        tags=data.get("tags", []),
        supported=data.get("supported", False),
        disabled=data.get("disabled", False),
        default_url=default_url,
        versions=versions,
        stability=data.get("stability"),
        setup_guide=data.get("setup_guide"),
        tracker=data.get("tracker"),
    )


def parse_index_dir(index_dir: Path) -> list[APWorldInfo]:
    """Parse all TOML files in an index directory.

    Side effect: for any world whose name appears in `index.lock`, fills
    each `APWorldVersion.sha256` from the lock entry. The lock keys are
    the TOML's `name` field (game_name), not the apworld key. Versions
    without a lock entry stay sha256=None.
    """
    worlds = []
    toml_dir = index_dir / "index"
    if not toml_dir.is_dir():
        return worlds

    lock = parse_lock_file(index_dir)

    for f in sorted(toml_dir.iterdir()):
        if f.suffix != ".toml":
            continue
        try:
            data = tomllib.loads(f.read_text(encoding="utf-8"))
            key = f.stem
            world = parse_world_toml(key, data)
            ver_shas = lock.get(world.game_name, {})
            for v in world.versions:
                v.sha256 = ver_shas.get(v.version)
            worlds.append(world)
        except Exception as exc:
            # OPS-18 hid behind a bare `continue` here for hours -- 99 TOMLs
            # silently dropped from /api/apworlds after PR #113's nested
            # fuzz_result shape failed `tomllib.loads`. Surface the parse
            # failure so the next class of outage is visible in `docker
            # logs` and any aggregator.
            logger.warning(
                "apworld_index: failed to parse %s: %s: %s",
                f.name, exc.__class__.__name__, exc,
            )
            continue

    return worlds


def build_game_lookup(worlds: list[APWorldInfo]) -> dict[str, APWorldInfo]:
    """Build a `game_name -> APWorldInfo` map for matching YAML.game strings.

    Case-sensitive on purpose: AP's own validator is case-sensitive on the
    `game:` key, so an exact match is the right contract. Callers that want
    fuzzy lookup can lowercase both sides before consulting this map.
    """
    return {w.game_name: w for w in worlds if w.game_name}


def resolve_local_path(index_dir: Path, world: APWorldInfo, version: APWorldVersion) -> Path | None:
    """Resolve a `local = "../apworlds/foo-x.y.z.apworld"` reference to an
    absolute path inside the cloned index repo. Returns None if there's no
    local source or the file is missing on disk."""
    if not version.local:
        return None
    # `local` paths in the TOMLs are relative to the index/ directory, so
    # resolve against `<index_dir>/index` then normalize.
    candidate = (index_dir / "index" / version.local).resolve()
    if candidate.is_file():
        return candidate
    return None


def parse_lock_file(index_dir: Path) -> dict[str, dict[str, str]]:
    """Parse index.lock → {display_name: {version: sha256}}."""
    lock_file = index_dir / "index.lock"
    if not lock_file.exists():
        return {}
    try:
        return tomllib.loads(lock_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def fetch_index(dest_dir: Path, repo_url: str = DEFAULT_INDEX_REPO) -> Path:
    """Clone or pull the Archipelago-index repo."""
    if (dest_dir / ".git").is_dir():
        subprocess.run(
            ["git", "-C", str(dest_dir), "pull", "--ff-only"],
            capture_output=True,
            timeout=60,
        )
    else:
        dest_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(dest_dir)],
            capture_output=True,
            timeout=120,
        )
    return dest_dir


def download_apworld(
    url: str, dest: Path, expected_sha: str | None = None
) -> Path:
    """Download an APWorld file from a URL with optional SHA-256 verification.

    Audit-2026-05-04 #5: reject non-https URLs (mandate TLS) and verify the
    downloaded bytes against `expected_sha` when provided. The index.lock
    file ships SHA-256 per pinned version; passing it through here closes a
    supply-chain class of bugs where the upstream URL is compromised
    between index curation and runtime download. The AP generator loads
    .apworld files as Python at generation time, so a swap-attack on a
    .apworld URL is RCE under `apweb`.
    """
    if not url.lower().startswith("https://"):
        raise ValueError(
            f"APWorld URL must use https:// (got: {url[:64]}...)"
        )
    req = Request(url, headers={"User-Agent": "archipelago-tools/1.0"})
    with urlopen(req, timeout=60) as resp:
        data = resp.read()
    if expected_sha:
        actual = hashlib.sha256(data).hexdigest()
        if actual.lower() != expected_sha.lower():
            raise ValueError(
                f"APWorld SHA-256 mismatch: expected "
                f"{expected_sha[:16]}..., got {actual[:16]}..."
            )
    dest.write_bytes(data)
    return dest


def list_installed(worlds_dir: Path) -> list[dict]:
    """List installed APWorld files with basic info."""
    installed = []
    if not worlds_dir.is_dir():
        return installed

    for f in sorted(worlds_dir.iterdir()):
        if f.suffix != ".apworld":
            continue
        info: dict = {"filename": f.name, "name": f.stem, "path": str(f)}
        # Check for .version sidecar file first (written by our installer)
        version_file = f.with_suffix(".version")
        if version_file.exists():
            info["version"] = version_file.read_text().strip()
        else:
            # Fallback: try to read version from the apworld zip's __init__.py
            try:
                zf = zipfile.ZipFile(f)
                for name in zf.namelist():
                    if name.endswith("/__init__.py"):
                        content = zf.read(name).decode("utf-8", errors="ignore")
                        for pattern in [
                            r'__version__\s*=\s*["\']([^"\']+)',
                            r'version\s*=\s*["\']([^"\']+)',
                        ]:
                            m = re.search(pattern, content)
                            if m:
                                info["version"] = m.group(1)
                                break
                        break
            except Exception:
                pass
        installed.append(info)

    return installed
