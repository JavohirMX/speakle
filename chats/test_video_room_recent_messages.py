from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matches.models import Match
from users.models import Language

from .models import RoomMessage, VideoRoom

User = get_user_model()


class VideoRoomRecentMessagesTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('vr_a', email='vr_a@x.com', password='pw')
        self.b = User.objects.create_user('vr_b', email='vr_b@x.com', password='pw')
        en = Language.objects.create(code='en-vr', name='English VR')
        es = Language.objects.create(code='es-vr', name='Spanish VR')
        m = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en,
                                 user1_learns=es, status='active')
        self.room = VideoRoom.objects.create(match=m)

    def _msgs(self, n):
        for i in range(1, n + 1):
            RoomMessage.objects.create(room=self.room, sender=self.a, content=f'msg {i:03d}')

    def test_shows_the_latest_50_in_chronological_order(self):
        self._msgs(60)
        self.client.force_login(self.a)
        r = self.client.get(reverse('chats:video_room', args=[self.room.room_id]))
        self.assertEqual(r.status_code, 200)
        got = [m.content for m in r.context['recent_messages']]
        self.assertEqual(len(got), 50)
        self.assertEqual(got[0], 'msg 011')
        self.assertEqual(got[-1], 'msg 060')
        self.assertEqual(got, sorted(got))

    def test_short_history_unchanged(self):
        self._msgs(3)
        self.client.force_login(self.a)
        r = self.client.get(reverse('chats:video_room', args=[self.room.room_id]))
        self.assertEqual([m.content for m in r.context['recent_messages']], ['msg 001', 'msg 002', 'msg 003'])
