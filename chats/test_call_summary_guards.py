"""404 and participant guards on end_call, statistics and call summary."""
import uuid

from django.urls import reverse

from .models import CallSession
from .test_api_views import ChatApiBase


class CallApiNotFoundTests(ChatApiBase):
    def test_end_call_unknown_room_is_404(self):
        r = self.client_for(self.a).post(
            reverse('chats:end_call_with_reason', args=[uuid.uuid4()]),
            {'end_reason': 'normal'})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['error'], 'Room not found')

    def test_statistics_unknown_room_is_404(self):
        r = self.client_for(self.a).get(
            reverse('chats:get_call_statistics', args=[uuid.uuid4()]))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['error'], 'Room not found')


class CallSummaryGuardTests(ChatApiBase):
    def test_room_member_who_missed_the_call_cannot_view_summary(self):
        s = CallSession.objects.create(
            room=self.video, status='ended', end_reason='normal')
        s.participants.add(self.a)  # b has room access but was not on the call
        r = self.client_for(self.b).get(
            reverse('chats:call_summary', args=[self.video.room_id, s.id]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/matches/', r.url)

    def test_session_from_another_room_is_not_found(self):
        other_match_room = None
        from matches.models import Match
        from django.contrib.auth import get_user_model
        U = get_user_model()
        c = U.objects.create_user('csr4', 'csr4@x.com', 'pw12345!')
        d = U.objects.create_user('csr5', 'csr5@x.com', 'pw12345!')
        other_match = Match.objects.create(
            user1=c, user2=d, user1_teaches=self.match.user1_teaches,
            user1_learns=self.match.user1_learns, status='active')
        from .models import VideoRoom
        other_room = VideoRoom.objects.create(match=other_match)
        foreign = CallSession.objects.create(
            room=other_room, status='ended', end_reason='normal')
        # Even a real participant of that session must not reach it
        # through this room's URL: the lookup is scoped to the room.
        foreign.participants.add(self.a)
        r = self.client_for(self.a).get(
            reverse('chats:call_summary',
                    args=[self.video.room_id, foreign.id]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/matches/', r.url)

    def test_unknown_room_redirects_with_error(self):
        r = self.client_for(self.a).get(
            reverse('chats:call_summary', args=[uuid.uuid4(), 1]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/matches/', r.url)
