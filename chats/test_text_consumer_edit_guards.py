"""Text-chat consumer: invalid edit requests are rejected with an error frame."""
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from users.models import Language
from matches.models import Match
from .models import ChatRoom, ChatMessage
from .test_api_views import _make_communicator

User = get_user_model()


class TextConsumerEditGuardTests(TransactionTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.a = User.objects.create_user('wg_a', 'wga@x.com', 'pw12345!')
        self.b = User.objects.create_user('wg_b', 'wgb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=self.a, user2=self.b,
                                 user1_teaches=en, user1_learns=ko,
                                 status='active')
        self.room = ChatRoom.objects.create(match=m)

    async def _connect(self, user):
        from .consumers import TextChatConsumer
        rid = str(self.room.room_id)
        scope = {'path': f'/ws/text-chat/{rid}/', 'user': user,
                 'url_route': {'kwargs': {'room_id': rid}}}
        c = _make_communicator(TextChatConsumer, scope)
        ok, _ = await c.connect()
        self.assertTrue(ok)
        return c

    async def _next(self, c, wanted, limit=8):
        for _ in range(limit):
            msg = await c.receive_json_from(timeout=5)
            if msg.get('type') == wanted:
                return msg
        self.fail(f'no {wanted} frame')

    async def test_edit_with_blank_content_rejected(self):
        msg = await database_sync_to_async(ChatMessage.objects.create)(
            room=self.room, sender=self.a, content='old')
        ca = await self._connect(self.a)
        await ca.send_json_to({'type': 'edit_message', 'message_id': msg.id,
                               'content': '   '})
        frame = await self._next(ca, 'error')
        self.assertEqual(frame['message'], 'Invalid edit request')
        saved = await database_sync_to_async(ChatMessage.objects.get)(pk=msg.pk)
        self.assertEqual(saved.content, 'old')
        await ca.disconnect()

    async def test_edit_without_message_id_rejected(self):
        ca = await self._connect(self.a)
        await ca.send_json_to({'type': 'edit_message', 'content': 'new'})
        frame = await self._next(ca, 'error')
        self.assertEqual(frame['message'], 'Invalid edit request')
        await ca.disconnect()
