# Architecture

How Speakle is put together. Checked against the code on `dev`. For setup see [README.md](../README.md), for production see [DEPLOYMENT.md](../DEPLOYMENT.md).

## Stack

- Python 3.11, Django 5.2, Django Channels 4 on Daphne (ASGI).
- Server-rendered Django templates with vanilla JavaScript. No front-end framework.
- Tailwind CSS 3 compiled to `static/css/tailwind.css`, plus hand-written `static/css/app.css` and `static/css/design.css`. Self-hosted fonts (Figtree, Bricolage Grotesque).
- SQLite in development, Postgres in Docker. Redis for the Channels layer, cache and sessions in Docker. Development uses an in-memory channel layer.
- Video is peer-to-peer WebRTC. The Django side only does signaling over WebSockets.
- Sessions are Django sessions (database-backed in development, Redis-backed with `settings_prod`). Django REST framework and SimpleJWT are installed but the main flow does not use token auth.

## Settings

- `config/settings.py` is the development and base settings. Debug is off unless `DEBUG=True`. `SECRET_KEY` is required (a throwaway key is used only when `DEBUG=True` or under the test runner).
- `config/settings_prod.py` imports the base settings and adds Postgres via `DATABASE_URL`, Redis channel layer, cache and sessions, SMTP email, HTTPS hardening and logging. Select it with `DJANGO_SETTINGS_MODULE=config.settings_prod`.

## Apps

| App | Owns |
|---|---|
| `users` | Custom `User` (username login), `Language`, `UserLanguage`, `UserBlock`, `UserReport`. Registration, login throttling, email verification, password reset, profile and language editing, block and report. |
| `matches` | `PotentialMatch`, `Match`, `MatchRequest`, `MatchFeedback`, `QuickMatchEntry`. Scoring in `services.py`, quick match in `quick.py`, match pages and JSON endpoints under `/matches/api/`. |
| `chats` | `VideoRoom`, `CallInvitation`, `CallSession`, `UserPresence`, `ChatRoom`, `ChatMessage`, `RoomMessage`, `TypingStatus`. Call and chat views, JSON endpoints under `/chats/api/`, WebSocket consumers. |
| `main` | Landing page, `PageStat` analytics (`analytics.py`), SEO helpers and endpoints (`seo.py`), staff-only `/stats/`, error pages, the `versioned_static` template tag. |

## Data model in short

- A `User` has many `UserLanguage` rows. Each has a language, a type (`native`, `fluent` or `learning`) and a proficiency (`beginner`, `intermediate`, `advanced`, `native`).
- A `Match` links two users with the language each teaches and learns. Statuses include `pending`, `active`, `ended` and `trial` (quick match).
- A `MatchRequest` is a request from one user to another with a status. Accepting turns it into an active `Match`.
- A `VideoRoom` belongs to one `Match` and has a UUID `room_id` used in URLs and WebSocket paths. A `CallSession` records each call (status, duration, end reason).
- A `CallInvitation` expires two minutes after it is created.
- A `UserBlock` hides two users from each other in matching, rooms and chat.

## Matching

`MatchingService` in `matches/services.py` finds partners where each person can teach what the other is learning, scores the best language pairing (see the README), and stores `PotentialMatch` rows. Users who are already matched, have a pending request, or have a block in either direction are excluded.

Quick match (`matches/quick.py`) pairs two waiting users with a mirrored language pair, creates a `trial` match with a 5 minute timer, and afterwards both users choose keep or skip. A waiting entry older than 3 minutes counts as abandoned. A verified email is required unless `QUICK_MATCH_REQUIRE_VERIFIED_EMAIL=False`.

## Call flow

1. From a match page the app can check partner availability (`/chats/api/partner-availability/<match_id>/`).
2. The caller sends an invitation (`/chats/api/send-invitation/<match_id>/`). The partner is notified over the notifications WebSocket and can accept, decline or let it expire.
3. On accept, both browsers open `/chats/room/<room_id>/` and connect to `/ws/video/<room_id>/`. The consumer relays WebRTC offers, answers and ICE candidates. Media then flows directly between browsers.
4. A `CallSession` is created and updated; ending the call stores the reason. Summaries and history are at `/chats/summary/...` and `/chats/history/<room_id>/`.

Calls use five public Google STUN servers (`stun.l.google.com` and `stun1` to `stun4`) and no TURN relay.

## WebSocket endpoints

Defined in `chats/routing.py`, served by `chats/consumers.py`, authenticated with Channels' `AuthMiddlewareStack`:

| Path | Consumer | Purpose |
|---|---|---|
| `/ws/video/<room_id>/` | `VideoCallConsumer` | WebRTC signaling, in-call chat, call start and end |
| `/ws/notifications/` | `UserNotificationConsumer` | Call invitations and other notifications |
| `/ws/text-chat/<room_id>/` | `TextChatConsumer` | Text chat, typing indicators, message edits |

## Security measures in the code

- Django CSRF protection, plus Django's default `X-Frame-Options: DENY` and `nosniff` headers.
- Room access is checked per user and refused when either side has blocked the other.
- Failed sign-ins are throttled per address and username (10 failures in 15 minutes). An optional per-address sign-up cap is available (`SIGNUPS_PER_HOUR_PER_IP`).
- Password reset does not reveal whether an email has an account. Verification links are signed and expire.
- Every page except the landing and sign-up pages is sent with `X-Robots-Tag: noindex`.

## Front-end notes

- Templates extend `main/templates/base.html`. Icons come from `partials/icons.html`.
- Design tokens and shared components are in `static/css/design.css`. Layout and page styles are in `static/css/app.css`. Per-page CSS can go in the `extra_css` block.
- Accessibility basics: skip link, one `h1` per page, labelled controls, a closed mobile menu that is removed from the tab order.
- The video room template loads Tailwind from `cdn.tailwindcss.com` rather than the compiled file.

## Tests

`python manage.py test` runs about 250 tests. Each app has its own `tests.py`; some have extra modules (for example `matches/test_views_extra.py`, `main/test_settings.py`, `main/test_analytics.py`). WebSocket consumers are tested with Channels' communicator test utilities.
