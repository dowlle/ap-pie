"""Optional anonymous session checks without a database or application workers."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ap-web"))

from flask import Flask, jsonify
import config
import app as application
from auth import requires_auth
from api import auth_routes


class CatalogSessionTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test-only"
        self.app.register_blueprint(auth_routes.bp)

        @self.app.get("/api/protected-test")
        @requires_auth
        def protected():
            return jsonify(ok=True)

        self.client = self.app.test_client()

    def test_anonymous_probe_is_public_but_strict_me_and_protected_stay_private(self):
        with patch.object(config, "DISCORD_CLIENT_ID", "fixture"), patch.object(config, "DISCORD_CLIENT_SECRET", "fixture"):
            response = self.client.get("/api/auth/me?optional=1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {"user": None, "auth_enabled": True})
            self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
            self.assertEqual(self.client.get("/api/protected-test").status_code, 401)

    def test_auth_not_configured_needs_no_protected_probe(self):
        with patch.object(config, "DISCORD_CLIENT_ID", ""), patch.object(config, "DISCORD_CLIENT_SECRET", ""):
            self.assertEqual(self.client.get("/api/auth/me?optional=1").json,
                             {"user": None, "auth_enabled": False})

    def test_signed_in_response_and_owner_flag_are_preserved(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 42
        user = {"id": 42, "discord_id": "fixture", "is_admin": False, "is_approved": True}
        with patch.object(auth_routes, "get_user", return_value=user), patch.object(config, "OWNER_DISCORD_ID", "fixture"):
            self.assertEqual(self.client.get("/api/auth/me?optional=1").json, {**user, "is_owner": True})

    def test_missing_account_clears_session(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 42
        with patch.object(auth_routes, "get_user", return_value=None):
            self.assertEqual(self.client.get("/api/auth/me?optional=1").json["user"], None)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_pending_deletion_remains_signed_out(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 42
        with patch.object(auth_routes, "get_user", return_value={"deletion_due_at": "2026-11-20"}):
            self.assertEqual(self.client.get("/api/auth/me?optional=1").json["user"], None)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)

    def test_public_favicon_and_optional_session_cache_policy(self):
        # Disable every startup worker and replace the server manager. This
        # tests the real catch-all route without managing any game process.
        with patch.object(config, "SECRET_KEY", "test-only"), \
                patch.object(config, "CORS_ORIGINS", "http://localhost"), \
                patch.object(config, "DATABASE_URL", ""), \
                patch.dict("os.environ", {"AP_INDEX_WARM": "0"}), \
                patch("db.init_db", side_effect=RuntimeError("test database disabled")), \
                patch.object(application, "ServerManager"):
            client = application.create_app().test_client()
            response = client.get("/favicon.ico")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, "image/svg+xml")
            self.assertIn(b"<svg", response.data)
            session_response = client.get("/api/auth/me?optional=1")
            self.assertEqual(session_response.status_code, 200)
            self.assertEqual(session_response.headers["Cache-Control"], "no-store")
            request_page = client.get("/report-issue")
            self.assertEqual(request_page.status_code, 200)
            self.assertIn(b'id="request-an-apworld"', request_page.data)


if __name__ == "__main__":
    unittest.main()
