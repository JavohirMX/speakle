"""Blocked-pair and access guards on chat room creation and entry."""
import uuid

from django.urls import reverse

from users.models import UserBlock
from .models import ChatRoom
from .test_api_views import ChatApiBase


class ChatRoomAccessTests(ChatApiBase):
    def test_blocked_pair_cannot_create_chat_room(self):
        UserBlock.objects.create(blocker=self.a, blocked=self.b)
        r = self.client_for(self.a).get(
            reverse('chats:create_chat_room', args=[self.match.id]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/matches/', r.url)
        self.assertEqual(ChatRoom.objects.count(), 1)  # only the fixture room

    def test_blocked_pair_chat_url_denied(self):
        UserBlock.objects.create(blocker=self.b, blocked=self.a)
        r = self.client_for(self.a).get(
            reverse('chats:get_chat_room_url', args=[self.match.id]))
        self.assertEqual(r.status_code, 403)

    def test_outsider_cannot_create_or_get_url(self):
        r = self.client_for(self.outsider).get(
            reverse('chats:create_chat_room', args=[self.match.id]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ChatRoom.objects.count(), 1)  # only the fixture room
        r = self.client_for(self.outsider).get(
            reverse('chats:get_chat_room_url', args=[self.match.id]))
        self.assertEqual(r.status_code, 403)

    def test_chat_url_returns_room_for_member(self):
        r = self.client_for(self.a).get(
            reverse('chats:get_chat_room_url', args=[self.match.id]))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['success'])
        room = ChatRoom.objects.get(match=self.match)
        self.assertEqual(body['room_id'], str(room.room_id))

    def test_create_chat_room_reuses_existing_room(self):
        self.client_for(self.a).get(
            reverse('chats:create_chat_room', args=[self.match.id]))
        self.assertEqual(ChatRoom.objects.filter(match=self.match).count(), 1)

    def test_text_chat_unknown_room_redirects(self):
        r = self.client_for(self.a).get(
            reverse('chats:text_chat', args=[uuid.uuid4()]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/matches/', r.url)

    def test_text_chat_outsider_denied(self):
        r = self.client_for(self.outsider).get(
            reverse('chats:text_chat', args=[self.chat.room_id]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/matches/', r.url)
