"""Project section navigation, breadcrumbs and redirects (CTR, Poképelago).

Renders every page in api/sections.py through the real blueprints and checks
that the section navigation, the visible breadcrumbs and the BreadcrumbList
structured data agree, that moved URLs answer with one permanent redirect,
and that no section page links to a URL that redirects or does not exist.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
from unittest import mock

repo_app = os.path.join(os.path.dirname(__file__), "..", "ap-web")
sys.path.insert(0, repo_app if os.path.isdir(repo_app) else "/app")

from flask import Flask

import analytics
import config
from api import ctr, guides, sections, site_info

HREF = re.compile(r'href="(/[^"#?]*)')
LD_JSON = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
# Links that leave these blueprints on purpose: the SPA, sign-in, and the
# download aliases that redirect to GitHub release assets.
OUTSIDE = ("/yaml-builder", "/apworlds", "/api/", "/ctr/download/", "/my/", "/rooms", "/img/", "/privacy", "/favicon")


class ProjectSectionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.patches = [
            mock.patch.object(analytics, "record_event", lambda *a, **k: None),
            mock.patch.object(analytics, "record_guide_entry", lambda *a, **k: None),
            mock.patch.object(analytics, "entry_path", lambda *a, **k: None),
        ]
        for patch in cls.patches:
            patch.start()
        app = Flask(__name__, template_folder=os.path.join(repo_app, "templates"))
        app.secret_key = "test-only"
        for blueprint in (ctr.bp, site_info.bp, guides.bp):
            app.register_blueprint(blueprint)
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        for patch in cls.patches:
            patch.stop()

    def get(self, path: str):
        return self.client.get(path)

    def breadcrumb_names(self, html: str) -> list[str]:
        for block in LD_JSON.findall(html):
            for node in json.loads(block).get("@graph", []):
                if node.get("@type") == "BreadcrumbList":
                    return [item["name"] for item in node["itemListElement"]]
        return []

    def test_every_section_page_has_navigation_and_matching_breadcrumbs(self) -> None:
        for key in sections.SECTIONS:
            for path in sections.section_paths(key):
                with self.subTest(path=path):
                    response = self.get(path)
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    self.assertEqual(html.count('class="section-nav"'), 1)
                    self.assertIn(f'<a href="{path}" class="current" aria-current="page">', html)
                    crumbs = sections.trail(key, path, "")
                    visible = re.search(r'<nav class="crumbs".*?</nav>', html, re.S).group(0)
                    for crumb in crumbs[:-1]:
                        self.assertIn(f'<a href="{crumb["path"]}">{crumb["name"]}</a>', visible)
                    names = self.breadcrumb_names(html)
                    self.assertEqual(names, ["Archipelago Pie"] + [c["name"] for c in crumbs[1:]])

    def test_ap_box_track_pages_sit_under_ap_box_locations(self) -> None:
        html = self.get("/ctr/reference/ap-boxes/mystery-caves").get_data(as_text=True)
        self.assertEqual(
            self.breadcrumb_names(html),
            ["Archipelago Pie", "CTR Archipelago", "How it works", "AP box locations", "Mystery Caves"],
        )
        self.assertIn('<a href="/ctr/reference/ap-boxes" class="active">AP box locations</a>', html)

    def test_moved_release_notes_redirect_permanently_in_one_hop(self) -> None:
        for old in ("/ctr/reference/0-2-0-release-notes", "/ctr/reference/0-2-0-release-notes/"):
            with self.subTest(old=old):
                response = self.get(old)
                self.assertEqual(response.status_code, 301)
                target = response.headers["Location"]
                self.assertTrue(target.endswith("/ctr/releases/0-2-0"), target)
                self.assertEqual(self.get("/ctr/releases/0-2-0").status_code, 200)
        latest = self.get("/ctr/releases")
        self.assertEqual(latest.status_code, 302)
        self.assertTrue(latest.headers["Location"].endswith("/ctr/releases/0-2-0"))

    def test_moved_guides_redirect_permanently_and_keep_the_query(self) -> None:
        moved = {
            "/guides/ctr": "/ctr/setup",
            "/guides/crash-team-racing-pc": "/ctr/play-on-pc",
            "/guides/pokepelago": "/pokepelago/setup",
            "/guides/pokepelago-twitch": "/pokepelago/twitch",
        }
        for old, new in moved.items():
            for variant in (old, old + "/"):
                with self.subTest(old=variant):
                    response = self.get(variant)
                    self.assertEqual(response.status_code, 301)
                    self.assertTrue(response.headers["Location"].endswith(new))
                    page = self.get(new)
                    self.assertEqual(page.status_code, 200)
                    self.assertIn(f'<link rel="canonical" href="{config.PUBLIC_BASE_URL}{new}"', page.get_data(as_text=True))
        tagged = self.get("/guides/ctr?utm_source=youtube")
        self.assertTrue(tagged.headers["Location"].endswith("/ctr/setup?utm_source=youtube"))
        self.assertEqual(self.get("/guides/getting-started").status_code, 200)

    def test_section_pages_only_link_to_pages_that_answer_directly(self) -> None:
        pages = [p for key in sections.SECTIONS for p in sections.section_paths(key)]
        pages += ["/guides", "/ctr/reference/ap-boxes/mystery-caves"]
        checked: dict[str, int] = {}
        for page in pages:
            html = self.get(page).get_data(as_text=True)
            for href in set(HREF.findall(html)):
                if href == "/" or href.startswith(OUTSIDE):
                    continue
                if href not in checked:
                    checked[href] = self.get(href).status_code
                with self.subTest(page=page, href=href):
                    self.assertEqual(checked[href], 200)

    def test_hubs_reach_every_section_page_in_one_click(self) -> None:
        for key, section in sections.SECTIONS.items():
            hub = self.get(section["path"]).get_data(as_text=True)
            links = set(HREF.findall(hub))
            for path in sections.section_paths(key):
                with self.subTest(path=path):
                    self.assertIn(path, links | {section["path"]})

    def test_guides_index_reaches_the_ctr_reference(self) -> None:
        html = self.get("/guides").get_data(as_text=True)
        self.assertIn('href="/ctr/reference"', html)
        self.assertIn('href="/ctr/reference/ap-boxes"', html)

    def test_sitemap_and_llms_list_only_the_new_urls(self) -> None:
        base = config.PUBLIC_BASE_URL
        for surface in ("/sitemap.xml", "/llms.txt"):
            with self.subTest(surface=surface):
                body = self.get(surface).get_data(as_text=True)
                for path in ("/ctr/releases/0-2-0", "/ctr/setup", "/ctr/play-on-pc", "/pokepelago/setup", "/pokepelago/twitch"):
                    self.assertIn(f"{base}{path}", body)
                for old in ("0-2-0-release-notes", "/guides/ctr", "/guides/crash-team-racing-pc", "/guides/pokepelago"):
                    self.assertNotIn(old, body)


if __name__ == "__main__":
    unittest.main()
