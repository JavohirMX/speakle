# Text Chat Implementation

## Overview

This document describes the standalone text chat functionality implemented for the Speakle language exchange platform. The text chat system operates independently from video calls and provides real-time messaging between matched users.

## Architecture

### Database Models

#### ChatRoom
- **Purpose**: Represents a text-only chat room between matched users
- **Key Fields**:
  - `room_id`: UUID for the chat room
  - `match`: ForeignKey to the Match model
  - `participants`: ManyToMany relationship with users
  - `created_at`, `last_activity`: Timestamp tracking
  - `is_active`: Boolean flag for room status

#### ChatMessage
- **Purpose**: Stores chat messages with rich features
- **Key Fields**:
  - `room`: ForeignKey to ChatRoom
  - `sender`: ForeignKey to User
  - `content`: Message text content
  - `reply_to`: ForeignKey to self for message replies
  - `is_edited`: Boolean flag for edited messages
  - `edited_at`: Timestamp of last edit
  - `read_by`: ManyToMany for read status tracking
  - `created_at`: Message timestamp
- **Indexes**: Optimized for room-based queries and timestamp ordering

#### TypingStatus
- **Purpose**: Tracks real-time typing indicators
- **Key Fields**:
  - `room`: ForeignKey to ChatRoom
  - `user`: ForeignKey to User
  - `is_typing`: Boolean status
  - `last_typing`: Timestamp of last typing activity

### WebSocket Consumer

#### TextChatConsumer
- **File**: `chats/consumers.py`
- **Features**:
  - Real-time message sending and receiving
  - Message editing and replies
  - Typing indicators
  - Connection management
  - Authentication and authorization
  - Automatic reconnection support

### Views and APIs

#### Web Views
- `chat_list`: Display all user chat rooms
- `create_chat_room`: Create new chat room from match
- `text_chat`: Main chat interface

#### API Endpoints
- `get_chat_room_url`: Get WebSocket URL for room
- `get_chat_messages`: Paginated message history
- `send_chat_message`: Send new message
- `edit_chat_message`: Edit existing message
- `mark_messages_read`: Mark messages as read
- `get_unread_count`: Get unread message count

## URL Structure

```
/chats/                           # Chat list
/chats/create/<int:match_id>/     # Create chat room
/chats/text/<str:room_id>/        # Text chat interface
/chats/api/room-url/<str:room_id>/ # Get WebSocket URL
/chats/api/messages/<str:room_id>/ # Get messages
/chats/api/send/<str:room_id>/     # Send message
/chats/api/edit/<int:message_id>/  # Edit message
/chats/api/read/<str:room_id>/     # Mark as read
/chats/api/unread/<str:room_id>/   # Get unread count
```

## WebSocket Protocol

### Connection
```
ws://localhost:8000/ws/text-chat/<room_id>/
```

### Message Types

#### Send Message
```json
{
    "type": "chat_message",
    "message": "Hello!",
    "reply_to": null
}
```

#### Edit Message
```json
{
    "type": "edit_message",
    "message_id": 123,
    "new_content": "Hello there!"
}
```

#### Typing Indicator
```json
{
    "type": "typing",
    "is_typing": true
}
```

#### Receive Message
```json
{
    "type": "chat_message",
    "message": {
        "id": 123,
        "content": "Hello!",
        "sender": "username",
        "timestamp": "2025-06-01T16:00:00Z",
        "is_edited": false,
        "reply_to": null
    }
}
```

## Features

### Real-time Messaging
- Instant message delivery via WebSockets
- Automatic reconnection on connection loss
- Connection status indicators

### Message Management
- Message editing with edit indicators
- Reply to specific messages
- Message threading for context

### Typing Indicators
- Real-time typing status
- Automatic timeout for inactive typing
- Visual indicators in UI

### Read Status
- Track which messages have been read
- Unread message counts
- Visual read indicators

### User Interface
- Modern, responsive design
- Smooth animations and transitions
- Mobile-friendly interface
- Dark/light theme support

## Security

### Authentication
- Django user authentication required
- Session-based authentication for WebSockets
- Participant verification for room access

### Authorization
- Users can only access rooms they're participants in
- Message editing restricted to original sender
- Read status limited to room participants

## Performance Optimizations

### Database
- Indexes on frequently queried fields
- Efficient pagination for message history
- Optimized queries with select_related and prefetch_related

### WebSocket
- Connection pooling and management
- Efficient message broadcasting
- Proper cleanup on disconnect

### Frontend
- Lazy loading of message history
- Optimistic UI updates
- Efficient DOM manipulation

## Installation

1. **Apply Migrations**:
   ```bash
   python manage.py makemigrations chats
   python manage.py migrate
   ```

2. **Update Settings**:
   The chat functionality uses the existing ASGI configuration and channel layers.

3. **Start Server**:
   ```bash
   python manage.py runserver
   ```

## Usage

1. **Access Chat List**: Navigate to `/chats/` to see all chat rooms
2. **Create Chat Room**: Click "Start Chat" from a match to create a room
3. **Start Chatting**: Enter the chat room and start messaging
4. **Real-time Features**: Use typing indicators, message editing, and replies

## Integration with Existing System

### Matches Integration
- Chat rooms are created from existing Match objects
- Participant management based on match participants
- Seamless integration with user authentication

### Coexistence with Video Chat
- Text chat operates independently from video calls
- Separate WebSocket consumers and routing
- Shared authentication and user management

## Troubleshooting

### Common Issues
1. **WebSocket Connection Failed**: Check ASGI configuration and channel layers
2. **Authentication Errors**: Ensure user is logged in and has proper session
3. **Message Not Sending**: Check room permissions and participant status

### Debug Mode
Enable Django debug mode for detailed error messages and logging.

## Future Enhancements

### Planned Features
- File and image sharing
- Message search functionality
- Emoji reactions
- Voice message support
- Message encryption

### Scalability
- Redis channel layers for production
- Message archiving for old conversations
- Horizontal scaling with multiple servers 