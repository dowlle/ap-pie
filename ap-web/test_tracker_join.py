import unittest
from html import escape
from types import SimpleNamespace
from threading import RLock
from unittest.mock import patch

from flask import Flask
from api.rooms import _external_tracker_to_room_shape
from tracker import _parse_tracker_html
from tracker_ws import grid_overrides


class TrackerJoinTests(unittest.TestCase):
    def test_html_preserves_names_but_does_not_guess_aliases(self):
        for name, expected in [("Appie's Poké + & #1", "Appie's Poké + & #1"),
                               ("Nickname (Real slot)", None), ("Real (parentheses)", None)]:
            with self.subTest(name=name):
                html = '<table id="checks-table"><tr><td>1</td><td>' + escape(name) + '</td><td>Pokepelago</td><td>Playing</td><td>2/10</td></tr></table>'
                player = _parse_tracker_html(html)[0]
                self.assertEqual(player["name"], name)
                self.assertEqual(player["connect_name"], expected)

    def test_websocket_uses_original_slot_info(self):
        state = SimpleNamespace(state="connected", lock=RLock(), slot_info={1: {"name": "Original (slot)"}},
                                client_status={}, checked_locations={})
        with patch("tracker_ws.manager.get_state", return_value=state):
            self.assertEqual(grid_overrides("room")[1]["connect_name"], "Original (slot)")

    def test_room_adapter_prefers_original_name_and_preserves_server(self):
        room = {"id": "room", "external_host": "archipelago.gg", "external_port": 45678}
        tracker = {"players": [{"slot": 1, "name": "Nickname (Original)", "connect_name": None,
                                "game": "Pokepelago", "checks_done": 2, "checks_total": 10}]}
        override = {1: {"connect_name": "Original", "client_status": 20, "status_label": "playing", "goal_completed": False}}
        with Flask(__name__).app_context(), patch("tracker.fetch_tracker_data", return_value=tracker):
            for ws, expected in [(override, "Original"), (None, None)]:
                with patch("tracker_ws.grid_overrides", return_value=ws):
                    result = _external_tracker_to_room_shape(room, "https://archipelago.gg/tracker/fixture")
                    self.assertEqual(result["players"][0]["connect_name"], expected)
                    self.assertEqual(result["connection_url"], "archipelago.gg:45678")


if __name__ == "__main__":
    unittest.main()
