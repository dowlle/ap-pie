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

    def test_bk_periods_coalescing_and_migration_idempotence(self):
        room_id = self.room["id"]
        db.associate_generated_room(room_id, "https://archipelago.gg/tracker/test-room", "test-room", self.host_id,
                                   [{"team": 0, "slot": 1, "player_name": "Appletini", "game": "Super Metroid",
                                     "yaml_id": self.yaml["id"], "yaml_owner_user_id": self.player_id}])
        first = db.update_room_slot_state(room_id, 0, 1, self.player_id, bk_action="set", slot_note="x" * 280,
                                          ping_policy="disabled")
        self.assertEqual(first["updated_by_username"], "CoordPlayer")
        self.assertEqual(first["ping_policy"], "disabled")
        for _ in range(3):
            confirmed = db.update_room_slot_state(room_id, 0, 1, self.host_id, bk_action="confirm")
            db.record_bk_confirmation(room_id, 0, 1, self.host_id, "Host confirmed Still BK", bk_since=confirmed["bk_since"])
            self.assertEqual(first["bk_since"], confirmed["bk_since"])
        events = db.get_activity(room_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["actor_user_id"], self.host_id)
        db.rollback_request_transaction()
        db.init_db(self.db_url)
        self.assertEqual(db.get_room_slot(room_id, 0, 1)["slot_note"], "x" * 280)
        cleared = db.update_room_slot_state(room_id, 0, 1, self.player_id, bk_action="clear")
        self.assertIsNone(cleared["bk_confirmed_at"])
        # A confirmation racing a clear must never start a blocked period.
        confirmed = db.update_room_slot_state(room_id, 0, 1, self.player_id, bk_action="confirm")
        self.assertIsNone(confirmed["bk_since"])
        self.assertIsNone(confirmed["bk_confirmed_at"])
        again = db.update_room_slot_state(room_id, 0, 1, self.player_id, bk_action="set")
        self.assertGreater(again["bk_since"], first["bk_since"])
        # A delayed confirmation from an earlier period cannot affect the new one.
        db.record_bk_confirmation(room_id, 0, 1, self.host_id, "Stale confirmation", bk_since=first["bk_since"])
        self.assertEqual(len(db.get_activity(room_id)), 1)
        db.record_bk_confirmation(room_id, 0, 1, self.host_id, "Host confirmed Still BK again", bk_since=again["bk_since"])
        self.assertEqual(len(db.get_activity(room_id)), 2)
        self.assertEqual(db.get_room_slot(room_id, 0, 1)["updated_by_user_id"], self.player_id)


if __name__ == "__main__":
    unittest.main()
