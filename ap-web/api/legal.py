"""FEAT-31: the server-rendered /privacy page.

Same machinery as the guides (markdown in the repo, rendered through the
guides layout, registered before the SPA catch-all) but kept in its own
blueprint and its own content directory: a privacy statement is not a guide,
and it should not appear on the guides index, in the guides shelves, or in
llms.txt as if it were tutorial content.

The page is the transparency half of the analytics work (GDPR Art. 13). If a
new event kind or prop is added to analytics.py, this content changes in the
same commit - that rule is written into analytics.py's module docstring too.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, render_template

import config
import seo

_LEGAL_DIR = Path(__file__).resolve().parent.parent / "legal"
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

bp = Blueprint("legal", __name__, template_folder=str(_TEMPLATES_DIR))

# Bump when the statement's content changes; drives the byline and sitemap.
PRIVACY_UPDATED = "2026-08-17"
PRIVACY_PATH = "/privacy"


def _canonical(path: str) -> str:
    return f"{config.PUBLIC_BASE_URL}{path}"


@bp.route(PRIVACY_PATH, strict_slashes=False)
def privacy() -> str:
    from api.guides import _render_markdown

    md_path = _LEGAL_DIR / "privacy.md"
    if not md_path.is_file():
        abort(404)
    body_html, sections = _render_markdown(md_path)
    # Deliberately not recorded as an analytics event: measuring who reads the
    # privacy statement would be a poor look, and it answers no question worth
    # asking. The page still counts in Cloudflare's edge pageviews.
    canonical_url = _canonical(PRIVACY_PATH)
    description = (
        "What Archipelago Pie records, what it deliberately does not "
        "record, how long it is kept, and how to ask for it to be removed."
    )
    page_node = seo.page(
        config.PUBLIC_BASE_URL,
        "WebPage",
        canonical_url,
        "Privacy | Archipelago Pie",
        description,
    )
    page_node.update({
        "datePublished": "2026-08-17",
        "dateModified": PRIVACY_UPDATED,
        "about": "Archipelago Pie privacy and analytics practices",
    })
    return render_template(
        "guides/guide.html",
        project_name=None,
        related=[],
        h1="Privacy",
        body_html=body_html,
        sections=sections,
        page_title="Privacy | Archipelago Pie",
        meta_description=description,
        canonical_url=canonical_url,
        og_type="website",
        date_published="2026-08-17",
        date_modified=PRIVACY_UPDATED,
        site_url=_canonical("/"),
        guides_url=_canonical("/guides"),
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL,
            page_node,
            {
                "@type": "BreadcrumbList",
                "@id": f"{canonical_url}#breadcrumb",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Archipelago Pie", "item": _canonical("/")},
                    {"@type": "ListItem", "position": 2, "name": "Privacy", "item": canonical_url},
                ],
            },
        ),
        video_url=None,
        video_title=None,
        video_thumb=None,
    )
