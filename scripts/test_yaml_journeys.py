"""Library update and save measurement tests. Use a disposable DATABASE_URL."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ap-web"))
from flask import Flask
import db
from api import user_yamls


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "Disposable database required")
class LibraryJourneys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db(os.environ["DATABASE_URL"])
        # Production imports API blueprints after database initialization.
        user_yamls._db_url = db._db_url
        cls.app = Flask(__name__)
        cls.app.secret_key = "disposable-journeys-only"
        cls.app.register_blueprint(user_yamls.bp)

    def setUp(self):
        self.user = db.create_or_update_user(uuid.uuid4().hex, "Journey test")
        self.other = db.create_or_update_user(uuid.uuid4().hex, "Other test")
        self.entry = db.create_user_yaml(user_id=self.user["id"], apworld_name="fixture", version="1", player_name="Original", label="Keep this label", kind="simple", option_values={"locks": 7}, yaml_content=None)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = self.user["id"]
        self.annotate = patch.object(user_yamls, "_annotate", side_effect=lambda value: value)
        self.annotate.start()

    def tearDown(self):
        self.annotate.stop()
        conn = db._get_conn()
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id IN (%s, %s)", (self.user["id"], self.other["id"]))
        conn.commit()

    def update(self, body):
        return self.client.patch(f'/api/my/yamls/{self.entry["id"]}', json=body)

    def test_update_keeps_id_and_label_then_preserves_advanced_document(self):
        response = self.update({"kind": "simple", "version": "1", "player_name": "Changed", "values": {"locks": 9}})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["id"], self.entry["id"])
        self.assertEqual(response.json["label"], "Keep this label")
        self.assertEqual(len(db.list_user_yamls(self.user["id"])), 1)
        text = "name: Changed\ngame: Fixture\nFixture:\n  locks: 9\n  house_rule: untouched\n"
        response = self.update({"kind": "advanced", "yaml_content": text})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["yaml_content"], text)
        self.assertIsNone(response.json["values"])
        response = self.update({"kind": "simple", "values": {"locks": 3}})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertIsNone(response.json["yaml_content"])

    def test_invalid_updates_and_version_change_leave_original_untouched(self):
        for body in [{"kind": "advanced"}, {"kind": "advanced", "yaml_content": "broken: ["}, {"kind": "advanced", "yaml_content": ""}, {"kind": "simple", "values": []}, {"version": "2"}]:
            self.assertEqual(self.update(body).status_code, 400)
            self.assertEqual(db.get_user_yaml(self.entry["id"])["values"], {"locks": 7})

    def test_library_ownership_is_still_enforced(self):
        with self.client.session_transaction() as session:
            session["user_id"] = self.other["id"]
        self.assertEqual(self.update({"values": {"locks": 0}}).status_code, 403)
        self.assertEqual(db.get_user_yaml(self.entry["id"])["values"], {"locks": 7})

    def test_saves_are_distinct_from_file_outputs_in_scorecard(self):
        attempt = uuid.uuid4().hex[:16]
        db.insert_event("builder_saved", ua_class="mobile", props={"game": "Fixture", "version": "1", "attempt_id": attempt})
        score = db.events_scorecard(1)
        row = next(row for row in score["devices"] if row["device"] == "mobile")
        self.assertGreaterEqual(row["saves"], 1)
        self.assertEqual(row["outputs"], 0)
        self.assertIn("builder_saved", {row["kind"] for row in score["human_external"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
