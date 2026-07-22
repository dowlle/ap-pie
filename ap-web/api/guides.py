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
from flask import Blueprint, Response, abort, render_template

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
        "h1": "Getting started with Archipelago",
        "page_title": "Getting started with Archipelago | Archipelago Pie",
        "meta_description": (
            "What Archipelago multiworld randomizers are, how YAML files, rooms, "
            "and clients fit together, and how a multiworld session gets started."
        ),
        "card_title": "Getting started with Archipelago",
        "card_blurb": (
            "New to multiworld? Start here: what Archipelago is, and how YAMLs, "
            "rooms, and clients fit together."
        ),
        "published": "2026-07-22",
        "updated": "2026-07-22",
        "project": "ap",
        "kicker": "Start here",
        "featured": True,
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
            "The 1999 classic as a native PC port, no emulator needed, thanks "
            "to the community decompilation. Setup in minutes."
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
        "updated": "2026-07-22",
        "project": "ctr",
        "kicker": "Randomizer",
        "featured": True,
    },
]

_GUIDES_BY_SLUG = {g["slug"]: g for g in GUIDES}


def _canonical(path: str) -> str:
    """Absolute canonical URL for a site-relative path like '/guides'."""
    return f"{config.PUBLIC_BASE_URL}{path}"


def _render_markdown(md_path: Path) -> str:
    """Render a repo-controlled markdown file to HTML.

    Core Markdown only: it handles the headings, lists, inline code, bold,
    italics, and links the guides use, preserves HTML comments (the VERIFY
    markers) as invisible-but-findable source, and leaves "--" untouched.
    """
    text = md_path.read_text(encoding="utf-8")
    return markdown.markdown(text, extensions=[], output_format="html")


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
    body_html = _render_markdown(md_path)
    return render_template(
        "guides/guide.html",
        h1=guide["h1"],
        body_html=body_html,
        page_title=guide["page_title"],
        meta_description=guide["meta_description"],
        canonical_url=_canonical(f"/guides/{slug}"),
        og_type="article",
        date_published=guide["published"],
        date_modified=guide["updated"],
        author_url=_canonical("/"),
        site_url=_canonical("/"),
        guides_url=_canonical("/guides"),
    )


@bp.route("/sitemap.xml")
def sitemap() -> Response:
    entries = [
        {"loc": _canonical("/"), "lastmod": None},
        {"loc": _canonical("/guides"), "lastmod": max(g["updated"] for g in GUIDES)},
    ] + [
        {"loc": _canonical(f"/guides/{g['slug']}"), "lastmod": g["updated"]}
        for g in GUIDES
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
    lines += [
        "",
        "## App",
        "",
        f"- [YAML room collector]({_canonical('/')}): host rooms and collect player YAMLs",
        f"- [Community APWorld index]({_canonical('/apworlds')}): browse community game integrations",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")

