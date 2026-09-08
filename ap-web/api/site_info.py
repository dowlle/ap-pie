"""Public release notes and issue-reporting instructions, without data intake."""
from pathlib import Path

from flask import Blueprint, render_template

import config
import seo

bp = Blueprint("site_info", __name__)
PAGES_UPDATED = "2026-09-08"
PAGES = {
    "/changelog": ("Changelog", "Recent updates and fixes to Archipelago Pie.", "changelog.md"),
    "/report-issue": ("Report an issue", "Report a problem with Archipelago Pie or find the right place for an APWorld issue.", "report-issue.md"),
}


def _page(path):
    from api.guides import _render_markdown
    title, description, filename = PAGES[path]
    html, _ = _render_markdown(Path(__file__).resolve().parent.parent / "site_pages" / filename)
    canonical = f"{config.PUBLIC_BASE_URL}{path}"
    return render_template(
        "guides/site-page.html", h1=title, body_html=html,
        page_title=f"{title} | Archipelago Pie", meta_description=description,
        canonical_url=canonical, og_type="website",
        structured_data=seo.graph(config.PUBLIC_BASE_URL, seo.page(
            config.PUBLIC_BASE_URL, "WebPage", canonical, title, description,
        )),
    )


@bp.get("/changelog")
def changelog():
    return _page("/changelog")


@bp.get("/report-issue")
def report_issue():
    return _page("/report-issue")
