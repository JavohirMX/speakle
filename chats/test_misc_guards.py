"""Leftover guard paths: call_history 404, feedback room 404, notifier."""
import json
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

from django.test import TestCase
from django.urls import reverse

from .models import CallSession
from .test_api_views import ChatApiBase
from . import views


class CallHistoryNotFoundTests(ChatApiBase):
    def test_unknown_room_redirects(self):
        r = self.client_for(self.a).get(
            reverse('chats:call_history', args=[uuid.uuid4()]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/matches/', r.url)


class FeedbackRoomNotFoundTests(ChatApiBase):
    def test_valid_session_unknown_room_is_404(self):
        s = CallSession.objects.create(room=self.video, status='ended')
        s.participants.add(self.a)
        r = self.client_for(self.a).post(
            reverse('chats:submit_feedback'),
            json.dumps({'session_id': s.id, 'rating': 4,
                        'room_id': str(uuid.uuid4())}),
            content_type='application/json')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['error'], 'Room not found')


class SendUserNotificationTests(TestCase):
    def test_sends_to_user_group_with_type_and_data(self):
        layer = MagicMock()
        layer.group_send = AsyncMock()
        with patch('chats.views.get_channel_layer', return_value=layer):
            views.send_user_notification(7, 'ping', {'x': 1})
        layer.group_send.assert_called_once()
        group, payload = layer.group_send.call_args.args
        self.assertEqual(group, 'user_notifications_7')
        self.assertEqual(payload, {'type': 'ping', 'x': 1})
