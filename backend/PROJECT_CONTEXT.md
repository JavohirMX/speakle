# PROJECT CONTEXT DOCUMENT (AI-OPTIMIZED)

## 1. PROJECT_META
- **name**: Speakle
- **description**: Global Language Exchange Platform - A comprehensive Django-based platform that connects language learners worldwide through intelligent matching and real-time video conversations
- **primary_language**: Python
- **repo_url**: __TBD__
- **version**: __TBD__
- **mission**: Break down language barriers and cultural boundaries by providing an accessible, secure, and engaging platform for language practice and cultural exchange

## 2. OBJECTIVES
- **main_goal**: Connect language learners worldwide through intelligent matching and real-time video conversations
- **secondary_goals**: 
  - Provide AI-powered compatibility scoring based on language preferences
  - Enable real-time WebRTC video chat without downloads
  - Create meaningful connections between native speakers and learners
  - Track call analytics and user progress
- **target_users**: Language learners seeking conversation practice with native speakers globally

## 3. STACK
- **frontend**:
  - **framework**: Vanilla JavaScript (no frameworks)
  - **language**: JavaScript/HTML5
  - **styling**: TailwindCSS (CDN), Custom CSS
  - **video**: WebRTC APIs (browser native)
- **backend**:
  - **framework**: Django 5.2.1
  - **language**: Python 3.11+
  - **real_time**: Django Channels 4.0.0 + WebSocket
- **database**:
  - **engine**: SQLite (development), PostgreSQL (production ready)
  - **schema_summary**: Custom User model, Language/UserLanguage, Match/MatchRequest, VideoRoom/CallSession, ChatRoom/ChatMessage models
- **APIs**:
  - **internal**: 
    - `/matches/api/` - Match requests, potential matches, statistics
    - `/chats/api/` - Call invitations, room management, messaging
    - `/users/` - Authentication, profile management
  - **external**: None (self-contained)
- **deployment**:
  - **method**: Django + Django Channels (ASGI)
  - **target_envs**: [dev, staging, prod]
  - **dependencies**: Redis (production WebSocket channel layer)

## 4. SYSTEM_DESIGN
- **data_flow**:
  - **frontend_to_backend**: Django templates → AJAX/Fetch → Django views → WebSocket for real-time
  - **backend_to_db**: Django ORM → SQLite/PostgreSQL
  - **auth_strategy**: Django sessions (no JWT in main flow)
- **core_modules**:
  - **users**: Custom User model, Language management, Multi-language proficiency tracking
  - **matches**: AI-powered compatibility scoring, Bidirectional language exchange matching, Match request workflow
  - **chats**: WebRTC video rooms, Call invitations, Real-time messaging, Call analytics and session tracking
  - **main**: Landing page, Global templates, Base navigation
- **component_tree**: Server-rendered Django templates with progressive enhancement via vanilla JS
- **websocket_architecture**: 3 consumers - VideoCallConsumer, UserNotificationConsumer, TextChatConsumer

## 5. RULES_AND_CONVENTIONS
- **file_structure**: 
  - Standard Django app structure: `config/` (settings), `main/` (landing), `users/` (auth), `matches/` (matching), `chats/` (video/text)
  - Templates in `app/templates/app/`, Static files in `static/`, Media uploads in `media/`
- **naming_conventions**:
  - **variables**: snake_case
  - **files**: snake_case.py, kebab-case.html
  - **APIs**: `/app/api/action-name/`
  - **URLs**: app_name:view_name pattern with namespacing
- **code_style**:
  - **linters**: __TBD__
  - **formatting**: __TBD__
  - **frontend**: TailwindCSS utility classes, BEM-like custom CSS for components
- **git_workflow**:
  - **branch_naming**: __TBD__
  - **commit_format**: __TBD__

## 6. FEATURE_LIST
- **implemented**:
  - Custom user authentication with email-based login
  - Multi-language profile system with proficiency levels (native, fluent, learning)
  - AI-powered compatibility scoring based on language preferences and interests
  - Bidirectional language exchange matching algorithm
  - WebRTC video chat with screen sharing and text chat during calls
  - Real-time call invitations with WebSocket notifications
  - Call session tracking with analytics (duration, quality, end reasons)
  - Text chat rooms with typing indicators and message editing
  - User presence tracking (online/offline status)
  - Match request workflow (send, accept, decline)
  - Call history and session summaries
  - Profile picture upload and bio management
- **planned**: __TBD__

## 7. USER_STORIES
- **examples**:
  - User registers with native/learning languages and proficiency levels
  - System finds compatible partners who teach what user wants to learn
  - User sends match request with optional message
  - Partner accepts/declines match request
  - Matched users can send call invitations and start video chats
  - Real-time WebRTC video sessions with text chat overlay
  - Call analytics track session quality and duration

## 8. LIMITATIONS
- **known_issues**: __TBD__
- **edge_cases**: 
  - WebSocket fallback handling for poor connections
  - Call invitation expiration (2 minutes)
  - Room access validation for security

## 9. NOTES
- **design_preferences**: 
  - No external dependencies for video chat (pure WebRTC)
  - Server-rendered templates over SPA architecture
  - Progressive enhancement with vanilla JavaScript
  - TailwindCSS for rapid UI development
- **reusable_patterns**: 
  - Django Channels WebSocket consumers for real-time features
  - AI-powered compatibility scoring algorithm
  - UUID-based room identification system
  - Comprehensive call session analytics
- **questions_for_user**: []

## 10. DESIGN_AND_UX_PRINCIPLES
- **UI/UX_goals**: Modern, accessible, mobile-responsive language exchange platform
- **color_scheme**: 
  - Primary: Blue gradient (#667eea to #764ba2)
  - Success: Green gradient (#84fab0 to #8fd3f4)  
  - Warning: Orange gradient (#ffecd2 to #fcb69f)
  - Neutral: Gray scale with Inter font family
- **typography**: Inter font family (Google Fonts), 16px base font size
- **component_design**: 
  - Glassmorphism effects with backdrop-filter blur
  - Gradient buttons and interactive elements
  - Card-based layouts with rounded corners and shadows
  - Notification badges with pulse animations
- **responsiveness**: Mobile-first design with TailwindCSS responsive utilities
- **accessibility**: Semantic HTML, ARIA labels, keyboard navigation support

## 11. TECHNICAL_ARCHITECTURE
- **websocket_endpoints**:
  - `/ws/video/{room_id}/` - WebRTC signaling and video chat
  - `/ws/notifications/` - Global user notifications
  - `/ws/text-chat/{room_id}/` - Text messaging in chat rooms
- **real_time_features**:
  - Cross-page call invitation notifications
  - WebSocket auto-reconnection with fallback polling
  - Browser native desktop notifications
  - Real-time typing indicators
  - Live user presence updates
- **security_features**:
  - Django CSRF protection
  - Room access validation per user
  - Authenticated WebSocket connections
  - Input validation and sanitization
- **performance_optimizations**:
  - Database indexes for common queries (pending invitations, messages)
  - Redis channel layer for production WebSocket scaling
  - CDN delivery for TailwindCSS
  - Optimized query patterns with select_related/prefetch_related

---

*This document serves as the comprehensive technical and functional reference for the Speakle project, covering all aspects from architecture to implementation details. Generated from comprehensive codebase analysis.* 