"""Text-chat consumer: block-mid-chat, throttle, empty message, typing."""
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TransactionTestCase

from users.models import Language, UserBlock
from matches.models import Match
from .models import ChatRoom, ChatMessage
from .test_api_views import _make_communicator

User = get_user_model()


class TextConsumerGuardTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.a = User.objects.create_user('tg_a', 'tga@x.com', 'pw12345!')
        self.b = User.objects.create_user('tg_b', 'tgb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=self.a, user2=self.b,
                                 user1_teaches=en, user1_learns=ko,
                                 status='active')
        self.room = ChatRoom.objects.create(match=m)

    async def _connect(self, user):
        from .consumers import TextChatConsumer
        rid = str(self.room.room_id)
        c = _make_communicator(TextChatConsumer, {
            'path': f'/ws/text-chat/{rid}/', 'user': user,
            'url_route': {'kwargs': {'room_id': rid}}})
        ok, _ = await c.connect()
        self.assertTrue(ok)
        return c

    async def _next(self, c, wanted, limit=8):
        for _ in range(limit):
            msg = await c.receive_json_from(timeout=5)
            if msg.get('type') == wanted:
                return msg
        self.fail(f'no {wanted} frame')

    def _message_count(self):
        return ChatMessage.objects.filter(room=self.room).count()

    async def test_block_mid_chat_stops_sending(self):
        ca = await self._connect(self.a)
        cb = await self._connect(self.b)
        await database_sync_to_async(UserBlock.objects.create)(
            blocker=self.b, blocked=self.a)
        await ca.send_json_to({'type': 'send_message', 'message': 'hello?'})
        frame = await self._next(ca, 'error')
        self.assertEqual(frame['message'],
                         'This conversation is no longer available.')
        count = await database_sync_to_async(self._message_count)()
        self.assertEqual(count, 0)
        await ca.disconnect()
        await cb.disconnect()

    async def test_throttled_user_gets_error_frame(self):
        cache.set(f'chat-send:{self.a.id}', 30, 60)
        ca = await self._connect(self.a)
        await ca.send_json_to({'type': 'send_message', 'message': 'spam'})
        frame = await self._next(ca, 'error')
        self.assertIn('too fast', frame['message'])
        count = await database_sync_to_async(self._message_count)()
        self.assertEqual(count, 0)
        await ca.disconnect()

    async def test_empty_message_rejected(self):
        ca = await self._connect(self.a)
        await ca.send_json_to({'type': 'send_message', 'message': '   '})
        frame = await self._next(ca, 'error')
        self.assertEqual(frame['message'], 'Empty message content')
        await ca.disconnect()

    async def test_typing_signals_reach_partner_only(self):
        ca = await self._connect(self.a)
        cb = await self._connect(self.b)
        await ca.send_json_to({'type': 'typing_start'})
        frame = await self._next(cb, 'typing_start')
        self.assertEqual(frame['user_id'], self.a.id)
        await ca.send_json_to({'type': 'typing_stop'})
        frame = await self._next(cb, 'typing_stop')
        self.assertEqual(frame['user_id'], self.a.id)
        await ca.disconnect()
        await cb.disconnect()
