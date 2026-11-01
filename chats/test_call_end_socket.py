"""Websocket call_end: persists reason/ended_by, closes intervals, deactivates room."""
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone

from users.models import Language
from matches.models import Match
from .models import VideoRoom, CallSession, CallParticipantInterval
from .test_api_views import _make_communicator

User = get_user_model()


class CallEndSocketTests(TransactionTestCase):
    def setUp(self):
        self.a = User.objects.create_user('ce_a', 'cea@x.com', 'pw12345!')
        self.b = User.objects.create_user('ce_b', 'ceb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=self.a, user2=self.b,
                                 user1_teaches=en, user1_learns=ko,
                                 status='active')
        self.room = VideoRoom.objects.create(match=m)

    async def _connect(self, user):
        from .consumers import VideoCallConsumer
        rid = str(self.room.room_id)
        c = _make_communicator(VideoCallConsumer, {
            'path': f'/ws/video-call/{rid}/', 'user': user,
            'url_route': {'kwargs': {'room_id': rid}}})
        ok, _ = await c.connect()
        self.assertTrue(ok)
        while True:
            frame = await c.receive_json_from(timeout=5)
            if frame.get('type') == 'user_joined' and frame.get('user_id') == user.id:
                break
        return c

    async def _next(self, c, wanted, limit=10):
        for _ in range(limit):
            msg = await c.receive_json_from(timeout=5)
            if msg.get('type') == wanted:
                return msg
        self.fail(f'no {wanted} frame')

    def _session(self):
        return CallSession.objects.get(room=self.room)

    async def test_call_end_persists_and_broadcasts(self):
        ca = await self._connect(self.a)
        cb = await self._connect(self.b)
        await ca.send_json_to({'type': 'call_start'})
        await self._next(ca, 'call_started')
        session = await database_sync_to_async(self._session)()
        await database_sync_to_async(CallParticipantInterval.objects.create)(
            session=session, user=self.a, joined_at=timezone.now())
        await ca.send_json_to({
            'type': 'call_end', 'end_reason': 'normal',
            'end_notes': 'good practice'})
        frame = await self._next(cb, 'call_ended_enhanced')
        self.assertEqual(frame['end_reason'], 'normal')
        self.assertIsNotNone(frame['session_summary'])
        self.assertIn('/summary/', frame['redirect_url'])

        session = await database_sync_to_async(self._session)()
        self.assertEqual(session.status, 'ended')
        self.assertEqual(session.end_reason, 'normal')
        self.assertEqual(session.end_notes, 'good practice')
        self.assertEqual(session.ended_by_id, self.a.id)
        open_intervals = await database_sync_to_async(
            CallParticipantInterval.objects.filter(
                session=session, left_at__isnull=True).count)()
        self.assertEqual(open_intervals, 0)
        room = await database_sync_to_async(VideoRoom.objects.get)(
            room_id=self.room.room_id)
        self.assertFalse(room.is_active)
        await ca.disconnect()
        await cb.disconnect()
