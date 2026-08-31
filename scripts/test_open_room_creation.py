#!/usr/bin/env python3
"""Focused authorization and quota checks for public room creation."""

from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

from flask import Blueprint, Flask, jsonify

repo_app = os.path.join(os.path.dirname(__file__), "..", "ap-web")
sys.path.insert(0, repo_app if os.path.isdir(repo_app) else "/app")

import config
import db
import api.rooms as rooms_api
from api.rooms import _open_room_creation_error
from auth import apply_auth_to_app


class OpenRoomAuthorization(unittest.TestCase):
    def setUp(self) -> None:
        self.original_features = dict(config.FEATURES)
        self.original_client_id = config.DISCORD_CLIENT_ID
        self.original_client_secret = config.DISCORD_CLIENT_SECRET
        config.DISCORD_CLIENT_ID = "test-client"
        config.DISCORD_CLIENT_SECRET = "test-secret"

        self.app = Flask(__name__)
        self.app.secret_key = "test-only"
        apply_auth_to_app(self.app)

        @self.app.route("/api/rooms")
        def rooms():
            return jsonify({"ok": True})

        templates_bp = Blueprint("room_templates", __name__)

        @templates_bp.route("/api/users/me/room-templates")
        def room_templates():
            return jsonify({"ok": True})

        self.app.register_blueprint(templates_bp)

        personal_bp = Blueprint("user_yamls", __name__)

        @personal_bp.route("/api/my/yamls")
        def saved_yamls():
            return jsonify({"ok": True})

        self.app.register_blueprint(personal_bp)

        rooms_bp = Blueprint("rooms", __name__)

        @rooms_bp.route("/api/rooms/<room_id>/generate")
        def room_generate(room_id: str):
            return jsonify({"ok": True, "room_id": room_id})

        self.app.register_blueprint(rooms_bp)

        @self.app.route("/api/roomsmith")
        def roomsmith():
            return jsonify({"ok": True})

    def tearDown(self) -> None:
        config.FEATURES.clear()
        config.FEATURES.update(self.original_features)
        config.DISCORD_CLIENT_ID = self.original_client_id
        config.DISCORD_CLIENT_SECRET = self.original_client_secret

    def _get(self, path: str, user: dict | None = None):
        with mock.patch.object(db, "get_user", return_value=user):
            with self.app.test_client() as client:
                if user:
                    with client.session_transaction() as session:
                        session["user_id"] = user["id"]
                return client.get(path)

    def test_anonymous_user_still_needs_discord_login(self) -> None:
        config.FEATURES["open_room_creation"] = True
        self.assertEqual(self._get("/api/rooms").status_code, 401)

    def test_unapproved_user_gets_room_surfaces_only_when_open(self) -> None:
        user = {"id": 7, "is_admin": False, "is_approved": False}
        config.FEATURES["open_room_creation"] = False
        self.assertEqual(self._get("/api/rooms", user).status_code, 403)

        config.FEATURES["open_room_creation"] = True
        self.assertEqual(self._get("/api/rooms", user).status_code, 200)
        self.assertEqual(
            self._get("/api/users/me/room-templates", user).status_code,
            200,
        )
        self.assertEqual(self._get("/api/my/yamls", user).status_code, 200)
        self.assertEqual(self._get("/api/rooms/example/generate", user).status_code, 403)
        self.assertEqual(self._get("/api/roomsmith", user).status_code, 403)


class OpenRoomQuotas(unittest.TestCase):
    def setUp(self) -> None:
        self.original = (
            config.ROOM_CREATION_PER_HOUR,
            config.ROOM_CREATION_MAX_ACTIVE,
            config.ROOM_CREATION_MAX_TOTAL,
        )
        config.ROOM_CREATION_PER_HOUR = 5
        config.ROOM_CREATION_MAX_ACTIVE = 10
        config.ROOM_CREATION_MAX_TOTAL = 50

    def tearDown(self) -> None:
        (
            config.ROOM_CREATION_PER_HOUR,
            config.ROOM_CREATION_MAX_ACTIVE,
            config.ROOM_CREATION_MAX_TOTAL,
        ) = self.original

    def test_quota_order_and_statuses(self) -> None:
        user = {"room_creation_blocked": True}
        self.assertEqual(
            _open_room_creation_error(user, {"recent": 0, "active": 0, "total": 0})[1],
            403,
        )

        user["room_creation_blocked"] = False
        self.assertEqual(
            _open_room_creation_error(user, {"recent": 5, "active": 0, "total": 0})[1],
            429,
        )
        self.assertEqual(
            _open_room_creation_error(user, {"recent": 0, "active": 10, "total": 10})[1],
            409,
        )
        self.assertEqual(
            _open_room_creation_error(user, {"recent": 0, "active": 0, "total": 50})[1],
            409,
        )
        self.assertIsNone(
            _open_room_creation_error(user, {"recent": 4, "active": 9, "total": 49})
        )


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "DATABASE_URL not set")
class OpenRoomDatabaseCounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db.init_db(os.environ["DATABASE_URL"])

    def test_migration_and_room_counters(self) -> None:
        token = uuid.uuid4().hex
        conn = db._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO users
                       (discord_id, discord_username, room_creation_blocked)
                   VALUES (%s, %s, FALSE)
                   RETURNING id, room_creation_blocked""",
                (f"open-room-test-{token}", f"open-room-test-{token}"),
            )
            user_id, blocked = cur.fetchone()
            self.assertFalse(blocked)
        conn.commit()

        room_ids = []
        try:
            for status in ("open", "closed", "generated"):
                room = db.create_room(
                    name=f"test-{status}",
                    host_name="open-room-test",
                    host_user_id=user_id,
                )
                room_ids.append(room["id"])
                db.update_room(room["id"], status=status)

            counts = db.get_room_creation_counts(user_id)
            self.assertEqual(counts, {"total": 3, "active": 1, "recent": 3})
        finally:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rooms WHERE id = ANY(%s)", (room_ids,))
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "DATABASE_URL not set")
class OpenRoomCreateRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db.init_db(os.environ["DATABASE_URL"])
        # api.rooms imports this sentinel by value; production imports the
        # blueprint after init_db, while this focused test imports it earlier.
        rooms_api._db_url = os.environ["DATABASE_URL"]

    def setUp(self) -> None:
        self.original_features = dict(config.FEATURES)
        self.original_client_id = config.DISCORD_CLIENT_ID
        self.original_client_secret = config.DISCORD_CLIENT_SECRET
        config.DISCORD_CLIENT_ID = "test-client"
        config.DISCORD_CLIENT_SECRET = "test-secret"

        token = uuid.uuid4().hex
        conn = db._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO users (discord_id, discord_username)
                   VALUES (%s, %s) RETURNING id""",
                (f"open-route-test-{token}", f"open-route-test-{token}"),
            )
            self.user_id = cur.fetchone()[0]
        conn.commit()

        self.app = Flask(__name__)
        self.app.secret_key = "test-only"
        self.app.register_blueprint(rooms_api.bp)
        apply_auth_to_app(self.app)

    def tearDown(self) -> None:
        conn = db._get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rooms WHERE host_user_id = %s", (self.user_id,))
            cur.execute("DELETE FROM users WHERE id = %s", (self.user_id,))
        conn.commit()
        config.FEATURES.clear()
        config.FEATURES.update(self.original_features)
        config.DISCORD_CLIENT_ID = self.original_client_id
        config.DISCORD_CLIENT_SECRET = self.original_client_secret

    def _post_room(self):
        with self.app.test_client() as client:
            with client.session_transaction() as session:
                session["user_id"] = self.user_id
            return client.post(
                "/api/rooms",
                json={"name": "Open access test", "host_name": "route-test"},
            )

    def test_create_route_obeys_feature_and_account_block(self) -> None:
        config.FEATURES["open_room_creation"] = False
        self.assertEqual(self._post_room().status_code, 403)

        config.FEATURES["open_room_creation"] = True
        created = self._post_room()
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json()["host_user_id"], self.user_id)

        db.set_user_room_creation_blocked(self.user_id, True)
        self.assertEqual(self._post_room().status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
