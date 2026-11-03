"""The quick-call modal POSTs to create-room and parses JSON. The view
used to answer with a redirect to an HTML page, so every 'enter room'
click showed 'Failed to create video room. Please try again.'"""
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from users.models import Language
from matches.models import Match
from .models import VideoRoom

User = get_user_model()


class CreateRoomApiTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('cra', 'cra@x.com', 'pw12345!')
        self.b = User.objects.create_user('crb', 'crb@x.com', 'pw12345!')
        self.out = User.objects.create_user('cro', 'cro@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.match = Match.objects.create(
            user1=self.a, user2=self.b, user1_teaches=en, user1_learns=ko, status='active')

    def test_post_returns_json_with_room_url(self):
        self.client.force_login(self.a)
        r = self.client.post(reverse('chats:create_video_room', args=[self.match.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/json')
        data = r.json()
        self.assertTrue(data['success'])
        room = VideoRoom.objects.get(match=self.match)
        self.assertEqual(data['room_url'], f'/chats/room/{room.room_id}/')
        self.assertTrue(data['created'])

    def test_post_is_idempotent(self):
        self.client.force_login(self.a)
        url = reverse('chats:create_video_room', args=[self.match.id])
        first = self.client.post(url).json()
        second = self.client.post(url).json()
        self.assertEqual(first['room_id'], second['room_id'])
        self.assertFalse(second['created'])
        self.assertEqual(VideoRoom.objects.filter(match=self.match).count(), 1)

    def test_post_outsider_gets_json_403(self):
        self.client.force_login(self.out)
        r = self.client.post(reverse('chats:create_video_room', args=[self.match.id]))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r['Content-Type'], 'application/json')

    def test_get_still_redirects_to_room(self):
        self.client.force_login(self.a)
        r = self.client.get(reverse('chats:create_video_room', args=[self.match.id]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/chats/room/', r.url)
