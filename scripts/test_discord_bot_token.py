#!/usr/bin/env python3
"""Discord bot service token: scope, identity, quotas, room hosts, tracker state."""

from __future__ import annotations

import io
import os
import sys
import unittest
from threading import RLock
from types import SimpleNamespace
from unittest import mock

from flask import Flask

repo_app = os.path.join(os.path.dirname(__file__), "..", "ap-web")
sys.path.insert(0, repo_app if os.path.isdir(repo_app) else "/app")

import config
import db
import api.rooms as rooms_api
import tracker
import tracker_ws
from auth import apply_auth_to_app

TOKEN = "t" * 48
DISCORD_ID = "123456789012345678"
OTHER_ID = "223456789012345678"
HEADERS = {"X-AP-Bot-Token": TOKEN, "X-Discord-User-Id": DISCORD_ID}

HOST = {"id": 7, "discord_id": DISCORD_ID, "discord_username": "host",
        "is_admin": True, "is_approved": False, "room_creation_blocked": False}
PLAYER = {"id": 8, "discord_id": OTHER_ID, "discord_username": "player",
          "is_admin": False, "is_approved": False, "room_creation_blocked": False}
ROOM = {"id": "room1", "name": "R", "host_name": "host", "status": "open",
        "host_user_id": 7, "max_players": 0, "max_yamls_per_user": 0,
        "claim_mode": False, "tracker_url": None}
YAML = "name: Appletini\ngame: Super Metroid\nSuper Metroid: {}\n"
ROOM_ID = "AbCdEfGhIjKlMnOpQrStUv"
TRACKER_ID = "ZyXwVuTsRqPoNmLkJiHgFe"


def users_by_discord(discord_id):
    return {DISCORD_ID: HOST, OTHER_ID: PLAYER}.get(discord_id, {})


class BotTokenBase(unittest.TestCase):
    def setUp(self) -> None:
        self.saved = (config.DISCORD_CLIENT_ID, config.DISCORD_CLIENT_SECRET,
                      config.DISCORD_BOT_TOKEN, dict(config.FEATURES))
        config.DISCORD_CLIENT_ID = "c"
        config.DISCORD_CLIENT_SECRET = "s"
        config.DISCORD_BOT_TOKEN = TOKEN
        config.FEATURES["open_room_creation"] = False

        app = Flask(__name__)
        app.secret_key = "test-only"
        apply_auth_to_app(app)
        app.register_blueprint(rooms_api.bp)
        # A few routes the token must never open, standing in for the rest.
        app.add_url_rule("/api/admin/users", "admin_users", lambda: "x")
        app.add_url_rule("/api/my/yamls", "my_yamls", lambda: "x")
        self.client = app.test_client()
        self.room = dict(ROOM)
        self.activity = []

        def add_activity(room_id, kind, message, **kw):
            self.activity.append((kind, message))
            return {}

        patches = [
            mock.patch.object(db, "get_user_by_discord_id", side_effect=users_by_discord),
            mock.patch.object(db, "get_user", return_value=None),
            mock.patch.object(rooms_api, "_db_url", "test-db"),
            mock.patch.object(rooms_api, "maybe_auto_close_room", side_effect=lambda rid: self.room),
            mock.patch.object(rooms_api, "get_room", side_effect=lambda rid: self.room),
            mock.patch.object(rooms_api, "add_activity", side_effect=add_activity),
            mock.patch.object(rooms_api, "update_room", side_effect=self._update_room),
            mock.patch.object(rooms_api, "get_yamls", return_value=[]),
            mock.patch.object(rooms_api, "add_yaml", side_effect=lambda **kw: {"id": 1, **kw}),
            mock.patch.object(rooms_api, "update_yaml_validation"),
            mock.patch.object(rooms_api, "count_yamls_by_submitter", return_value=0),
            mock.patch.object(rooms_api.analytics, "record_event"),
            mock.patch.object(rooms_api, "get_room_creation_counts",
                              return_value={"recent": 0, "active": 0, "total": 0}),
            mock.patch.object(rooms_api, "create_room", side_effect=self._create_room),
            mock.patch("api.apworlds.auto_pin_for_room_game"),
        ]
        for p in patches:
            p.start()
        self.addCleanup(mock.patch.stopall)
        self.created = []

    def tearDown(self) -> None:
        (config.DISCORD_CLIENT_ID, config.DISCORD_CLIENT_SECRET,
         config.DISCORD_BOT_TOKEN, features) = self.saved
        config.FEATURES.clear()
        config.FEATURES.update(features)

    def _update_room(self, room_id, **fields):
        self.room.update(fields)
        return dict(self.room)

    def _create_room(self, **kw):
        self.created.append(kw)
        return {"id": "new1", **kw}

    def headers(self, **over):
        h = dict(HEADERS)
        h.update(over)
        return {k: v for k, v in h.items() if v is not None}


class TokenScope(BotTokenBase):
    def test_accepted_on_every_listed_route(self) -> None:
        for method, path, kwargs in [
            ("post", "/api/rooms", {"json": {"name": "n", "host_name": "h"}}),
            ("put", "/api/rooms/room1", {"json": {"description": "x"}}),
            ("post", "/api/rooms/room1/close", {}),
            ("post", "/api/rooms/room1/yamls",
             {"data": {"file": (io.BytesIO(YAML.encode()), "a.yaml")},
              "content_type": "multipart/form-data"}),
            ("post", "/api/rooms/room1/generated-room/preview", {"json": {}}),
            ("put", "/api/rooms/room1/generated-room", {"json": {}}),
        ]:
            with self.subTest(route=f"{method} {path}"):
                resp = getattr(self.client, method)(path, headers=self.headers(), **kwargs)
                # Past the auth hook: any status except the bot-auth refusals.
                self.assertNotIn(resp.status_code, (401, 403), resp.get_json())

    def test_tracker_and_activity_reads_pass_auth(self) -> None:
        with mock.patch.object(rooms_api, "_external_tracker_to_room_shape", return_value={"status": "ok"}):
            self.room["tracker_url"] = "https://archipelago.gg/tracker/x"
            resp = self.client.get("/api/rooms/room1/tracker", headers=self.headers())
            self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/api/rooms/room1/activity-stream", headers=self.headers())
        self.assertEqual(resp.status_code, 200)

    def test_refused_on_unlisted_routes(self) -> None:
        for method, path in [
            ("get", "/api/rooms"),
            ("get", "/api/rooms/room1"),
            ("delete", "/api/rooms/room1"),
            ("post", "/api/rooms/room1/reopen"),
            ("post", "/api/rooms/room1/yamls/create"),
            ("put", "/api/rooms/room1/slots/0/1/owner"),
            ("get", "/api/admin/users"),
            ("get", "/api/my/yamls"),
        ]:
            with self.subTest(route=f"{method} {path}"):
                resp = getattr(self.client, method)(path, headers=self.headers())
                self.assertEqual(resp.status_code, 403)
                self.assertEqual(resp.get_json()["code"], "bot_route_not_allowed")

    def test_wrong_missing_and_short_token_refused(self) -> None:
        body = {"json": {"name": "n", "host_name": "h"}}
        resp = self.client.post("/api/rooms", headers=self.headers(**{"X-AP-Bot-Token": "x" * 48}), **body)
        self.assertEqual((resp.status_code, resp.get_json()["code"]), (401, "bot_token_invalid"))
        resp = self.client.post("/api/rooms", **body)
        self.assertEqual(resp.status_code, 401)
        config.DISCORD_BOT_TOKEN = "short"
        resp = self.client.post("/api/rooms", headers=self.headers(**{"X-AP-Bot-Token": "short"}), **body)
        self.assertEqual(resp.status_code, 401)
        config.DISCORD_BOT_TOKEN = ""
        resp = self.client.post("/api/rooms", headers=self.headers(**{"X-AP-Bot-Token": ""}), **body)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(self.created, [])

    def test_token_is_compared_in_constant_time(self) -> None:
        with mock.patch("auth.hmac.compare_digest", return_value=False) as cmp:
            resp = self.client.post("/api/rooms", headers=self.headers(),
                                    json={"name": "n", "host_name": "h"})
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(cmp.called)

    def test_session_cookie_does_not_widen_the_token(self) -> None:
        with self.client.session_transaction() as s:
            s["user_id"] = 7
        resp = self.client.get("/api/rooms", headers=self.headers())
        self.assertEqual(resp.status_code, 403)


class Identity(BotTokenBase):
    def test_unknown_discord_id_refused_and_no_account_created(self) -> None:
        with mock.patch.object(db, "create_or_update_user") as create_user:
            resp = self.client.post(
                "/api/rooms", headers=self.headers(**{"X-Discord-User-Id": "999999999999999999"}),
                json={"name": "n", "host_name": "h"})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.get_json()["code"], "discord_user_not_registered")
        create_user.assert_not_called()
        self.assertEqual(self.created, [])

    def test_discord_id_required_and_validated(self) -> None:
        for value in (None, "", "abc", "1; DROP TABLE users"):
            with self.subTest(value=value):
                resp = self.client.post("/api/rooms", headers=self.headers(**{"X-Discord-User-Id": value}),
                                        json={"name": "n", "host_name": "h"})
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_json()["code"], "discord_user_required")

    def test_room_is_created_in_the_members_name(self) -> None:
        resp = self.client.post("/api/rooms", headers=self.headers(), json={
            "name": "n", "host_name": "h", "host_user_id": 999})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(self.created[0]["host_user_id"], 7)

    def test_site_admin_acts_as_ordinary_member(self) -> None:
        # HOST is an admin; through the bot they still cannot touch others' rooms.
        self.room["host_user_id"] = 8
        resp = self.client.put("/api/rooms/room1", headers=self.headers(), json={"description": "x"})
        self.assertEqual(resp.status_code, 403)
        resp = self.client.post("/api/rooms/room1/close", headers=self.headers())
        self.assertEqual(resp.status_code, 403)

    def test_owner_routes_need_the_host(self) -> None:
        resp = self.client.post("/api/rooms/room1/close", headers=self.headers(**{"X-Discord-User-Id": OTHER_ID}))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.room["status"], "open")
        resp = self.client.post("/api/rooms/room1/close", headers=self.headers())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.room["status"], "closed")

    def test_pending_deletion_refused(self) -> None:
        with mock.patch.object(db, "get_user_by_discord_id",
                               return_value={**HOST, "deletion_due_at": "2026-12-01"}):
            resp = self.client.post("/api/rooms", headers=self.headers(),
                                    json={"name": "n", "host_name": "h"})
        self.assertEqual(resp.status_code, 401)


class CreationRules(BotTokenBase):
    def create(self, discord_id=OTHER_ID):
        return self.client.post("/api/rooms", headers=self.headers(**{"X-Discord-User-Id": discord_id}),
                                json={"name": "n", "host_name": "h"})

    def test_approval_skipped_even_with_open_creation_off(self) -> None:
        self.assertFalse(PLAYER["is_approved"])
        self.assertFalse(config.FEATURES["open_room_creation"])
        self.assertEqual(self.create().status_code, 201)

    def test_same_account_without_the_token_still_needs_approval(self) -> None:
        with mock.patch.object(db, "get_user", return_value=PLAYER):
            with self.client.session_transaction() as s:
                s["user_id"] = 8
            resp = self.client.post("/api/rooms", json={"name": "n", "host_name": "h"})
        self.assertEqual(resp.status_code, 403)

    def test_blocked_account_refused(self) -> None:
        blocked = {**PLAYER, "room_creation_blocked": True}
        with mock.patch.object(db, "get_user_by_discord_id", return_value=blocked):
            resp = self.create()
        self.assertEqual(resp.status_code, 403)
        self.assertIn("disabled", resp.get_json()["error"])
        self.assertEqual(self.created, [])

    def test_quotas_enforced(self) -> None:
        for counts, status in [({"recent": config.ROOM_CREATION_PER_HOUR, "active": 0, "total": 0}, 429),
                               ({"recent": 0, "active": config.ROOM_CREATION_MAX_ACTIVE, "total": 0}, 409),
                               ({"recent": 0, "active": 0, "total": config.ROOM_CREATION_MAX_TOTAL}, 409)]:
            with self.subTest(counts=counts), mock.patch.object(
                    rooms_api, "get_room_creation_counts", return_value=counts):
                self.assertEqual(self.create().status_code, status)
        self.assertEqual(self.created, [])

    def test_activity_carries_via_discord_marker(self) -> None:
        self.create()
        self.assertTrue(any(m.endswith("(via Discord)") for _, m in self.activity), self.activity)


class YamlUpload(BotTokenBase):
    def upload(self, data: bytes, discord_id=OTHER_ID):
        return self.client.post(
            "/api/rooms/room1/yamls", headers=self.headers(**{"X-Discord-User-Id": discord_id}),
            data={"file": (io.BytesIO(data), "a.yaml")}, content_type="multipart/form-data")

    def test_member_who_is_not_the_host_can_upload_and_is_the_submitter(self) -> None:
        added = []
        with mock.patch.object(rooms_api, "add_yaml", side_effect=lambda **kw: added.append(kw) or {"id": 1}):
            resp = self.upload(YAML.encode())
        self.assertEqual(resp.status_code, 201, resp.get_json())
        self.assertEqual(added[0]["submitter_user_id"], 8)
        self.assertTrue(any(k == "yaml_uploaded" and m.endswith("(via Discord)") for k, m in self.activity))

    def test_claim_mode_does_not_hide_the_member(self) -> None:
        self.room["claim_mode"] = True
        added = []
        with mock.patch.object(rooms_api, "add_yaml", side_effect=lambda **kw: added.append(kw) or {"id": 1}):
            self.upload(YAML.encode())
        self.assertEqual(added[0]["submitter_user_id"], 8)

    def test_per_player_cap_applies(self) -> None:
        self.room["max_yamls_per_user"] = 1
        with mock.patch.object(rooms_api, "count_yamls_by_submitter", return_value=1):
            self.assertEqual(self.upload(YAML.encode()).status_code, 400)

    def test_closed_room_refused(self) -> None:
        self.room["status"] = "closed"
        self.assertEqual(self.upload(YAML.encode()).status_code, 400)

    def test_non_utf8_is_a_400_not_a_crash(self) -> None:
        resp = self.upload(b"name: \xff\xfe\xfa\ngame: x\n")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("UTF-8", resp.get_json()["error"])

    def test_non_utf8_is_a_400_for_browser_hosts_too(self) -> None:
        with mock.patch.object(db, "get_user", return_value=HOST):
            with self.client.session_transaction() as s:
                s["user_id"] = 7
            resp = self.client.post(
                "/api/rooms/room1/yamls", data={"file": (io.BytesIO(b"\xff\xfe\xfa"), "a.yaml")},
                content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)


class StatusValidation(BotTokenBase):
    def test_unknown_status_rejected_known_accepted(self) -> None:
        resp = self.client.put("/api/rooms/room1", headers=self.headers(), json={"status": "bogus"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.room["status"], "open")
        for ok in ("closed", "open", "playing"):
            resp = self.client.put("/api/rooms/room1", headers=self.headers(), json={"status": ok})
            self.assertEqual(resp.status_code, 200, ok)


TRACKER_FIXTURE = {"room_id": TRACKER_ID, "players": [
    {"slot": 1, "name": "Appletini", "game": "Super Metroid", "checks_done": 1, "checks_total": 5}]}


class RoomHosts(BotTokenBase):
    def status_response(self, payload, code=200):
        return mock.Mock(status_code=code, content=b"{}", json=mock.Mock(return_value=payload),
                         raise_for_status=mock.Mock())

    def link(self, host):
        return f"https://{host}/room/{ROOM_ID}"

    def test_room_links_from_both_hosts_resolve(self) -> None:
        for host in ("archipelago.gg", "multiworld.gg", "www.multiworld.gg"):
            with self.subTest(host=host), mock.patch.object(tracker, "is_safe_tracker_url", return_value=True), \
                    mock.patch.object(tracker.requests, "get", return_value=self.status_response(
                        {"tracker": TRACKER_ID, "last_port": 40123})) as get:
                out = tracker.resolve_room_url(self.link(host))
                self.assertEqual(out["tracker_url"], f"https://{host}/tracker/{TRACKER_ID}")
                self.assertEqual((out["host"], out["port"]), (host, 40123))
                self.assertEqual(get.call_args.args[0], f"https://{host}/api/room_status/{ROOM_ID}")

    def test_unknown_hosts_and_odd_links_rejected(self) -> None:
        for url in (f"https://evil.example/room/{ROOM_ID}", f"https://archipelago.gg.evil.example/room/{ROOM_ID}",
                    f"https://user@archipelago.gg/room/{ROOM_ID}", f"https://archipelago.gg:8080/room/{ROOM_ID}",
                    "https://multiworld.gg/lobby/abc", "https://multiworld.gg/room/short",
                    "http://127.0.0.1/room/" + ROOM_ID):
            with self.subTest(url=url):
                self.assertIsNone(tracker.parse_room_url(url))

    def test_missing_room_and_paused_room(self) -> None:
        with mock.patch.object(tracker, "is_safe_tracker_url", return_value=True):
            with mock.patch.object(tracker.requests, "get", return_value=self.status_response({}, 404)):
                self.assertIn("error", tracker.resolve_room_url(self.link("multiworld.gg")))
            with mock.patch.object(tracker.requests, "get", return_value=self.status_response(
                    {"tracker": TRACKER_ID, "last_port": -1})):
                self.assertIsNone(tracker.resolve_room_url(self.link("multiworld.gg"))["port"])
            with mock.patch.object(tracker.requests, "get", return_value=self.status_response({"last_port": 5})):
                self.assertIn("error", tracker.resolve_room_url(self.link("multiworld.gg")))

    def test_preview_and_set_accept_multiworld_room_link(self) -> None:
        resolved = {"tracker_url": f"https://multiworld.gg/tracker/{TRACKER_ID}", "host": "multiworld.gg",
                    "port": 40123, "room_id": ROOM_ID}
        with mock.patch("tracker.is_safe_tracker_url", return_value=True), \
                mock.patch("tracker.resolve_room_url", return_value=resolved), \
                mock.patch("tracker.fetch_tracker_data", return_value=TRACKER_FIXTURE), \
                mock.patch.object(rooms_api, "get_yamls_with_submitters", return_value=[]), \
                mock.patch.object(rooms_api, "_maybe_reschedule_tracker_ws") as resched, \
                mock.patch("db.associate_generated_room", return_value=[{"team": 0, "slot": 1}]):
            resp = self.client.post("/api/rooms/room1/generated-room/preview", headers=self.headers(),
                                    json={"tracker_url": self.link("multiworld.gg")})
            self.assertEqual(resp.status_code, 200, resp.get_json())
            self.assertEqual(resp.get_json()["external_host"], "multiworld.gg")
            self.assertEqual(self.room["status"], "open")  # preview writes nothing

            resp = self.client.put("/api/rooms/room1/generated-room", headers=self.headers(),
                                   json={"tracker_url": self.link("multiworld.gg")})
            self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertEqual(self.room["tracker_url"], resolved["tracker_url"])
        self.assertEqual((self.room["external_host"], self.room["external_port"]), ("multiworld.gg", 40123))
        self.assertEqual(self.room["status"], "playing")
        self.assertEqual(resp.get_json()["server"], {"host": "multiworld.gg", "port": 40123})
        resched.assert_called_once()
        self.assertTrue(any(k == "generated_room_attached" and m.endswith("(via Discord)")
                            for k, m in self.activity))

    def test_tracker_urls_on_both_hosts_parse(self) -> None:
        with mock.patch.object(tracker, "is_safe_tracker_url", return_value=True):
            for host in ("archipelago.gg", "multiworld.gg"):
                self.assertEqual(tracker.parse_tracker_url(f"https://{host}/tracker/{TRACKER_ID}")["host"], host)

    def test_multiworld_tracker_markup_parses_including_goal_override(self) -> None:
        html = ('<table id="checks-table" class="table non-unique-item-table"><tbody>'
                '<tr><td>\n<a href="/tracker/x/0/1">\n 1\n</a>\n</td><td>Appletini</td><td>Super Metroid</td>'
                '<td>Goal Completed (via override)</td><td class="center-column" data-sort="5">5/5</td>'
                '<td class="center-column">100.00</td></tr>'
                '<tr><td><a href="/tracker/x/0/2">2</a></td><td>Pie</td><td>Pokepelago</td>'
                '<td>Playing</td><td class="center-column">1/10</td><td>10.00</td></tr></tbody></table>')
        players = tracker._parse_tracker_html(html)
        self.assertEqual([(p["slot"], p["status"]) for p in players], [(1, 30), (2, 10)])
        self.assertEqual(players[0]["checks_total"], 5)


class ReleaseCollect(unittest.TestCase):
    def connection(self):
        conn = tracker_ws.TrackerConnection("room1", "https://archipelago.gg/tracker/x", "archipelago.gg", 40000, "Bot")
        conn.state.slot_info = {1: {"name": "A", "game": "G"}, 2: {"name": "B", "game": "G"}}
        conn.state.state = "connected"
        return conn

    def test_release_and_collect_become_per_slot_state_and_events(self) -> None:
        conn = self.connection()
        conn._on_print_json({"type": "Release", "team": 0, "slot": 1, "data": [{"type": "text", "text": "A released"}]})
        conn._on_print_json({"type": "Collect", "team": 0, "slot": 2, "data": [{"type": "text", "text": "B collected"}]})
        with mock.patch("tracker_ws.manager.get_state", return_value=conn.state):
            ov = tracker_ws.grid_overrides("room1")
        self.assertEqual((ov[1]["released"], ov[1]["collected"]), (True, False))
        self.assertEqual((ov[2]["released"], ov[2]["collected"]), (False, True))
        types = [(e["type"], e["slot"]) for e in conn.state.activity]
        self.assertEqual(types, [("Release", 1), ("Collect", 2)])

    def test_bad_slot_ignored(self) -> None:
        conn = self.connection()
        for slot in (None, "x", 0, -3):
            conn._on_print_json({"type": "Release", "slot": slot, "data": []})
        self.assertEqual(conn.state.released_slots, set())

    def test_tracker_response_exposes_the_state(self) -> None:
        override = {1: {"connect_name": "A", "client_status": 20, "status_label": "playing",
                        "goal_completed": False, "released": True, "collected": False}}
        room = {"id": "room1", "external_host": "multiworld.gg", "external_port": 40123}
        with Flask(__name__).app_context(), mock.patch("tracker.fetch_tracker_data", return_value=TRACKER_FIXTURE):
            with mock.patch("tracker_ws.grid_overrides", return_value=override):
                out = rooms_api._external_tracker_to_room_shape(room, "https://multiworld.gg/tracker/x")
            self.assertTrue(out["players"][0]["released"])
            self.assertFalse(out["players"][0]["collected"])
            self.assertTrue(out["release_tracking"])
            with mock.patch("tracker_ws.grid_overrides", return_value=None):
                out = rooms_api._external_tracker_to_room_shape(room, "https://multiworld.gg/tracker/x")
            self.assertFalse(out["players"][0]["released"])
            self.assertFalse(out["release_tracking"])
            self.assertEqual(out["connection_url"], "multiworld.gg:40123")


if __name__ == "__main__":
    unittest.main()
