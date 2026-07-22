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
    cards = [
        {
            "path": f"/guides/{g['slug']}",
            "card_title": g["card_title"],
            "card_blurb": g["card_blurb"],
        }
        for g in GUIDES
    ]
    return render_template(
        "guides/index.html",
        guides=cards,
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
    )


@bp.route("/sitemap.xml")
def sitemap() -> Response:
    paths = ["/", "/guides"] + [f"/guides/{g['slug']}" for g in GUIDES]
    urls = [_canonical(p) for p in paths]
    xml = render_template("guides/sitemap.xml", urls=urls)
    return Response(xml, mimetype="application/xml")
