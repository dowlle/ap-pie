"""FEAT-58: server-rendered Timberborn Archipelago section.

Same pattern as api/ctr.py: full HTML on the server, registered before the SPA
catch-all. The whole section sits behind config.FEATURES["timberborn_section"]
(on for beta, off in production until the Timberborn v0.1.0 release): while it
is off, every route here answers 404 and the section stays out of the sitemap,
llms.txt, the guides shelf and the homepage.

Release checklist for this file: set STABLE["released"] and "available", drop
`upcoming` from RELEASE_HISTORY and the release page's draft fields, fill
MOD_LISTINGS, and bump `updated` and `verified_against` on every page after
rechecking it against the tagged sources.
"""

from __future__ import annotations

import re
from pathlib import Path

from flask import Blueprint, abort, redirect, render_template, request, session

import analytics
import config
import seo
from api import project_pages, sections

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_REFERENCE_DIR = Path(__file__).resolve().parent.parent / "guides" / "timberborn-reference"

bp = Blueprint("timberborn", __name__, template_folder=str(_TEMPLATES_DIR))

FEATURE = "timberborn_section"
SECTION = "timber"


@bp.before_request
def _require_feature():
    if not config.FEATURES.get(FEATURE):
        abort(404)


MOD_REPO = "https://github.com/dowlle/timberborn-modding"
APWORLD_REPO = "https://github.com/dowlle/TimberbornArchipelago"
_GITHUB_RELEASES = f"{MOD_REPO}/releases"
_RELEASE_BASE = f"{MOD_REPO}/releases/download"
AI_DISCLOSURE_URL = f"{MOD_REPO}#ai-usage-disclosure"

OG_IMAGE = "/img/timberborn/og-timberborn.jpg"


def release_assets(version: str) -> dict:
    """GitHub asset URLs of a mod release. Every release carries the same three
    files: the mod, the APWorld and the template YAML."""
    tag = f"{_RELEASE_BASE}/v{version}"
    return {
        "mod": f"{tag}/Archipelago.zip",
        "apworld": f"{tag}/timberborn.apworld",
        "yaml": f"{tag}/Timberborn.yaml",
    }


# The stable channel. `available` stays False until the GitHub release exists;
# until then the download aliases send people to the GitHub releases page
# instead of a missing asset.
STABLE: dict = {
    "version": "0.1.0",
    "released": None,
    "available": False,
    "downloads": release_assets("0.1.0"),
}

# Releases that stay downloadable after a newer one replaces them, newest
# first, with version-pinned aliases at /timberborn/download/<version>/<asset>.
KEPT_VERSIONS: list[str] = ["0.1.0"]

# mod.io and Steam Workshop listings. None until the listing exists: the pages
# then say the listing arrives with the release instead of linking it.
MOD_LISTINGS: dict[str, str | None] = {"modio": None, "workshop": None}

ASSET_LABELS = {"mod": "Mod (Archipelago.zip)", "apworld": "APWorld", "yaml": "Template YAML"}

PAGES_UPDATED = "2026-09-28"
_DRAFT_STATUS = "Draft for 0.1.0"
_DRAFT_VERIFIED = "the 0.1.0 release candidate"

REFERENCE_PAGES: list[dict] = [
    {
        "slug": "checks",
        "title": "Checks: the AP Shop and milestones",
        "short_title": "Checks",
        "blurb": "The four shop paths, prices and tiers, why a slot is locked, scouts, and the milestones that fire as your colony grows.",
        "description": "How checks work in Timberborn Archipelago: the four-path AP Shop, science prices, tier gates, scouts, and population, well-being, survival, Wonder and resource milestones.",
        "file": "checks.md",
    },
    {
        "slug": "items",
        "title": "Items: blueprints, boosts, packages and traps",
        "short_title": "Items",
        "blurb": "What the multiworld can send you, how progressive items work, where received goods go, and what each trap does.",
        "description": "Every item in Timberborn Archipelago: blueprints and progressive items, boosts, scouts, skips, resource packages and delivery, and the three traps.",
        "file": "items.md",
    },
    {
        "slug": "goals",
        "title": "Goals and survival",
        "short_title": "Goals and survival",
        "blurb": "The seven goals, how each is counted, and which buildings logic expects before a drought or badtide.",
        "description": "The seven Timberborn Archipelago goals with their targets, how droughts, badtides and the Wonder are counted, and the survival requirements in logic.",
        "file": "goals.md",
    },
    {
        "slug": "factions",
        "title": "Folktails and Iron Teeth",
        "short_title": "Factions",
        "blurb": "Unlocking Iron Teeth, faction-only buildings, tiers, badwater and what differs between the two factions.",
        "description": "Playing Timberborn Archipelago as Folktails or Iron Teeth: unlocking Iron Teeth, faction-only buildings, shop tiers, badwater and the Wonders.",
        "file": "factions.md",
    },
    {
        "slug": "options",
        "title": "Every Timberborn option",
        "short_title": "Options",
        "blurb": "All YAML options with their values, defaults and effects, grouped by topic.",
        "description": "Every Timberborn Archipelago YAML option with its range, default and effect: goals, shop, blueprints, milestones, resource packages and traps.",
        "file": "options.md",
    },
]
for _page in REFERENCE_PAGES:
    _page.setdefault("published", PAGES_UPDATED)
    _page.setdefault("updated", PAGES_UPDATED)
    _page.setdefault("verified_against", _DRAFT_VERIFIED)
    _page.setdefault("status_label", _DRAFT_STATUS)
_REFERENCE_BY_SLUG = {page["slug"]: page for page in REFERENCE_PAGES}

RELEASE_PAGES: list[dict] = [
    {
        "slug": "0-1-0",
        "version": "0.1.0",
        "title": "What's new in 0.1.0?",
        "page_title": "Timberborn Archipelago 0.1.0 release notes",
        "short_title": "0.1.0 release notes",
        "blurb": "The first release for Timberborn 1.1: new buildings, starting blueprints, trap and delivery options, survival logic and many fixes.",
        "description": "Everything new in Timberborn Archipelago 0.1.0: Timberborn 1.1 support, ten new buildings, starting blueprints, trap weights, goods delivery, survival logic and fixes.",
        "file": "0-1-0-release-notes.md",
        "published": PAGES_UPDATED,
        "updated": PAGES_UPDATED,
        "verified_against": "0.1.0",
        "status_label": "Draft release notes",
        "draft_notice": "Draft: these notes are for the upcoming 0.1.0 release and can still change before it is published.",
        "og_image": OG_IMAGE,
        "og_image_width": 1200,
        "og_image_height": 630,
        "og_image_alt": "A Folktails colony in Timberborn Archipelago, with farms along a river and the AP Log on the right",
    },
]
_RELEASE_BY_SLUG = {page["slug"]: page for page in RELEASE_PAGES}

# Releases on /timberborn/releases, newest first. The list starts at 0.1.0,
# the first release for Timberborn 1.1; the pre-alpha builds stay on GitHub.
RELEASE_HISTORY: list[dict] = [
    {"version": "0.1.0", "date": "", "notes": "/timberborn/releases/0-1-0", "upcoming": True,
     "summary": "The first release for Timberborn 1.1, with new buildings, starting blueprints, trap and delivery options and survival logic."},
]

# Consumed by api/guides.py for /sitemap.xml and /llms.txt.
TIMBERBORN_PAGES: list[dict] = [
    {"path": "/timberborn", "title": "Timberborn Archipelago",
     "blurb": "Timberborn as an Archipelago randomizer: the tech tree is spread across the multiworld."},
    {"path": "/timberborn/download", "title": "Download Timberborn Archipelago",
     "blurb": "The mod, the APWorld and the template YAML for the current release."},
    {"path": "/timberborn/reference", "title": "How Timberborn Archipelago works",
     "blurb": "The AP Shop, items, goals, factions and every option."},
    *[{"path": f"/timberborn/reference/{p['slug']}", "title": p["title"], "blurb": p["blurb"],
       "lastmod": p["updated"]} for p in REFERENCE_PAGES],
    {"path": "/timberborn/releases", "title": "Timberborn Archipelago releases",
     "blurb": "Every Timberborn Archipelago release with its release notes."},
    *[{"path": f"/timberborn/releases/{p['slug']}", "title": p["page_title"], "blurb": p["blurb"],
       "lastmod": p["updated"]} for p in RELEASE_PAGES],
]

TIMBERBORN_FAQ: list[dict] = [
    {"q": "Which version of Timberborn do I need?",
     "a_html": "Timberborn 1.1. The mod is built for 1.1; earlier game versions are not supported."},
    {"q": "Do players need to install the APWorld?",
     "a_html": "No. Only the person who generates the multiworld installs the APWorld. Players need the mod, their YAML and the room details. See the <a href=\"/timberborn/setup\">setup guide</a>."},
    {"q": "Can I play Iron Teeth?",
     "a_html": "Yes. Set the faction in your YAML and start an Iron Teeth colony. The mod unlocks Iron Teeth for you, so you don't need to reach well-being 8 with Folktails first. See <a href=\"/timberborn/reference/factions\">Factions</a>."},
    {"q": "How long is a game?",
     "a_html": "That depends on your goal. The default, completing your faction's Wonder, needs shop tier 4 and the Wonder's production chains, so it makes a long game. Population, Well-being or Droughts with a lower target make a shorter game. See <a href=\"/timberborn/reference/goals\">Goals and survival</a>."},
    {"q": "Is it free?",
     "a_html": "Yes. The mod and the APWorld are free and open source under the MIT licence, on <a href=\"https://github.com/dowlle/timberborn-modding\" rel=\"noopener noreferrer\">GitHub</a>. You need your own copy of Timberborn."},
    {"q": "Something went wrong. Where do I get help?",
     "a_html": "Open an issue on <a href=\"https://github.com/dowlle/timberborn-modding/issues\" rel=\"noopener noreferrer\">GitHub</a> with your faction, the mod version and what happened. Bug reports for the APWorld go there too."},
]


def _canonical(path: str) -> str:
    return project_pages.canonical(path)


def _view(page: str) -> None:
    analytics.record_event(
        "timberborn_view",
        user_id=session.get("user_id"),
        props={"page": page, "from_path": analytics.entry_path(request)},
        req=request,
    )


def _section(path: str, title: str) -> dict:
    return sections.context(SECTION, path, title)


def _stable_notes() -> str:
    return next(
        (f"/timberborn/releases/{p['slug']}" for p in RELEASE_PAGES if p["version"] == STABLE["version"]),
        "/timberborn/releases",
    )


def _software_node() -> dict:
    node = {
        "@type": "SoftwareApplication",
        "@id": f"{_canonical('/timberborn')}#software",
        "name": "Timberborn Archipelago",
        "description": (
            "A Timberborn mod and APWorld that make Timberborn a game in "
            "Archipelago multiworld randomizers."
        ),
        "url": _canonical("/timberborn"),
        "applicationCategory": "GameApplication",
        "softwareVersion": STABLE["version"],
        "image": _canonical(OG_IMAGE),
        "downloadUrl": [_canonical("/timberborn/download/mod")],
        "publisher": {"@id": seo.organization_id(config.PUBLIC_BASE_URL)},
        "isPartOf": {"@id": seo.website_id(config.PUBLIC_BASE_URL)},
    }
    if STABLE["released"]:
        node["datePublished"] = STABLE["released"]
    return node


def _faq_node(url: str) -> dict:
    return {
        "@type": "FAQPage",
        "@id": f"{url}#faq",
        "isPartOf": {"@id": f"{url}#page"},
        "inLanguage": "en",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", item["a_html"])},
            }
            for item in TIMBERBORN_FAQ
        ],
    }


def _common(page_title: str, description: str, canonical_url: str) -> dict:
    return {
        "stable": STABLE,
        "stable_notes": _stable_notes(),
        "listings": MOD_LISTINGS,
        "ai_disclosure_url": AI_DISCLOSURE_URL,
        "mod_repo": MOD_REPO,
        "page_title": page_title,
        "meta_description": description,
        "canonical_url": canonical_url,
        "og_type": "website",
        "og_image": _canonical(OG_IMAGE),
        "og_image_width": 1200,
        "og_image_height": 630,
        "og_image_alt": "A Folktails colony in Timberborn Archipelago, with farms along a river and the AP Log on the right",
        "site_url": _canonical("/"),
    }


@bp.route("/timberborn", strict_slashes=False)
def timberborn_landing() -> str:
    _view("landing")
    canonical_url = _canonical("/timberborn")
    title = "Timberborn Archipelago | Archipelago Pie"
    description = (
        "Play Timberborn in an Archipelago multiworld: the tech tree is spread "
        "across other players' games, and you buy checks with science."
    )
    page_node = seo.page(config.PUBLIC_BASE_URL, "WebPage", canonical_url, title, description)
    page_node["mainEntity"] = {"@id": f"{canonical_url}#software"}
    nav = _section("/timberborn", "Timberborn Archipelago")
    return render_template(
        "timberborn/landing.html",
        **nav,
        **_common(title, description, canonical_url),
        faq=TIMBERBORN_FAQ,
        reference_pages=REFERENCE_PAGES,
        latest_release=RELEASE_PAGES[0],
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL, page_node, _software_node(), nav["breadcrumb_node"], _faq_node(canonical_url),
        ),
    )


@bp.route("/timberborn/download", strict_slashes=False)
def timberborn_download() -> str:
    _view("download")
    canonical_url = _canonical("/timberborn/download")
    title = "Download Timberborn Archipelago | Archipelago Pie"
    description = (
        "Download the Timberborn Archipelago mod, APWorld and template YAML, "
        "then follow the setup guide to join a multiworld."
    )
    page_node = seo.page(config.PUBLIC_BASE_URL, "WebPage", canonical_url, title, description)
    page_node["mainEntity"] = {"@id": f"{_canonical('/timberborn')}#software"}
    nav = _section("/timberborn/download", "Download")
    older = [
        {
            "version": version,
            "notes": next((f"/timberborn/releases/{p['slug']}" for p in RELEASE_PAGES if p["version"] == version),
                          f"{_GITHUB_RELEASES}/tag/v{version}"),
        }
        for version in KEPT_VERSIONS
        if version != STABLE["version"]
    ]
    return render_template(
        "timberborn/download.html",
        **nav,
        **_common(title, description, canonical_url),
        older_versions=older,
        github_releases=_GITHUB_RELEASES,
        structured_data=seo.graph(config.PUBLIC_BASE_URL, page_node, _software_node(), nav["breadcrumb_node"]),
    )


def _asset_redirect(version: str, asset: str):
    url = release_assets(version).get(asset)
    if url is None:
        abort(404)
    if not STABLE["available"] and version == STABLE["version"]:
        # The GitHub release does not exist yet: send people to the release
        # list instead of a missing file.
        url = _GITHUB_RELEASES
    analytics.record_event(
        "timberborn_download",
        user_id=session.get("user_id"),
        props={"asset": asset, "version": version, "from_path": analytics.entry_path(request)},
        req=request,
    )
    return redirect(url, code=302)


@bp.route("/timberborn/download/<asset>")
def timberborn_download_redirect(asset: str):
    return _asset_redirect(STABLE["version"], asset)


@bp.route("/timberborn/download/<version>/<asset>")
def timberborn_download_version_redirect(version: str, asset: str):
    if version not in KEPT_VERSIONS:
        abort(404)
    return _asset_redirect(version, asset)


@bp.route("/timberborn/reference", strict_slashes=False)
def timberborn_reference_index() -> str:
    _view("reference")
    canonical_url = _canonical("/timberborn/reference")
    title = "How Timberborn Archipelago works | Archipelago Pie"
    description = (
        "How Timberborn Archipelago changes Timberborn: the AP Shop and milestones, "
        "items and traps, goals and survival, factions and every option."
    )
    nav = _section("/timberborn/reference", "How it works")
    return render_template(
        "timberborn/reference-index.html",
        **nav,
        **_common(title, description, canonical_url),
        pages=REFERENCE_PAGES,
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL,
            seo.page(config.PUBLIC_BASE_URL, "CollectionPage", canonical_url, title, description),
            nav["breadcrumb_node"],
        ),
    )


def _article(page: dict, path: str, title_suffix: str, analytics_page: str) -> str:
    return project_pages.article_page(
        section_key=SECTION,
        content_dir=_REFERENCE_DIR,
        page=page,
        path=path,
        title_suffix=title_suffix,
        event="timberborn_view",
        analytics_page=analytics_page,
        default_image=OG_IMAGE,
        pager_back={"path": "/timberborn/reference", "label": "How it works"},
    )


@bp.route("/timberborn/reference/<slug>", strict_slashes=False)
def timberborn_reference_page(slug: str):
    page = _REFERENCE_BY_SLUG.get(slug)
    if page is None:
        abort(404)
    return _article(page, f"/timberborn/reference/{slug}", "Timberborn Archipelago", f"reference/{slug}")


@bp.route("/timberborn/releases", strict_slashes=False)
def timberborn_releases_index() -> str:
    _view("releases")
    canonical_url = _canonical("/timberborn/releases")
    title = "Timberborn Archipelago releases | Archipelago Pie"
    description = "Every Timberborn Archipelago release from 0.1.0 on, with its date and release notes."
    nav = _section("/timberborn/releases", "Releases")
    return render_template(
        "project/releases-index.html",
        **nav,
        **_common(title, description, canonical_url),
        releases=RELEASE_HISTORY,
        releases_heading="Timberborn Archipelago releases",
        download_path="/timberborn/download",
        releases_lede_html=(
            "Every release from 0.1.0 on, newest first. 0.1.0 is the first release for "
            "Timberborn 1.1. Get the current release from the "
            "<a href=\"/timberborn/download\">download page</a>."
        ),
        releases_footer_html=(
            "The earlier pre-alpha test builds were made for Timberborn 1.0 and are still on "
            f"<a href=\"{_GITHUB_RELEASES}\" rel=\"noopener noreferrer\">GitHub</a>."
        ),
        test_builds_url=None,
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL,
            seo.page(config.PUBLIC_BASE_URL, "CollectionPage", canonical_url, title, description),
            nav["breadcrumb_node"],
        ),
    )


@bp.route("/timberborn/releases/<slug>", strict_slashes=False)
def timberborn_release_page(slug: str):
    page = _RELEASE_BY_SLUG.get(slug)
    if page is None:
        abort(404)
    return _article(page, f"/timberborn/releases/{slug}", "Archipelago Pie", f"releases/{slug}")
