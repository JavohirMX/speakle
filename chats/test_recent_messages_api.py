"""API tests for get_recent_messages (chats:get_recent_messages).

The view body was uncovered: access denial, missing room, the last-50
window and its chronological re-ordering, and the is_own_message flag.
"""
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from users.models import Language
from matches.models import Match
from .models import VideoRoom, RoomMessage

User = get_user_model()


class RecentMessagesApiTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='msg1', email='m1@example.com', password='x')
        self.user2 = User.objects.create_user(
            username='msg2', email='m2@example.com', password='x')
        self.outsider = User.objects.create_user(
            username='msg3', email='m3@example.com', password='x')
        en = Language.objects.create(name='English', code='en', flag_emoji='US')
        ko = Language.objects.create(name='Korean', code='ko', flag_emoji='KR')
        self.match = Match.objects.create(
            user1=self.user1, user2=self.user2,
            user1_teaches=en, user1_learns=ko, status='active')
        self.room = VideoRoom.objects.create(match=self.match)
        self.url = reverse('chats:get_recent_messages',
                           args=[self.room.room_id])

    def test_returns_messages_chronological_with_own_flag(self):
        RoomMessage.objects.create(room=self.room, sender=self.user1, content='one')
        RoomMessage.objects.create(room=self.room, sender=self.user2, content='two')
        RoomMessage.objects.create(room=self.room, sender=self.user1, content='three')
        self.client.force_login(self.user1)
        data = self.client.get(self.url).json()
        self.assertTrue(data['success'])
        self.assertEqual([m['content'] for m in data['messages']],
                         ['one', 'two', 'three'])
        self.assertEqual([m['is_own_message'] for m in data['messages']],
                         [True, False, True])

    def test_keeps_only_the_latest_50_oldest_first(self):
        for i in range(55):
            RoomMessage.objects.create(
                room=self.room, sender=self.user1, content=f'msg-{i:02d}')
        self.client.force_login(self.user1)
        data = self.client.get(self.url).json()
        contents = [m['content'] for m in data['messages']]
        self.assertEqual(len(contents), 50)
        self.assertEqual(contents[0], 'msg-05')  # the oldest kept
        self.assertEqual(contents[-1], 'msg-54')
        self.assertEqual(contents, sorted(contents))

    def test_outsider_gets_403(self):
        self.client.force_login(self.outsider)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['error'], 'Access denied')

    def test_missing_room_gets_404(self):
        self.client.force_login(self.user1)
        r = self.client.get(reverse('chats:get_recent_messages',
                                    args=[uuid.uuid4()]))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['error'], 'Room not found')

    def test_anonymous_is_redirected_to_login(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/users/login/', r.url)
