import json
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import Q
from django.db import models

class VideoCallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'video_call_{self.room_id}'
        self.user = self.scope['user']
        
        print(f"WebSocket connection attempt for room: {self.room_id}")
        print(f"User: {self.user}")
        print(f"User authenticated: {self.user.is_authenticated}")
        
        # Accept connection first
        await self.accept()
        print(f"WebSocket connection accepted")
        
        # Send connection test message
        await self.send(text_data=json.dumps({
            'type': 'connection_test',
            'message': f'WebSocket connected successfully to room {self.room_id}!',
            'room_id': self.room_id,
            'user_id': self.user.id if self.user.is_authenticated else None
        }))
        
        # Check authentication
        if not self.user.is_authenticated:
            print("User not authenticated")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Authentication required'
            }))
            await self.close()
            return
        
        # Verify user has access to this room
        has_access = await self.check_room_access()
        print(f"User has room access: {has_access}")
        if not has_access:
            print("User doesn't have room access")
            await self.send(text_data=json.dumps({
                'type': 'error', 
                'message': 'Room access denied'
            }))
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        print(f"User {self.user.username} joined room group")
        
        # Notify room that user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_id': self.user.id,
                'username': self.user.username,
                'room_id': self.room_id
            }
        )

    async def disconnect(self, close_code):
        print(f"WebSocket disconnected with code: {close_code}")
        
        # Notify room that user left (before leaving group)
        if hasattr(self, 'user') and hasattr(self, 'room_group_name') and self.user.is_authenticated:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'room_id': self.room_id
                }
            )
        
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            print(f"Received message type: {message_type} from user: {self.user.username}")
            
            if message_type == 'offer':
                await self.handle_offer(data)
            elif message_type == 'answer':
                await self.handle_answer(data)
            elif message_type == 'ice_candidate':
                await self.handle_ice_candidate(data)
            elif message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'call_start':
                await self.handle_call_start(data)
            elif message_type == 'call_end':
                await self.handle_call_end(data)
            elif message_type == 'peer_ready':
                await self.handle_peer_ready(data)
            elif message_type == 'video_status':
                await self.handle_video_status(data)
            elif message_type == 'audio_status':
                await self.handle_audio_status(data)
            elif message_type == 'test':
                await self.send(text_data=json.dumps({
                    'type': 'test_response',
                    'message': 'Test message received successfully!',
                    'echo': data
                }))
            else:
                print(f"Unknown message type: {message_type}")
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))
                
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON data'
            }))
        except Exception as e:
            print(f"Error in receive: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Server error: {str(e)}'
            }))

    async def handle_offer(self, data):
        """Handle WebRTC offer"""
        offer = data.get('offer')
        if not offer:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'No offer data provided'
            }))
            return
            
        print(f"Broadcasting offer from {self.user.username}")
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_offer',
                'offer': offer,
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'room_id': self.room_id
            }
        )

    async def handle_answer(self, data):
        """Handle WebRTC answer"""
        answer = data.get('answer')
        if not answer:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'No answer data provided'
            }))
            return
            
        print(f"Broadcasting answer from {self.user.username}")
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_answer',
                'answer': answer,
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'room_id': self.room_id
            }
        )

    async def handle_ice_candidate(self, data):
        """Handle ICE candidate"""
        candidate = data.get('candidate')
        if not candidate:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'No ICE candidate data provided'
            }))
            return
            
        print(f"Broadcasting ICE candidate from {self.user.username}")
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_ice_candidate',
                'candidate': candidate,
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'room_id': self.room_id
            }
        )

    async def handle_peer_ready(self, data):
        """Handle peer ready notification"""
        print(f"Peer ready notification from {self.user.username}")
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'peer_ready',
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'room_id': self.room_id
            }
        )

    async def handle_video_status(self, data):
        """Handle video status change"""
        video_enabled = data.get('video_enabled', True)
        print(f"Video status change from {self.user.username}: {video_enabled}")
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'video_status_change',
                'video_enabled': video_enabled,
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'room_id': self.room_id
            }
        )

    async def handle_audio_status(self, data):
        """Handle audio status change"""
        audio_enabled = data.get('audio_enabled', True)
        print(f"Audio status change from {self.user.username}: {audio_enabled}")
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'audio_status_change',
                'audio_enabled': audio_enabled,
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'room_id': self.room_id
            }
        )

    async def handle_chat_message(self, data):
        """Handle text chat message during video call"""
        message_content = data.get('message', '').strip()
        if not message_content:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Empty message content'
            }))
            return
            
        print(f"Chat message from {self.user.username}: {message_content}")
        
        # Save message to database
        await self.save_chat_message(message_content)
        
        # Get current timestamp
        from django.utils import timezone
        current_time = timezone.now()
        
        # Broadcast to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_content,
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'timestamp': str(current_time),
                'room_id': self.room_id
            }
        )

    async def handle_call_start(self, data):
        """Handle call session start"""
        print(f"Call start from {self.user.username}")
        await self.create_call_session(data)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_started',
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'video_enabled': data.get('video_enabled', True),
                'audio_enabled': data.get('audio_enabled', True),
                'room_id': self.room_id
            }
        )

    async def handle_call_end(self, data):
        """Handle call session end"""
        print(f"Call end from {self.user.username}")
        await self.end_call_session()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_ended',
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'room_id': self.room_id
            }
        )

    # Group message handlers (events sent TO clients)
    async def user_joined(self, event):
        """Send user joined notification to client"""
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_id': event['user_id'],
            'username': event['username'],
            'room_id': event.get('room_id', self.room_id)
        }))

    async def user_left(self, event):
        """Send user left notification to client"""
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user_id': event['user_id'],
            'username': event['username'],
            'room_id': event.get('room_id', self.room_id)
        }))

    async def webrtc_offer(self, event):
        """Forward WebRTC offer to other users (not sender)"""
        if hasattr(self, 'user') and event['sender_id'] != self.user.id:
            print(f"Forwarding offer to {self.user.username}")
            await self.send(text_data=json.dumps({
                'type': 'offer',
                'offer': event['offer'],
                'sender_id': event['sender_id'],
                'sender_username': event['sender_username'],
                'room_id': event.get('room_id', self.room_id)
            }))

    async def webrtc_answer(self, event):
        """Forward WebRTC answer to other users (not sender)"""
        if hasattr(self, 'user') and event['sender_id'] != self.user.id:
            print(f"Forwarding answer to {self.user.username}")
            await self.send(text_data=json.dumps({
                'type': 'answer',
                'answer': event['answer'],
                'sender_id': event['sender_id'],
                'sender_username': event['sender_username'],
                'room_id': event.get('room_id', self.room_id)
            }))

    async def webrtc_ice_candidate(self, event):
        """Forward ICE candidate to other users (not sender)"""
        if hasattr(self, 'user') and event['sender_id'] != self.user.id:
            print(f"Forwarding ICE candidate to {self.user.username}")
            await self.send(text_data=json.dumps({
                'type': 'ice_candidate',
                'candidate': event['candidate'],
                'sender_id': event['sender_id'],
                'sender_username': event['sender_username'],
                'room_id': event.get('room_id', self.room_id)
            }))

    async def peer_ready(self, event):
        """Forward peer ready notification"""
        if hasattr(self, 'user') and event['sender_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'peer_ready',
                'sender_id': event['sender_id'],
                'sender_username': event['sender_username'],
                'room_id': event.get('room_id', self.room_id)
            }))

    async def video_status_change(self, event):
        """Forward video status change"""
        if hasattr(self, 'user') and event['sender_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'video_status_change',
                'video_enabled': event['video_enabled'],
                'sender_id': event['sender_id'],
                'sender_username': event['sender_username'],
                'room_id': event.get('room_id', self.room_id)
            }))

    async def audio_status_change(self, event):
        """Forward audio status change"""
        if hasattr(self, 'user') and event['sender_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'audio_status_change',
                'audio_enabled': event['audio_enabled'],
                'sender_id': event['sender_id'],
                'sender_username': event['sender_username'],
                'room_id': event.get('room_id', self.room_id)
            }))

    async def chat_message(self, event):
        """Forward chat message to all users"""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'timestamp': event['timestamp'],
            'room_id': event.get('room_id', self.room_id)
        }))

    async def call_started(self, event):
        """Forward call started notification"""
        await self.send(text_data=json.dumps({
            'type': 'call_started',
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'video_enabled': event.get('video_enabled', True),
            'audio_enabled': event.get('audio_enabled', True),
            'room_id': event.get('room_id', self.room_id)
        }))

    async def call_ended(self, event):
        """Forward call ended notification"""
        await self.send(text_data=json.dumps({
            'type': 'call_ended',
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'room_id': event.get('room_id', self.room_id)
        }))

    # Database operations
    @database_sync_to_async
    def check_room_access(self):
        """Check if user has access to the video room"""
        try:
            from .models import VideoRoom
            from matches.models import Match
            
            # Try to get the room first
            try:
                room = VideoRoom.objects.get(room_id=self.room_id)
                return room.can_user_access(self.user)
            except VideoRoom.DoesNotExist:
                # If room doesn't exist, check if user has a match that could create this room
                # This is a more permissive approach for development
                print(f"Room {self.room_id} doesn't exist, checking match access")
                
                # Get all matches where user is involved
                user_matches = Match.objects.filter(
                    Q(user1=self.user) | Q(user2=self.user),
                    status='active'
                )
                
                # For development, allow access if user has any active matches
                return user_matches.exists()
                
        except Exception as e:
            print(f"Error checking room access: {e}")
            # For development, be permissive
            return True

    @database_sync_to_async
    def save_chat_message(self, content):
        """Save chat message to database"""
        try:
            from .models import VideoRoom, RoomMessage
            
            # Get or create room
            room, created = VideoRoom.objects.get_or_create(
                room_id=self.room_id,
                defaults={'created_by': self.user}
            )
            
            if created:
                print(f"Created new room: {self.room_id}")
            
            # Create message
            message = RoomMessage.objects.create(
                room=room,
                sender=self.user,
                content=content
            )
            print(f"Saved chat message: {message.id}")
            
        except Exception as e:
            print(f"Error saving chat message: {e}")

    @database_sync_to_async
    def create_call_session(self, data):
        """Create a new call session"""
        try:
            from .models import VideoRoom, CallSession
            
            # Get or create room
            room, created = VideoRoom.objects.get_or_create(
                room_id=self.room_id,
                defaults={'created_by': self.user}
            )
            
            if created:
                print(f"Created new room: {self.room_id}")
            
            # Create session
            session = CallSession.objects.create(
                room=room,
                video_enabled=data.get('video_enabled', True),
                audio_enabled=data.get('audio_enabled', True),
                status='active'
            )
            session.participants.add(self.user)
            
            # Update room status
            room.is_active = True
            room.save()
            
            print(f"Created call session: {session.id}")
            
        except Exception as e:
            print(f"Error creating call session: {e}")

    @database_sync_to_async
    def end_call_session(self):
        """End the current call session"""
        try:
            from django.utils import timezone
            from .models import VideoRoom
            
            room = VideoRoom.objects.get(room_id=self.room_id)
            
            # End all active sessions
            active_sessions = room.sessions.filter(status='active')
            for session in active_sessions:
                session.status = 'ended'
                session.ended_at = timezone.now()
                session.calculate_duration()
                session.save()
                print(f"Ended call session: {session.id}")
            
            # Update room status
            room.is_active = False
            room.save()
            
        except Exception as e:
            print(f"Error ending call session: {e}") 