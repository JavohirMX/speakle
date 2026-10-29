"""Blocking a user closes live rooms: sockets get access_revoked and drop."""
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from users.models import Language
from matches.models import Match
from .models import VideoRoom, ChatRoom, CallSession
from .test_api_views import _make_communicator

User = get_user_model()


class AccessRevokedTests(TransactionTestCase):
    def setUp(self):
        self.a = User.objects.create_user('ar_a', 'ara@x.com', 'pw12345!')
        self.b = User.objects.create_user('ar_b', 'arb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.match = Match.objects.create(
            user1=self.a, user2=self.b,
            user1_teaches=en, user1_learns=ko, status='active')
        self.video = VideoRoom.objects.create(match=self.match)
        self.chat = ChatRoom.objects.create(match=self.match)

    async def _connect(self, consumer_path, consumer_cls, user, room):
        rid = str(room.room_id)
        c = _make_communicator(consumer_cls, {
            'path': consumer_path.format(rid), 'user': user,
            'url_route': {'kwargs': {'room_id': rid}}})
        ok, _ = await c.connect()
        self.assertTrue(ok)
        return c

    async def _next(self, c, wanted, limit=10):
        for _ in range(limit):
            msg = await c.receive_json_from(timeout=5)
            if msg.get('type') == wanted:
                return msg
        self.fail(f'no {wanted} frame')

    async def test_block_closes_video_and_text_sockets_and_ends_call(self):
        from .consumers import VideoCallConsumer, TextChatConsumer
        from .models import close_rooms_for_pair

        va = await self._connect('/ws/video-call/{}', VideoCallConsumer,
                                 self.a, self.video)
        # drain the join echo
        while True:
            frame = await va.receive_json_from(timeout=5)
            if frame.get('type') == 'user_joined':
                break
        ta = await self._connect('/ws/text-chat/{}', TextChatConsumer,
                                 self.a, self.chat)
        session = await database_sync_to_async(CallSession.objects.create)(
            room=self.video, status='active')

        await database_sync_to_async(close_rooms_for_pair)(self.b, self.a)

        for sock in (va, ta):
            frame = await self._next(sock, 'error')
            self.assertTrue(frame['closed'])
            # The consumer then closes the socket itself.
            close = await sock.receive_output(timeout=2)
            self.assertEqual(close['type'], 'websocket.close')

        await session.arefresh_from_db()
        self.assertEqual(session.status, 'ended')
        await self.video.arefresh_from_db()
        self.assertFalse(self.video.is_active)
