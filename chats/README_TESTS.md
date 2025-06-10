# Chats App Tests

This document describes the comprehensive test suite for the chats app, which handles video calling and messaging functionality in the Speakle language exchange platform.

## Test Structure

The test suite is organized into several test classes that cover different aspects of the chats app:

### Model Tests

#### 1. VideoRoomModelTest
Tests the `VideoRoom` model functionality:
- Video room creation and basic properties
- Room ID uniqueness
- Participant access control
- User access permissions
- String representation

#### 2. CallInvitationModelTest
Tests the `CallInvitation` model functionality:
- Call invitation creation
- Automatic expiry time setting (2 minutes)
- Expiry detection logic
- Invitation acceptance validation
- String representation

#### 3. UserPresenceModelTest
Tests the `UserPresence` model functionality:
- User presence creation
- Online/offline status management
- Class method for updating presence
- String representation for online/offline users

#### 4. CallSessionModelTest
Tests the `CallSession` model functionality:
- Call session creation with participants
- Duration calculation for completed calls
- Human-readable duration display
- Success detection logic
- String representation

#### 5. RoomMessageModelTest
Tests the `RoomMessage` model functionality:
- Chat message creation
- Message ordering by timestamp
- String representation

### View Tests

#### ChatsViewsTest
Tests all the API endpoints and views:
- Video room creation and access control
- Getting video room URLs via API
- Sending call invitations with WebSocket notifications
- Handling offline partner scenarios
- Accepting and declining call invitations
- Getting pending invitations
- Setting user online status
- Authorization requirements for all endpoints

### WebSocket Tests

#### WebSocketConsumerTest (TransactionTestCase)
Tests the real-time WebSocket functionality:
- Video call consumer connection with authenticated users
- Chat message handling through WebSocket
- WebRTC offer/answer signaling
- User notification consumer for call invitations

### Integration Tests

#### ChatsIntegrationTest
Tests complete user workflows:
- Complete call invitation and acceptance flow
- Full call session lifecycle from start to finish
- Message exchange during calls
- Call ending with analytics

## Running the Tests

### Run All Chats Tests
```bash
python manage.py test chats.tests
```

### Run Specific Test Classes
```bash
# Model tests only
python manage.py test chats.tests.VideoRoomModelTest
python manage.py test chats.tests.CallInvitationModelTest
python manage.py test chats.tests.UserPresenceModelTest
python manage.py test chats.tests.CallSessionModelTest
python manage.py test chats.tests.RoomMessageModelTest

# View tests
python manage.py test chats.tests.ChatsViewsTest

# WebSocket tests
python manage.py test chats.tests.WebSocketConsumerTest

# Integration tests
python manage.py test chats.tests.ChatsIntegrationTest
```

### Run Individual Tests
```bash
python manage.py test chats.tests.VideoRoomModelTest.test_video_room_creation
python manage.py test chats.tests.ChatsViewsTest.test_send_call_invitation_api
```

### Run with Verbose Output
```bash
python manage.py test chats.tests -v 2
```

## Test Dependencies

The tests require the following:
- Django testing framework
- Channels testing utilities for WebSocket tests
- Mock/patch for external dependencies (WebSocket notifications)
- Test database (automatically created by Django)

## Test Data

Each test class sets up its own test data in the `setUp` method:
- Test users (testuser1, testuser2, etc.)
- Test languages (English, Korean)
- Test matches between users
- Video rooms and call invitations as needed

The tests use Django's `TestCase` which provides automatic database rollback, ensuring tests don't interfere with each other.

## Coverage

The test suite covers:
- ✅ All model methods and properties
- ✅ All view endpoints and API responses
- ✅ Authentication and authorization
- ✅ WebSocket message handling
- ✅ Real-time notifications
- ✅ Complete user workflows
- ✅ Error handling and edge cases
- ✅ Call session analytics
- ✅ Message persistence

## Mocking

The tests use Python's `unittest.mock` to mock external dependencies:
- WebSocket notifications (`send_user_notification`)
- Channel layer communications

This ensures tests are isolated and don't depend on external services.

## WebSocket Testing

WebSocket tests use Django Channels' `WebsocketCommunicator` to simulate real WebSocket connections and message exchanges. These tests verify:
- Connection establishment
- Message routing
- Real-time signaling for video calls
- User notifications

## Running Tests in Development

For development, you can run tests with coverage to see which parts of the code are tested:

```bash
# Install coverage if not already installed
pip install coverage

# Run tests with coverage
coverage run --source='.' manage.py test chats.tests
coverage report
coverage html  # Generate HTML coverage report
```

## Continuous Integration

These tests are designed to run in CI/CD environments and should pass consistently. They use in-memory databases and mock external dependencies to ensure fast, reliable execution. 