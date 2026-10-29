"""Chat content must not reach stdout or logs (the app's analytics stance is no chat content)."""
import contextlib
import io
import logging

from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from matches.models import Match
from users.models import Language

from .consumers import VideoCallConsumer
from .models import VideoRoom

User = get_user_model()
SECRET = 'zebra-pancake-7731-private-words'


class _Collect(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class VideoChatLoggingPrivacyTests(TransactionTestCase):
    def setUp(self):
        self.a = User.objects.create_user('lp_a', email='lp_a@x.com', password='pw')
        self.b = User.objects.create_user('lp_b', email='lp_b@x.com', password='pw')
        en = Language.objects.create(code='en-lp', name='English LP')
        es = Language.objects.create(code='es-lp', name='Spanish LP')
        m = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en,
                                 user1_learns=es, status='active')
        self.room = VideoRoom.objects.create(match=m)

    async def test_chat_message_text_is_not_written_to_stdout_or_logs(self):
        handler = _Collect()
        root = logging.getLogger()
        old_level = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                c = WebsocketCommunicator(VideoCallConsumer.as_asgi(), f'/ws/video/{self.room.room_id}/')
                c.scope['user'] = self.a
                c.scope['url_route'] = {'kwargs': {'room_id': str(self.room.room_id)}}
                ok, _ = await c.connect()
                self.assertTrue(ok)
                await c.send_json_to({'type': 'chat_message', 'message': SECRET})
                await c.receive_json_from()
                await c.receive_json_from()
                await c.disconnect()
        finally:
            root.removeHandler(handler)
            root.setLevel(old_level)
        self.assertNotIn(SECRET, out.getvalue())
        self.assertFalse([l for l in handler.lines if SECRET in l])
        self.assertEqual(out.getvalue().strip(), '', 'consumers should log, not print')
