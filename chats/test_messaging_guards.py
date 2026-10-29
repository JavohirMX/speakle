"""Remaining messaging API guards: 404s, 403s, edit edge cases."""
import uuid

from django.urls import reverse

from .models import ChatRoom, ChatMessage
from .test_api_views import ChatApiBase


class MessagingGuardTests(ChatApiBase):
    def test_send_to_unknown_room_is_404(self):
        r = self.client_for(self.a).post(
            reverse('chats:send_chat_message', args=[uuid.uuid4()]),
            {'content': 'hi'})
        self.assertEqual(r.status_code, 404)

    def test_edit_rejects_empty_content(self):
        m = ChatMessage.objects.create(room=self.chat, sender=self.a, content='x')
        r = self.client_for(self.a).post(
            reverse('chats:edit_chat_message', args=[m.id]), {'content': '  '})
        self.assertEqual(r.status_code, 400)
        m.refresh_from_db()
        self.assertEqual(m.content, 'x')

    def test_non_text_message_cannot_be_edited(self):
        m = ChatMessage.objects.create(
            room=self.chat, sender=self.a, content='sys', message_type='system')
        r = self.client_for(self.a).post(
            reverse('chats:edit_chat_message', args=[m.id]), {'content': 'new'})
        self.assertEqual(r.status_code, 403)
        m.refresh_from_db()
        self.assertEqual(m.content, 'sys')

    def test_mark_read_outsider_denied_and_unknown_room_404(self):
        r = self.client_for(self.outsider).post(
            reverse('chats:mark_messages_read', args=[self.chat.room_id]))
        self.assertEqual(r.status_code, 403)
        r = self.client_for(self.a).post(
            reverse('chats:mark_messages_read', args=[uuid.uuid4()]))
        self.assertEqual(r.status_code, 404)

    def test_unread_count_outsider_denied_and_unknown_room_404(self):
        r = self.client_for(self.outsider).get(
            reverse('chats:get_unread_count', args=[self.chat.room_id]))
        self.assertEqual(r.status_code, 403)
        r = self.client_for(self.a).get(
            reverse('chats:get_unread_count', args=[uuid.uuid4()]))
        self.assertEqual(r.status_code, 404)

    def test_chat_list_creates_missing_room(self):
        self.chat.delete()
        self.assertFalse(ChatRoom.objects.filter(match=self.match).exists())
        r = self.client_for(self.a).get(reverse('chats:chat_list'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(ChatRoom.objects.filter(match=self.match).exists())
