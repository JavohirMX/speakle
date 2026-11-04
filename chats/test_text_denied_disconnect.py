"""Rejected text sockets must not alter a room when they disconnect."""
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from . import test_text_consumer_guards as guards
from .consumers import TextChatConsumer
from .models import TypingStatus
from .test_api_views import _make_communicator


class TextDeniedDisconnectTests(TransactionTestCase):
    setUp = guards.TextConsumerGuardTests.setUp
    _connect = guards.TextConsumerGuardTests._connect
    _next = guards.TextConsumerGuardTests._next

    async def _reject_and_disconnect(self, user):
        rid = str(self.room.room_id)
        c = _make_communicator(TextChatConsumer, {
            'path': f'/ws/text-chat/{rid}/', 'user': user,
            'url_route': {'kwargs': {'room_id': rid}}})
        self.assertTrue((await c.connect())[0])
        await self._next(c, 'error')
        self.assertEqual((await c.receive_output(timeout=2))['type'], 'websocket.close')
        await c.disconnect()

    async def test_outsider_disconnect_does_not_create_typing_row(self):
        outsider = await database_sync_to_async(get_user_model().objects.create_user)(
            'denied-outsider', password='fixture-only')
        await self._reject_and_disconnect(outsider)
        count = await database_sync_to_async(TypingStatus.objects.filter(
            room=self.room, user=outsider).count)()
        self.assertEqual(count, 0)

    async def test_outsider_disconnect_does_not_broadcast_user_left(self):
        outsider = await database_sync_to_async(get_user_model().objects.create_user)(
            'denied-outsider', password='fixture-only')
        peer = await self._connect(self.b)
        await self._next(peer, 'user_joined')
        await self._reject_and_disconnect(outsider)
        await peer.send_json_to({'type': 'ping'})
        frames = []
        for _ in range(8):
            frame = await peer.receive_json_from(timeout=5)
            frames.append(frame)
            if frame.get('type') == 'pong':
                break
        self.assertFalse(any(f.get('type') == 'user_left' and
                             f.get('user_id') == outsider.id for f in frames), frames)
        await peer.disconnect()

    async def test_anonymous_disconnect_does_not_log_cleanup_error(self):
        with self.assertNoLogs('chats.consumers', level='ERROR'):
            await self._reject_and_disconnect(AnonymousUser())
