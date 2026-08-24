"""Reviewed APWorld editorial metadata.

The upstream Archipelago index remains the source for catalogue-native data.
This module loads AP-Pie's small, reviewed overlay separately so that a
repository README, a wiki page, or an index field can never silently become
published copy.  It deliberately does not register an API route yet: the
future route layer should consume :func:`join_index_record` after the detail
page publication policy has been implemented.

The overlay uses TOML because it is familiar to APWorld contributors, easy to
review in git, and distinct from player YAML files.  Sources describe evidence;
claims record concise, internal facts.  Neither field is a published paragraph.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import tomllib
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse


SCHEMA_VERSION = 1
CONTENT_DIR = Path(__file__).with_name("apworld_content")

REVIEW_STATES = frozenset({"draft", "reviewed", "stale", "retired"})
PUBLICATION_STATUSES = frozenset({"unpublished", "beta_preview", "published"})
COPY_STATUSES = frozenset({"not_started", "original_draft", "approved_original"})
SOURCE_KINDS = frozenset({
    "versioned_primary",
    "official_archipelago_guide",
    "maintainer_documentation",
    "miraheze_wiki",
    "community_lead",
    "ap_pie_authority",
})
ROUTE_ACTIONS = frozenset({"replace_detail_route"})
ROUTE_KINDS = frozenset({"spa", "server"})
_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")

_ROOT_KEYS = frozenset({
    "schema_version",
    "apworld_name",
    "slug",
    "review_state",
    "publication_status",
    "reviewed_by",
    "reviewed_at",
    "next_review_at",
    "editorial",
    "sources",
    "claims",
    "route",
})
_EDITORIAL_KEYS = frozenset({"copy_status", "writing_policy", "copy_reviewed_by", "copy_reviewed_at"})
_SOURCE_KEYS = frozenset({"id", "kind", "url", "revision", "verified_at"})
_CLAIM_KEYS = frozenset({"id", "topic", "fact", "source_refs", "applies_to_versions", "verified_at"})
_ROUTE_KEYS = frozenset({"action", "path", "kind"})


class EditorialValidationError(ValueError):
    """Raised when one or more reviewed metadata files fail their contract."""

    def __init__(self, errors: Iterable[str]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class EditorialSource:
    id: str
    kind: str
    url: str
    revision: str | None
    verified_at: str


@dataclass(frozen=True)
class EditorialClaim:
    id: str
    topic: str
    fact: str
    source_refs: tuple[str, ...]
    applies_to_versions: tuple[str, ...]
    verified_at: str


@dataclass(frozen=True)
class RouteOverride:
    action: str
    path: str
    kind: str


@dataclass(frozen=True)
class EditorialRecord:
    apworld_name: str
    slug: str
    review_state: str
    publication_status: str
    reviewed_by: str
    reviewed_at: str
    next_review_at: str
    copy_status: str
    sources: tuple[EditorialSource, ...]
    claims: tuple[EditorialClaim, ...]
    route: RouteOverride | None = None

    @property
    def is_public(self) -> bool:
        """Only explicitly published, currently reviewed records are public."""
        return self.review_state == "reviewed" and self.publication_status == "published"

    @property
    def is_beta_preview(self) -> bool:
        """A beta preview still requires reviewed evidence, never production use."""
        return self.review_state == "reviewed" and self.publication_status == "beta_preview"

    def public_overlay(self) -> dict[str, Any] | None:
        """Return intentionally small public data, withholding draft evidence.

        Source URLs and internal normalized claim text stay out of catalogue
        responses. A future detail renderer can use the private record to write
        original AP-Pie copy after its own approval gate.
        """
        if not self.is_public:
            return None
        return self._overlay()

    def beta_preview_overlay(self) -> dict[str, Any] | None:
        """Return a noindex preview only when the caller explicitly opts in.

        Production callers must use :meth:`public_overlay`, which cannot expose
        ``beta_preview`` records. The deployment-specific caller must also add
        noindex at the HTTP response level before rendering such a route.
        """
        if not self.is_beta_preview:
            return None
        overlay = self._overlay()
        overlay["beta_preview_only"] = True
        return overlay

    def _overlay(self) -> dict[str, Any]:
        overlay: dict[str, Any] = {
            "slug": self.slug,
            "review_state": self.review_state,
            "publication_status": self.publication_status,
            "reviewed_at": self.reviewed_at,
            "next_review_at": self.next_review_at,
        }
        if self.route:
            overlay["route_override"] = self.route.path
            overlay["route_kind"] = self.route.kind
        return overlay


def _unknown_keys(value: Mapping[str, Any], allowed: frozenset[str], label: str, errors: list[str]) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        errors.append(f"{label}: unknown field(s): {', '.join(unknown)}")


def _text(value: Any, label: str, errors: list[str], *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: expected a non-empty string")
        return None
    return value.strip()


def _iso_date(value: Any, label: str, errors: list[str]) -> str | None:
    text = _text(value, label, errors)
    if text is None:
        return None
    try:
        date.fromisoformat(text)
    except ValueError:
        errors.append(f"{label}: expected an ISO date (YYYY-MM-DD)")
        return None
    return text


def _string_list(value: Any, label: str, errors: list[str]) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        errors.append(f"{label}: expected a non-empty list of strings")
        return ()
    values: list[str] = []
    for position, item in enumerate(value):
        text = _text(item, f"{label}[{position}]", errors)
        if text:
            values.append(text)
    if len(values) != len(set(values)):
        errors.append(f"{label}: duplicate values are not allowed")
    return tuple(values)


def _http_url(value: Any, label: str, errors: list[str]) -> str | None:
    text = _text(value, label, errors)
    if text is None:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        errors.append(f"{label}: expected an absolute http(s) URL")
        return None
    return text


def _record_from_data(data: Any, path: Path) -> EditorialRecord:
    errors: list[str] = []
    label = path.as_posix()
    if not isinstance(data, dict):
        raise EditorialValidationError([f"{label}: expected a TOML table"])
    _unknown_keys(data, _ROOT_KEYS, label, errors)

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}.schema_version: expected {SCHEMA_VERSION}")
    apworld_name = _text(data.get("apworld_name"), f"{label}.apworld_name", errors)
    slug = _text(data.get("slug"), f"{label}.slug", errors)
    if slug and not _SLUG_RE.fullmatch(slug):
        errors.append(f"{label}.slug: use lowercase letters, digits, and single hyphens")
    review_state = _text(data.get("review_state"), f"{label}.review_state", errors)
    if review_state and review_state not in REVIEW_STATES:
        errors.append(f"{label}.review_state: unsupported state {review_state!r}")
    publication_status = _text(data.get("publication_status"), f"{label}.publication_status", errors)
    if publication_status and publication_status not in PUBLICATION_STATUSES:
        errors.append(f"{label}.publication_status: unsupported status {publication_status!r}")
    reviewed_by = _text(data.get("reviewed_by"), f"{label}.reviewed_by", errors)
    reviewed_at = _iso_date(data.get("reviewed_at"), f"{label}.reviewed_at", errors)
    next_review_at = _iso_date(data.get("next_review_at"), f"{label}.next_review_at", errors)
    if reviewed_at and next_review_at and next_review_at < reviewed_at:
        errors.append(f"{label}.next_review_at: cannot precede reviewed_at")

    editorial = data.get("editorial")
    copy_status: str | None = None
    if not isinstance(editorial, dict):
        errors.append(f"{label}.editorial: expected a table")
    else:
        _unknown_keys(editorial, _EDITORIAL_KEYS, f"{label}.editorial", errors)
        copy_status = _text(editorial.get("copy_status"), f"{label}.editorial.copy_status", errors)
        if copy_status and copy_status not in COPY_STATUSES:
            errors.append(f"{label}.editorial.copy_status: unsupported status {copy_status!r}")
        policy = _text(editorial.get("writing_policy"), f"{label}.editorial.writing_policy", errors)
        if policy and policy != "original-ap-pie-copy":
            errors.append(f"{label}.editorial.writing_policy: must be 'original-ap-pie-copy'")
        copy_reviewer = editorial.get("copy_reviewed_by")
        copy_reviewed_at = editorial.get("copy_reviewed_at")
        if copy_status == "approved_original":
            _text(copy_reviewer, f"{label}.editorial.copy_reviewed_by", errors)
            _iso_date(copy_reviewed_at, f"{label}.editorial.copy_reviewed_at", errors)
        elif copy_reviewer is not None or copy_reviewed_at is not None:
            errors.append(f"{label}.editorial: copy review fields require approved_original copy")

    sources_raw = data.get("sources")
    sources: list[EditorialSource] = []
    source_ids: set[str] = set()
    if not isinstance(sources_raw, list) or not sources_raw:
        errors.append(f"{label}.sources: expected at least one source table")
    else:
        for position, source in enumerate(sources_raw):
            source_label = f"{label}.sources[{position}]"
            if not isinstance(source, dict):
                errors.append(f"{source_label}: expected a table")
                continue
            _unknown_keys(source, _SOURCE_KEYS, source_label, errors)
            source_id = _text(source.get("id"), f"{source_label}.id", errors)
            if source_id and source_id in source_ids:
                errors.append(f"{source_label}.id: duplicate source id {source_id!r}")
            if source_id:
                source_ids.add(source_id)
            kind = _text(source.get("kind"), f"{source_label}.kind", errors)
            if kind and kind not in SOURCE_KINDS:
                errors.append(f"{source_label}.kind: unsupported source kind {kind!r}")
            url = _http_url(source.get("url"), f"{source_label}.url", errors)
            revision = _text(source.get("revision"), f"{source_label}.revision", errors, required=False)
            verified_at = _iso_date(source.get("verified_at"), f"{source_label}.verified_at", errors)
            if source_id and kind and url and verified_at:
                sources.append(EditorialSource(source_id, kind, url, revision, verified_at))

    claims_raw = data.get("claims", [])
    claims: list[EditorialClaim] = []
    claim_ids: set[str] = set()
    if not isinstance(claims_raw, list):
        errors.append(f"{label}.claims: expected a list of tables")
    else:
        for position, claim in enumerate(claims_raw):
            claim_label = f"{label}.claims[{position}]"
            if not isinstance(claim, dict):
                errors.append(f"{claim_label}: expected a table")
                continue
            _unknown_keys(claim, _CLAIM_KEYS, claim_label, errors)
            claim_id = _text(claim.get("id"), f"{claim_label}.id", errors)
            if claim_id and claim_id in claim_ids:
                errors.append(f"{claim_label}.id: duplicate claim id {claim_id!r}")
            if claim_id:
                claim_ids.add(claim_id)
            topic = _text(claim.get("topic"), f"{claim_label}.topic", errors)
            fact = _text(claim.get("fact"), f"{claim_label}.fact", errors)
            source_refs = _string_list(claim.get("source_refs"), f"{claim_label}.source_refs", errors)
            missing_refs = sorted(set(source_refs) - source_ids)
            if missing_refs:
                errors.append(f"{claim_label}.source_refs: unknown source id(s): {', '.join(missing_refs)}")
            applies_to_versions = _string_list(
                claim.get("applies_to_versions"), f"{claim_label}.applies_to_versions", errors
            )
            if "*" in applies_to_versions and len(applies_to_versions) > 1:
                errors.append(f"{claim_label}.applies_to_versions: '*' cannot be mixed with specific versions")
            verified_at = _iso_date(claim.get("verified_at"), f"{claim_label}.verified_at", errors)
            if claim_id and topic and fact and source_refs and applies_to_versions and verified_at:
                claims.append(EditorialClaim(claim_id, topic, fact, source_refs, applies_to_versions, verified_at))

    route_raw = data.get("route")
    route: RouteOverride | None = None
    if route_raw is not None:
        route_label = f"{label}.route"
        if not isinstance(route_raw, dict):
            errors.append(f"{route_label}: expected a table")
        else:
            _unknown_keys(route_raw, _ROUTE_KEYS, route_label, errors)
            action = _text(route_raw.get("action"), f"{route_label}.action", errors)
            if action and action not in ROUTE_ACTIONS:
                errors.append(f"{route_label}.action: unsupported action {action!r}")
            route_path = _text(route_raw.get("path"), f"{route_label}.path", errors)
            if route_path and (not route_path.startswith("/") or "?" in route_path or "#" in route_path):
                errors.append(f"{route_label}.path: use an absolute site path without query or fragment")
            route_kind = _text(route_raw.get("kind"), f"{route_label}.kind", errors)
            if route_kind and route_kind not in ROUTE_KINDS:
                errors.append(f"{route_label}.kind: expected 'spa' or 'server'")
            if action and route_path and route_kind:
                route = RouteOverride(action, route_path, route_kind)

    if review_state == "reviewed" and publication_status in {"published", "beta_preview"}:
        if copy_status != "approved_original":
            errors.append(f"{label}: publishable records require approved original AP-Pie copy")
        if not any(source.kind in {"versioned_primary", "official_archipelago_guide", "maintainer_documentation", "ap_pie_authority"} for source in sources):
            errors.append(f"{label}: publishable records require a primary, official, maintainer, or AP-Pie authority source")
    elif publication_status in {"published", "beta_preview"}:
        errors.append(f"{label}: only reviewed records may be published or previewed on beta")
    if review_state in {"stale", "retired"} and publication_status == "published":
        errors.append(f"{label}: {review_state} records cannot remain published")
    if route and not (review_state == "reviewed" and publication_status == "published"):
        errors.append(f"{label}.route: route overrides require a reviewed published record")

    if errors:
        raise EditorialValidationError(errors)
    assert apworld_name and slug and review_state and publication_status and reviewed_by and reviewed_at and next_review_at and copy_status
    return EditorialRecord(
        apworld_name=apworld_name,
        slug=slug,
        review_state=review_state,
        publication_status=publication_status,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        next_review_at=next_review_at,
        copy_status=copy_status,
        sources=tuple(sources),
        claims=tuple(claims),
        route=route,
    )


def load_reviewed_apworlds(content_dir: Path | str = CONTENT_DIR) -> dict[str, EditorialRecord]:
    """Load valid, version-controlled overlays keyed by upstream APWorld name.

    Only TOML files directly inside ``content_dir`` are loaded. Invalid fixtures
    live in a subdirectory so CI can test rejection without making the service
    unusable.  A missing file is the canonical representation of ``absent``.
    """
    root = Path(content_dir)
    records: dict[str, EditorialRecord] = {}
    slugs: set[str] = set()
    source_ids: set[str] = set()
    errors: list[str] = []
    for path in sorted(root.glob("*.toml")):
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            record = _record_from_data(data, path)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{path.as_posix()}: could not parse TOML: {exc}")
            continue
        except EditorialValidationError as exc:
            errors.extend(exc.errors)
            continue
        if record.apworld_name in records:
            errors.append(f"{path.as_posix()}: duplicate apworld_name {record.apworld_name!r}")
        if record.slug in slugs:
            errors.append(f"{path.as_posix()}: duplicate slug {record.slug!r}")
        for source in record.sources:
            if source.id in source_ids:
                errors.append(f"{path.as_posix()}: duplicate source id {source.id!r} across records")
            source_ids.add(source.id)
        records[record.apworld_name] = record
        slugs.add(record.slug)
    if errors:
        raise EditorialValidationError(errors)
    return records


def join_index_record(
    index_record: Mapping[str, Any],
    overlays: Mapping[str, EditorialRecord],
    *,
    include_beta_previews: bool = False,
) -> dict[str, Any]:
    """Keep upstream and reviewed data distinct at the integration boundary.

    The eventual ``/api/apworlds`` integration should call this after loading
    the upstream index. It returns no editorial facts for draft, stale, or
    retired entries. Beta previews require an explicit opt-in from a
    deployment-aware caller; production must keep the default. That prevents a
    beta prototype from accidentally gaining a production detail route or a
    reviewer badge.
    """
    index = dict(index_record)
    name = index.get("name")
    record = overlays.get(name) if isinstance(name, str) else None
    editorial = record.public_overlay() if record else None
    if editorial is None and include_beta_previews and record:
        editorial = record.beta_preview_overlay()
    return {
        "index": index,
        "editorial": editorial,
        "review_state": record.review_state if record else "absent",
    }
