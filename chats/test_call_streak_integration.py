"""Consumer to streak wiring: real call_start / call_end websocket messages.

matches/test_streaks.py builds CallParticipantInterval rows by hand. These
tests drive the actual VideoCallConsumer so the rows are the ones the
consumer writes, then ask the streak code whether the session counts.

Limits, stated plainly: the test clock is not advanced. After the real
messages have run, call and interval timestamps are shifted in the database
to stand in for a call that lasted several minutes. This proves the
consumer writes the presence rows and the streak code reads them as
intended. It does not prove real-network behaviour.
"""
import datetime as dt

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone

from matches.models import Match, MatchSession
from matches.streaks import joint_presence_seconds, session_completed
from users.models import Language

from .consumers import VideoCallConsumer
from .models import CallParticipantInterval, CallSession, VideoRoom

User = get_user_model()


class CallStreakIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.anna = User.objects.create_user('ci_anna', email='ci_a@x.com', password='pw')
        self.boris = User.objects.create_user('ci_boris', email='ci_b@x.com', password='pw')
        en = Language.objects.create(code='en-ci', name='English CI')
        es = Language.objects.create(code='es-ci', name='Spanish CI')
        self.match = Match.objects.create(
            user1=self.anna, user2=self.boris,
            user1_teaches=en, user1_learns=es, status='active')
        self.room = VideoRoom.objects.create(match=self.match)

    def comm(self, user):
        c = WebsocketCommunicator(VideoCallConsumer.as_asgi(), f'/ws/video/{self.room.room_id}/')
        c.scope['user'] = user
        c.scope['url_route'] = {'kwargs': {'room_id': str(self.room.room_id)}}
        return c

    async def connect(self, user):
        c = self.comm(user)
        ok, _ = await c.connect()
        self.assertTrue(ok)
        return c

    @database_sync_to_async
    def last_call(self):
        return CallSession.objects.get(room=self.room)

    @database_sync_to_async
    def intervals(self):
        return list(CallParticipantInterval.objects.filter(session__room=self.room)
                    .order_by('user_id', 'joined_at').values_list('user_id', 'left_at'))

    @database_sync_to_async
    def stand_in_for_minutes(self, minutes, boris_leaves_after=None):
        """Shift the real rows back in time so the call looks `minutes` long."""
        call = CallSession.objects.get(room=self.room)
        end = timezone.now()
        start = end - dt.timedelta(minutes=minutes)
        CallSession.objects.filter(id=call.id).update(started_at=start, ended_at=end)
        for iv in CallParticipantInterval.objects.filter(session=call):
            left = end
            if boris_leaves_after is not None and iv.user_id == self.boris.id:
                left = start + dt.timedelta(minutes=boris_leaves_after)
            CallParticipantInterval.objects.filter(id=iv.id).update(joined_at=start, left_at=left)
        return MatchSession.objects.create(
            match=self.match, proposed_by=self.anna, starts_at=start,
            duration_minutes=30, status='accepted')

    @database_sync_to_async
    def credit(self, session):
        call = CallSession.objects.get(room=self.room)
        return session_completed(session), joint_presence_seconds(call, self.anna.id, self.boris.id)

    async def test_both_signal_then_hangup_earns_credit(self):
        a, b = await self.connect(self.anna), await self.connect(self.boris)
        await a.send_json_to({'type': 'call_start', 'video_enabled': True, 'audio_enabled': True})
        await b.send_json_to({'type': 'call_start', 'video_enabled': True, 'audio_enabled': True})
        await a.send_json_to({'type': 'call_end', 'end_reason': 'user_hangup'})
        await a.disconnect(); await b.disconnect()

        rows = await self.intervals()
        self.assertEqual({uid for uid, _ in rows}, {self.anna.id, self.boris.id})
        self.assertTrue(all(left is not None for _, left in rows), 'hangup must close every interval')
        call = await self.last_call()
        self.assertEqual(call.status, 'ended')

        session = await self.stand_in_for_minutes(20)
        completed, joint = await self.credit(session)
        self.assertTrue(completed)
        self.assertAlmostEqual(joint, 20 * 60, delta=2)

    async def test_partner_who_never_signals_earns_no_credit(self):
        a, b = await self.connect(self.anna), await self.connect(self.boris)
        await a.send_json_to({'type': 'call_start', 'video_enabled': True, 'audio_enabled': True})
        await a.send_json_to({'type': 'call_end', 'end_reason': 'user_hangup'})
        await a.disconnect(); await b.disconnect()

        rows = await self.intervals()
        self.assertEqual({uid for uid, _ in rows}, {self.anna.id})
        session = await self.stand_in_for_minutes(20)
        completed, joint = await self.credit(session)
        self.assertFalse(completed)
        self.assertEqual(joint, 0)

    async def test_short_overlap_earns_no_credit(self):
        a, b = await self.connect(self.anna), await self.connect(self.boris)
        await a.send_json_to({'type': 'call_start', 'video_enabled': True, 'audio_enabled': True})
        await b.send_json_to({'type': 'call_start', 'video_enabled': True, 'audio_enabled': True})
        await a.send_json_to({'type': 'call_end', 'end_reason': 'user_hangup'})
        await a.disconnect(); await b.disconnect()

        session = await self.stand_in_for_minutes(20, boris_leaves_after=2)
        completed, joint = await self.credit(session)
        self.assertFalse(completed)
        self.assertAlmostEqual(joint, 2 * 60, delta=2)

    async def test_disconnect_without_hangup_closes_that_users_interval(self):
        a, b = await self.connect(self.anna), await self.connect(self.boris)
        await a.send_json_to({'type': 'call_start', 'video_enabled': True, 'audio_enabled': True})
        await b.send_json_to({'type': 'call_start', 'video_enabled': True, 'audio_enabled': True})
        await b.disconnect()
        rows = dict(await self.intervals())
        self.assertIsNotNone(rows[self.boris.id], 'dropped socket must close boris interval')
        self.assertIsNone(rows[self.anna.id], 'anna is still in the call')
        await a.disconnect()
