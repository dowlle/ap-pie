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

import json
import re
from pathlib import Path

import markdown
from flask import Blueprint, abort, redirect, render_template, request, session

import analytics
import config
import seo
from api import sections

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_REFERENCE_DIR = Path(__file__).resolve().parent.parent / "guides" / "ctr-reference"

bp = Blueprint("ctr", __name__, template_folder=str(_TEMPLATES_DIR))


_RELEASE_BASE = "https://github.com/dowlle/ctr-native-ap/releases/download"

# The stable channel. Updating this dict is a manual step on the CTR release
# checklist: bump version/released and point the asset URLs at the new GitHub
# Release. The visible page version and the redirect targets both read from
# here so they cannot drift apart.
STABLE: dict = {
    "version": "0.2.0",
    "released": "2026-09-10",
    "downloads": {
        "windows": f"{_RELEASE_BASE}/v0.2.0/ctr-archipelago-v0.2.0-windows-x86.zip",
        "linux": f"{_RELEASE_BASE}/v0.2.0/ctr-archipelago-v0.2.0-linux-x86.tar.gz",
        "apworld": f"{_RELEASE_BASE}/v0.2.0/ctr.apworld",
        "template": f"{_RELEASE_BASE}/v0.2.0/Crash.Team.Racing.yaml",
    },
}

# The testing channel. None hides the testing card on /ctr/download. When a
# pre-release tag exists on GitHub, set this to e.g.
#   {"version": "0.2.0-pre1", "url": "https://github.com/dowlle/ctr-native-ap/releases/tag/v0.2.0-pre1"}
# and the card renders with the client/seed compatibility warning. Testing
# builds deliberately get no stable redirect aliases: stable URLs are for
# tutorials, and tutorials only ever reference the stable channel.
PRERELEASE: dict | None = None

# Bump when page content materially changes; feeds the sitemap lastmod.
PAGES_UPDATED = "2026-09-25"

REFERENCE_PAGES: list[dict] = [
    {
        "slug": "warp-pads",
        "title": "Warp pads and requirements",
        "short_title": "Warp pads",
        "blurb": "How to read a pad, why routes change, and what happens when a requirement is met.",
        "description": "Learn how randomized warp-pad requirements work in CTR Archipelago and how to read the icons shown above each pad.",
        "file": "warp-pads.md",
        "published": "2026-08-20",
        "updated": "2026-09-25",
        "verified_against": "0.2.0",
        "status_label": "Current stable",
    },
    {
        "slug": "progression",
        "title": "Progression and kart upgrades",
        "short_title": "Progression",
        "blurb": "What arrives as an item, what opens the Adventure hubs, and how Progressive Stats work.",
        "description": "Understand item progression, kart upgrades, Progressive Boost and Progressive Stats in CTR Archipelago.",
        "file": "progression.md",
        "published": "2026-08-20",
        "updated": "2026-09-25",
        "verified_against": "0.2.0",
        "status_label": "Current stable",
    },
    {
        "slug": "randomized-content",
        "title": "What can be randomized?",
        "short_title": "Randomized content",
        "blurb": "Choose which rewards, racers, kart upgrades, traps and goals appear in your world.",
        "description": "See which parts of Crash Team Racing can change in a CTR Archipelago world, from warp pads and locations to kart capabilities.",
        "file": "randomized-content.md",
        "published": "2026-08-20",
        "updated": "2026-09-11",
        "verified_against": "0.2.0",
        "status_label": "Current stable",
    },
]

_REFERENCE_BY_SLUG = {page["slug"]: page for page in REFERENCE_PAGES}

# Release notes, newest first. They moved from /ctr/reference/<slug> to
# /ctr/releases/<slug> on 2026-09-25; RELEASE_REDIRECTS keeps the old URLs
# answering with a permanent redirect so links and search results carry over.
RELEASE_PAGES: list[dict] = [
    {
        "slug": "0-2-1",
        "title": "What changed in 0.2.1?",
        "page_title": "CTR Archipelago 0.2.1 release notes",
        "short_title": "0.2.1 release notes",
        "blurb": "Everything new since 0.2.0: Hit Character, Slide Coliseum and Turbo Track races, Cortex Vortex, the Adventure tracker and room links.",
        "description": "Everything new in CTR Archipelago 0.2.1: Hit Character checks, trial track races, Cortex Vortex, the in-game Adventure tracker, room links on Windows, item box colours and logic fixes.",
        "file": "0-2-1-release-notes.md",
        "published": "2026-09-25",
        "updated": "2026-09-25",
        "verified_against": "0.2.1",
        # Draft until the GitHub release is published; then "Full release notes".
        "status_label": "Upcoming release",
    },
    {
        "slug": "0-2-0",
        "title": "What changed in 0.2.0?",
        "page_title": "CTR Archipelago 0.2.0 release notes",
        "short_title": "0.2.0 release notes",
        "blurb": "The complete player-facing changelog from 0.1.5 to stable 0.2.0, with setup, videos and known limitations.",
        "description": "Everything new in CTR Archipelago 0.2.0: checks, racers, kart progression, twenty traps, goals, experimental recorded AI and community testing.",
        "file": "0-2-0-release-notes.md",
        "published": "2026-08-25",
        "updated": "2026-09-25",
        "verified_against": "0.2.0",
        "status_label": "Full release notes",
    },
]
_RELEASE_BY_SLUG = {page["slug"]: page for page in RELEASE_PAGES}
RELEASE_REDIRECTS = {"0-2-0-release-notes": "/ctr/releases/0-2-0"}

# Stable releases for /ctr/releases, newest first. `notes` is the page on
# this site when one exists, otherwise the GitHub release. Summaries are the
# release titles from GitHub. Test builds are linked as a group, not listed.
# `upcoming` marks a release whose notes are up before the GitHub release is
# published; drop it and bump STABLE when the release goes out.
_GITHUB_RELEASES = "https://github.com/dowlle/ctr-native-ap/releases"
RELEASE_HISTORY: list[dict] = [
    {"version": "0.2.1", "date": "2026-09-25", "notes": "/ctr/releases/0-2-1", "upcoming": True,
     "summary": "Hit Character checks, trial track races, Cortex Vortex, the Adventure tracker and room links."},
    {"version": "0.2.0", "date": "2026-09-10", "notes": "/ctr/releases/0-2-0",
     "summary": "Stable release: new checks, racers, kart progression, twenty traps and more goals."},
    {"version": "0.1.5", "date": "2026-08-06", "notes": f"{_GITHUB_RELEASES}/tag/v0.1.5",
     "summary": "Other players' items show as the Archipelago logo on the warp pads."},
    {"version": "0.1.4", "date": "2026-07-23", "notes": f"{_GITHUB_RELEASES}/tag/v0.1.4",
     "summary": "The smoother-ride patch."},
    {"version": "0.1.3", "date": "2026-07-21", "notes": f"{_GITHUB_RELEASES}/tag/v0.1.3",
     "summary": "The correctness patch."},
    {"version": "0.1.2", "date": "2026-07-20", "notes": f"{_GITHUB_RELEASES}/tag/v0.1.2",
     "summary": "Position checks in logic, Universal Tracker, and the Steam Deck."},
    {"version": "0.1.1", "date": "2026-07-17", "notes": f"{_GITHUB_RELEASES}/tag/v0.1.1",
     "summary": "Fixes from the wild, DeathLink, one-lap cups."},
    {"version": "0.1.0", "date": "2026-07-15", "notes": f"{_GITHUB_RELEASES}/tag/v0.1.0",
     "summary": "First public release."},
]

# AP box location pictures. Generated by scripts/import_ctr_ap_boxes.py from
# the CTR editor render manifest; the pictures live under /img/ctr/ap-boxes/.
AP_BOXES_PUBLISHED = "2026-09-24"
AP_BOXES_UPDATED = "2026-09-24"
AP_BOX_TRACKS: list[dict] = json.loads(
    (_REFERENCE_DIR / "ap-boxes.json").read_text(encoding="utf-8")
)["tracks"]
_AP_BOX_TRACK_BY_SLUG = {track["slug"]: track for track in AP_BOX_TRACKS}
AP_BOX_MAP_CAPTION = (
    "Map seen from above. Select a number to jump to that box. Orange arrows show "
    "the driving direction; lighter road is higher up."
)
AP_BOX_TOTAL = sum(len(track["boxes"]) for track in AP_BOX_TRACKS)

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
    {
        "path": "/ctr/releases",
        "title": "CTR Archipelago releases",
        "blurb": "Every stable CTR Archipelago release with its date and release notes.",
    },
    *[
        {
            "path": f"/ctr/releases/{page['slug']}",
            "title": page["title"],
            "blurb": page["blurb"],
            "lastmod": page["updated"],
        }
        for page in RELEASE_PAGES
    ],
    {
        "path": "/ctr/reference/ap-boxes",
        "title": "CTR AP box locations",
        "blurb": "A picture of every AP item box on all 18 CTR tracks.",
        "lastmod": AP_BOXES_UPDATED,
    },
    *[
        {
            "path": f"/ctr/reference/ap-boxes/{track['slug']}",
            "title": f"{track['name']} AP box locations",
            "blurb": f"Pictures of all {len(track['boxes'])} AP item boxes on {track['name']}.",
            "lastmod": AP_BOXES_UPDATED,
        }
        for track in AP_BOX_TRACKS
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


# Questions on /ctr. `a_html` is shown on the page; the FAQPage structured
# data uses the same answer with the tags removed, so the two cannot differ.
CTR_FAQ: list[dict] = [
    {"q": "Do I need an emulator?",
     "a_html": "No. CTR Archipelago is a native PC game built on the community decompilation of Crash Team Racing. It connects to your Archipelago room by itself, without an emulator, ROM patching or a separate client."},
    {"q": "Which disc do I need?",
     "a_html": "A disc image of your own North American (NTSC-U) Crash Team Racing disc: a <code>.bin</code>, a <code>.cue</code> with its <code>.bin</code>, or a <code>.chd</code>. The European and Japanese releases are refused, and no game data is included."},
    {"q": "Does it run on Linux and Steam Deck?",
     "a_html": "Yes. There is a Linux build next to the Windows one. On Steam Deck, add the game to Steam and start it from Gaming Mode; the on-screen keyboard opens when you select a connection field."},
    {"q": "Do players need to install the APWorld?",
     "a_html": "No. Only the person who generates the multiworld installs the APWorld. Players need the game client, their disc image and the room details. See the <a href=\"/ctr/setup\">setup guide</a>."},
    {"q": "Is it free?",
     "a_html": "Yes. CTR Archipelago is free and open source under the GPL-3.0 licence, on <a href=\"https://github.com/dowlle/ctr-native-ap\" rel=\"noopener noreferrer\">GitHub</a>. You need your own copy of the game."},
    {"q": "Can I play Crash Team Racing on PC without the randomizer?",
     "a_html": "Yes. <a href=\"/ctr/play-on-pc\">Play Crash Team Racing on PC</a> explains how to run the plain game natively."},
    {"q": "Something went wrong. Where do I get help?",
     "a_html": "Run <code>support-bundle.bat</code> (Windows) or <code>support-bundle.sh</code> (Linux) next to the game, then attach the archive to a <a href=\"https://github.com/dowlle/ctr-native-ap/issues/new/choose\" rel=\"noopener noreferrer\">GitHub issue</a> or bring it to the Crash Team Racing channel on the Archipelago Discord."},
]


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
            for item in CTR_FAQ
        ],
    }


def _section(path: str, title: str, extra: list[tuple[str, str]] | None = None) -> dict:
    return sections.context("ctr", path, title, extra)


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
    nav = _section("/ctr", "CTR Archipelago")
    return render_template(
        "ctr/landing.html",
        **nav,
        faq=CTR_FAQ,
        latest_release=next(p for p in RELEASE_PAGES if p["verified_against"] == STABLE["version"]),
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
            nav["breadcrumb_node"],
            _faq_node(canonical_url),
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
    nav = _section("/ctr/download", "Download")
    return render_template(
        "ctr/download.html",
        **nav,
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
            nav["breadcrumb_node"],
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
    title = "How CTR Archipelago works | Archipelago Pie"
    description = (
        "Learn how CTR Archipelago changes Crash Team Racing, including "
        "randomized warp pads, progression, kart upgrades, and checks."
    )
    canonical_url = _canonical("/ctr/reference")
    nav = _section("/ctr/reference", "How it works")
    return render_template(
        "ctr/reference-index.html",
        **nav,
        pages=REFERENCE_PAGES,
        ap_box_total=AP_BOX_TOTAL,
        stable=STABLE,
        page_title=title,
        meta_description=description,
        canonical_url=canonical_url,
        og_type="website",
        og_image=_canonical("/img/ctr/og-ctr.jpg"),
        site_url=_canonical("/"),
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL,
            seo.page(config.PUBLIC_BASE_URL, "CollectionPage", canonical_url, title, description),
            nav["breadcrumb_node"],
        ),
    )


def _article_page(page: dict, path: str, title_suffix: str, analytics_page: str) -> str:
    md_path = _REFERENCE_DIR / page["file"]
    if not md_path.is_file():
        abort(404)
    body_html, sections_on_page = _render_reference_markdown(md_path)
    analytics.record_event(
        "ctr_view",
        user_id=session.get("user_id"),
        props={"page": analytics_page, "from_path": analytics.entry_path(request)},
        req=request,
    )
    canonical_url = _canonical(path)
    title = f"{page.get('page_title', page['title'])} | {title_suffix}"
    nav = _section(path, page["short_title"])
    page_node = seo.page(config.PUBLIC_BASE_URL, "WebPage", canonical_url, title, page["description"])
    page_node["mainEntity"] = {"@id": f"{canonical_url}#article"}
    article = {
        "@type": "TechArticle",
        "@id": f"{canonical_url}#article",
        "headline": page["title"],
        "description": page["description"],
        "author": {"@id": seo.author_id(config.PUBLIC_BASE_URL)},
        "publisher": {"@id": seo.organization_id(config.PUBLIC_BASE_URL)},
        "datePublished": page["published"],
        "dateModified": page["updated"],
        "mainEntityOfPage": {"@id": f"{canonical_url}#page"},
        "isPartOf": {"@id": seo.website_id(config.PUBLIC_BASE_URL)},
        "image": _canonical("/img/ctr/og-ctr.jpg"),
        "inLanguage": "en",
    }
    return render_template(
        "ctr/reference-page.html",
        **nav,
        page=page,
        body_html=body_html,
        sections=sections_on_page,
        page_title=title,
        meta_description=page["description"],
        canonical_url=canonical_url,
        og_type="article",
        og_image=_canonical("/img/ctr/og-ctr.jpg"),
        site_url=_canonical("/"),
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL,
            seo.author(config.PUBLIC_BASE_URL),
            page_node,
            article,
            nav["breadcrumb_node"],
        ),
    )


@bp.route("/ctr/reference/<slug>", strict_slashes=False)
def ctr_reference_page(slug: str):
    if slug in RELEASE_REDIRECTS:
        return redirect(RELEASE_REDIRECTS[slug], code=301)
    page = _REFERENCE_BY_SLUG.get(slug)
    if page is None:
        abort(404)
    return _article_page(page, f"/ctr/reference/{slug}", "CTR Archipelago reference", f"reference/{slug}")


@bp.route("/ctr/releases", strict_slashes=False)
def ctr_releases_index() -> str:
    analytics.record_event(
        "ctr_view",
        user_id=session.get("user_id"),
        props={"page": "releases", "from_path": analytics.entry_path(request)},
        req=request,
    )
    title = "CTR Archipelago releases | Archipelago Pie"
    description = (
        "Every stable CTR Archipelago release with its date and release notes, "
        f"from the first public version to the current {STABLE['version']}."
    )
    canonical_url = _canonical("/ctr/releases")
    nav = _section("/ctr/releases", "Releases")
    return render_template(
        "ctr/releases-index.html",
        **nav,
        releases=RELEASE_HISTORY,
        stable=STABLE,
        test_builds_url=_GITHUB_RELEASES,
        page_title=title,
        meta_description=description,
        canonical_url=canonical_url,
        og_type="website",
        og_image=_canonical("/img/ctr/og-ctr.jpg"),
        site_url=_canonical("/"),
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL,
            seo.page(config.PUBLIC_BASE_URL, "CollectionPage", canonical_url, title, description),
            nav["breadcrumb_node"],
        ),
    )


@bp.route("/ctr/releases/<slug>", strict_slashes=False)
def ctr_release_page(slug: str):
    page = _RELEASE_BY_SLUG.get(slug)
    if page is None:
        abort(404)
    return _article_page(page, f"/ctr/releases/{slug}", "Archipelago Pie", f"releases/{slug}")


@bp.route("/ctr/reference/ap-boxes", strict_slashes=False)
def ctr_ap_boxes_index() -> str:
    analytics.record_event(
        "ctr_view",
        user_id=session.get("user_id"),
        props={"page": "reference/ap-boxes", "from_path": analytics.entry_path(request)},
        req=request,
    )
    canonical_url = _canonical("/ctr/reference/ap-boxes")
    title = "CTR AP box locations | CTR Archipelago reference"
    description = (
        f"Find any AP item box in CTR Archipelago: {AP_BOX_TOTAL} labelled pictures "
        "across all 18 tracks, one page per track."
    )
    og_image = _canonical("/img/ctr/ap-boxes/og/index.jpg")
    page_node = seo.page(config.PUBLIC_BASE_URL, "CollectionPage", canonical_url, title, description)
    page_node["primaryImageOfPage"] = og_image
    hubs: list[dict] = []
    for track in AP_BOX_TRACKS:
        if not hubs or hubs[-1]["name"] != track["hub"]:
            hubs.append({"name": track["hub"], "tracks": []})
        hubs[-1]["tracks"].append(track)
    nav = _section("/ctr/reference/ap-boxes", "AP box locations")
    return render_template(
        "ctr/ap-boxes-index.html",
        **nav,
        hubs=hubs,
        tracks=AP_BOX_TRACKS,
        total=AP_BOX_TOTAL,
        published=AP_BOXES_PUBLISHED,
        updated=AP_BOXES_UPDATED,
        page_title=title,
        meta_description=description,
        canonical_url=canonical_url,
        og_type="article",
        og_image=og_image,
        og_image_width=1200,
        og_image_height=630,
        og_image_alt=f"CTR Archipelago AP box locations: {AP_BOX_TOTAL} boxes on 18 tracks, with labelled pictures",
        site_url=_canonical("/"),
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL,
            page_node,
            nav["breadcrumb_node"],
        ),
    )


@bp.route("/ctr/reference/ap-boxes/<track_slug>")
def ctr_ap_boxes_track(track_slug: str) -> str:
    track = _AP_BOX_TRACK_BY_SLUG.get(track_slug)
    if track is None:
        abort(404)
    analytics.record_event(
        "ctr_view",
        user_id=session.get("user_id"),
        props={"page": f"reference/ap-boxes/{track_slug}", "from_path": analytics.entry_path(request)},
        req=request,
    )
    position = AP_BOX_TRACKS.index(track)
    previous_track = AP_BOX_TRACKS[position - 1] if position > 0 else None
    next_track = AP_BOX_TRACKS[position + 1] if position + 1 < len(AP_BOX_TRACKS) else None
    path = f"/ctr/reference/ap-boxes/{track_slug}"
    canonical_url = _canonical(path)
    title = f"{track['name']} AP box locations | CTR Archipelago"
    description = (
        f"Where to find all {len(track['boxes'])} AP item boxes on {track['name']} "
        "in CTR Archipelago, with a labelled picture of each box."
    )
    page_node = seo.page(config.PUBLIC_BASE_URL, "WebPage", canonical_url, title, description)
    og_image = _canonical(f"/img/ctr/ap-boxes/og/{track_slug}.jpg")
    page_node["primaryImageOfPage"] = og_image
    # Every box picture as an ImageObject, so image search can match a
    # query like "Mystery Caves item box 13" to its labelled picture.
    page_node["image"] = [
        {
            "@type": "ImageObject",
            "contentUrl": _canonical(box["full"]),
            "thumbnailUrl": _canonical(box["thumb"]),
            "name": box["name"],
            "caption": f"{box['name']}. {box['hint']}" if box.get("hint") else box["name"],
            "width": 1280,
            "height": 720,
        }
        for box in track["boxes"]
    ]
    nav = _section(path, track["name"], [(track["name"], path)])
    return render_template(
        "ctr/ap-boxes-track.html",
        **nav,
        track=track,
        map_caption=AP_BOX_MAP_CAPTION,
        previous_track=previous_track,
        next_track=next_track,
        published=AP_BOXES_PUBLISHED,
        updated=AP_BOXES_UPDATED,
        page_title=title,
        meta_description=description,
        canonical_url=canonical_url,
        og_type="article",
        og_image=og_image,
        og_image_width=1200,
        og_image_height=630,
        og_image_alt=f"Map of {track['name']} in CTR Archipelago with its {len(track['boxes'])} AP boxes numbered",
        site_url=_canonical("/"),
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL,
            page_node,
            nav["breadcrumb_node"],
        ),
    )
