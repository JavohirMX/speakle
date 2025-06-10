import json
import uuid
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer

from users.models import Language, UserLanguage
from matches.models import Match
from .models import VideoRoom, CallInvitation, UserPresence, CallSession, RoomMessage
from .consumers import VideoCallConsumer, UserNotificationConsumer

User = get_user_model()


class VideoRoomModelTest(TestCase):
    """Test VideoRoom model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Create test languages
        self.english = Language.objects.create(
            name='English',
            code='en',
            flag_emoji='🇺🇸'
        )
        self.korean = Language.objects.create(
            name='Korean',
            code='ko',
            flag_emoji='🇰🇷'
        )
        
        # Create a match
        self.match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active'
        )
    
    def test_video_room_creation(self):
        """Test VideoRoom creation and basic functionality."""
        room = VideoRoom.objects.create(match=self.match)
        
        self.assertEqual(room.match, self.match)
        self.assertIsNotNone(room.room_id)
        self.assertFalse(room.is_active)
        self.assertIsNotNone(room.created_at)
        self.assertIsNotNone(room.last_activity)
    
    def test_room_id_is_unique(self):
        """Test that room_id is unique."""
        room1 = VideoRoom.objects.create(match=self.match)
        
        # Create another match and room
        user3 = User.objects.create_user(
            username='testuser3',
            email='test3@example.com',
            password='testpass123'
        )
        match2 = Match.objects.create(
            user1=user3,
            user2=self.user2,
            user1_teaches=self.korean,
            user1_learns=self.english,
            status='active'
        )
        room2 = VideoRoom.objects.create(match=match2)
        
        self.assertNotEqual(room1.room_id, room2.room_id)
    
    def test_get_participants(self):
        """Test getting room participants."""
        room = VideoRoom.objects.create(match=self.match)
        participants = room.get_participants()
        
        self.assertEqual(len(participants), 2)
        self.assertIn(self.user1, participants)
        self.assertIn(self.user2, participants)
    
    def test_can_user_access(self):
        """Test user access control."""
        room = VideoRoom.objects.create(match=self.match)
        
        # Users in the match should have access
        self.assertTrue(room.can_user_access(self.user1))
        self.assertTrue(room.can_user_access(self.user2))
        
        # Other users should not have access
        user3 = User.objects.create_user(
            username='testuser3',
            email='test3@example.com',
            password='testpass123'
        )
        self.assertFalse(room.can_user_access(user3))
    
    def test_string_representation(self):
        """Test string representation of VideoRoom."""
        room = VideoRoom.objects.create(match=self.match)
        expected_str = f"Room {room.room_id} for {self.match}"
        self.assertEqual(str(room), expected_str)


class CallInvitationModelTest(TestCase):
    """Test CallInvitation model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Create test languages
        self.english = Language.objects.create(
            name='English',
            code='en',
            flag_emoji='🇺🇸'
        )
        self.korean = Language.objects.create(
            name='Korean',
            code='ko',
            flag_emoji='🇰🇷'
        )
        
        # Create a match and room
        self.match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active'
        )
        self.room = VideoRoom.objects.create(match=self.match)
    
    def test_call_invitation_creation(self):
        """Test CallInvitation creation."""
        invitation = CallInvitation.objects.create(
            room=self.room,
            caller=self.user1,
            receiver=self.user2,
            message="Want to practice Korean?"
        )
        
        self.assertEqual(invitation.room, self.room)
        self.assertEqual(invitation.caller, self.user1)
        self.assertEqual(invitation.receiver, self.user2)
        self.assertEqual(invitation.status, 'pending')
        self.assertEqual(invitation.message, "Want to practice Korean?")
        self.assertIsNotNone(invitation.expires_at)
    
    def test_invitation_auto_expiry_setting(self):
        """Test that expires_at is automatically set."""
        before_creation = timezone.now()
        invitation = CallInvitation.objects.create(
            room=self.room,
            caller=self.user1,
            receiver=self.user2
        )
        after_creation = timezone.now()
        
        # Should expire 2 minutes after creation
        expected_min = before_creation + timedelta(minutes=2)
        expected_max = after_creation + timedelta(minutes=2)
        
        self.assertGreaterEqual(invitation.expires_at, expected_min)
        self.assertLessEqual(invitation.expires_at, expected_max)
    
    def test_is_expired(self):
        """Test invitation expiry detection."""
        # Create an invitation with past expiry
        invitation = CallInvitation.objects.create(
            room=self.room,
            caller=self.user1,
            receiver=self.user2
        )
        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save()
        
        self.assertTrue(invitation.is_expired())
        
        # Test non-expired invitation
        invitation.expires_at = timezone.now() + timedelta(minutes=1)
        invitation.save()
        
        self.assertFalse(invitation.is_expired())
    
    def test_can_accept(self):
        """Test invitation acceptance validation."""
        invitation = CallInvitation.objects.create(
            room=self.room,
            caller=self.user1,
            receiver=self.user2
        )
        
        # Fresh invitation should be acceptable
        self.assertTrue(invitation.can_accept())
        
        # Expired invitation should not be acceptable
        invitation.expires_at = timezone.now() - timedelta(minutes=1)
        invitation.save()
        self.assertFalse(invitation.can_accept())
        
        # Accepted invitation should not be acceptable again
        invitation.expires_at = timezone.now() + timedelta(minutes=1)
        invitation.status = 'accepted'
        invitation.save()
        self.assertFalse(invitation.can_accept())
    
    def test_string_representation(self):
        """Test string representation of CallInvitation."""
        invitation = CallInvitation.objects.create(
            room=self.room,
            caller=self.user1,
            receiver=self.user2
        )
        expected_str = f"Call invitation from {self.user1.username} to {self.user2.username}"
        self.assertEqual(str(invitation), expected_str)


class UserPresenceModelTest(TestCase):
    """Test UserPresence model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_presence_creation(self):
        """Test UserPresence creation."""
        presence = UserPresence.objects.create(user=self.user, is_online=True)
        
        self.assertEqual(presence.user, self.user)
        self.assertTrue(presence.is_online)
        self.assertIsNotNone(presence.last_seen)
    
    def test_update_presence_method(self):
        """Test update_presence class method."""
        # Test creating presence
        presence = UserPresence.update_presence(self.user, is_online=True)
        
        self.assertEqual(presence.user, self.user)
        self.assertTrue(presence.is_online)
        
        # Test updating existing presence
        presence = UserPresence.update_presence(self.user, is_online=False)
        
        self.assertFalse(presence.is_online)
        self.assertIsNone(presence.current_room)
    
    def test_string_representation(self):
        """Test string representation of UserPresence."""
        presence = UserPresence.objects.create(user=self.user, is_online=True)
        expected_str = f"{self.user.username} - Online"
        self.assertEqual(str(presence), expected_str)
        
        # Test offline representation
        presence.is_online = False
        presence.save()
        self.assertIn("Last seen", str(presence))


class CallSessionModelTest(TestCase):
    """Test CallSession model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Create test languages
        self.english = Language.objects.create(
            name='English',
            code='en',
            flag_emoji='🇺🇸'
        )
        self.korean = Language.objects.create(
            name='Korean',
            code='ko',
            flag_emoji='🇰🇷'
        )
        
        # Create a match and room
        self.match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active'
        )
        self.room = VideoRoom.objects.create(match=self.match)
    
    def test_call_session_creation(self):
        """Test CallSession creation."""
        session = CallSession.objects.create(
            room=self.room,
            status='active',
            video_enabled=True,
            audio_enabled=True
        )
        session.participants.add(self.user1, self.user2)
        
        self.assertEqual(session.room, self.room)
        self.assertEqual(session.status, 'active')
        self.assertTrue(session.video_enabled)
        self.assertTrue(session.audio_enabled)
        self.assertEqual(session.participants.count(), 2)
    
    def test_calculate_duration(self):
        """Test duration calculation."""
        session = CallSession.objects.create(
            room=self.room,
            status='ended'
        )
        
        # Simulate a 5-minute call
        session.started_at = timezone.now() - timedelta(minutes=5)
        session.ended_at = timezone.now()
        session.calculate_duration()
        
        self.assertIsNotNone(session.duration)
        # Allow some variance for test execution time
        self.assertGreater(session.duration.total_seconds(), 290)  # ~5 minutes
        self.assertLess(session.duration.total_seconds(), 310)
    
    def test_get_duration_display(self):
        """Test human-readable duration display."""
        session = CallSession.objects.create(room=self.room)
        
        # Test various durations
        session.duration = timedelta(seconds=30)
        self.assertEqual(session.get_duration_display(), "30s")
        
        session.duration = timedelta(minutes=5, seconds=30)
        self.assertEqual(session.get_duration_display(), "5m 30s")
        
        session.duration = timedelta(hours=1, minutes=30, seconds=45)
        self.assertEqual(session.get_duration_display(), "1h 30m 45s")
        
        session.duration = None
        self.assertEqual(session.get_duration_display(), "Unknown")
    
    def test_was_successful(self):
        """Test successful call detection."""
        session = CallSession.objects.create(
            room=self.room,
            status='ended',
            end_reason='normal'
        )
        self.assertTrue(session.was_successful())
        
        session.end_reason = 'connection_lost'
        session.save()
        self.assertFalse(session.was_successful())
    
    def test_string_representation(self):
        """Test string representation of CallSession."""
        session = CallSession.objects.create(room=self.room)
        expected_str = f"Call session in {self.room.room_id} at {session.started_at}"
        self.assertEqual(str(session), expected_str)


class RoomMessageModelTest(TestCase):
    """Test RoomMessage model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Create test languages
        self.english = Language.objects.create(
            name='English',
            code='en',
            flag_emoji='🇺🇸'
        )
        self.korean = Language.objects.create(
            name='Korean',
            code='ko',
            flag_emoji='🇰🇷'
        )
        
        # Create a match and room
        self.match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active'
        )
        self.room = VideoRoom.objects.create(match=self.match)
    
    def test_room_message_creation(self):
        """Test RoomMessage creation."""
        message = RoomMessage.objects.create(
            room=self.room,
            sender=self.user1,
            content="Hello, how are you?"
        )
        
        self.assertEqual(message.room, self.room)
        self.assertEqual(message.sender, self.user1)
        self.assertEqual(message.content, "Hello, how are you?")
        self.assertIsNotNone(message.timestamp)
    
    def test_message_ordering(self):
        """Test that messages are ordered by timestamp."""
        message1 = RoomMessage.objects.create(
            room=self.room,
            sender=self.user1,
            content="First message"
        )
        message2 = RoomMessage.objects.create(
            room=self.room,
            sender=self.user2,
            content="Second message"
        )
        
        messages = RoomMessage.objects.filter(room=self.room)
        self.assertEqual(messages.first(), message1)
        self.assertEqual(messages.last(), message2)
    
    def test_string_representation(self):
        """Test string representation of RoomMessage."""
        message = RoomMessage.objects.create(
            room=self.room,
            sender=self.user1,
            content="Test message"
        )
        expected_str = f"Message from {self.user1.username} in {self.room.room_id}"
        self.assertEqual(str(message), expected_str)


class ChatsViewsTest(TestCase):
    """Test chats app views."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Create test languages
        self.english = Language.objects.create(
            name='English',
            code='en',
            flag_emoji='🇺🇸'
        )
        self.korean = Language.objects.create(
            name='Korean',
            code='ko',
            flag_emoji='🇰🇷'
        )
        
        # Create a match
        self.match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active'
        )
    
    def test_create_video_room_view(self):
        """Test video room creation view."""
        self.client.login(username='testuser1', password='testpass123')
        
        response = self.client.get(
            reverse('chats:create_video_room', args=[self.match.id])
        )
        
        # Should redirect to the video room
        self.assertEqual(response.status_code, 302)
        
        # Check that a video room was created
        self.assertTrue(VideoRoom.objects.filter(match=self.match).exists())
    
    def test_create_video_room_unauthorized(self):
        """Test unauthorized access to video room creation."""
        user3 = User.objects.create_user(
            username='testuser3',
            email='test3@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser3', password='testpass123')
        
        response = self.client.get(
            reverse('chats:create_video_room', args=[self.match.id])
        )
        
        # Should redirect with error
        self.assertEqual(response.status_code, 302)
    
    def test_get_video_room_url_api(self):
        """Test getting video room URL via API."""
        self.client.login(username='testuser1', password='testpass123')
        
        response = self.client.get(
            reverse('chats:get_video_room_url', args=[self.match.id])
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('room_url', data)
        self.assertIn('room_id', data)
    
    @patch('chats.views.send_user_notification')
    def test_send_call_invitation_api(self, mock_notification):
        """Test sending call invitation via API."""
        # Set up user presence
        UserPresence.objects.create(user=self.user2, is_online=True)
        
        self.client.login(username='testuser1', password='testpass123')
        
        response = self.client.post(
            reverse('chats:send_call_invitation', args=[self.match.id]),
            {'message': 'Want to practice Korean?'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('invitation_id', data)
        
        # Check that invitation was created
        invitation = CallInvitation.objects.get(id=data['invitation_id'])
        self.assertEqual(invitation.caller, self.user1)
        self.assertEqual(invitation.receiver, self.user2)
        self.assertEqual(invitation.message, 'Want to practice Korean?')
        
        # Check that notification was sent
        mock_notification.assert_called_once()
    
    def test_send_call_invitation_partner_offline(self):
        """Test sending invitation when partner is offline."""
        # Don't create UserPresence or create with is_online=False
        UserPresence.objects.create(user=self.user2, is_online=False)
        
        self.client.login(username='testuser1', password='testpass123')
        
        response = self.client.post(
            reverse('chats:send_call_invitation', args=[self.match.id])
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertIn('not online', data['error'])
    
    @patch('chats.views.send_user_notification')
    def test_respond_to_invitation_accept(self, mock_notification):
        """Test accepting a call invitation."""
        # Create invitation
        room = VideoRoom.objects.create(match=self.match)
        invitation = CallInvitation.objects.create(
            room=room,
            caller=self.user1,
            receiver=self.user2
        )
        
        self.client.login(username='testuser2', password='testpass123')
        
        response = self.client.post(
            reverse('chats:respond_to_invitation', args=[invitation.id]),
            {'response': 'accept'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['action'], 'accepted')
        
        # Check invitation status
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, 'accepted')
        self.assertIsNotNone(invitation.responded_at)
        
        # Check notification was sent
        mock_notification.assert_called_once()
    
    @patch('chats.views.send_user_notification')
    def test_respond_to_invitation_decline(self, mock_notification):
        """Test declining a call invitation."""
        # Create invitation
        room = VideoRoom.objects.create(match=self.match)
        invitation = CallInvitation.objects.create(
            room=room,
            caller=self.user1,
            receiver=self.user2
        )
        
        self.client.login(username='testuser2', password='testpass123')
        
        response = self.client.post(
            reverse('chats:respond_to_invitation', args=[invitation.id]),
            {'response': 'decline'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['action'], 'declined')
        
        # Check invitation status
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, 'declined')
        
        # Check notification was sent
        mock_notification.assert_called_once()
    
    def test_get_pending_invitations(self):
        """Test getting pending invitations."""
        # Create room and invitation
        room = VideoRoom.objects.create(match=self.match)
        invitation = CallInvitation.objects.create(
            room=room,
            caller=self.user1,
            receiver=self.user2,
            message="Let's practice!"
        )
        
        self.client.login(username='testuser2', password='testpass123')
        
        response = self.client.get(reverse('chats:get_pending_invitations'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['invitations']), 1)
        self.assertEqual(data['invitations'][0]['caller'], 'testuser1')
        self.assertEqual(data['invitations'][0]['message'], "Let's practice!")
    
    def test_set_online_status(self):
        """Test setting user online status."""
        self.client.login(username='testuser1', password='testpass123')
        
        response = self.client.post(
            reverse('chats:set_online_status'),
            {'is_online': 'true'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Check presence was updated
        presence = UserPresence.objects.get(user=self.user1)
        self.assertTrue(presence.is_online)
    
    def test_unauthorized_api_access(self):
        """Test that API endpoints require authentication."""
        endpoints = [
            ('chats:get_video_room_url', [self.match.id]),
            ('chats:send_call_invitation', [self.match.id]),
            ('chats:get_pending_invitations', []),
            ('chats:set_online_status', []),
        ]
        
        for endpoint_name, args in endpoints:
            response = self.client.get(reverse(endpoint_name, args=args))
            # Should redirect to login or return 403/401
            self.assertIn(response.status_code, [302, 401, 403])


class WebSocketConsumerTest(TransactionTestCase):
    """Test WebSocket consumers."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Create test languages
        self.english = Language.objects.create(
            name='English',
            code='en',
            flag_emoji='🇺🇸'
        )
        self.korean = Language.objects.create(
            name='Korean',
            code='ko',
            flag_emoji='🇰🇷'
        )
        
        # Create a match and room
        self.match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active'
        )
        self.room = VideoRoom.objects.create(match=self.match)
    
    @database_sync_to_async
    def create_test_data(self):
        """Create test data asynchronously."""
        return self.room
    
    async def test_video_call_consumer_connection_with_auth(self):
        """Test VideoCallConsumer connection with authenticated user."""
        # Mock authenticated user in scope
        scope = {
            'type': 'websocket',
            'path': f'/ws/video/{self.room.room_id}/',
            'query_string': b'',
            'headers': [],
            'user': self.user1,
            'url_route': {
                'kwargs': {'room_id': str(self.room.room_id)}
            }
        }
        
        communicator = WebsocketCommunicator(VideoCallConsumer.as_asgi(), scope)
        connected, subprotocol = await communicator.connect()
        
        self.assertTrue(connected)
        
        # Should receive connection test message
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'connection_test')
        self.assertEqual(response['room_id'], str(self.room.room_id))
        
        await communicator.disconnect()
    
    async def test_video_call_consumer_message_handling(self):
        """Test message handling in VideoCallConsumer."""
        scope = {
            'type': 'websocket',
            'path': f'/ws/video/{self.room.room_id}/',
            'query_string': b'',
            'headers': [],
            'user': self.user1,
            'url_route': {
                'kwargs': {'room_id': str(self.room.room_id)}
            }
        }
        
        communicator = WebsocketCommunicator(VideoCallConsumer.as_asgi(), scope)
        connected, subprotocol = await communicator.connect()
        
        # Skip connection test message
        await communicator.receive_json_from()
        
        # Test chat message
        await communicator.send_json_to({
            'type': 'chat_message',
            'message': 'Hello, how are you?'
        })
        
        # Should receive chat message back
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'chat_message')
        self.assertEqual(response['message'], 'Hello, how are you?')
        self.assertEqual(response['sender'], 'testuser1')
        
        await communicator.disconnect()
    
    async def test_video_call_consumer_webrtc_offer(self):
        """Test WebRTC offer handling."""
        scope = {
            'type': 'websocket',
            'path': f'/ws/video/{self.room.room_id}/',
            'query_string': b'',
            'headers': [],
            'user': self.user1,
            'url_route': {
                'kwargs': {'room_id': str(self.room.room_id)}
            }
        }
        
        communicator = WebsocketCommunicator(VideoCallConsumer.as_asgi(), scope)
        connected, subprotocol = await communicator.connect()
        
        # Skip connection test message
        await communicator.receive_json_from()
        
        # Test WebRTC offer
        offer_data = {
            'type': 'offer',
            'offer': {
                'type': 'offer',
                'sdp': 'test-sdp-data'
            }
        }
        
        await communicator.send_json_to(offer_data)
        
        # Should receive offer back
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'webrtc_offer')
        self.assertEqual(response['sender_username'], 'testuser1')
        self.assertIn('offer', response)
        
        await communicator.disconnect()
    
    async def test_user_notification_consumer(self):
        """Test UserNotificationConsumer."""
        scope = {
            'type': 'websocket',
            'path': f'/ws/notifications/{self.user1.id}/',
            'query_string': b'',
            'headers': [],
            'user': self.user1,
            'url_route': {
                'kwargs': {'user_id': self.user1.id}
            }
        }
        
        communicator = WebsocketCommunicator(UserNotificationConsumer.as_asgi(), scope)
        connected, subprotocol = await communicator.connect()
        
        self.assertTrue(connected)
        
        # Test receiving notification via channel layer
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f'user_notifications_{self.user1.id}',
            {
                'type': 'call_invitation_received',
                'invitation_id': 123,
                'caller_username': 'testuser2',
                'message': 'Want to practice?'
            }
        )
        
        # Should receive the notification
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'call_invitation_received')
        self.assertEqual(response['caller_username'], 'testuser2')
        self.assertEqual(response['message'], 'Want to practice?')
        
        await communicator.disconnect()


class ChatsIntegrationTest(TestCase):
    """Integration tests for chats functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Create test languages
        self.english = Language.objects.create(
            name='English',
            code='en',
            flag_emoji='🇺🇸'
        )
        self.korean = Language.objects.create(
            name='Korean',
            code='ko',
            flag_emoji='🇰🇷'
        )
        
        # Create a match
        self.match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active'
        )
    
    @patch('chats.views.send_user_notification')
    def test_complete_call_flow(self, mock_notification):
        """Test complete call invitation and acceptance flow."""
        # Set users online
        UserPresence.objects.create(user=self.user1, is_online=True)
        UserPresence.objects.create(user=self.user2, is_online=True)
        
        # User1 sends invitation
        self.client.login(username='testuser1', password='testpass123')
        response = self.client.post(
            reverse('chats:send_call_invitation', args=[self.match.id]),
            {'message': 'Want to practice Korean together?'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        invitation_id = data['invitation_id']
        
        # User2 checks pending invitations
        self.client.login(username='testuser2', password='testpass123')
        response = self.client.get(reverse('chats:get_pending_invitations'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['invitations']), 1)
        self.assertEqual(data['invitations'][0]['id'], invitation_id)
        
        # User2 accepts invitation
        response = self.client.post(
            reverse('chats:respond_to_invitation', args=[invitation_id]),
            {'response': 'accept'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['action'], 'accepted')
        self.assertIn('room_url', data)
        
        # Verify invitation status
        invitation = CallInvitation.objects.get(id=invitation_id)
        self.assertEqual(invitation.status, 'accepted')
        self.assertIsNotNone(invitation.responded_at)
        
        # Verify video room exists
        self.assertTrue(VideoRoom.objects.filter(match=self.match).exists())
    
    def test_call_session_lifecycle(self):
        """Test complete call session lifecycle."""
        room = VideoRoom.objects.create(match=self.match)
        
        # Start call session
        session = CallSession.objects.create(
            room=room,
            status='starting'
        )
        session.participants.add(self.user1, self.user2)
        
        # Update to active
        session.status = 'active'
        session.save()
        
        # Add some messages during call
        RoomMessage.objects.create(
            room=room,
            sender=self.user1,
            content="Can you hear me?"
        )
        RoomMessage.objects.create(
            room=room,
            sender=self.user2,
            content="Yes, clearly!"
        )
        
        # End call session
        session.status = 'ended'
        session.end_reason = 'normal'
        session.ended_by = self.user1
        session.ended_at = timezone.now()
        session.calculate_duration()
        session.save()
        
        # Verify session data
        self.assertEqual(session.participants.count(), 2)
        self.assertEqual(session.end_reason, 'normal')
        self.assertIsNotNone(session.duration)
        self.assertTrue(session.was_successful())
        
        # Verify messages were saved
        messages = RoomMessage.objects.filter(room=room)
        self.assertEqual(messages.count(), 2)
        self.assertEqual(messages.first().content, "Can you hear me?")
        self.assertEqual(messages.last().content, "Yes, clearly!")
