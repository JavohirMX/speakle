# Speakle - Language Exchange Platform

A Django-based web application that connects language learners worldwide for video chat exchanges.

## Features

### Core Functionality
- User registration and authentication
- Profile creation with languages and proficiency levels
- Language partner matching system
- Real-time video chat with WebRTC
- Match request system

### Enhanced Video Chat System
- **Real-time Call Invitations**: Send invitations with optional messages
- **Partner Availability Checking**: See if your partner is online before calling
- **Call Status Tracking**: Real-time updates on invitation responses
- **Video Room Management**: Secure rooms for each match pair
- **Call History**: Track your conversation sessions

### Global Notification System ✨ NEW!
- **Cross-Page Notifications**: Receive call invitations on any page
- **WebSocket Real-Time Updates**: Instant notifications without page refresh
- **Browser Notifications**: Native desktop notifications with permission request
- **Audio Alerts**: Sound notifications for incoming calls
- **Visual Indicators**: Badge counter on navigation for pending calls
- **Toast Notifications**: Elegant in-app notification toasts
- **Auto-Reconnection**: Robust WebSocket connection with automatic reconnection

### Notification Features
- 📞 **Incoming Call Modals**: Beautiful modal dialogs for call invitations
- 🔔 **Browser Integration**: Native OS notifications that work even when tab is inactive
- 🎵 **Sound Alerts**: Audio notifications for important events
- 📊 **Badge Counters**: Visual indicators for pending invitations
- 🔄 **Real-Time Sync**: Instant updates across all open tabs
- ⏰ **Expiration Handling**: Automatic cleanup of expired invitations
- 🌐 **Cross-Browser Support**: Works on all modern browsers

## Technology Stack

- **Backend**: Django 5.0 + Django Channels for WebSocket support
- **Frontend**: HTML5, TailwindCSS, Vanilla JavaScript
- **Real-Time**: WebSocket connections with Redis channel layer
- **Video**: WebRTC for peer-to-peer video communication
- **Database**: SQLite (development) / PostgreSQL (production)

## Installation

1. Clone the repository
2. Create virtual environment: `python -m venv .venv`
3. Activate virtual environment: `source .venv/bin/activate` (Linux/Mac) or `.venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Run migrations: `python manage.py migrate`
6. Create superuser: `python manage.py createsuperuser`
7. Start Redis server (required for WebSocket channels)
8. Run development server: `python manage.py runserver`

## Key Models

### User & Profile
- Custom user model with language preferences
- UserLanguage model for tracking proficiency levels
- Profile information including bio and interests

### Matching System
- Match model for connecting compatible language partners
- Request system for managing match proposals
- Language compatibility checking

### Enhanced Video Chat
- **VideoRoom**: Secure rooms for each match pair
- **CallSession**: Track individual call sessions with duration
- **CallInvitation**: Complete invitation system with status tracking
- **UserPresence**: Real-time online status tracking
- **RoomMessage**: Chat messages within video rooms

## Real-Time Features

### WebSocket Consumers
1. **VideoCallConsumer**: Handles video room communication (signaling, chat, status)
2. **UserNotificationConsumer**: Global user notifications (call invitations, responses)

### Notification Types
- `call_invitation_received`: Instant invitation delivery
- `call_invitation_accepted`: Real-time acceptance feedback
- `call_invitation_declined`: Immediate decline notification
- `call_invitation_cancelled`: Cancellation alerts

## Usage

1. **Register** and complete your profile with languages
2. **Find Partners** using the matching system
3. **Send Requests** to potential language exchange partners
4. **Start Video Calls** with real-time invitation system:
   - Check partner availability
   - Send invitation with optional message
   - Receive instant WebSocket notifications
   - Accept/decline calls from any page
5. **Practice Languages** in secure video rooms
6. **Track Progress** with call history and session data

## New User Experience Flow

1. **Anywhere on the site**: Receive instant call notifications
2. **Toast notifications** appear in top-right corner
3. **Browser notifications** show even when tab is inactive
4. **Audio alerts** play for incoming calls
5. **Badge indicators** show pending call count
6. **Modal dialogs** provide easy accept/decline interface
7. **Real-time updates** across all open tabs
8. **Automatic cleanup** of expired invitations

## Browser Notification Support

The system automatically requests notification permissions and provides:
- Desktop notifications that appear even when Speakle tab is not active
- Clickable notifications that bring focus back to the application
- Automatic cleanup and replacement of outdated notifications
- Cross-browser compatibility

## WebSocket Architecture

### Notification Groups
- Each user has a dedicated notification group: `user_notifications_{user_id}`
- Real-time delivery of call invitations and responses
- Automatic reconnection on connection loss
- Graceful handling of page visibility changes

### Connection Management
- Automatic reconnection on disconnect
- Proper cleanup on page unload
- Heartbeat mechanisms for connection monitoring
- Cross-tab synchronization

## Testing the Notification System

1. Open two browser windows/tabs with different user accounts
2. Have both users online and matched
3. Send a call invitation from one user
4. Observe real-time notifications on the other user's screen:
   - Toast notification appears
   - Browser notification shows (if permitted)
   - Audio alert plays
   - Badge counter updates
   - Modal dialog appears for easy response

## Development Notes

- WebSocket connections are managed globally in the base template
- Notifications work across all pages for authenticated users
- System gracefully degrades if WebSocket connection fails
- Polling backup ensures reliability
- Browser notification permissions are requested automatically

## Future Enhancements

- Mobile push notifications
- Integration with calendar systems
- Advanced matching algorithms
- Group video sessions
- Screen sharing capabilities
- Recording features
- Language learning progress tracking

---

Built with ❤️ for language learners worldwide. 