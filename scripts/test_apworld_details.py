"""Catalog detail routing, publication boundaries and crawler metadata.

Uses the real route handlers and built SPA shell with an in-memory catalog.
No database, network, background workers or APWorld execution is needed.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ap-web"))

from flask import Flask, jsonify, send_from_directory
import analytics
import app as application
import config
from api import apworlds, guides
from apworld_catalog import public_catalog
from apworld_editorial import load_reviewed_apworlds


def fixture_world(name="animal_well", display_name="ANIMAL WELL", **extra):
    return dict(name=name, display_name=display_name, disabled=False,
                supported=True, is_builtin=False, home="https://example.com/",
                tags=[], game_name=display_name, stability="stable",
                setup_guide=None, tracker=None, updated_at=None,
                versions=[], downloadable_versions=[], builder_versions=[], **extra)


def test_app():
    app = Flask(__name__)
    app.secret_key = "test-only"
    app.register_blueprint(apworlds.bp)
    app.register_blueprint(guides.bp)

    @app.get("/api/auth/me")
    def me():
        return jsonify(auth_enabled=True, user=None)

    @app.get("/api/features")
    def features():
        return jsonify(generation=False, open_room_creation=False, timberborn_section=False)

    @app.get("/api/deployment")
    def deployment():
        return jsonify(label="")

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path):
        if (application.DIST_DIR / path).is_file():
            return send_from_directory(application.DIST_DIR, path)
        if path in application.PUBLIC_ROUTE_SEO:
            return application._public_spa_response(path)
        return send_from_directory(application.DIST_DIR, "index.html"), 404

    return app


class APWorldDetailsTests(unittest.TestCase):
    def setUp(self):
        self.worlds = [
            fixture_world(), fixture_world("sm", "Super Metroid"),
            fixture_world("ctr", "Crash Team Racing"),
            fixture_world("pokepelago", "Poképelago"),
            fixture_world("new_world", "New World"),
            {**fixture_world("retired", "Retired"), "disabled": True},
        ]
        self.patches = [
            mock.patch.object(apworlds, "_get_index", side_effect=lambda: self.worlds),
            mock.patch.object(analytics, "record_event"),
            mock.patch.object(analytics, "record_guide_entry"),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.client = test_app().test_client()

    def test_every_active_world_has_a_route_without_publishing_editorial(self):
        for label in ("", "beta"):
            with mock.patch.object(config, "DEPLOYMENT_LABEL", label):
                worlds = self.client.get("/api/apworlds").get_json()
                self.assertEqual(len(worlds), 5)
                for world in worlds:
                    response = self.client.get("/apworlds/" + world["detail_slug"])
                    self.assertEqual(response.status_code, 301 if world["name"] in ("ctr", "pokepelago") else 200)
                for name in ("sm", "animal_well", "new_world"):
                    self.assertIsNone(next(w for w in worlds if w["name"] == name)["editorial"])

    def test_unknown_and_disabled_routes_are_404(self):
        for path in ("/apworlds/unknown", "/apworlds/retired"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_game_section_overrides_redirect(self):
        for slug, target in (("crash-team-racing", "/ctr"), ("pokepelago", "/pokepelago")):
            response = self.client.get("/apworlds/" + slug)
            self.assertEqual(response.status_code, 301)
            self.assertEqual(response.headers["Location"], target)

    def test_detail_seo_is_server_rendered_and_escaped(self):
        self.worlds.append(fixture_world("escape", 'A <script>alert("x")</script>'))
        for slug, name in (("animal-well", "ANIMAL WELL"), ("new-world", "New World"), ("escape", "A &lt;script&gt;")):
            html = self.client.get("/apworlds/" + slug).get_data(as_text=True)
            self.assertIn("<title>" + name, html)
            self.assertIn(f'rel="canonical" href="{config.PUBLIC_BASE_URL}/apworlds/{slug}"', html)
            self.assertIn('name="description"', html)
            self.assertNotIn('name="robots" content="noindex', html)
            self.assertNotIn("<script>alert", html)
            self.assertIn('property="og:image"', html)

    def test_sitemap_lists_active_detail_routes_without_override_duplicates(self):
        xml = self.client.get("/sitemap.xml").get_data(as_text=True)
        for slug in ("animal-well", "super-metroid", "new-world"):
            self.assertEqual(xml.count(f"<loc>{config.PUBLIC_BASE_URL}/apworlds/{slug}</loc>"), 1)
        for slug in ("retired", "crash-team-racing", "pokepelago"):
            self.assertNotIn("/apworlds/" + slug + "</loc>", xml)

    def test_social_images_resolve_for_all_requested_page_families(self):
        paths = ["/", "/apworlds", "/yaml-builder", "/guides"]
        paths.extend(guides.guide_path(g) for g in guides.live_guides())
        import re
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                image = re.search(r'<meta property="og:image" content="([^"]+)"', html).group(1)
                self.assertIn('name="twitter:card" content="summary_large_image"', html)
                self.assertIn('name="twitter:image"', html)
                from urllib.parse import urlsplit
                with self.client.get(urlsplit(image).path) as image_response:
                    self.assertEqual(image_response.status_code, 200)

    def test_slug_collisions_are_deterministic_and_reserve_editorial_routes(self):
        worlds = [fixture_world("animal-well"), fixture_world("A B"), fixture_world("a_b"), fixture_world("!!!")]
        overlays = load_reviewed_apworlds()
        forward = public_catalog(worlds, overlays)
        reverse = public_catalog(list(reversed(worlds)), overlays)
        self.assertEqual({w["name"]: w["detail_slug"] for w in forward},
                         {w["name"]: w["detail_slug"] for w in reverse})
        self.assertEqual(len({w["detail_slug"] for w in forward}), len(worlds))
        self.assertTrue(forward[0]["detail_slug"].startswith("animal-well-"))

    def test_only_reviewed_published_original_copy_is_exposed(self):
        overlays = load_reviewed_apworlds()
        published = replace(overlays["sm"], publication_status="published")
        for review_state, publication, visible in (
            ("reviewed", "published", True), ("draft", "unpublished", False),
            ("stale", "unpublished", False), ("retired", "unpublished", False),
            ("reviewed", "beta_preview", False),
        ):
            with self.subTest(review_state=review_state, publication=publication):
                record = replace(published, review_state=review_state, publication_status=publication)
                joined = public_catalog([fixture_world("sm")], {"sm": record})[0]
                self.assertEqual(joined["editorial"] is not None, visible)
                if visible:
                    self.assertEqual(joined["editorial"]["copy"]["answer"], published.copy.answer)

    def test_duplicate_display_names_have_distinct_detail_metadata(self):
        self.worlds = [fixture_world("first", "Same Game"), fixture_world("second", "Same Game")]
        worlds = self.client.get("/api/apworlds").get_json()
        self.assertEqual(len({world["detail_title"] for world in worlds}), 2)
        self.assertEqual(len({world["detail_description"] for world in worlds}), 2)
        for world in worlds:
            html = self.client.get(world["detail_href"]).get_data(as_text=True)
            self.assertIn(f'<title>{world["detail_title"]}</title>', html)
            self.assertIn(world["name"], world["detail_title"])

    def test_long_names_keep_full_heading_and_compact_metadata(self):
        name = "A community integration with a very long descriptive game name"
        self.worlds = [fixture_world("long_name", name)]
        world = self.client.get("/api/apworlds").get_json()[0]
        html = self.client.get(world["detail_href"]).get_data(as_text=True)
        self.assertLessEqual(len(world["detail_title"]), 65)
        self.assertIn(f"<h1>{name} Archipelago</h1>", html)
        self.assertIn(f'<title>{world["detail_title"]}</title>', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
