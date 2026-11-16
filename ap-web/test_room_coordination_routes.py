import unittest
from unittest.mock import patch

from flask import Flask

from api import public


class RoomCoordinationRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = "test-only"
        app.register_blueprint(public.bp)
        app.testing = True
        self.client = app.test_client()
        self.db_available = patch.object(public, "_db_url", "test-db")
        self.db_available.start()

    def tearDown(self):
        self.db_available.stop()

    def login(self, user_id=7):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id

    @patch.object(public.analytics, "record_event")
    @patch.object(public, "get_yamls", return_value=[])
    @patch.object(public, "maybe_auto_close_room", return_value={
        "id": "room", "name": "Room", "description": "", "status": "closed",
        "host_name": "Host", "host_user_id": 7,
    })
    def test_anonymous_room_capabilities_do_not_grant_host_access(self, _room, _yamls, _analytics):
        response = self.client.get("/api/public/rooms/room")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["viewer_capabilities"]["can_manage_room"])
        self.assertNotIn("host_user_id", payload)

    @patch.object(public.analytics, "record_event")
    @patch.object(public, "get_yamls_with_submitters", return_value=[])
    @patch.object(public, "get_user", return_value={"id": 7, "discord_username": "Host"})
    @patch.object(public, "maybe_auto_close_room", return_value={
        "id": "room", "name": "Room", "description": "", "status": "closed",
        "host_name": "Host", "host_user_id": 7,
    })
    def test_host_receives_manage_capability_without_owner_identifier(
        self, _room, _user, _yamls, _analytics,
    ):
        self.login()
        response = self.client.get("/api/public/rooms/room")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["viewer_capabilities"]["can_manage_room"])
        self.assertNotIn("host_user_id", payload)

    @patch.object(public, "get_room", return_value={"id": "room", "host_user_id": 1})
    def test_anonymous_claim_is_rejected(self, _get_room):
        response = self.client.post("/api/public/rooms/room/slots/0/1/claim")
        self.assertEqual(response.status_code, 401)

    @patch("db.get_generated_room", return_value={"room_id": "room"})
    @patch("db.get_room_slot", return_value={"player_name": "Appletini", "owner_user_id": None})
    @patch("db.claim_room_slot", return_value=None)
    @patch.object(public, "get_user", return_value={"id": 7, "discord_username": "Player"})
    @patch.object(public, "get_room", return_value={"id": "room", "host_user_id": 1})
    def test_claim_race_returns_conflict(self, _room, _user, _claim, _slot, _association):
        self.login()
        response = self.client.post("/api/public/rooms/room/slots/0/1/claim")
        self.assertEqual(response.status_code, 409)

    @patch("db.get_room_slot", return_value={"player_name": "Appletini", "owner_user_id": 9})
    @patch.object(public, "get_user", return_value={"id": 7, "discord_username": "Viewer"})
    @patch.object(public, "get_room", return_value={"id": "room", "host_user_id": 1})
    def test_non_owner_cannot_mutate_state(self, _room, _user, _slot):
        self.login()
        response = self.client.patch(
            "/api/public/rooms/room/slots/0/1/state",
            json={"bk_action": "set"},
        )
        self.assertEqual(response.status_code, 403)

    @patch("db.update_room_slot_state", return_value={
        "team": 0, "slot": 1, "player_name": "Appletini", "game": "Super Metroid",
        "owner_user_id": 7, "owner_username": "Player", "bk_since": "2026-08-26T12:00:00+00:00",
        "bk_confirmed_at": "2026-08-26T12:00:00+00:00", "go_mode_since": None,
        "slot_note": "", "state_updated_at": "2026-08-26T12:00:00+00:00",
    })
    @patch("db.get_room_slot", return_value={"player_name": "Appletini", "owner_user_id": 7})
    @patch.object(public, "add_activity")
    @patch.object(public, "get_user", return_value={"id": 7, "discord_username": "Player"})
    @patch.object(public, "get_room", return_value={"id": "room", "host_user_id": 1})
    def test_owner_can_set_bk(self, _room, _user, _activity, _slot, _update):
        self.login()
        response = self.client.patch(
            "/api/public/rooms/room/slots/0/1/state",
            json={"bk_action": "set"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["is_mine"])
        self.assertNotIn("owner_user_id", response.get_json())

    @patch("db.get_room_slot", return_value={"player_name": "Appletini", "owner_user_id": 7})
    @patch.object(public, "get_user", return_value={"id": 7, "discord_username": "Player"})
    @patch.object(public, "get_room", return_value={"id": "room", "host_user_id": 1})
    def test_note_limit_is_enforced(self, _room, _user, _slot):
        self.login()
        response = self.client.patch(
            "/api/public/rooms/room/slots/0/1/state",
            json={"slot_note": "x" * 281},
        )
        self.assertEqual(response.status_code, 400)

    def test_state_permission_matrix_and_attribution(self):
        for role, user, expected in [
            ("anonymous", None, 401),
            ("owner", {"id": 7, "discord_username": "Owner"}, 200),
            ("host", {"id": 1, "discord_username": "Host"}, 200),
            ("admin", {"id": 8, "discord_username": "Admin", "is_admin": True}, 200),
            ("other", {"id": 9, "discord_username": "Other"}, 403),
        ]:
            with self.subTest(role=role), \
                 patch.object(public, "_current_session_user", return_value=user), \
                 patch.object(public, "get_room", return_value={"host_user_id": 1}), \
                 patch("db.get_room_slot", return_value={"owner_user_id": 7, "player_name": "Slot"}), \
                 patch("db.update_room_slot_state", return_value={
                     "team": 0, "slot": 1, "player_name": "Slot", "owner_user_id": 7,
                     "updated_by_username": (user or {}).get("discord_username"),
                 }) as update, patch.object(public, "add_activity") as activity:
                response = self.client.patch("/api/public/rooms/room/slots/0/1/state",
                                             json={"bk_action": "set", "go_mode": True, "slot_note": "Ready"})
                self.assertEqual(response.status_code, expected)
                if expected == 200:
                    self.assertTrue(response.json["can_edit"])
                    self.assertEqual(response.json["updated_by_username"], user["discord_username"])
                    self.assertEqual(activity.call_args.kwargs["actor_user_id"], user["id"])
                else:
                    update.assert_not_called()

    def test_invalid_updates_and_inactive_confirmation_do_not_write(self):
        with patch.object(public, "_current_session_user", return_value={"id": 7}), \
             patch.object(public, "get_room", return_value={"host_user_id": 1}), \
             patch("db.get_room_slot", return_value={"owner_user_id": 7}), \
             patch("db.update_room_slot_state") as update:
            for body in [[], ["bk_action"], "text", {}, {"slot_note": None},
                         {"bk_action": []}, {"go_mode": 1}, {"slot_note": 12},
                         {"ping_policy": "enabled"}, {"unknown": True}]:
                with self.subTest(body=body):
                    self.assertEqual(self.client.patch("/api/public/rooms/room/slots/0/1/state", json=body).status_code, 400)
            self.assertEqual(self.client.patch("/api/public/rooms/room/slots/0/1/state",
                                              json={"bk_action": "confirm"}).status_code, 409)
            update.assert_not_called()

    def test_anonymous_slot_overlay_hides_actor_and_owner(self):
        state = {"team": 0, "slot": 1, "player_name": "Slot", "owner_user_id": 7,
                 "owner_username": "Owner", "updated_by_user_id": 1, "updated_by_username": "Host"}
        payload = public._serialize_generated_slot(state, None, {"host_user_id": 1})
        self.assertIsNone(payload["owner_username"])
        self.assertIsNone(payload["updated_by_username"])
        self.assertNotIn("updated_by_user_id", payload)
        self.assertNotIn("owner_user_id", payload)
        self.assertFalse(payload["can_edit"])

    def test_confirmation_is_coalesced_and_noop_changes_do_not_add_activity(self):
        state = {"team": 0, "slot": 1, "player_name": "Slot", "owner_user_id": 7,
                 "bk_since": "2026-11-15T12:00:00Z", "go_mode_since": None, "slot_note": ""}
        with patch.object(public, "_current_session_user", return_value={"id": 7}), \
             patch.object(public, "get_room", return_value={"host_user_id": 1}), \
             patch("db.get_room_slot", return_value=state), \
             patch("db.update_room_slot_state", return_value=state), \
             patch("db.record_bk_confirmation") as confirmation, \
             patch.object(public, "add_activity") as activity:
            response = self.client.patch("/api/public/rooms/room/slots/0/1/state", json={"bk_action": "confirm"})
            self.assertEqual(response.status_code, 200)
            confirmation.assert_called_once()
            self.assertEqual(self.client.patch("/api/public/rooms/room/slots/0/1/state",
                             json={"bk_action": "set", "go_mode": False, "slot_note": ""}).status_code, 200)
            activity.assert_not_called()

    def test_slot_list_identity_gate_and_coordination_activity(self):
        state = {"team": 0, "slot": 1, "player_name": "Slot", "owner_user_id": 7,
                 "owner_username": "Owner", "updated_by_username": "Host"}
        events = [{"event_type": kind, "message": "Host changed something"}
                  for kind in ["slot_coordination_updated", "slot_bk_confirmed:0:1", "settings"]]
        with patch.object(public, "get_room", return_value={"host_user_id": 1}), \
             patch("db.get_generated_room", return_value={"room_id": "room"}), \
             patch("db.list_room_slots", return_value=[state]), \
             patch("db.get_activity", return_value=events) as activity:
            response = self.client.get("/api/public/rooms/room/slots")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["activity"], [])
            self.assertIsNone(response.json["slots"][0]["updated_by_username"])
            activity.assert_not_called()
            with patch.object(public, "_current_session_user", return_value={"id": 1}):
                response = self.client.get("/api/public/rooms/room/slots")
            self.assertEqual(len(response.json["activity"]), 2)
            self.assertTrue(response.json["slots"][0]["can_edit"])
            self.assertEqual(response.json["slots"][0]["updated_by_username"], "Host")


if __name__ == "__main__":
    unittest.main()
