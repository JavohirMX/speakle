"""Error-path and edge tests for room_status, check_invitation_status,
the video_room missing-room redirect, and the _format_minutes helper.
"""
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from users.models import Language
from matches.models import Match
from .models import VideoRoom, CallInvitation, CallSession
from .views import _format_minutes

User = get_user_model()


class RoomStatusApiTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='rs1', email='rs1@example.com', password='x')
        self.user2 = User.objects.create_user(
            username='rs2', email='rs2@example.com', password='x')
        self.outsider = User.objects.create_user(
            username='rs3', email='rs3@example.com', password='x')
        en = Language.objects.create(name='English', code='en', flag_emoji='US')
        ko = Language.objects.create(name='Korean', code='ko', flag_emoji='KR')
        self.match = Match.objects.create(
            user1=self.user1, user2=self.user2,
            user1_teaches=en, user1_learns=ko, status='active')
        self.room = VideoRoom.objects.create(match=self.match)
        self.url = reverse('chats:room_status', args=[self.room.room_id])

    def test_idle_room_status(self):
        self.client.force_login(self.user1)
        data = self.client.get(self.url).json()
        self.assertFalse(data['is_active'])
        self.assertFalse(data['has_active_session'])
        self.assertEqual(data['participant_count'], 0)

    def test_active_session_reports_participants(self):
        session = CallSession.objects.create(room=self.room, status='active')
        session.participants.add(self.user1, self.user2)
        self.client.force_login(self.user1)
        data = self.client.get(self.url).json()
        self.assertTrue(data['has_active_session'])
        self.assertEqual(data['participant_count'], 2)

    def test_outsider_gets_403(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_missing_room_gets_404(self):
        self.client.force_login(self.user1)
        r = self.client.get(reverse('chats:room_status', args=[uuid.uuid4()]))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['error'], 'Room not found')

    def test_video_room_missing_room_redirects(self):
        self.client.force_login(self.user1)
        r = self.client.get(reverse('chats:video_room', args=[uuid.uuid4()]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/matches/', r.url)


class InvitationStatusApiTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.caller = User.objects.create_user(
            username='is1', email='is1@example.com', password='x')
        self.receiver = User.objects.create_user(
            username='is2', email='is2@example.com', password='x')
        en = Language.objects.create(name='English', code='en', flag_emoji='US')
        ko = Language.objects.create(name='Korean', code='ko', flag_emoji='KR')
        self.match = Match.objects.create(
            user1=self.caller, user2=self.receiver,
            user1_teaches=en, user1_learns=ko, status='active')
        self.room = VideoRoom.objects.create(match=self.match)
        self.invitation = CallInvitation.objects.create(
            room=self.room, caller=self.caller, receiver=self.receiver,
            expires_at=timezone.now() + timedelta(minutes=5))

    def test_caller_sees_pending_status(self):
        self.client.force_login(self.caller)
        data = self.client.get(
            reverse('chats:check_invitation_status',
                    args=[self.invitation.id])).json()
        self.assertEqual(data['status'], 'pending')
        self.assertIsNone(data['responded_at'])
        self.assertFalse(data['is_expired'])

    def test_past_expiry_marks_is_expired(self):
        self.invitation.expires_at = timezone.now() - timedelta(minutes=1)
        self.invitation.save()
        self.client.force_login(self.caller)
        data = self.client.get(
            reverse('chats:check_invitation_status',
                    args=[self.invitation.id])).json()
        self.assertTrue(data['is_expired'])

    def test_receiver_cannot_read_caller_status_endpoint(self):
        # The endpoint is scoped to the caller; anyone else gets 404.
        self.client.force_login(self.receiver)
        r = self.client.get(reverse('chats:check_invitation_status',
                                    args=[self.invitation.id]))
        self.assertEqual(r.status_code, 404)


class FormatMinutesTest(TestCase):
    def test_seconds_only(self):
        self.assertEqual(_format_minutes(timedelta(seconds=42)), '42s')

    def test_minutes_only(self):
        self.assertEqual(_format_minutes(timedelta(minutes=7)), '7m')

    def test_hours_and_minutes(self):
        self.assertEqual(_format_minutes(timedelta(hours=1, minutes=5)), '1h 05m')
