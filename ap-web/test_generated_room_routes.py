import unittest
from unittest.mock import patch

from flask import Flask

from api import rooms


ROOM = {"id": "room", "name": "Room", "status": "closed", "host_user_id": None, "tracker_url": None}
YAMLS = [{
    "id": 10,
    "player_name": "Appletini",
    "game": "Super Metroid",
    "submitter_user_id": 7,
    "submitter_username": "Player",
}]
TRACKER = {"room_id": "generated", "players": [{"slot": 1, "name": "Appletini", "game": "Super Metroid"}]}


class GeneratedRoomRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = "test-only"
        app.register_blueprint(rooms.bp)
        app.testing = True
        self.client = app.test_client()
        self.patches = [
            patch.object(rooms, "_db_url", "test-db"),
            patch.object(rooms, "maybe_auto_close_room", return_value=ROOM),
            patch.object(rooms, "get_room", return_value=ROOM),
            patch.object(rooms, "get_yamls_with_submitters", return_value=YAMLS),
            patch("tracker.parse_tracker_url", return_value={"room_id": "generated"}),
            patch("tracker.fetch_tracker_data", return_value=TRACKER),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def test_preview_suggests_exact_yaml_owner(self):
        response = self.client.post(
            "/api/rooms/room/generated-room/preview",
            json={"tracker_url": "https://archipelago.gg/tracker/generated"},
        )
        self.assertEqual(response.status_code, 200)
        roster = response.get_json()["roster"]
        self.assertEqual(roster[0]["match_status"], "exact")
        self.assertEqual(roster[0]["suggested_yaml_id"], 10)

    @patch.object(rooms, "_maybe_reschedule_tracker_ws")
    @patch.object(rooms, "add_activity")
    @patch.object(rooms, "update_room", return_value={**ROOM, "status": "playing"})
    @patch("db.associate_generated_room", return_value=[{"team": 0, "slot": 1}])
    def test_confirm_persists_mapping_and_enters_playing(
        self, associate, update, _activity, _reschedule,
    ):
        response = self.client.put(
            "/api/rooms/room/generated-room",
            json={
                "tracker_url": "https://archipelago.gg/tracker/generated",
                "mappings": [{"team": 0, "slot": 1, "yaml_id": 10}],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["room"]["status"], "playing")
        self.assertEqual(associate.call_args.args[4][0]["yaml_owner_user_id"], 7)
        update.assert_called_once_with(
            "room", tracker_url="https://archipelago.gg/tracker/generated", status="playing",
        )


if __name__ == "__main__":
    unittest.main()
