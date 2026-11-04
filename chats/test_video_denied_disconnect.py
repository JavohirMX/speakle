"""A rejected video socket never joined, so it must not broadcast a departure."""
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from . import test_text_consumer_guards as guards
from .consumers import VideoCallConsumer
from .models import VideoRoom
from .test_api_views import _make_communicator


class VideoDeniedDisconnectTests(TransactionTestCase):
    setUp = guards.TextConsumerGuardTests.setUp
    _next = guards.TextConsumerGuardTests._next

    async def _socket(self, user, room):
        rid = str(room.room_id)
        c = _make_communicator(VideoCallConsumer, {
            'path': f'/ws/video-call/{rid}/', 'user': user,
            'url_route': {'kwargs': {'room_id': rid}}})
        self.assertTrue((await c.connect())[0])
        return c

    async def test_outsider_disconnect_does_not_broadcast_departure(self):
        room = await database_sync_to_async(VideoRoom.objects.create)(match=self.room.match)
        outsider = await database_sync_to_async(get_user_model().objects.create_user)(
            'denied-video-outsider', password='fixture-only')
        peer = await self._socket(self.b, room)
        await self._next(peer, 'user_joined')
        denied = await self._socket(outsider, room)
        await self._next(denied, 'error')
        self.assertEqual((await denied.receive_output(timeout=2))['type'], 'websocket.close')
        await denied.disconnect()
        await peer.send_json_to({'type': 'test'})
        frames = []
        for _ in range(8):
            frame = await peer.receive_json_from(timeout=5)
            frames.append(frame)
            if frame.get('type') == 'test_response':
                break
        self.assertFalse(any(f.get('type') == 'user_left' and
                             f.get('user_id') == outsider.id for f in frames), frames)
        await peer.disconnect()

    async def test_joined_peer_disconnect_still_broadcasts_departure(self):
        room = await database_sync_to_async(VideoRoom.objects.create)(match=self.room.match)
        peer = await self._socket(self.b, room)
        await self._next(peer, 'user_joined')
        mine = await self._socket(self.a, room)
        await self._next(mine, 'user_joined')
        await mine.disconnect()
        left = await self._next(peer, 'user_left')
        self.assertEqual(left['user_id'], self.a.id)
        await peer.disconnect()
