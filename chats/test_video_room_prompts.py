"""Conversation topic card in the video room."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from chats.models import VideoRoom
from matches.models import Match
from users.models import Language

User = get_user_model()


class VideoRoomPromptsTests(TestCase):
    def setUp(self):
        self.u1 = User.objects.create_user('anna', password='pw')
        self.u2 = User.objects.create_user('boris', password='pw')
        self.outsider = User.objects.create_user('cora', password='pw')
        lang = Language.objects.create(name='Testlang', code='tl')
        self.match = Match.objects.create(
            user1=self.u1, user2=self.u2,
            user1_teaches=lang, user1_learns=lang, status='active')
        self.room = VideoRoom.objects.create(match=self.match)
        self.url = reverse('chats:video_room', args=[self.room.room_id])

    def test_room_page_has_topic_card_and_prompts(self):
        self.client.force_login(self.u1)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="topicCard"')
        self.assertContains(resp, 'id="toggleTopic"')
        self.assertContains(resp, 'callPrompts')
        self.assertGreaterEqual(len(resp.context['call_prompts']), 1)
        self.assertIn('level', resp.context['call_prompts'][0])
        self.assertIn('text', resp.context['call_prompts'][0])

    def test_outsider_gets_no_prompts(self):
        self.client.force_login(self.outsider)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
