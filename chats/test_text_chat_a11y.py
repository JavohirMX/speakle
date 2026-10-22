from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matches.models import Match
from users.models import Language

from .models import ChatRoom

User = get_user_model()


class TextChatEditDialogTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('ta_a', email='ta_a@x.com', password='pw')
        self.b = User.objects.create_user('ta_b', email='ta_b@x.com', password='pw')
        en = Language.objects.create(code='en-ta', name='English TA')
        es = Language.objects.create(code='es-ta', name='Spanish TA')
        match = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en,
                                     user1_learns=es, status='active')
        self.room = ChatRoom.objects.create(match=match)

    def test_edit_dialog_is_labelled_and_closable(self):
        self.client.force_login(self.a)
        html = self.client.get(reverse('chats:text_chat', args=[self.room.room_id])).content.decode()
        self.assertIn('id="editModal" class="edit-modal" role="dialog" aria-modal="true" aria-labelledby="editModalTitle"', html)
        self.assertIn('id="editModalTitle"', html)
        self.assertIn('aria-label="Close" onclick="closeEditModal()"', html)
        self.assertIn('id="editTextarea" class="edit-textarea" aria-label="Message text"', html)
        self.assertIn("e.key === 'Escape'", html)

    def test_message_actions_stay_keyboard_reachable(self):
        self.client.force_login(self.a)
        html = self.client.get(reverse('chats:text_chat', args=[self.room.room_id])).content.decode()
        self.assertIn('.message:focus-within .message-actions', html)
        block = html.split('.message-actions {', 1)[1].split('}', 1)[0]
        self.assertNotIn('display: none', block)

    def test_icon_click_and_tab_trap_are_wired(self):
        self.client.force_login(self.a)
        html = self.client.get(reverse('chats:text_chat', args=[self.room.room_id])).content.decode()
        # The Edit button wraps an <svg>; a real click targets the icon, so match with closest().
        self.assertIn("e.target.closest('.edit-btn')", html)
        self.assertIn("e.target.closest('.reply-btn')", html)
        self.assertNotIn("e.target.classList.contains('edit-btn')", html)
        self.assertIn("e.key === 'Tab'", html)
