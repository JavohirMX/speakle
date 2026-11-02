"""The text-chat page used to ship a dead call-invitation modal whose ids
(statusText, statusIndicator, waitingResponse, ...) collided with the real
quick-call modal in base.html. document.getElementById then hit the dead
markup first, so opening a video call from chat sat on 'Checking
availability...' forever."""
import re
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from users.models import Language
from matches.models import Match
from .models import ChatRoom

User = get_user_model()


class CallModalIdTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('cmida', 'ca@x.com', 'pw12345!')
        self.b = User.objects.create_user('cmidb', 'cb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.match = Match.objects.create(
            user1=self.a, user2=self.b, user1_teaches=en, user1_learns=ko, status='active')
        self.chat = ChatRoom.objects.create(match=self.match)

    def test_served_page_has_unique_status_ids(self):
        self.client.force_login(self.a)
        r = self.client.get(reverse('chats:text_chat', args=[self.chat.room_id]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        ids = re.findall(r'id="([^"${][^"]*)"', html)
        dupes = {i for i in ids if ids.count(i) > 1}
        self.assertEqual(dupes, set(), f'duplicate element ids: {dupes}')
        self.assertNotIn('callInvitationModal', html)
        self.assertIn('id="connStatusText"', html)
