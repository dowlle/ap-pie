"""FEAT-39: server-rendered guide pages.

These routes are deliberately NOT part of the React SPA. They render full HTML
on the server so that search engines and AI answer systems get complete
content, a real <title>, meta description, canonical URL, and Open Graph tags
without executing any JavaScript. The SPA catch-all in app.py is registered
after every blueprint, so these paths win over the client-side router.

Content lives in repo-controlled markdown files under ap-web/guides/. It is
NOT user input, so raw HTML in the source (e.g. the <!-- VERIFY: ... -->
review markers) is preserved on purpose. No raw-HTML passthrough extension is
enabled and the smarty extension is deliberately avoided so that "--" is never
rewritten into a dash.
"""

from __future__ import annotations

from pathlib import Path

import markdown
from flask import Blueprint, Response, abort, render_template, request, session

import analytics
import config

_GUIDES_DIR = Path(__file__).resolve().parent.parent / "guides"
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

bp = Blueprint("guides", __name__, template_folder=str(_TEMPLATES_DIR))


# Registry of guide pages. Order here is the order shown on the index and in
# the sitemap. `file` is resolved against _GUIDES_DIR. Adding a guide is a
# matter of dropping a markdown file in ap-web/guides/ and adding a row here.
# `published`/`updated` feed the byline + TechArticle structured data: bump
# `updated` whenever a guide's content materially changes (part of the same
# release-sweep discipline that keeps guide content current).
# Project shelves for the guides index (design ruling 2026-07-22: variant B,
# grouped sections with a rail nav, Archipelago basics first). `soon` renders
# a ghosted placeholder card until that project's guide ships.
PROJECTS: list[dict] = [
    {"key": "ap", "name": "Archipelago basics", "sub": "start here if multiworld is new", "color": "#6da8c9"},
    {"key": "ctr", "name": "Crash Team Racing", "sub": "native PC port + randomizer", "color": "#e8a857"},
    {
        "key": "poke", "name": "Pokepelago", "sub": "catch across worlds", "color": "#e05d5d",
        "soon": {
            "kicker": "Setup",
            "title": "Pokepelago setup",
            "blurb": "Catching across worlds: the browser client and how your dex feeds the multiworld. Coming soon.",
        },
    },
    {
        "key": "timber", "name": "Timberborn", "sub": "beavers meet the item pool", "color": "#7fa65a",
        "soon": {
            "kicker": "Setup",
            "title": "Timberborn Archipelago setup",
            "blurb": "Mod install, faction picks, and your first shuffled colony. Coming soon.",
        },
    },
]

GUIDES: list[dict[str, str]] = [
    {
        "slug": "getting-started",
        "file": "getting-started.md",
        "h1": "Getting started with the Archipelago randomizer",
        "page_title": "Getting started with the Archipelago randomizer | Archipelago Pie",
        "meta_description": (
            "Learn how the Archipelago randomizer connects game worlds, then choose "
            "how to join a room, create a solo seed, or organize a multiworld."
        ),
        "card_title": "Getting started with Archipelago",
        "card_blurb": (
            "Learn the basics, then choose the right path for joining a group, "
            "playing solo, or organizing a multiworld."
        ),
        "published": "2026-07-22",
        "updated": "2026-08-19",
        "project": "ap",
        "kicker": "Start here",
        "featured": True,
        "path_tabs": True,
    },
    {
        "slug": "hosting-on-archipelago-pie",
        "file": "hosting-on-archipelago-pie.md",
        "h1": "How to host a room on Archipelago Pie",
        "page_title": "Hosting an Archipelago Pie collection room | Archipelago Pie",
        "meta_description": (
            "Create an Archipelago Pie collection room, set its rules and "
            "APWorld versions, collect YAMLs, then close and download it for generation."
        ),
        "card_title": "Host a room on Archipelago Pie",
        "card_blurb": (
            "Create a collection room, share it with players, review submissions, "
            "and download everything for local generation."
        ),
        "published": "2026-08-19",
        "updated": "2026-08-19",
        "project": "ap",
        "kicker": "Archipelago Pie",
        "featured": False,
    },
    {
        "slug": "hosting-a-multiworld",
        "file": "hosting-a-multiworld.md",
        "h1": "Hosting a multiworld",
        "page_title": "Hosting an Archipelago multiworld | Archipelago Pie",
        "meta_description": (
            "How to host an Archipelago multiworld: collect player YAMLs, "
            "generate the game, put the server online via archipelago.gg or "
            "your own machine, and run the session."
        ),
        "card_title": "Hosting a multiworld",
        "card_blurb": (
            "Collect the YAMLs, generate the game, put the server online, and "
            "run the session for your group."
        ),
        "published": "2026-07-22",
        "updated": "2026-08-19",
        "project": "ap",
        "kicker": "Hosting",
        "featured": False,
    },
    {
        "slug": "setting-up-your-yaml",
        "file": "setting-up-your-yaml.md",
        "h1": "Setting up your YAML",
        "page_title": "Setting up your Archipelago YAML | Archipelago Pie",
        "meta_description": (
            "How Archipelago YAML files work: getting a template from the "
            "website or the Launcher, reading the option shapes and weights, "
            "validating the file, and handing it to your host."
        ),
        "card_title": "Setting up your YAML",
        "card_blurb": (
            "Get a template, change the options you care about, validate the "
            "file, and hand it to your host."
        ),
        "published": "2026-07-22",
        "updated": "2026-08-19",
        "project": "ap",
        "kicker": "Your settings",
        "featured": False,
    },
    {
        "slug": "setting-up-a-game-client",
        "file": "setting-up-a-game-client.md",
        "h1": "Setting up an Archipelago game client",
        "page_title": "Setting up an Archipelago game client | Archipelago Pie",
        "meta_description": (
            "Learn what an Archipelago client or connector does, which files and "
            "room details you need, the common setup patterns, and how to troubleshoot."
        ),
        "card_title": "Set up your game client",
        "card_blurb": (
            "Understand clients, connectors, generated patches, room details, "
            "and the checks to run before you start playing."
        ),
        "published": "2026-08-19",
        "updated": "2026-08-19",
        "project": "ap",
        "kicker": "Connect and play",
        "featured": False,
    },
    {
        "slug": "setting-up-poptracker",
        "file": "setting-up-poptracker.md",
        "h1": "Setting up PopTracker",
        "page_title": "Setting up PopTracker for Archipelago | Archipelago Pie",
        "meta_description": (
            "Install PopTracker, find a community pack for your game, load it, "
            "and connect auto-tracking to your Archipelago room."
        ),
        "card_title": "Setting up PopTracker",
        "card_blurb": (
            "Install the tracker, find your game's community pack, and connect "
            "auto-tracking to your room."
        ),
        "published": "2026-07-22",
        "updated": "2026-08-19",
        "project": "ap",
        "kicker": "Tracking",
        "featured": False,
    },
    {
        "slug": "crash-team-racing-pc",
        "file": "crash-team-racing-pc.md",
        "h1": "Play Crash Team Racing on PC",
        "page_title": "Play Crash Team Racing on PC | Archipelago Pie",
        "meta_description": (
            "Crash Team Racing runs natively on PC through a community "
            "decompilation. No emulator needed: download the ctr-native port, "
            "add your own disc image, and play."
        ),
        "card_title": "Play Crash Team Racing on PC",
        "card_blurb": (
            "The 1999 classic as a native PC port with no emulator involved, "
            "thanks to the community decompilation. It sets up in minutes."
        ),
        "published": "2026-07-22",
        "updated": "2026-07-22",
        "project": "ctr",
        "kicker": "Vanilla on PC",
        "featured": False,
    },
    {
        "slug": "ctr",
        "file": "ctr.md",
        "h1": "Crash Team Racing setup guide",
        "page_title": "Crash Team Racing Archipelago setup | Archipelago Pie",
        "meta_description": (
            "Set up the native Crash Team Racing Archipelago client: what you need, "
            "first launch, adding your disc image, and connecting to your room."
        ),
        "card_title": "Crash Team Racing setup",
        "card_blurb": (
            "Get the native CTR Archipelago client installed, launched, and "
            "connected to your multiworld room."
        ),
        "published": "2026-07-22",
        "updated": "2026-08-16",
        "project": "ctr",
        "kicker": "Randomizer",
        "featured": True,
        # Optional per-guide video embed (design ruling 2026-07-22: "videos
        # embed in guides, descriptions link back"). Set to a youtube-nocookie
        # embed URL to show a "Watch" block above the guide body; omit/None
        # for guides with no video yet.
        "video_url": "https://www.youtube-nocookie.com/embed/9x63P6JP93E",
        "video_title": "How to play the Crash Team Racing Archipelago | For players",
        "video_thumb": "/img/ctr/tutorial-thumb.webp",
    },
]

_GUIDES_BY_SLUG = {g["slug"]: g for g in GUIDES}


def _canonical(path: str) -> str:
    """Absolute canonical URL for a site-relative path like '/guides'."""
    return f"{config.PUBLIC_BASE_URL}{path}"


def _render_markdown(md_path: Path) -> tuple[str, list[dict]]:
    """Render a repo-controlled markdown file to HTML plus a section list.

    Core Markdown plus the `toc` extension only: toc adds ids to headings
    (deep links + the on-page rail) without enabling raw-HTML passthrough
    or smart punctuation, so HTML comments (the VERIFY markers) stay
    invisible-but-findable and "--" is never rewritten. Returns the HTML
    and the h2 sections as [{"id": ..., "name": ...}].
    """
    text = md_path.read_text(encoding="utf-8")
    md = markdown.Markdown(extensions=["toc"], output_format="html")
    html = md.convert(text)
    sections = [
        {"id": t["id"], "name": t["name"]}
        for t in md.toc_tokens
        if t["level"] == 2
    ]
    return html, sections


@bp.route("/guides")
def guides_index() -> str:
    shelves = []
    for p in PROJECTS:
        cards = [
            {
                "path": f"/guides/{g['slug']}",
                "kicker": g.get("kicker", "Guide"),
                "title": g["card_title"],
                "blurb": g["card_blurb"],
                "featured": bool(g.get("featured")),
            }
            for g in GUIDES
            if g.get("project") == p["key"]
        ]
        cards.sort(key=lambda c: not c["featured"])
        shelves.append({
            "key": p["key"],
            "name": p["name"],
            "sub": p["sub"],
            "color": p["color"],
            "cards": cards,
            "soon": p.get("soon"),
            "count": len(cards) + (1 if p.get("soon") else 0),
        })
    return render_template(
        "guides/index.html",
        shelves=shelves,
        page_title="Guides | Archipelago Pie",
        meta_description=(
            "Setup guides for Archipelago multiworld randomizers: start with the "
            "basics, then follow a guide for your game to get connected and playing."
        ),
        canonical_url=_canonical("/guides"),
        og_type="website",
    )


@bp.route("/guides/<slug>")
def guide_page(slug: str) -> str:
    guide = _GUIDES_BY_SLUG.get(slug)
    if guide is None:
        abort(404)
    md_path = _GUIDES_DIR / guide["file"]
    if not md_path.is_file():
        abort(404)
    body_html, sections = _render_markdown(md_path)
    # FEAT-31: guides are server-rendered, so a read is visible here without
    # any client-side script. `from_path` records the internal page the
    # reader arrived from (external referrers collapse to "external"), which
    # is what makes the guides-to-app journey measurable across documents.
    # `user_id` is attached when a session exists, for the same reason the
    # rest of the log does it: signed-in journeys are already attributable.
    analytics.record_event(
        "guide_view",
        user_id=session.get("user_id"),
        props={"slug": slug, "from_path": analytics.entry_path(request)},
        req=request,
    )

    # Section navigation: the shelf this guide belongs to plus its sibling
    # guides, so every guide page can say where it lives and link sideways.
    # The CTR shelf additionally links the /ctr product pages (FEAT-40).
    project = next((p for p in PROJECTS if p["key"] == guide.get("project")), None)
    related = []
    if guide.get("project") == "ctr":
        related += [
            {"path": "/ctr", "kicker": "Overview", "title": "CTR Archipelago",
             "blurb": "What the randomizer is and why it is fun."},
            {"path": "/ctr/download", "kicker": "Downloads", "title": "Download CTR Archipelago",
             "blurb": "Current stable builds for Windows and Linux."},
        ]
    related += [
        {"path": f"/guides/{g['slug']}", "kicker": g.get("kicker", "Guide"),
         "title": g["card_title"], "blurb": g["card_blurb"]}
        for g in GUIDES
        if g.get("project") == guide.get("project") and g["slug"] != slug
    ]
    return render_template(
        "guides/guide.html",
        project_name=project["name"] if project else None,
        related=related,
        h1=guide["h1"],
        body_html=body_html,
        sections=sections,
        page_title=guide["page_title"],
        meta_description=guide["meta_description"],
        canonical_url=_canonical(f"/guides/{slug}"),
        og_type="article",
        date_published=guide["published"],
        date_modified=guide["updated"],
        author_url=_canonical("/"),
        site_url=_canonical("/"),
        guides_url=_canonical("/guides"),
        video_url=guide.get("video_url"),
        video_title=guide.get("video_title"),
        video_thumb=guide.get("video_thumb"),
        path_tabs=guide.get("path_tabs", False),
    )


@bp.route("/sitemap.xml")
def sitemap() -> Response:
    from api.ctr import CTR_PAGES, PAGES_UPDATED as CTR_UPDATED
    from api.legal import PRIVACY_PATH as LEGAL_PRIVACY_PATH
    from api.legal import PRIVACY_UPDATED as LEGAL_PRIVACY_UPDATED

    entries = [
        {"loc": _canonical("/"), "lastmod": None},
        {"loc": _canonical("/apworlds"), "lastmod": "2026-08-19"},
        {"loc": _canonical("/guides"), "lastmod": max(g["updated"] for g in GUIDES)},
    ] + [
        {"loc": _canonical(f"/guides/{g['slug']}"), "lastmod": g["updated"]}
        for g in GUIDES
    ] + [
        {"loc": _canonical(p["path"]), "lastmod": CTR_UPDATED}
        for p in CTR_PAGES
    ] + [
        {"loc": _canonical(LEGAL_PRIVACY_PATH), "lastmod": LEGAL_PRIVACY_UPDATED},
    ]
    xml = render_template("guides/sitemap.xml", entries=entries)
    return Response(xml, mimetype="application/xml")


@bp.route("/robots.txt")
def robots() -> Response:
    """Real robots.txt (the SPA catch-all used to swallow this path and serve
    HTML to crawlers). Allow everything; noindex environments (beta) are
    handled at the proxy via X-Robots-Tag, not here."""
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {_canonical('/sitemap.xml')}\n"
    )
    return Response(body, mimetype="text/plain")


@bp.route("/llms.txt")
def llms() -> Response:
    """GEO: a compact markdown index for AI crawlers and answer engines,
    following the llms.txt convention. Generated from the guide registry so
    it never goes stale separately."""
    lines = [
        "# Archipelago Pie",
        "",
        "> Setup guides and lobby tools for Archipelago multiworld randomizers, "
        "including Crash Team Racing on PC. Guides are server-rendered plain "
        "HTML and safe to cite.",
        "",
        "## Guides",
        "",
    ]
    for g in GUIDES:
        lines.append(
            f"- [{g['card_title']}]({_canonical('/guides/' + g['slug'])}): {g['card_blurb']}"
        )
    from api.ctr import CTR_PAGES

    lines += [
        "",
        "## CTR Archipelago",
        "",
    ]
    for p in CTR_PAGES:
        lines.append(f"- [{p['title']}]({_canonical(p['path'])}): {p['blurb']}")
    lines += [
        "",
        "## App",
        "",
        f"- [YAML room collector]({_canonical('/')}): host rooms and collect player YAMLs",
        f"- [Community APWorld index]({_canonical('/apworlds')}): browse community game integrations",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")
