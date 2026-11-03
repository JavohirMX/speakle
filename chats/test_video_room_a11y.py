"""Accessibility regression tests for the video room template.

Grounded defects found in the current dev template (audit Nov 4, 2026):
- the in-call chat input needs a stable descriptive label;
  the text-chat equivalent already carries aria-label="Message".
- the three "x" close buttons (chat panel, end-call dialog, call-summary
  dialog) expose "×" as their only accessible name.
- the end-call and call-summary overlays are plain divs with no dialog
  semantics, unlike editModal/globalIncomingCallModal which carry
  explicit dialog roles. Native modal dialogs supply focus handling,
  background inertness, Escape dismissal and focus return.
"""
from html.parser import HTMLParser

from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from matches.models import Match
from users.models import Language
from chats.models import VideoRoom

User = get_user_model()


class TemplateElements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.by_id = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.by_id[attrs['id']] = (tag, attrs)


class VideoRoomA11yTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='a11yuser1', email='a11y1@example.com', password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='a11yuser2', email='a11y2@example.com', password='testpass123'
        )
        self.english = Language.objects.create(name='English', code='en', flag_emoji='')
        self.korean = Language.objects.create(name='Korean', code='ko', flag_emoji='')
        self.match = Match.objects.create(
            user1=self.user1, user2=self.user2,
            user1_teaches=self.english, user1_learns=self.korean,
            status='active',
        )
        self.room = VideoRoom.objects.create(match=self.match)
        self.client.login(username='a11yuser1', password='testpass123')
        response = self.client.get(reverse('chats:video_room', args=[self.room.room_id]))
        self.assertEqual(response.status_code, 200)
        self.html = response.content.decode('utf-8')
        self.elements = TemplateElements(self.html).by_id

    def test_chat_input_has_accessible_name(self):
        self.assertEqual(self.elements['chatInput'][1]['aria-label'], 'Chat message')

    def test_close_buttons_have_accessible_names(self):
        names = {
            'closeChatBtn': 'Close chat',
            'closeCallEndModal': 'Close end call dialog',
            'closeCallSummaryModal': 'Close call summary dialog',
        }
        for element_id, name in names.items():
            with self.subTest(element=element_id):
                self.assertEqual(self.elements[element_id][1].get('aria-label'), name)

    def test_overlays_are_named_native_modal_dialogs(self):
        for element_id, title_id in (
            ('callEndModal', 'endCallTitle'),
            ('callSummaryModal', 'callSummaryTitle'),
        ):
            with self.subTest(element=element_id):
                tag, attrs = self.elements[element_id]
                self.assertEqual(tag, 'dialog')
                self.assertEqual(attrs['aria-labelledby'], title_id)
                self.assertIn(title_id, self.elements)
                self.assertNotIn('open', attrs)
                self.assertIn(f"document.getElementById('{element_id}').showModal()", self.html)
                self.assertIn(f"document.getElementById('{element_id}').close()", self.html)
