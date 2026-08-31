#!/usr/bin/env python3
"""Focused integration checks for account recovery and permanent erasure."""

from __future__ import annotations

import hashlib
import os
import stat
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from flask import Flask

repo_app = os.path.join(os.path.dirname(__file__), "..", "ap-web")
sys.path.insert(0, repo_app if os.path.isdir(repo_app) else "/app")

import account_erasure
import config
import db
import api.auth_routes as auth_routes
from psycopg2.extensions import TRANSACTION_STATUS_IDLE
from api.account import bp as account_bp
from api.auth_routes import bp as auth_bp
from auth import apply_auth_to_app


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "DATABASE_URL not set")
class AccountLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        db.init_db(os.environ["DATABASE_URL"])

    def test_grace_recovery_hard_delete_and_restore_replay(self) -> None:
        token = uuid.uuid4().hex
        temp = tempfile.TemporaryDirectory()
        original = (
            config.ACCOUNT_ERASURE_LEDGER,
            config.OUTPUT_DIR,
            config.ACCOUNT_ERASURE_RECEIPT_DAYS,
        )
        config.ACCOUNT_ERASURE_LEDGER = str(Path(temp.name) / "receipts.jsonl")
        config.OUTPUT_DIR = str(Path(temp.name) / "output")
        config.ACCOUNT_ERASURE_RECEIPT_DAYS = 14
        Path(config.OUTPUT_DIR).mkdir()

        conn = db._get_conn()
        user_id = other_id = None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO users
                              (discord_id, discord_username, room_creation_blocked)
                       VALUES (%s, %s, TRUE) RETURNING id""",
                    (f"delete-{token}", f"Delete Me {token}"),
                )
                user_id = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO users (discord_id, discord_username)
                       VALUES (%s, %s) RETURNING id""",
                    (f"other-{token}", f"Other {token}"),
                )
                other_id = cur.fetchone()[0]
            conn.commit()

            owned = db.create_room("Owned", "Delete Me", host_user_id=user_id)
            other = db.create_room("Other", "Other", host_user_id=other_id)
            seed = f"erase_{token}"
            db.update_room(owned["id"], seed=seed)
            owned_yaml = db.add_yaml(
                owned["id"], "OtherSlot", "Test", "name: OtherSlot\ngame: Test\n",
                "other.yaml", submitter_user_id=other_id,
            )
            submitted_yaml = db.add_yaml(
                other["id"], f"DeleteSlot{token}", "Test",
                f"name: DeleteSlot{token}\ngame: Test\n", "delete.yaml",
                submitter_user_id=user_id,
            )
            db.add_activity(
                other["id"], "yaml_submitted", f"Delete Me {token} uploaded a YAML",
                actor_user_id=user_id, subject_yaml_id=submitted_yaml["id"],
            )
            db.create_user_yaml(
                user_id=user_id, apworld_name="test", version="1",
                player_name="DeleteSlot", label="Mine", kind="simple",
                option_values={}, yaml_content=None,
            )
            db.create_preset(
                apworld_name="test", version="1", name="Mine", description="",
                kind="simple", option_values={}, yaml_content=None,
                author_user_id=user_id,
            )
            db.create_room_template(user_id, "Mine", {"description": "test"})
            db.insert_event("page_view", user_id=user_id, room_id=owned["id"], props={})
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO apworld_maintainers
                              (apworld_name, discord_user_id, granted_by)
                       VALUES (%s, %s, %s)""",
                    (f"kept-{token}", f"other-{token}", user_id),
                )
                cur.execute(
                    """INSERT INTO apworld_maintainers
                              (apworld_name, discord_user_id, granted_by)
                       VALUES (%s, %s, %s)""",
                    (f"removed-{token}", f"delete-{token}", other_id),
                )
                cur.execute(
                    """INSERT INTO apworld_index_requests
                              (apworld_name, display_name, requested_version,
                               source_url, requester_user_id, requester_role)
                       VALUES (%s, 'Test', '1', 'https://example.test/test', %s, 'room_host')""",
                    (f"request-{token}", user_id),
                )
            conn.commit()

            exported = db.export_account_data(user_id)
            self.assertEqual(exported["account"]["id"], user_id)
            self.assertIn(
                submitted_yaml["id"], {row["id"] for row in exported["submissions"]}
            )
            self.assertNotIn(
                owned_yaml["id"], {row["id"] for row in exported["submissions"]}
            )

            # First scheduling is reversible and changes no content.
            first = hashlib.sha256(b"first").hexdigest()
            db.create_account_deletion_token(user_id, first)
            scheduled = db.schedule_account_deletion(user_id, first, 7)
            self.assertTrue(scheduled["deletion_due_at"])
            self.assertTrue(db.get_room(owned["id"]))
            self.assertEqual(account_erasure.process_due_account(user_id), {})
            self.assertTrue(db.cancel_account_deletion(user_id))
            self.assertIsNone(db.get_user(user_id)["deletion_due_at"])

            # Schedule an already-due deletion, then let the production worker
            # write its off-DB receipt and perform the irreversible graph erase.
            second = hashlib.sha256(b"second").hexdigest()
            db.create_account_deletion_token(user_id, second)
            db.schedule_account_deletion(user_id, second, 0)
            Path(config.OUTPUT_DIR, f"AP_{seed}.zip").write_bytes(b"zip")
            Path(config.OUTPUT_DIR, f"AP_{seed}.apsave").write_bytes(b"save")
            Path(config.OUTPUT_DIR, f"AP_{seed}.versions.json").write_text("{}")
            removed = account_erasure.process_due_accounts()
            self.assertEqual(len(removed), 1)
            self.assertFalse(db.get_user(user_id))
            self.assertFalse(db.get_room(owned["id"]))
            self.assertTrue(db.get_room(other["id"]))
            self.assertIsNone(db.get_yaml(submitted_yaml["id"]))
            self.assertFalse(Path(config.OUTPUT_DIR, f"AP_{seed}.zip").exists())
            self.assertFalse(Path(config.OUTPUT_DIR, f"AP_{seed}.apsave").exists())
            self.assertFalse(Path(config.OUTPUT_DIR, f"AP_{seed}.versions.json").exists())

            with conn.cursor() as cur:
                cur.execute(
                    "SELECT granted_by FROM apworld_maintainers WHERE apworld_name = %s",
                    (f"kept-{token}",),
                )
                self.assertIsNone(cur.fetchone()[0])
                cur.execute(
                    "SELECT 1 FROM apworld_maintainers WHERE apworld_name = %s",
                    (f"removed-{token}",),
                )
                self.assertIsNone(cur.fetchone())

            receipts = account_erasure.list_receipts()
            self.assertEqual(receipts[0]["user_id"], user_id)
            self.assertEqual(
                stat.S_IMODE(Path(config.ACCOUNT_ERASURE_LEDGER).stat().st_mode),
                0o600,
            )

            # Simulate an older database dump bringing the erased id back. The
            # receipt replay must remove it before normal service resumes.
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO users (id, discord_id, discord_username)
                       VALUES (%s, %s, %s)""",
                    (user_id, f"delete-{token}", "Restored old row"),
                )
            conn.commit()
            account_erasure.process_due_accounts()
            self.assertFalse(db.get_user(user_id))

            recreated = db.create_or_update_user(f"delete-{token}", "Recreated")
            self.assertTrue(recreated["room_creation_blocked"])
            db.set_user_room_creation_blocked(recreated["id"], False)
            refreshed = db.create_or_update_user(f"delete-{token}", "Recreated")
            self.assertFalse(refreshed["room_creation_blocked"])
        finally:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rooms WHERE host_user_id = %s", (other_id,))
                cur.execute(
                    "DELETE FROM apworld_maintainers WHERE apworld_name IN (%s, %s)",
                    (f"kept-{token}", f"removed-{token}"),
                )
                cur.execute("DELETE FROM users WHERE discord_id IN (%s, %s)", (
                    f"delete-{token}", f"other-{token}",
                ))
                cur.execute(
                    "DELETE FROM room_creation_blocks WHERE discord_id_hmac = %s",
                    (db.discord_id_hmac(f"delete-{token}"),),
                )
            conn.commit()
            (
                config.ACCOUNT_ERASURE_LEDGER,
                config.OUTPUT_DIR,
                config.ACCOUNT_ERASURE_RECEIPT_DAYS,
            ) = original
            temp.cleanup()

    def test_empty_sweeper_read_closes_its_transaction(self) -> None:
        db.list_due_account_deletions()
        self.assertEqual(
            db._get_conn().get_transaction_status(), TRANSACTION_STATUS_IDLE
        )

    def test_oauth_reauth_schedule_and_same_identity_recovery(self) -> None:
        token = uuid.uuid4().hex
        temp = tempfile.TemporaryDirectory()
        original_auth = (
            config.DISCORD_CLIENT_ID,
            config.DISCORD_CLIENT_SECRET,
            config.OWNER_DISCORD_ID,
            config.ACCOUNT_ERASURE_LEDGER,
            config.OUTPUT_DIR,
        )
        config.DISCORD_CLIENT_ID = "test-client"
        config.DISCORD_CLIENT_SECRET = "test-secret"
        config.OWNER_DISCORD_ID = ""
        config.ACCOUNT_ERASURE_LEDGER = str(Path(temp.name) / "receipts.jsonl")
        config.OUTPUT_DIR = str(Path(temp.name) / "output")
        Path(config.OUTPUT_DIR).mkdir()
        user = db.create_or_update_user(f"oauth-{token}", f"OAuth {token}")

        app = Flask(__name__)
        app.secret_key = "account-lifecycle-test"
        app.register_blueprint(auth_bp)
        app.register_blueprint(account_bp)
        apply_auth_to_app(app)

        try:
            client = app.test_client()
            other_session = app.test_client()
            for test_client in (client, other_session):
                with test_client.session_transaction() as sess:
                    sess["user_id"] = user["id"]

            started = client.get("/api/auth/account-delete-reauth")
            self.assertEqual(started.status_code, 302)
            with client.session_transaction() as sess:
                state = sess["oauth_state"]

            with (
                mock.patch.object(auth_routes, "exchange_code", return_value={"access_token": "test"}),
                mock.patch.object(
                    auth_routes,
                    "get_discord_user",
                    return_value={"id": f"oauth-{token}", "global_name": f"OAuth {token}"},
                ),
            ):
                callback = client.get(f"/api/auth/callback?state={state}&code=test")
            self.assertEqual(callback.status_code, 302)
            self.assertIn("/my/account?delete=ready", callback.location)

            scheduled = client.post(
                "/api/my/account/deletion", json={"confirmation": "DELETE"}
            )
            self.assertEqual(scheduled.status_code, 200)
            self.assertEqual(scheduled.headers.get("Clear-Site-Data"), '"cache", "storage"')
            self.assertTrue(db.get_user(user["id"])["deletion_due_at"])

            # A second signed cookie is invalidated as soon as it touches any
            # endpoint; there is no server-side session list to enumerate.
            self.assertEqual(other_session.get("/api/auth/me").status_code, 401)

            login = client.get("/api/auth/login?next=/account-recovery")
            self.assertEqual(login.status_code, 302)
            with client.session_transaction() as sess:
                recovery_state = sess["oauth_state"]
            with (
                mock.patch.object(auth_routes, "exchange_code", return_value={"access_token": "test"}),
                mock.patch.object(
                    auth_routes,
                    "get_discord_user",
                    return_value={"id": f"oauth-{token}", "global_name": f"OAuth {token}"},
                ),
            ):
                recovery_callback = client.get(
                    f"/api/auth/callback?state={recovery_state}&code=test"
                )
            self.assertEqual(recovery_callback.status_code, 302)
            self.assertIn("/account-recovery", recovery_callback.location)
            self.assertEqual(client.get("/api/auth/account-recovery").status_code, 200)
            self.assertEqual(client.post("/api/auth/account-recovery").status_code, 200)
            self.assertEqual(client.get("/api/auth/me").status_code, 200)
            self.assertIsNone(db.get_user(user["id"])["deletion_due_at"])

            for _ in range(4):
                self.assertEqual(
                    client.get("/api/auth/account-delete-reauth").status_code, 302
                )
            limited = client.get("/api/auth/account-delete-reauth")
            self.assertEqual(limited.status_code, 429)
            self.assertGreater(int(limited.headers["Retry-After"]), 0)

            # At the exact deadline recovery closes. A fresh OAuth callback
            # completes the due erasure synchronously and creates an empty new
            # account instead of trapping the person in the sweeper interval.
            expired_token = hashlib.sha256(b"expired").hexdigest()
            db.create_account_deletion_token(user["id"], expired_token)
            db.schedule_account_deletion(user["id"], expired_token, 0)
            expired_login = client.get("/api/auth/login")
            self.assertEqual(expired_login.status_code, 302)
            with client.session_transaction() as sess:
                expired_state = sess["oauth_state"]
            with (
                mock.patch.object(auth_routes, "exchange_code", return_value={"access_token": "test"}),
                mock.patch.object(
                    auth_routes,
                    "get_discord_user",
                    return_value={"id": f"oauth-{token}", "global_name": f"OAuth {token}"},
                ),
            ):
                expired_callback = client.get(
                    f"/api/auth/callback?state={expired_state}&code=test"
                )
            self.assertEqual(expired_callback.status_code, 302)
            self.assertIn("/my/account?deletion=completed", expired_callback.location)
            self.assertFalse(db.get_user(user["id"]))
            recreated = db.get_user_by_discord_id(f"oauth-{token}")
            self.assertTrue(recreated)
            self.assertNotEqual(recreated["id"], user["id"])
            self.assertEqual(client.get("/api/auth/me").status_code, 200)
        finally:
            conn = db._get_conn()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE discord_id = %s", (f"oauth-{token}",))
            conn.commit()
            (
                config.DISCORD_CLIENT_ID,
                config.DISCORD_CLIENT_SECRET,
                config.OWNER_DISCORD_ID,
                config.ACCOUNT_ERASURE_LEDGER,
                config.OUTPUT_DIR,
            ) = original_auth
            temp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
