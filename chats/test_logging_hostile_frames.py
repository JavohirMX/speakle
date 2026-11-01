"""Malformed or hostile frames must not echo client-chosen text into stdout or logs.

Covers the print-to-logger conversion in chats/consumers.py: unrecognised frame
types and malformed ids are client-controlled strings. Sender name and message
length are still logged (metadata, not anonymous logging).
"""
import asyncio
import contextlib
import io
import json
import logging
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from matches.models import Match
from users.models import Language
from .consumers import VideoCallConsumer, TextChatConsumer
from .models import VideoRoom, ChatRoom
User = get_user_model()
M = 'MKR-7731-zebra'  # marker that must never appear

class H(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.rows = []

    def emit(self, record):
        self.rows.append(logging.Formatter().format(record))  # includes any traceback

class HostileFrameLoggingTests(TransactionTestCase):
    def setUp(self):
        self.a = User.objects.create_user('pr_a', email='pa@x.com', password='pw')
        self.b = User.objects.create_user('pr_b', email='pb@x.com', password='pw')
        en = Language.objects.create(code='en-pr', name='E'); es = Language.objects.create(code='es-pr', name='S')
        m = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en, user1_learns=es, status='active')
        self.v = VideoRoom.objects.create(match=m); self.t = ChatRoom.objects.create(match=m)

    async def run_probe(self, cons, path, rid, frames):
        h = H(); root = logging.getLogger(); old = root.level
        root.addHandler(h); root.setLevel(logging.DEBUG); out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                c = WebsocketCommunicator(cons.as_asgi(), path)
                c.scope['user'] = self.a; c.scope['url_route'] = {'kwargs': {'room_id': str(rid)}}
                ok, _ = await c.connect(); assert ok
                for f in frames:
                    await c.send_to(text_data=f if isinstance(f, str) else json.dumps(f))
                await asyncio.sleep(0.3)
                await c.disconnect()
        finally:
            root.removeHandler(h); root.setLevel(old)
        return h.rows, out.getvalue()

    async def test_marker_never_logged(self):
        frames = [
            '{bad json ' + M,                                   # invalid JSON
            json.dumps([M]),                                    # JSON list
            {'type': M},                                        # unknown type carrying marker
            {'type': 'chat_message', 'message': 123},           # non-string
            {'type': 'chat_message', 'message': {'x': M}},      # dict
            {'type': 'chat_message', 'message': M * 60},        # too long
            {'type': 'offer', 'offer': M},                      # SDP-like
            {'type': 'ice_candidate', 'candidate': M},
            {'type': 'call_end', 'end_notes': M, 'end_reason': M, 'connection_quality': M, 'network_issues': M},
        ]
        tframes = [
            '{bad ' + M, {'type': M}, {'type': 'send_message', 'message': {'x': M}},
            {'type': 'send_message', 'message': M, 'reply_to': M},
            {'type': 'edit_message', 'message_id': M, 'content': M},
            {'type': 'edit_message', 'message_id': 999999, 'content': M},
            {'type': 'send_message', 'message': M * 200},
        ]
        for name, cons, path, rid, fr in (('video', VideoCallConsumer, f'/ws/video/{self.v.room_id}/', self.v.room_id, frames),
                                          ('text', TextChatConsumer, f'/ws/text-chat/{self.t.room_id}/', self.t.room_id, tframes)):
            rows, out = await self.run_probe(cons, path, rid, fr)
            self.assertNotIn('MKR', out, f'{name}: stdout')
            leaked = [r.splitlines()[0] for r in rows if 'MKR' in r]
            self.assertEqual(leaked, [], f'{name}: log records')
