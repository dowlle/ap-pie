"""Project section navigation, breadcrumbs and redirects (CTR, Timberborn, Poképelago).

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
from api import ctr, guides, sections, site_info, timberborn

HREF = re.compile(r'href="(/[^"#?]*)')
LD_JSON = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
# Links that leave these blueprints on purpose: the SPA, sign-in, and the
# download aliases that redirect to GitHub release assets.
OUTSIDE = ("/yaml-builder", "/apworlds", "/api/", "/ctr/download/", "/timberborn/download/", "/my/", "/rooms", "/img/", "/privacy", "/favicon")


def _app() -> Flask:
    app = Flask(__name__, template_folder=os.path.join(repo_app, "templates"))
    app.secret_key = "test-only"
    for blueprint in (ctr.bp, site_info.bp, guides.bp, timberborn.bp):
        app.register_blueprint(blueprint)
    return app


class ProjectSectionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.patches = [
            mock.patch.object(analytics, "record_event", lambda *a, **k: None),
            mock.patch.object(analytics, "record_guide_entry", lambda *a, **k: None),
            mock.patch.object(analytics, "entry_path", lambda *a, **k: None),
            # The Timberborn section is beta-only until its v0.1.0 release;
            # these checks cover it switched on. TimberbornSwitchedOffTest
            # covers the production state.
            mock.patch.dict(config.FEATURES, {"timberborn_section": True}),
        ]
        for patch in cls.patches:
            patch.start()
        cls.client = _app().test_client()

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

    def test_release_notes_moved_and_listed_in_the_overview(self) -> None:
        for old in ("/ctr/reference/0-2-0-release-notes", "/ctr/reference/0-2-0-release-notes/"):
            with self.subTest(old=old):
                response = self.get(old)
                self.assertEqual(response.status_code, 301)
                target = response.headers["Location"]
                self.assertTrue(target.endswith("/ctr/releases/0-2-0"), target)
                self.assertEqual(self.get("/ctr/releases/0-2-0").status_code, 200)
        overview = self.get("/ctr/releases").get_data(as_text=True)
        self.assertIn('href="/ctr/releases/0-2-0"', overview)
        self.assertIn('href="/ctr/releases/0-2-1"', overview)
        self.assertEqual(self.get("/ctr/releases/0-2-1").status_code, 200)
        self.assertIn('href="/ctr/releases/0-2-2"', overview)
        self.assertEqual(self.get("/ctr/releases/0-2-2").status_code, 200)
        self.assertIn('href="https://github.com/dowlle/ctr-native-ap/releases/tag/v0.1.0"', overview)

    def test_older_versions_stay_downloadable_after_a_new_stable(self) -> None:
        # 0.2.2 is stable today; 0.2.1 and 0.2.0 stay downloadable under "Older versions".
        page = self.get("/ctr/download").get_data(as_text=True)
        self.assertIn('id="older-versions"', page)
        self.assertIn('href="/ctr/download/0.2.1/windows"', page)
        self.assertIn('href="/ctr/download/0.2.0/windows"', page)
        self.assertIn('href="/ctr/releases/0-2-0"', page)
        response = self.get("/ctr/download/0.2.0/windows")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            "https://github.com/dowlle/ctr-native-ap/releases/download/v0.2.0/ctr-archipelago-v0.2.0-windows-x86.zip",
        )
        self.assertTrue(self.get("/ctr/download/windows").headers["Location"].endswith("/v0.2.2/ctr-archipelago-v0.2.2-windows-x86.zip"))
        # A future stable bump keeps the outgoing 0.2.2 downloadable the same way.
        with mock.patch.dict(ctr.STABLE, {"version": "0.3.0", "downloads": ctr.release_assets("0.3.0")}), \
                mock.patch.object(ctr, "KEPT_VERSIONS", ["0.3.0", "0.2.2"]):
            page = self.get("/ctr/download").get_data(as_text=True)
            self.assertIn('href="/ctr/download/0.2.2/windows"', page)
            self.assertTrue(self.get("/ctr/download/windows").headers["Location"].endswith("/v0.3.0/ctr-archipelago-v0.3.0-windows-x86.zip"))
        self.assertEqual(self.get("/ctr/download/0.1.0/windows").status_code, 404)

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

    def test_guides_index_reaches_the_timberborn_section(self) -> None:
        html = self.get("/guides").get_data(as_text=True)
        for path in ("/timberborn/setup", "/timberborn/reference", "/timberborn/download"):
            self.assertIn(f'href="{path}"', html)
        self.assertNotIn("Coming soon.", html.split('id="timber"')[-1].split("</section>")[0])

    def test_timberborn_downloads_wait_for_the_release(self) -> None:
        # Until the GitHub release exists every alias opens the release list.
        self.assertFalse(timberborn.STABLE["available"])
        for asset in ("mod", "apworld", "yaml"):
            with self.subTest(asset=asset):
                response = self.get(f"/timberborn/download/{asset}")
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], "https://github.com/dowlle/timberborn-modding/releases")
        self.assertEqual(self.get("/timberborn/download/windows").status_code, 404)
        self.assertEqual(self.get("/timberborn/download/0.0.5/mod").status_code, 404)
        page = self.get("/timberborn/download").get_data(as_text=True)
        self.assertIn("Placeholder for release", page)
        with mock.patch.dict(timberborn.STABLE, {"available": True, "released": "2026-10-01"}):
            self.assertEqual(
                self.get("/timberborn/download/mod").headers["Location"],
                "https://github.com/dowlle/timberborn-modding/releases/download/v0.1.0/Archipelago.zip",
            )
            self.assertTrue(self.get("/timberborn/download/0.1.0/apworld").headers["Location"].endswith("/v0.1.0/timberborn.apworld"))
        with mock.patch.dict(timberborn.MOD_LISTINGS, {"modio": "https://mod.io/g/timberborn/m/example", "workshop": "https://steamcommunity.com/sharedfiles/filedetails/?id=1"}):
            self.assertNotIn("Placeholder for release", self.get("/timberborn/download").get_data(as_text=True))

    def test_timberborn_release_notes_are_a_marked_draft(self) -> None:
        overview = self.get("/timberborn/releases").get_data(as_text=True)
        self.assertIn('href="/timberborn/releases/0-1-0"', overview)
        self.assertIn("upcoming", overview)
        self.assertNotIn("current stable", overview)
        notes = self.get("/timberborn/releases/0-1-0").get_data(as_text=True)
        self.assertIn("Draft: these notes are for the upcoming 0.1.0 release", notes)

    def test_sitemap_and_llms_list_only_the_new_urls(self) -> None:
        base = config.PUBLIC_BASE_URL
        for surface in ("/sitemap.xml", "/llms.txt"):
            with self.subTest(surface=surface):
                body = self.get(surface).get_data(as_text=True)
                for path in ("/ctr/releases/0-2-0", "/ctr/setup", "/ctr/play-on-pc", "/pokepelago/setup", "/pokepelago/twitch",
                             "/timberborn", "/timberborn/setup", "/timberborn/reference/options", "/timberborn/releases/0-1-0"):
                    self.assertIn(f"{base}{path}", body)
                for old in ("0-2-0-release-notes", "/guides/ctr", "/guides/crash-team-racing-pc", "/guides/pokepelago"):
                    self.assertNotIn(old, body)



class TimberbornSwitchedOffTest(unittest.TestCase):
    """Production state until the Timberborn v0.1.0 release: no Timberborn
    page answers, and nothing links or lists one."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.patches = [
            mock.patch.object(analytics, "record_event", lambda *a, **k: None),
            mock.patch.object(analytics, "record_guide_entry", lambda *a, **k: None),
            mock.patch.object(analytics, "entry_path", lambda *a, **k: None),
            mock.patch.dict(config.FEATURES, {"timberborn_section": False}),
        ]
        for patch in cls.patches:
            patch.start()
        cls.client = _app().test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        for patch in cls.patches:
            patch.stop()

    def test_every_timberborn_url_answers_404(self) -> None:
        paths = sections.section_paths("timber") + [
            "/timberborn/download/mod", "/timberborn/download/0.1.0/mod", "/guides/timberborn",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_no_surface_links_or_lists_timberborn(self) -> None:
        for surface in ("/guides", "/sitemap.xml", "/llms.txt", "/ctr", "/pokepelago"):
            with self.subTest(surface=surface):
                body = self.client.get(surface).get_data(as_text=True)
                self.assertNotIn("/timberborn", body)
        self.assertIn("Coming soon.", self.client.get("/guides").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
