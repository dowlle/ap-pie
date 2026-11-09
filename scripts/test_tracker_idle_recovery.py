"""Tracker demand survives idle eviction without editing the room link.

Uses the real manager/async task lifecycle with fake sockets, no DB/network.
"""
import asyncio
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ap-web'))
import tracker_ws

class FakeConnection:
    def __init__(self, room_id, tracker_url, host, port, slot_name):
        self.state = tracker_ws.TrackerState(room_id=room_id, tracker_url=tracker_url,
            host=host, port=port, slot_name=slot_name)
        self.stopped = False
    async def run(self):
        await asyncio.Event().wait()
    def stop(self):
        self.stopped = True

class IdleRecovery(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.patch = patch.object(tracker_ws, 'TrackerConnection', FakeConnection)
        self.patch.start()
        self.manager = tracker_ws.TrackerManager()
        self.manager._loop = asyncio.get_running_loop()
        self.manager._max = 2
        self.manager._idle_minutes = 5
    async def asyncTearDown(self):
        tasks = list(self.manager._tasks.values())
        for rid in list(self.manager._connections):
            self.manager._cancel(rid)
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.settle()
        self.patch.stop()
    async def settle(self):
        for _ in range(4):
            await asyncio.sleep(0)
    def add(self, rid='room', port=12345):
        self.manager._do_schedule(rid, 'https://archipelago.gg/tracker/test', 'archipelago.gg', port, 'Hypno')
        return self.manager._connections[rid]
    def age(self, rid='room'):
        self.manager._connections[rid].state.last_packet_at = time.time() - 1000
        self.manager._last_read[rid] = time.time() - 1000

    async def test_polled_quiet_room_is_not_evicted(self):
        conn = self.add()
        self.age()
        self.assertIs(self.manager.get_state('room'), conn.state)
        self.manager._expire_idle()
        self.assertFalse(conn.stopped)

    async def test_idle_read_resumes_once_without_manual_relink(self):
        old = self.add()
        self.age()
        self.manager._expire_idle()
        await self.settle()
        self.assertTrue(old.stopped)
        self.assertNotIn('room', self.manager._connections)
        for _ in range(5):
            self.assertIsNone(self.manager.get_state('room'))
        await self.settle()
        new = self.manager._connections['room']
        self.assertIsNot(new, old)
        self.assertEqual(new.state.port, 12345)
        self.assertEqual(new.state.slot_name, 'Hypno')
        self.assertNotIn('room', self.manager._dormant)
        self.assertEqual(len(self.manager._tasks), 1)

    async def test_explicit_cancel_prevents_lazy_resurrection(self):
        self.add()
        self.age()
        self.manager._expire_idle()
        await self.settle()
        self.manager._cancel('room')
        self.assertIsNone(self.manager.get_state('room'))
        await self.settle()
        self.assertNotIn('room', self.manager._connections)

    async def test_reschedule_replaces_dormant_settings(self):
        self.add()
        self.age()
        self.manager._expire_idle()
        await self.settle()
        await self.manager._reschedule_async('room', 'https://archipelago.gg/tracker/new', 'archipelago.gg', 54321, 'New slot')
        self.assertEqual(self.manager.get_state('room').port, 54321)
        self.assertNotIn('room', self.manager._dormant)

    async def test_queued_cancel_wins_over_racing_api_read(self):
        self.add()
        self.age()
        self.manager._expire_idle()
        await self.settle()
        self.manager.cancel('room')
        self.assertIsNone(self.manager.get_state('room'))
        await self.settle()
        self.assertNotIn('room', self.manager._connections)
        self.assertNotIn('room', self.manager._dormant)

    async def test_recovery_respects_cap_and_can_retry_when_space_returns(self):
        self.add()
        self.age()
        self.manager._expire_idle()
        await self.settle()
        self.add('other1')
        self.add('other2')
        self.assertIsNone(self.manager.get_state('room'))
        await self.settle()
        self.assertEqual(len(self.manager._connections), 2)
        self.manager._cancel('other1')
        await self.settle()
        self.assertIsNone(self.manager.get_state('room'))
        await self.settle()
        self.assertIn('room', self.manager._connections)

    async def test_queued_requests_cannot_exceed_connection_cap(self):
        for rid in ('a','b','c'):
            self.manager.schedule(rid, 'https://archipelago.gg/tracker/test', 'archipelago.gg', 12345, 'Hypno')
        await self.settle()
        self.assertEqual(len(self.manager._connections), 2)

    async def test_old_completion_cannot_remove_replacement(self):
        self.add()
        old_task = self.manager._tasks['room']
        await self.manager._reschedule_async('room', 'https://archipelago.gg/tracker/new', 'archipelago.gg', 54321, 'Hypno')
        self.manager._on_done('room', old_task)
        self.assertEqual(self.manager.get_state('room').port, 54321)

    async def test_dormant_settings_are_bounded(self):
        for rid in ('a','b','c'):
            self.add(rid)
            self.age(rid)
            self.manager._expire_idle()
            await self.settle()
        self.assertEqual(list(self.manager._dormant), ['b','c'])

if __name__ == '__main__':
    unittest.main()
