"""Library update and save measurement tests. Use a disposable DATABASE_URL."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ap-web"))
from flask import Flask
from werkzeug.exceptions import RequestEntityTooLarge
from app import oversized_request_response
import db
from api import presets, rooms, submit, user_yamls
from yaml_limits import MAX_BUILDER_YAML_BYTES, MAX_OPTION_VALUES_BYTES


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "Disposable database required")
class LibraryJourneys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db(os.environ["DATABASE_URL"])
        # Production imports API blueprints after database initialization.
        for module in (user_yamls, presets, rooms, submit):
            cls.enterClassContext(patch.object(module, "_db_url", db._db_url))
        cls.app = Flask(__name__)
        cls.app.secret_key = "disposable-journeys-only"
        cls.app.register_error_handler(RequestEntityTooLarge, oversized_request_response)
        for module in (user_yamls, presets, rooms, submit):
            cls.app.register_blueprint(module.bp)
        cls.app.teardown_request(lambda _: db.rollback_request_transaction())

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
            cur.execute("DELETE FROM apworld_presets WHERE author_user_id = %s", (self.user["id"],))
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


    @staticmethod
    def sized_yaml(size):
        header = "name: Sized\ngame: Fixture\nFixture: {}\n# "
        units, remainder = divmod(size - len(header), 2)
        return header + "é" * units + "x" * remainder

    def check_storage_boundaries(self, limit, payload):
        metadata = {"apworld_name": "fixture", "version": "1", "player_name": "Sized", "name": "Sized"}
        schema = {"schema": {"options": [{"name": "locks"}, {"name": "large"}]}}
        with patch.object(presets, "_schema_for", return_value=(SimpleNamespace(game_name="Fixture"), schema)):
            for path, method in [
                ("/api/my/yamls", self.client.post),
                (f'/api/my/yamls/{self.entry["id"]}', self.client.patch),
                ("/api/presets", self.client.post),
            ]:
                for size in (limit - 1, limit + 1):
                    with self.subTest(path=path, size=size):
                        data = payload(size)
                        response = method(path, json={**metadata, **data})
                        if size < limit:
                            self.assertIn(response.status_code, (200, 201))
                            key = "yaml_content" if data["kind"] == "advanced" else "values"
                            self.assertEqual(response.json[key], data[key])
                        else:
                            self.assertEqual(response.status_code, 400)
                            self.assertIn(f"{size:,} bytes", response.json["error"])
                            self.assertIn(f"{limit:,} bytes", response.json["error"])
                            if data["kind"] == "simple":
                                self.assertEqual(response.json["code"], "option_values_too_large")

    def test_library_and_preset_yaml_byte_boundaries(self):
        self.check_storage_boundaries(
            MAX_BUILDER_YAML_BYTES,
            lambda size: {"kind": "advanced", "yaml_content": self.sized_yaml(size)},
        )

    def test_library_and_preset_option_byte_boundaries(self):
        # JSONB expands small exponents that would fit in the request JSON.
        overhead = len('{"locks": "", "large": 0.' + "0" * 99 + "1}")
        self.check_storage_boundaries(
            MAX_OPTION_VALUES_BYTES,
            lambda size: {"kind": "simple", "values": {"locks": "x" * (size - overhead), "large": 1e-100}},
        )

    def test_public_and_host_submission_request_boundaries(self):
        # Exercise the same request cap with a smaller value to avoid
        # parsing the default 50 MiB several times in CI.
        limit = 2 * MAX_BUILDER_YAML_BYTES

        def body_for(text):
            return json.dumps({"yaml_content": text}, ensure_ascii=False, separators=(",", ":")).encode()

        def multipart_body(text):
            return (
                b'--fixture\r\nContent-Disposition: form-data; name="file"; filename="sized.yaml"\r\n'
                b'Content-Type: text/yaml\r\n\r\n'
                + text.encode() + b"\r\n--fixture--\r\n"
            )

        sample = self.sized_yaml(50)
        with patch.dict(self.app.config, MAX_CONTENT_LENGTH=limit), patch(
            "api.apworlds.auto_pin_for_room_game",
        ), patch("api.apworlds._get_game_lookup", return_value={}):
            for public, multipart in [(True, False), (False, False), (True, True), (False, True)]:
                room = db.create_room("Size boundary", "Journey test", host_user_id=self.user["id"])
                self.addCleanup(db.delete_room, room["id"])
                path = f'/api/submit/{room["id"]}' if public else f'/api/rooms/{room["id"]}/yamls'
                if not public and not multipart:
                    path += "/create"
                encode = multipart_body if multipart else body_for
                content_type = "multipart/form-data; boundary=fixture" if multipart else "application/json"
                overhead = len(encode(sample)) - len(sample.encode())
                for size in (limit - 1, limit + 1):
                    with self.subTest(path=path, multipart=multipart, size=size):
                        body = encode(self.sized_yaml(size - overhead))
                        self.assertEqual(len(body), size)
                        response = self.client.post(path, data=body, content_type=content_type)
                        self.assertEqual(response.status_code, 201 if size < limit else 413)
                        if size < limit:
                            self.assertEqual(response.json["validation_status"], "validated")
                        else:
                            self.assertIn(f"{size:,} bytes", response.json["error"])
                            self.assertIn(f"{limit:,} bytes", response.json["error"])
                self.assertEqual(len(db.get_yamls(room["id"])), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
