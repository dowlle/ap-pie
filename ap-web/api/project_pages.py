"""Shared rendering for project section article pages (CTR, Timberborn).

Reference pages and release notes of every project section render the same
way: repo-controlled markdown, the section navigation and breadcrumbs from
api/sections.py, and one TechArticle plus BreadcrumbList in the structured
data. Keeping that here means the structured-data code exists once.
"""
from __future__ import annotations

from pathlib import Path

import markdown
from flask import abort, render_template, request, session

import analytics
import config
import seo
from api import sections


def canonical(path: str) -> str:
    return f"{config.PUBLIC_BASE_URL}{path}"


def render_markdown(md_path: Path) -> tuple[str, list[dict]]:
    """Markdown to HTML plus the h2 sections for the on-page rail.

    Core Markdown plus `toc` only, as in api/guides.py: no raw-HTML
    passthrough extension and no smart punctuation."""
    text = md_path.read_text(encoding="utf-8")
    renderer = markdown.Markdown(extensions=["toc"], output_format="html")
    html = renderer.convert(text)
    on_page = [
        {"id": token["id"], "name": token["name"]}
        for token in renderer.toc_tokens
        if token["level"] == 2
    ]
    return html, on_page


def article_page(
    *,
    section_key: str,
    content_dir: Path,
    page: dict,
    path: str,
    title_suffix: str,
    event: str,
    analytics_page: str,
    default_image: str,
    pager_back: dict,
) -> str:
    """Render one reference or release-notes page of a project section."""
    md_path = content_dir / page["file"]
    if not md_path.is_file():
        abort(404)
    body_html, on_page = render_markdown(md_path)
    analytics.record_event(
        event,
        user_id=session.get("user_id"),
        props={"page": analytics_page, "from_path": analytics.entry_path(request)},
        req=request,
    )
    canonical_url = canonical(path)
    title = f"{page.get('page_title', page['title'])} | {title_suffix}"
    nav = sections.context(section_key, path, page["short_title"])
    page_node = seo.page(config.PUBLIC_BASE_URL, "WebPage", canonical_url, title, page["description"])
    page_node["mainEntity"] = {"@id": f"{canonical_url}#article"}
    image = canonical(page.get("og_image", default_image))
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
        "image": image,
        "inLanguage": "en",
    }
    return render_template(
        "project/reference-page.html",
        **nav,
        page=page,
        pager_back=pager_back,
        body_html=body_html,
        sections=on_page,
        page_title=title,
        meta_description=page["description"],
        canonical_url=canonical_url,
        og_type="article",
        og_image=image,
        og_image_width=page.get("og_image_width"),
        og_image_height=page.get("og_image_height"),
        og_image_alt=page.get("og_image_alt"),
        site_url=canonical("/"),
        structured_data=seo.graph(
            config.PUBLIC_BASE_URL,
            seo.author(config.PUBLIC_BASE_URL),
            page_node,
            article,
            nav["breadcrumb_node"],
        ),
    )
