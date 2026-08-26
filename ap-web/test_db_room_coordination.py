import os
import unittest

import db


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "TEST_DATABASE_URL is not configured")
class RoomCoordinationDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_url = os.environ["TEST_DATABASE_URL"]
        db.init_db(cls.db_url)

    def setUp(self):
        conn = db._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO users (discord_id, discord_username, is_approved)
                   VALUES ('coord-host', 'CoordHost', TRUE), ('coord-player', 'CoordPlayer', TRUE)
                   RETURNING id"""
            )
            self.host_id, self.player_id = [row[0] for row in cur.fetchall()]
        conn.commit()
        self.room = db.create_room("Coordination test", "CoordHost", host_user_id=self.host_id)
        self.yaml = db.add_yaml(
            self.room["id"], "Appletini", "Super Metroid", "name: Appletini", "Appletini.yaml",
            submitter_user_id=self.player_id,
        )

    def tearDown(self):
        conn = db._get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rooms WHERE id = %s", (self.room["id"],))
            cur.execute("DELETE FROM users WHERE discord_id IN ('coord-host', 'coord-player')")
        conn.commit()

    def test_schema_claim_lock_state_and_host_override(self):
        slots = db.associate_generated_room(
            self.room["id"], "https://archipelago.gg/tracker/test-room", "test-room", self.host_id,
            [{
                "team": 0, "slot": 1, "player_name": "Appletini", "game": "Super Metroid",
                "yaml_id": self.yaml["id"], "yaml_owner_user_id": self.player_id,
            }],
        )
        self.assertEqual(slots[0]["owner_user_id"], self.player_id)
        self.assertEqual(slots[0]["owner_source"], "yaml")

        corrected = db.associate_generated_room(
            self.room["id"], "https://archipelago.gg/tracker/test-room", "test-room", self.host_id,
            [{
                "team": 0, "slot": 1, "player_name": "Appletini", "game": "Super Metroid",
                "yaml_id": self.yaml["id"], "yaml_owner_user_id": self.host_id,
            }],
        )
        self.assertEqual(corrected[0]["owner_user_id"], self.host_id)
        restored = db.associate_generated_room(
            self.room["id"], "https://archipelago.gg/tracker/test-room", "test-room", self.host_id,
            [{
                "team": 0, "slot": 1, "player_name": "Appletini", "game": "Super Metroid",
                "yaml_id": self.yaml["id"], "yaml_owner_user_id": self.player_id,
            }],
        )
        self.assertEqual(restored[0]["owner_user_id"], self.player_id)

        self.assertIsNotNone(db.release_room_slot(self.room["id"], 0, 1, self.player_id))
        # An explicit release locks the decision. Refreshing the YAML mapping
        # must not silently give the slot back to its former submitter.
        refreshed = db.associate_generated_room(
            self.room["id"], "https://archipelago.gg/tracker/test-room", "test-room", self.host_id,
            [{
                "team": 0, "slot": 1, "player_name": "Appletini", "game": "Super Metroid",
                "yaml_id": self.yaml["id"], "yaml_owner_user_id": self.player_id,
            }],
        )
        self.assertIsNone(refreshed[0]["owner_user_id"])
        self.assertTrue(refreshed[0]["ownership_locked"])

        self.assertIsNotNone(db.claim_room_slot(self.room["id"], 0, 1, self.host_id))
        self.assertIsNone(db.claim_room_slot(self.room["id"], 0, 1, self.player_id))

        state = db.update_room_slot_state(
            self.room["id"], 0, 1, self.host_id,
            bk_action="set", go_mode=True, slot_note="Waiting for Gravity Suit.",
        )
        self.assertIsNotNone(state["bk_since"])
        self.assertIsNotNone(state["bk_confirmed_at"])
        self.assertIsNotNone(state["go_mode_since"])
        self.assertEqual(state["slot_note"], "Waiting for Gravity Suit.")

        confirmed = db.update_room_slot_state(
            self.room["id"], 0, 1, self.host_id, bk_action="confirm",
        )
        self.assertEqual(confirmed["bk_since"], state["bk_since"])
        self.assertGreaterEqual(confirmed["bk_confirmed_at"], state["bk_confirmed_at"])

        cleared = db.update_room_slot_state(
            self.room["id"], 0, 1, self.host_id, bk_action="clear", go_mode=False,
        )
        self.assertIsNone(cleared["bk_since"])
        self.assertIsNone(cleared["go_mode_since"])

        assigned = db.assign_room_slot_owner(
            self.room["id"], 0, 1, self.player_id, self.host_id,
        )
        self.assertEqual(assigned["owner_user_id"], self.player_id)
        self.assertEqual(assigned["owner_source"], "host")


if __name__ == "__main__":
    unittest.main()
