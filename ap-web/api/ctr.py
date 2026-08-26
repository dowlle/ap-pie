"""FEAT-40: server-rendered CTR Archipelago section.

Same pattern as api/guides.py: these routes are NOT part of the React SPA.
They render full HTML on the server so search engines and AI answer systems
get complete content, a real <title>, meta description, canonical URL, and
Open Graph tags without executing any JavaScript. The blueprint is registered
before the SPA catch-all in app.py, so these paths win over the client-side
router.

The download routes exist so that tutorials, video descriptions, and Discord
pins can link a stable URL (/ctr/download/windows) that never goes stale:
the redirect target moves to the new artifact when a release ships, the
public URL does not.
"""

from __future__ import annotations

from pathlib import Path

import markdown
from flask import Blueprint, abort, redirect, render_template, request, session

import analytics
import config
import seo

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_REFERENCE_DIR = Path(__file__).resolve().parent.parent / "guides" / "ctr-reference"

bp = Blueprint("ctr", __name__, template_folder=str(_TEMPLATES_DIR))


_RELEASE_BASE = "https://github.com/dowlle/ctr-native-ap/releases/download"

# The stable channel. Updating this dict is a manual step on the CTR release
# checklist: bump version/released and point the asset URLs at the new GitHub
# Release. The visible page version and the redirect targets both read from
# here so they cannot drift apart.
STABLE: dict = {
    "version": "0.1.5",
    "released": "2026-08-06",
    "downloads": {
        "windows": f"{_RELEASE_BASE}/v0.1.5/ctr-archipelago-v0.1.5-windows-x86.zip",
        "linux": f"{_RELEASE_BASE}/v0.1.5/ctr-archipelago-v0.1.5-linux-x86.tar.gz",
        "apworld": f"{_RELEASE_BASE}/v0.1.5/ctr.apworld",
        "template": f"{_RELEASE_BASE}/v0.1.5/Crash.Team.Racing.yaml",
    },
}

# The testing channel. None hides the testing card on /ctr/download. When a
# pre-release tag exists on GitHub, set this to e.g.
#   {"version": "0.2.0-pre1", "url": "https://github.com/dowlle/ctr-native-ap/releases/tag/v0.2.0-pre1"}
# and the card renders with the client/seed compatibility warning. Testing
# builds deliberately get no stable redirect aliases: stable URLs are for
# tutorials, and tutorials only ever reference the stable channel.
PRERELEASE: dict | None = {
    "version": "0.2.0 Alpha 4",
    "url": "https://github.com/dowlle/ctr-archipelago-apworld/releases/tag/v0.2.0-alpha4",
}

# Bump when page content materially changes; feeds the sitemap lastmod.
PAGES_UPDATED = "2026-08-26"

REFERENCE_PAGES: list[dict] = [
    {
        "slug": "0-2-0-release-notes",
        "title": "What changed in 0.2.0?",
        "short_title": "0.2.0 release notes",
        "blurb": "The complete player-facing changelog from 0.1.5 through the current 0.2.0 Alpha 4 preview.",
        "description": "A player-first guide to every major CTR Archipelago change since 0.1.5, including new checks, racers, kart progression, goals and Alpha 4 testing.",
        "file": "0-2-0-release-notes.md",
        "published": "2026-08-25",
        "updated": "2026-08-26",
        "verified_against": "0.2.0 Alpha 4",
        "status_label": "Full release notes",
    },
    {
        "slug": "warp-pads",
        "title": "Warp pads and requirements",
        "short_title": "Warp pads",
        "blurb": "How to read a pad, why routes change, and what happens when a requirement is met.",
        "description": "Learn how randomized warp-pad requirements work in CTR Archipelago and how to read the icons shown above each pad.",
        "file": "warp-pads.md",
        "published": "2026-08-20",
        "updated": "2026-08-20",
        "verified_against": "0.2.0 Alpha 4",
        "status_label": "0.2.0 preview",
    },
    {
        "slug": "progression",
        "title": "Progression and kart upgrades",
        "short_title": "Progression",
        "blurb": "What arrives as an item, what opens the Adventure hubs, and how Progressive Stats work.",
        "description": "Understand item progression, kart upgrades, Progressive Boost and Progressive Stats in CTR Archipelago.",
        "file": "progression.md",
        "published": "2026-08-20",
        "updated": "2026-08-20",
        "verified_against": "0.2.0 Alpha 4",
        "status_label": "0.2.0 preview",
    },
    {
        "slug": "randomized-content",
        "title": "What can be randomized?",
        "short_title": "Randomized content",
        "blurb": "A player-first map of progression, checks, characters, kart capabilities, traps, and goals.",
        "description": "See which parts of Crash Team Racing can change in a CTR Archipelago world, from warp pads and locations to kart capabilities.",
        "file": "randomized-content.md",
        "published": "2026-08-20",
        "updated": "2026-08-20",
        "verified_against": "0.2.0 Alpha 4",
        "status_label": "0.2.0 preview",
    },
]

_REFERENCE_BY_SLUG = {page["slug"]: page for page in REFERENCE_PAGES}

# Consumed by api/guides.py for /sitemap.xml and /llms.txt so the CTR section
# never goes stale in either surface separately.
CTR_PAGES: list[dict] = [
    {
        "path": "/ctr",
        "title": "CTR Archipelago",
        "blurb": "Crash Team Racing as a native Archipelago randomizer, no emulator involved.",
    },
    {
        "path": "/ctr/download",
        "title": "Download CTR Archipelago",
        "blurb": "Current stable CTR Archipelago downloads for Windows and Linux.",
    },
    {
        "path": "/ctr/reference",
        "title": "CTR Archipelago reference",
        "blurb": "How randomized warp pads, progression, kart upgrades, and other non-vanilla systems work.",
    },
    *[
        {
            "path": f"/ctr/reference/{page['slug']}",
            "title": page["title"],
            "blurb": page["blurb"],
        }
        for page in REFERENCE_PAGES
    ],
]


def _canonical(path: str) -> str:
    return f"{config.PUBLIC_BASE_URL}{path}"


def _render_reference_markdown(md_path: Path) -> tuple[str, list[dict]]:
    text = md_path.read_text(encoding="utf-8")
    renderer = markdown.Markdown(extensions=["toc"], output_format="html")
    html = renderer.convert(text)
    sections = [
        {"id": token["id"], "name": token["name"]}
        for token in renderer.toc_tokens
        if token["level"] == 2
    ]
    return html, sections


def _software_node() -> dict:
    return {
        "@type": "SoftwareApplication",
        "@id": f"{_canonical('/ctr')}#software",
        "name": "CTR Archipelago",
        "description": (
            "A native Crash Team Racing client and randomizer integration for "
            "Archipelago multiworld games."
        ),
        "url": _canonical("/ctr"),
        "applicationCategory": "GameApplication",
        "operatingSystem": ["Windows", "Linux", "SteamOS"],
        "softwareVersion": STABLE["version"],
        "datePublished": STABLE["released"],
        "image": _canonical("/img/ctr/og-ctr.jpg"),
        "downloadUrl": [
            _canonical("/ctr/download/windows"),
            _canonical("/ctr/download/linux"),
        ],
        "publisher": {"@id": seo.organization_id(config.PUBLIC_BASE_URL)},
        "isPartOf": {"@id": seo.website_id(config.PUBLIC_BASE_URL)},
    }


def _breadcrumb(path: str, name: str, include_download: bool = False) -> dict:
    items = [
        {"@type": "ListItem", "position": 1, "name": "Archipelago Pie", "item": _canonical("/")},
        {"@type": "ListItem", "position": 2, "name": "CTR Archipelago", "item": _canonical("/ctr")},
    ]
    if include_download:
        items.append({"@type": "ListItem", "position": 3, "name": name, "item": _canonical(path)})
    return {
        "@type": "BreadcrumbList",
        "@id": f"{_canonical(path)}#breadcrumb",
        "itemListElement": items,
    }


@bp.route("/ctr", strict_slashes=False)
def ctr_landing() -> str:
    analytics.record_event(
        "ctr_view",
        user_id=session.get("user_id"),
        props={"page": "landing", "from_path": analytics.entry_path(request)},
        req=request,
    )
    canonical_url = _canonical("/ctr")
    description = (
        "Play Crash Team Racing in an Archipelago multiworld. Race for progression, "
        "exchange items with other games, and skip the emulator."
    )
    page_node = seo.page(
        config.PUBLIC_BASE_URL,
        "WebPage",
        canonical_url,
        "Crash Team Racing Archipelago | Archipelago Pie",
        description,
    )
    page_node["mainEntity"] = {"@id": f"{canonical_url}#software"}
    return render_template(
        "ctr/landing.html",
        stable=STABLE,
        page_title="Crash Team Racing Archipelago | Archipelago Pie",
        meta_description=description,
        canonical_url=canonical_url,
        og_type="website",
        og_image=_canonical("/img/ctr/og-ctr.jpg"),
        site_url=_canonical("/"),
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL,
            page_node,
            _software_node(),
            _breadcrumb("/ctr", "CTR Archipelago"),
        ),
    )


@bp.route("/ctr/download", strict_slashes=False)
def ctr_download() -> str:
    analytics.record_event(
        "ctr_view",
        user_id=session.get("user_id"),
        props={"page": "download", "from_path": analytics.entry_path(request)},
        req=request,
    )
    canonical_url = _canonical("/ctr/download")
    description = (
        "Download the latest CTR Archipelago client for Windows, Linux, or Steam Deck, "
        "then follow the setup guide to join a multiworld."
    )
    page_node = seo.page(
        config.PUBLIC_BASE_URL,
        "WebPage",
        canonical_url,
        "Download CTR Archipelago | Archipelago Pie",
        description,
    )
    page_node["mainEntity"] = {"@id": f"{_canonical('/ctr')}#software"}
    return render_template(
        "ctr/download.html",
        stable=STABLE,
        prerelease=PRERELEASE,
        page_title="Download CTR Archipelago | Archipelago Pie",
        meta_description=description,
        canonical_url=canonical_url,
        og_type="website",
        og_image=_canonical("/img/ctr/og-ctr.jpg"),
        site_url=_canonical("/"),
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL,
            page_node,
            _software_node(),
            _breadcrumb("/ctr/download", "Download CTR Archipelago", include_download=True),
        ),
    )


@bp.route("/ctr/download/<platform>")
def ctr_download_redirect(platform: str):
    url = STABLE["downloads"].get(platform)
    if url is None:
        abort(404)
    # FEAT-31: the conversion event for the whole CTR section. These are the
    # stable aliases tutorials and video descriptions point at, so this also
    # shows which channel sends people here.
    analytics.record_event(
        "ctr_download",
        user_id=session.get("user_id"),
        props={
            "asset": platform,
            "version": STABLE["version"],
            "from_path": analytics.entry_path(request),
        },
        req=request,
    )
    return redirect(url, code=302)


@bp.route("/ctr/wiki", strict_slashes=False)
def ctr_wiki_redirect():
    return redirect("/ctr/reference", code=301)


@bp.route("/ctr/reference", strict_slashes=False)
def ctr_reference_index() -> str:
    analytics.record_event(
        "ctr_view",
        user_id=session.get("user_id"),
        props={"page": "reference", "from_path": analytics.entry_path(request)},
        req=request,
    )
    return render_template(
        "ctr/reference-index.html",
        pages=REFERENCE_PAGES,
        stable=STABLE,
        page_title="CTR Archipelago reference | Archipelago Pie",
        meta_description=(
            "Learn how CTR Archipelago changes Crash Team Racing, including "
            "randomized warp pads, progression, kart upgrades, and checks."
        ),
        canonical_url=_canonical("/ctr/reference"),
        og_type="website",
        og_image=_canonical("/img/ctr/og-ctr.jpg"),
        site_url=_canonical("/"),
    )


@bp.route("/ctr/reference/<slug>")
def ctr_reference_page(slug: str) -> str:
    page = _REFERENCE_BY_SLUG.get(slug)
    if page is None:
        abort(404)
    md_path = _REFERENCE_DIR / page["file"]
    if not md_path.is_file():
        abort(404)
    body_html, sections = _render_reference_markdown(md_path)
    analytics.record_event(
        "ctr_view",
        user_id=session.get("user_id"),
        props={"page": f"reference/{slug}", "from_path": analytics.entry_path(request)},
        req=request,
    )
    related = [candidate for candidate in REFERENCE_PAGES if candidate["slug"] != slug]
    return render_template(
        "ctr/reference-page.html",
        page=page,
        related=related,
        body_html=body_html,
        sections=sections,
        page_title=f"{page['title']} | CTR Archipelago reference",
        meta_description=page["description"],
        canonical_url=_canonical(f"/ctr/reference/{slug}"),
        og_type="article",
        og_image=_canonical("/img/ctr/og-ctr.jpg"),
        site_url=_canonical("/"),
    )
