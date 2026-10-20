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
from matches.models import Match, MatchRequest
from .models import VideoRoom, CallInvitation, UserPresence, CallSession, RoomMessage
from .consumers import VideoCallConsumer, UserNotificationConsumer

User = get_user_model()



def _make_communicator(consumer, scope):
    """Build a WebsocketCommunicator and inject the user / url_route into its scope.

    WebsocketCommunicator takes (application, path); extra scope keys such as
    'user' and 'url_route' must be set on the communicator's scope afterwards.
    """
    communicator = WebsocketCommunicator(consumer.as_asgi(), scope['path'])
    for key in ('user', 'url_route'):
        if key in scope:
            communicator.scope[key] = scope[key]
    return communicator

async def _receive_type(communicator, wanted, limit=6):
    """Skip join/handshake frames (user_joined, notification_connected...) until `wanted` arrives."""
    for _ in range(limit):
        msg = await communicator.receive_json_from()
        if msg.get('type') == wanted:
            return msg
    raise AssertionError('never received %s' % wanted)


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
        self.assertEqual(len(data['invitations']), 1)
        self.assertEqual(data['invitations'][0]['caller'], 'testuser1')
        self.assertEqual(data['invitations'][0]['message'], "Let's practice!")
    
    def test_get_user_status_automatic(self):
        """Test getting user online status with automatic detection."""
        self.client.login(username='testuser1', password='testpass123')
        
        response = self.client.get(reverse('chats:get_user_status'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('is_online', data)
        self.assertIn('message', data)
        self.assertIn('automatic', data['message'])
        
        # Check presence was updated automatically
        presence = UserPresence.objects.get(user=self.user1)
        self.assertTrue(presence.is_online)  # Should be online since they just made a request
    
    def test_heartbeat_endpoint(self):
        """Test heartbeat endpoint for maintaining presence."""
        self.client.login(username='testuser1', password='testpass123')
        
        response = self.client.post(reverse('chats:heartbeat'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('is_online', data)
        self.assertIn('timestamp', data)
        
        # Check presence was updated
        presence = UserPresence.objects.get(user=self.user1)
        self.assertTrue(presence.is_online)
    
    def test_unauthorized_api_access(self):
        """Test that API endpoints require authentication."""
        endpoints = [
            ('chats:get_video_room_url', [self.match.id]),
            ('chats:send_call_invitation', [self.match.id]),
            ('chats:get_pending_invitations', []),
            ('chats:get_user_status', []),
            ('chats:heartbeat', []),
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
        
        communicator = _make_communicator(VideoCallConsumer, scope)
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
        
        communicator = _make_communicator(VideoCallConsumer, scope)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        scope2 = dict(scope, user=self.user2)
        other = _make_communicator(VideoCallConsumer, scope2)
        connected2, _ = await other.connect()
        self.assertTrue(connected2)

        await communicator.send_json_to({
            'type': 'offer',
            'offer': {'type': 'offer', 'sdp': 'test-sdp-data'}
        })

        # The other participant receives the offer...
        response = await _receive_type(other, 'offer')
        self.assertEqual(response['sender_username'], 'testuser1')
        self.assertIn('offer', response)

        # ...and the sender never gets its own offer echoed back.
        while not await communicator.receive_nothing():
            msg = await communicator.receive_json_from()
            self.assertNotEqual(msg.get('type'), 'offer')

        await communicator.disconnect()
        await other.disconnect()

    async def test_block_during_call_stops_offers(self):
        from users.models import UserBlock
        scope = {'type': 'websocket', 'path': f'/ws/video/{self.room.room_id}/', 'query_string': b'',
                 'headers': [], 'user': self.user1,
                 'url_route': {'kwargs': {'room_id': str(self.room.room_id)}}}
        mine = _make_communicator(VideoCallConsumer, scope)
        self.assertTrue((await mine.connect())[0])
        other = _make_communicator(VideoCallConsumer, dict(scope, user=self.user2))
        self.assertTrue((await other.connect())[0])
        await database_sync_to_async(UserBlock.objects.create)(blocker=self.user2, blocked=self.user1)

        await mine.send_json_to({'type': 'offer', 'offer': {'type': 'offer', 'sdp': 'x'}})
        err = await _receive_type(mine, 'error')
        self.assertIn('no longer available', err['message'])
        while not await other.receive_nothing():
            self.assertNotEqual((await other.receive_json_from()).get('type'), 'offer')
        await other.disconnect()

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
        
        communicator = _make_communicator(UserNotificationConsumer, scope)
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
                'caller_id': self.user2.id,
                'match_id': 1,
                'expires_at': '2030-01-01T00:00:00Z',
                'message': 'Want to practice?'
            }
        )
        
        # Should receive the notification
        response = await _receive_type(communicator, 'call_invitation_received')
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


class ChatListPageTests(TestCase):
    def test_chat_list_shows_partner_languages_and_unread(self):
        from matches.models import Match
        from users.models import Language
        from .models import ChatRoom, ChatMessage
        U = get_user_model()
        a = U.objects.create_user('cla', 'cla@x.com', 'pw12345!')
        b = U.objects.create_user('clb', 'clb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=a, user2=b, user1_teaches=en, user1_learns=ko, status='active')
        room = ChatRoom.objects.create(match=m)
        ChatMessage.objects.create(room=room, sender=b, content='annyeong')
        c = Client(); c.force_login(a)
        r = c.get(reverse('chats:chat_list'))
        self.assertContains(r, 'you teach English')
        self.assertContains(r, 'you learn Korean')
        self.assertContains(r, 'annyeong')
        self.assertContains(r, reverse('chats:text_chat', args=[room.room_id]))
        self.assertEqual(r.context['total_unread'], 1)


class TextChatApiTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # the send throttle lives in the cache
        from matches.models import Match
        from .models import ChatRoom
        U = get_user_model()
        self.a = U.objects.create_user('tca', 'tca@x.com', 'pw12345!')
        self.b = U.objects.create_user('tcb', 'tcb@x.com', 'pw12345!')
        self.c = U.objects.create_user('tcc', 'tcc@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en, user1_learns=ko, status='active')
        self.room = ChatRoom.objects.create(match=m)
        self.client = Client()
        self.client.force_login(self.a)

    def _send(self, content, **extra):
        with patch('chats.views.send_user_notification'):
            return self.client.post(reverse('chats:send_chat_message', args=[self.room.room_id]),
                                    {'content': content, **extra})

    def test_flooding_is_limited_per_user(self):
        from django.core.cache import cache
        from .models import ChatMessage
        from users.throttle import CHAT_LIMIT
        cache.clear()
        for i in range(CHAT_LIMIT):
            self.assertEqual(self._send('m%d' % i).status_code, 200)
        self.assertEqual(self._send('one too many').status_code, 429)
        self.assertEqual(ChatMessage.objects.filter(content='one too many').count(), 0)
        cache.clear()

    def test_send_message_saves_it(self):
        r = self._send('  hello  ')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.room.messages.get().content, 'hello')

    def test_empty_and_too_long_messages_rejected(self):
        self.assertEqual(self._send('   ').status_code, 400)
        self.assertEqual(self._send('x' * 1001).status_code, 400)
        self.assertEqual(self.room.messages.count(), 0)

    def test_outsider_cannot_send_or_read(self):
        self.client.force_login(self.c)
        self.assertEqual(self._send('hi').status_code, 403)
        r = self.client.get(reverse('chats:get_chat_messages', args=[self.room.room_id]))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.room.messages.count(), 0)

    def test_reply_to_message_from_other_room_rejected(self):
        r = self._send('hi', reply_to=99999)
        self.assertEqual(r.status_code, 400)

    def test_login_required(self):
        r = Client().post(reverse('chats:send_chat_message', args=[self.room.room_id]), {'content': 'x'})
        self.assertEqual(r.status_code, 302)

    def test_edit_only_own_message(self):
        from .models import ChatMessage
        mine = ChatMessage.objects.create(room=self.room, sender=self.a, content='old')
        theirs = ChatMessage.objects.create(room=self.room, sender=self.b, content='theirs')
        with patch('chats.views.send_user_notification'):
            ok = self.client.post(reverse('chats:edit_chat_message', args=[mine.id]), {'content': 'new'})
            no = self.client.post(reverse('chats:edit_chat_message', args=[theirs.id]), {'content': 'hack'})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(no.status_code, 404)
        mine.refresh_from_db(); theirs.refresh_from_db()
        self.assertEqual(mine.content, 'new')
        self.assertEqual(theirs.content, 'theirs')

    def test_text_chat_page_renders_for_participant_only(self):
        url = reverse('chats:text_chat', args=[self.room.room_id])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.c)
        self.assertNotEqual(self.client.get(url).status_code, 200)

    def test_mark_read_only_clears_partner_messages(self):
        from .models import ChatMessage
        ChatMessage.objects.create(room=self.room, sender=self.b, content='1')
        ChatMessage.objects.create(room=self.room, sender=self.b, content='2')
        ChatMessage.objects.create(room=self.room, sender=self.a, content='mine')
        url = reverse('chats:get_unread_count', args=[self.room.room_id])
        self.assertEqual(self.client.get(url).json()['unread_count'], 2)
        r = self.client.post(reverse('chats:mark_messages_read', args=[self.room.room_id]))
        self.assertEqual(r.json()['marked_read'], 2)
        self.assertEqual(self.client.get(url).json()['unread_count'], 0)
        self.assertFalse(self.room.messages.get(content='mine').is_read)


class CallHistoryPageTests(TestCase):
    def setUp(self):
        from matches.models import Match
        U = get_user_model()
        self.a = U.objects.create_user('cha', 'cha@x.com', 'pw12345!')
        self.b = U.objects.create_user('chb', 'chb@x.com', 'pw12345!')
        self.o = U.objects.create_user('cho', 'cho@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en, user1_learns=ko, status='active')
        self.room = VideoRoom.objects.create(match=m)
        self.url = reverse('chats:call_history', args=[self.room.room_id])
        self.client.force_login(self.a)

    def _session(self, minutes):
        s = CallSession.objects.create(room=self.room, status='ended', duration=timedelta(minutes=minutes))
        s.participants.add(self.a, self.b)
        return s

    def test_empty_state_has_no_invented_numbers(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'No calls yet')
        self.assertIsNone(r.context['total_time'])
        self.assertIsNone(r.context['average_time'])

    def test_totals_and_average_are_computed(self):
        self._session(10); self._session(20)
        r = self.client.get(self.url)
        self.assertEqual(r.context['total_time'], '30m')
        self.assertEqual(r.context['average_time'], '15m')

    def test_outsider_is_redirected(self):
        self.client.force_login(self.o)
        self.assertEqual(self.client.get(self.url).status_code, 302)


class CallSummaryPageTests(TestCase):
    def setUp(self):
        from matches.models import Match
        U = get_user_model()
        self.a = U.objects.create_user('csa', 'csa@x.com', 'pw12345!')
        self.b = U.objects.create_user('csb', 'csb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en, user1_learns=ko, status='active')
        self.room = VideoRoom.objects.create(match=m)
        self.s = CallSession.objects.create(room=self.room, status='ended', duration=timedelta(minutes=12), end_notes='Good chat')
        self.s.participants.add(self.a, self.b)
        self.url = reverse('chats:call_summary', args=[self.room.room_id, self.s.id])

    def test_summary_renders_without_fake_progress(self):
        self.client.force_login(self.a)
        r = self.client.get(self.url)
        self.assertContains(r, 'lasted 12m')
        self.assertContains(r, 'Good chat')
        self.assertNotContains(r, '% Progress')
        self.assertNotContains(r, 'Korean Progress')

    def test_partner_rating_is_not_shown_to_other_user(self):
        self.client.force_login(self.b)
        r = self.client.post(reverse('chats:submit_feedback'),
                             data=json.dumps({'session_id': self.s.id, 'rating': 2, 'room_id': str(self.room.room_id)}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.client.force_login(self.a)
        r = self.client.get(self.url)
        self.assertNotContains(r, 'rated this call')
        self.assertNotContains(r, '2/5')
        self.assertContains(r, 'Good chat')


class TextChatConsumerReplyTests(TransactionTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # the send throttle lives in the cache
        from matches.models import Match
        from .models import ChatRoom
        self.a = User.objects.create_user('tcc_a', 'tcca@x.com', 'pw12345!')
        self.b = User.objects.create_user('tcc_b', 'tccb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en, user1_learns=ko, status='active')
        self.room = ChatRoom.objects.create(match=m)

    async def _connect(self, user):
        from .consumers import TextChatConsumer
        rid = str(self.room.room_id)
        scope = {'type': 'websocket', 'path': f'/ws/text-chat/{rid}/', 'query_string': b'', 'headers': [],
                 'user': user, 'url_route': {'kwargs': {'room_id': rid}}}
        c = _make_communicator(TextChatConsumer, scope)
        ok, _ = await c.connect()
        self.assertTrue(ok)
        return c

    async def _next(self, c, wanted, limit=8):
        for _ in range(limit):
            msg = await c.receive_json_from()
            if msg.get('type') == wanted:
                return msg
        self.fail(f'no {wanted} frame')

    async def test_reply_broadcast_carries_quoted_message(self):
        from .models import ChatMessage
        original = await database_sync_to_async(ChatMessage.objects.create)(room=self.room, sender=self.a, content='first')
        ca = await self._connect(self.a)
        cb = await self._connect(self.b)
        await cb.send_json_to({'type': 'send_message', 'message': 'second', 'reply_to': original.id})
        msg = await self._next(ca, 'new_message')
        self.assertEqual(msg['content'], 'second')
        self.assertEqual(msg['reply_to']['id'], original.id)
        self.assertEqual(msg['reply_to']['content'], 'first')
        self.assertEqual(msg['reply_to']['sender_username'], 'tcc_a')
        await ca.disconnect(); await cb.disconnect()

    async def test_plain_message_has_no_reply(self):
        ca = await self._connect(self.a)
        await ca.send_json_to({'type': 'send_message', 'message': 'hello'})
        msg = await self._next(ca, 'new_message')
        self.assertIsNone(msg['reply_to'])
        await ca.disconnect()

    async def test_flooding_gets_error_frame_and_is_not_saved(self):
        from .models import ChatMessage
        from users.throttle import CHAT_LIMIT
        ca = await self._connect(self.a)
        for i in range(CHAT_LIMIT):
            await ca.send_json_to({'type': 'send_message', 'message': 'm%d' % i})
            await self._next(ca, 'new_message')
        await ca.send_json_to({'type': 'send_message', 'message': 'too many'})
        err = await self._next(ca, 'error')
        self.assertIn('too fast', err['message'])
        saved = await database_sync_to_async(ChatMessage.objects.filter(content='too many').count)()
        self.assertEqual(saved, 0)
        await ca.disconnect()


class OutsiderAccessSweepTests(TestCase):
    """A signed-in user who is not in the match must get nothing from any room-scoped URL."""

    def setUp(self):
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.a = User.objects.create_user('sw_a', 'sw_a@x.com', 'pw12345!')
        self.b = User.objects.create_user('sw_b', 'sw_b@x.com', 'pw12345!')
        self.out = User.objects.create_user('sw_out', 'sw_out@x.com', 'pw12345!')
        for u in (self.a, self.b, self.out):
            UserLanguage.objects.create(user=u, language=en, language_type='native', proficiency='native')
            UserLanguage.objects.create(user=u, language=ko, language_type='learning', proficiency='beginner')
        self.match = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en, user1_learns=ko, status='active')
        self.room = VideoRoom.objects.create(match=self.match)
        self.client = Client()
        self.client.force_login(self.out)

    def test_outsider_gets_no_room_data(self):
        urls = [
            reverse('chats:video_room', args=[self.room.room_id]),
            reverse('chats:room_status', args=[self.room.room_id]),
            reverse('chats:get_recent_messages', args=[self.room.room_id]),
            reverse('chats:get_call_statistics', args=[self.room.room_id]),
            reverse('chats:call_history', args=[self.room.room_id]),
            reverse('chats:get_video_room_url', args=[self.match.id]),
            reverse('chats:check_partner_availability', args=[self.match.id]),
        ]
        for url in urls:
            r = self.client.get(url)
            body = r.content.decode()
            self.assertNotIn('sw_a@x.com', body, url)
            self.assertNotEqual(r.status_code, 200, f'{url} returned 200 to an outsider')

    def test_outsider_cannot_create_rooms_or_invites(self):
        for url in (reverse('chats:create_video_room', args=[self.match.id]),
                    reverse('chats:send_call_invitation', args=[self.match.id]),
                    reverse('chats:create_chat_room', args=[self.match.id])):
            before = (VideoRoom.objects.count(), CallInvitation.objects.count())
            r = self.client.post(url)
            self.assertNotEqual(r.status_code, 200, url)
            self.assertEqual(before, (VideoRoom.objects.count(), CallInvitation.objects.count()), url)


class BlockEndsRoomAccessTests(TestCase):
    """After one user blocks the other, the blocked user must not keep chatting or calling."""

    def setUp(self):
        from django.core.cache import cache
        from users.models import UserBlock
        from .models import ChatRoom
        cache.clear()
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.a = User.objects.create_user('bl_a', 'bl_a@x.com', 'pw12345!')
        self.b = User.objects.create_user('bl_b', 'bl_b@x.com', 'pw12345!')
        self.match = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en, user1_learns=ko, status='active')
        self.chat = ChatRoom.objects.create(match=self.match)
        self.video = VideoRoom.objects.create(match=self.match)
        self.UserBlock = UserBlock

    def _send(self, user):
        c = Client(); c.force_login(user)
        with patch('chats.views.send_user_notification'):
            return c.post(reverse('chats:send_chat_message', args=[self.chat.room_id]), {'content': 'hi'})

    def test_access_before_block(self):
        self.assertEqual(self._send(self.b).status_code, 200)

    def test_blocked_user_cannot_send_or_open_rooms(self):
        self.UserBlock.objects.create(blocker=self.a, blocked=self.b)
        self.assertEqual(self._send(self.b).status_code, 403)
        c = Client(); c.force_login(self.b)
        self.assertNotEqual(c.get(reverse('chats:video_room', args=[self.video.room_id])).status_code, 200)
        self.assertNotEqual(c.get(reverse('chats:text_chat', args=[self.chat.room_id])).status_code, 200)
        self.assertEqual(c.get(reverse('chats:get_video_room_url', args=[self.match.id])).status_code, 403)

    def test_blocker_is_also_cut_off(self):
        self.UserBlock.objects.create(blocker=self.a, blocked=self.b)
        self.assertEqual(self._send(self.a).status_code, 403)


class CleanupCommandTests(TestCase):
    def setUp(self):
        from io import StringIO
        self.out = StringIO()
        self.u1 = User.objects.create_user('cc1', 'cc1@x.com', 'pw12345!')
        self.u2 = User.objects.create_user('cc2', 'cc2@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.match = Match.objects.create(
            user1=self.u1, user2=self.u2, user1_teaches=en, user1_learns=ko, status='active'
        )
        self.room = VideoRoom.objects.create(match=self.match)

    def _invite(self, status, created_days_ago=0, expires_in_minutes=10):
        inv = CallInvitation.objects.create(
            room=self.room, caller=self.u1, receiver=self.u2, status=status,
            expires_at=timezone.now() + timedelta(minutes=expires_in_minutes),
        )
        CallInvitation.objects.filter(pk=inv.pk).update(
            created_at=timezone.now() - timedelta(days=created_days_ago)
        )
        return inv

    def test_invitations_cleanup_marks_expired_pending_and_deletes_old_finished(self):
        from django.core.management import call_command
        expired_pending = self._invite('pending', expires_in_minutes=-5)
        live_pending = self._invite('pending', expires_in_minutes=10)
        old_declined = self._invite('declined', created_days_ago=30)
        recent_declined = self._invite('declined', created_days_ago=1)

        call_command('cleanup_expired_invitations', stdout=self.out)

        expired_pending.refresh_from_db()
        live_pending.refresh_from_db()
        self.assertEqual(expired_pending.status, 'expired')
        self.assertEqual(live_pending.status, 'pending')
        self.assertFalse(CallInvitation.objects.filter(pk=old_declined.pk).exists())
        self.assertTrue(CallInvitation.objects.filter(pk=recent_declined.pk).exists())

    def test_invitations_cleanup_dry_run_changes_nothing(self):
        from django.core.management import call_command
        expired_pending = self._invite('pending', expires_in_minutes=-5)
        old_declined = self._invite('declined', created_days_ago=30)

        call_command('cleanup_expired_invitations', '--dry-run', stdout=self.out)

        expired_pending.refresh_from_db()
        self.assertEqual(expired_pending.status, 'pending')
        self.assertTrue(CallInvitation.objects.filter(pk=old_declined.pk).exists())
        self.assertIn('DRY RUN', self.out.getvalue())

    def test_offline_cleanup_only_touches_stale_online_users(self):
        from django.core.management import call_command
        stale = UserPresence.objects.create(user=self.u1, is_online=True)
        fresh = UserPresence.objects.create(user=self.u2, is_online=True)
        UserPresence.objects.filter(pk=stale.pk).update(last_seen=timezone.now() - timedelta(minutes=30))

        call_command('cleanup_offline_users', stdout=self.out)

        stale.refresh_from_db()
        fresh.refresh_from_db()
        self.assertFalse(stale.is_online)
        self.assertTrue(fresh.is_online)

    def test_offline_cleanup_dry_run_changes_nothing(self):
        from django.core.management import call_command
        stale = UserPresence.objects.create(user=self.u1, is_online=True)
        UserPresence.objects.filter(pk=stale.pk).update(last_seen=timezone.now() - timedelta(minutes=30))

        call_command('cleanup_offline_users', '--dry-run', stdout=self.out)

        stale.refresh_from_db()
        self.assertTrue(stale.is_online)


from .models import ChatRoom, ChatMessage


class ListQueryCountTests(TestCase):
    """List pages must not issue queries per row."""

    def _setup(self, partners):
        from django.contrib.auth import get_user_model
        from users.models import Language
        U = get_user_model()
        me = U.objects.filter(username='qme').first() or U.objects.create_user('qme', 'qme@x.com', 'pw12345!')
        en, _ = Language.objects.get_or_create(name='English', defaults={'code': 'en'})
        ko, _ = Language.objects.get_or_create(name='Korean', defaults={'code': 'ko'})
        rooms = []
        for i in range(partners):
            other = U.objects.create_user(f'qp{partners}_{i}', f'qp{partners}_{i}@x.com', 'pw12345!')
            m = Match.objects.create(user1=me, user2=other, user1_teaches=en, user1_learns=ko, status='active')
            room = ChatRoom.objects.create(match=m)
            ChatMessage.objects.create(room=room, sender=other, content=f'first {i}')
            ChatMessage.objects.create(room=room, sender=other, content=f'latest {i}')
            MatchRequest.objects.create(sender=other, receiver=me, sender_teaches=ko, sender_learns=en)
            rooms.append(room)
        self.client.force_login(me)
        return me, rooms

    def _count(self, url):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as q:
            self.assertEqual(self.client.get(url).status_code, 200)
        return len(q)

    def test_list_pages_use_constant_queries(self):
        from django.urls import reverse
        self._setup(2)
        urls = [reverse('chats:chat_list'), reverse('matches:my_matches'), reverse('matches:requests')]
        for u in urls:
            self.client.get(u)  # warm one-time caches
        small = [self._count(u) for u in urls]
        self._setup(8)
        big = [self._count(u) for u in urls]
        self.assertEqual(small, big)

    def test_chat_list_shows_unread_and_latest_message(self):
        from django.urls import reverse
        me, rooms = self._setup(1)
        r = self.client.get(reverse('chats:chat_list'))
        self.assertContains(r, 'latest 0')
        self.assertNotContains(r, 'first 0')
        self.assertEqual(r.context['total_unread'], 2)


class VideoRoomAssetsTests(TestCase):
    def test_video_room_uses_compiled_css_not_a_cdn(self):
        a = User.objects.create_user('va', 'va@example.com', 'pw12345!x')
        b = User.objects.create_user('vb', 'vb@example.com', 'pw12345!x')
        en, ko = Language.objects.create(name='English', code='en'), Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=a, user2=b, user1_teaches=en, user1_learns=ko, status='active')
        room = VideoRoom.objects.create(match=m)
        self.client.force_login(a)
        r = self.client.get(reverse('chats:video_room', args=[room.room_id]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertNotIn('cdn.tailwindcss.com', html)
        self.assertRegex(html, r'/static/css/tailwind\.css\?v=[0-9a-f]{10}')
