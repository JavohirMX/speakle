"""Relay and attendance tests for the video-call signaling handlers.

Covers the previously untested handle_answer / handle_ice_candidate /
handle_peer_ready paths in chats/consumers.py: payload relay to the peer,
sender echo suppression, missing-payload error frames, and the streak
provenance wiring - answer and peer_ready must open a
CallParticipantInterval on the room's active session.
"""
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from channels.db import database_sync_to_async

from users.models import Language
from matches.models import Match
from .models import (
    VideoRoom, CallSession, CallParticipantInterval,
)
from .consumers import VideoCallConsumer
from .tests import _make_communicator, _receive_type

User = get_user_model()


class SignalingRelayTest(TransactionTestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='relayuser1', email='r1@example.com', password='x')
        self.user2 = User.objects.create_user(
            username='relayuser2', email='r2@example.com', password='x')
        self.english = Language.objects.create(
            name='English', code='en', flag_emoji='US')
        self.korean = Language.objects.create(
            name='Korean', code='ko', flag_emoji='KR')
        self.match = Match.objects.create(
            user1=self.user1, user2=self.user2,
            user1_teaches=self.english, user1_learns=self.korean,
            status='active')
        self.room = VideoRoom.objects.create(match=self.match)
        self.session = CallSession.objects.create(
            room=self.room, status='active')

    def _scope(self, user):
        return {
            'type': 'websocket',
            'path': f'/ws/video/{self.room.room_id}/',
            'query_string': b'',
            'headers': [],
            'user': user,
            'url_route': {'kwargs': {'room_id': str(self.room.room_id)}},
        }

    async def _pair(self):
        mine = _make_communicator(VideoCallConsumer, self._scope(self.user1))
        self.assertTrue((await mine.connect())[0])
        other = _make_communicator(VideoCallConsumer, self._scope(self.user2))
        self.assertTrue((await other.connect())[0])
        # connect() accepts before group_add completes; wait for the join
        # broadcast (itself a group message) so early sends are not missed.
        for _ in range(4):
            joined = await _receive_type(mine, 'user_joined')
            if joined['user_id'] == self.user2.id:
                break
        else:
            self.fail('never saw partner join broadcast')
        return mine, other

    def _open_intervals(self, user):
        return CallParticipantInterval.objects.filter(
            session=self.session, user=user, left_at__isnull=True).count()

    async def test_answer_relayed_to_peer_not_sender_and_records_attendance(self):
        mine, other = await self._pair()
        await mine.send_json_to({
            'type': 'answer',
            'answer': {'type': 'answer', 'sdp': 'answer-sdp'},
        })
        got = await _receive_type(other, 'answer')
        self.assertEqual(got['answer']['sdp'], 'answer-sdp')
        self.assertEqual(got['sender_username'], 'relayuser1')
        while not await mine.receive_nothing():
            self.assertNotEqual(
                (await mine.receive_json_from()).get('type'), 'answer')
        # Streak provenance: answering opens a presence interval.
        count = await database_sync_to_async(self._open_intervals)(self.user1)
        self.assertEqual(count, 1)
        await mine.disconnect()
        await other.disconnect()

    async def test_answer_without_payload_returns_error(self):
        mine, other = await self._pair()
        await mine.send_json_to({'type': 'answer'})
        err = await _receive_type(mine, 'error')
        self.assertIn('No answer data provided', err['message'])
        count = await database_sync_to_async(self._open_intervals)(self.user1)
        self.assertEqual(count, 0)  # a failed frame must not fake attendance
        await mine.disconnect()
        await other.disconnect()

    async def test_ice_candidate_relayed_and_missing_payload_errors(self):
        mine, other = await self._pair()
        await mine.send_json_to({
            'type': 'ice_candidate',
            'candidate': {'candidate': 'candidate:1 ...', 'sdpMid': '0'},
        })
        got = await _receive_type(other, 'ice_candidate')
        self.assertEqual(got['candidate']['sdpMid'], '0')
        self.assertEqual(got['sender_username'], 'relayuser1')

        await mine.send_json_to({'type': 'ice_candidate'})
        err = await _receive_type(mine, 'error')
        self.assertIn('No ICE candidate data provided', err['message'])
        await mine.disconnect()
        await other.disconnect()

    async def test_peer_ready_relayed_and_records_attendance(self):
        mine, other = await self._pair()
        await other.send_json_to({'type': 'peer_ready'})
        got = await _receive_type(mine, 'peer_ready')
        self.assertEqual(got['sender_username'], 'relayuser2')
        count = await database_sync_to_async(self._open_intervals)(self.user2)
        self.assertEqual(count, 1)
        # Ready twice must not duplicate the open interval.
        await other.send_json_to({'type': 'peer_ready'})
        await _receive_type(mine, 'peer_ready')
        count = await database_sync_to_async(self._open_intervals)(self.user2)
        self.assertEqual(count, 1)
        await mine.disconnect()
        await other.disconnect()
