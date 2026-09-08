#!/usr/bin/env python3
"""Integration coverage for favorites, pre-YAML membership and cache repair.

Use a disposable DATABASE_URL. Never point this test at a live database.
"""
import hashlib
import io
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ap-web"))
from flask import Flask
import db
from api.account import bp
from api import apworlds
from apworld_options_parser import BUILDER_SCHEMA_FORMAT_VERSION
from auth import apply_auth_to_app


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "Disposable DATABASE_URL required")
class PersonalFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db(os.environ["DATABASE_URL"])
        db.init_db(os.environ["DATABASE_URL"])
        cls.app = Flask(__name__)
        cls.app.secret_key = "local-feature-tests-only"
        cls.app.register_blueprint(bp)
        apply_auth_to_app(cls.app)

    def setUp(self):
        self.users = [db.create_or_update_user(uuid.uuid4().hex, name) for name in ("Player", "Other")]
        self.room = db.create_room("Shared", "Other", host_user_id=self.users[1]["id"])
        self.client = self.app.test_client()

    def login(self, index=0):
        with self.client.session_transaction() as session:
            session["user_id"] = self.users[index]["id"]

    def tearDown(self):
        conn = db._get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rooms WHERE id = %s", (self.room["id"],))
            cur.execute("DELETE FROM users WHERE id IN (%s, %s)", tuple(u["id"] for u in self.users))
        conn.commit()

    def test_favorites_auth_scope_validation_and_idempotence(self):
        self.assertEqual(self.client.get("/api/my/favorite-games").status_code, 401)
        self.assertEqual(self.client.put("/api/my/favorite-games/test", json={}).status_code, 401)
        self.login()
        with patch.object(apworlds, "_get_index_worlds", return_value=[SimpleNamespace(name="test", disabled=False)]):
            self.assertEqual(self.client.put("/api/my/favorite-games/test").status_code, 415)
            for _ in range(2):
                response = self.client.put("/api/my/favorite-games/test", json={"user_id": self.users[1]["id"]})
                self.assertEqual(response.json, {"games": ["test"]})
            self.assertEqual(self.client.put("/api/my/favorite-games/unknown", json={}).status_code, 404)
        self.assertEqual(db.get_favorite_games(self.users[1]["id"]), [])
        db._get_conn().rollback()
        db.init_db(os.environ["DATABASE_URL"])
        self.assertEqual(self.client.get("/api/my/favorite-games").json, {"games": ["test"]})
        self.assertEqual(db.get_account_summary(self.users[0]["id"])["counts"]["favorite_games"], 1)
        self.assertEqual(db.export_account_data(self.users[0]["id"])["favorite_games"][0]["apworld_name"], "test")
        self.assertEqual(self.client.delete("/api/my/favorite-games/test", json={}).json, {"games": []})

    def test_join_before_yaml_persists_without_host_access(self):
        path = f'/api/my/rooms/{self.room["id"]}'
        self.assertEqual(self.client.put(path, json={}).status_code, 401)
        self.login()
        self.assertEqual(self.client.get("/api/my/rooms").json, {"rooms": []})
        for _ in range(2):
            response = self.client.put(path, json={})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json["rooms"]), 1)
        summary = response.json["rooms"][0]
        self.assertTrue(summary["joined"])
        self.assertFalse(summary["is_host"])
        self.assertEqual(set(summary), {"id", "name", "status", "submit_deadline", "is_host", "joined"})
        self.assertEqual(db.get_yamls(self.room["id"]), [])
        self.assertEqual(db.list_rooms(host_user_id=self.users[0]["id"]), [])
        self.assertEqual(db.get_room(self.room["id"])["host_user_id"], self.users[1]["id"])
        self.assertEqual(db.export_account_data(self.users[0]["id"])["room_memberships"][0]["room_id"], self.room["id"])
        self.assertEqual(self.client.delete(path, json={}).json, {"rooms": []})

    def test_join_obeys_closed_room_and_deadline(self):
        self.login()
        path = f'/api/my/rooms/{self.room["id"]}'
        db.update_room(self.room["id"], status="closed")
        self.assertEqual(self.client.put(path, json={}).status_code, 409)
        db.update_room(self.room["id"], status="open", submit_deadline="2000-01-01T00:00:00Z")
        self.assertEqual(self.client.put(path, json={}).status_code, 409)
        self.assertEqual(db.get_my_rooms(self.users[0]["id"]), [])

    def test_account_erasure_removes_both_libraries(self):
        user_id = self.users[0]["id"]
        db.set_favorite_game(user_id, "test", True)
        db.set_room_membership(user_id, self.room["id"], True)
        db.permanently_delete_account(user_id, receipt_replay=True)
        self.assertEqual(db.get_favorite_games(user_id), [])
        self.assertEqual(db.get_my_rooms(user_id), [])
        self.assertTrue(db.get_room(self.room["id"]))

    def test_negative_cache_retries_once_per_parser_version(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as z:
            z.writestr("fixture/__init__.py", "class W: pass")
        raw = data.getvalue()
        sha = hashlib.sha256(raw).hexdigest()
        db.set_builder_schema(sha, "fixture", "1", None)
        conn = db._get_conn()
        with conn.cursor() as cur:
            cur.execute("UPDATE apworld_builder_schemas SET parser_version = 0 WHERE sha256 = %s", (sha,))
        conn.commit()
        world = SimpleNamespace(name="fixture", display_name="Fixture", game_name="Fixture", disabled=False,
            versions=[SimpleNamespace(version="1", sha256=sha, url="https://example.com/fixture.apworld", local=None)])
        try:
            with self.app.app_context(), patch.object(apworlds, "_get_index_worlds", return_value=[world]), patch.object(apworlds, "_fetch_apworld_bytes", return_value=raw) as fetch:
                for _ in range(2):
                    self.assertIsNone(apworlds.builder_schemas_for_pins([{"apworld_name": "fixture", "version": "1"}])[0]["schema"])
                self.assertEqual(fetch.call_count, 1)
                self.assertEqual(db.get_builder_schema(sha)["parser_version"], BUILDER_SCHEMA_FORMAT_VERSION)
        finally:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM apworld_builder_schemas WHERE sha256 = %s", (sha,))
            conn.commit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
