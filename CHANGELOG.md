# Changelog

## Unreleased (dev)

### Added
- Docs: README rewritten with screenshots, accurate quickstart (including `populate_languages`), configuration table, deploy summary and known limits. DEPLOYMENT.md rewritten to match `docker-compose.yml`. New `docs/ARCHITECTURE.md` replaces the stale `PROJECT_CONTEXT.md`.
- Video calls: ICE servers are configurable (`WEBRTC_STUN_URLS`, `WEBRTC_TURN_URLS`, `WEBRTC_TURN_USERNAME`, `WEBRTC_TURN_CREDENTIAL`) so a TURN relay can be added. Default stays the five Google STUN servers. No credentials are committed.
- Login and sign-up pages get their own description and OG/Twitter titles instead of repeating the home page ones.
- Performance: the ~140 KB of inline CSS in every page moved into cacheable static files (`app.css`, `design.css`) linked with a content hash. Pages drop from ~100 KB to ~38 KB of HTML with identical rendering (pixel-compared).
- Redesign: "sticker pop" design system, app shell with side rail and mobile tab bar, new landing page.
- UX pass: toasts for server messages, inline sign-up validation, auto-login after sign-up, working password reset, safe `?next=` redirect, nav badges and correct active states.
- Email verification (signed, expiring tokens). Quick match can require a verified email.
- Quick match: timed trial call with keep or skip.
- Conversation prompts and private post-call feedback on matches.
- Block and report users, with admin review.
- Sign-up is all-or-nothing (no account without its languages); replaced profile pictures are deleted from storage.
- Profile page shows a "Finish your profile" checklist until the account is complete.
- List pages (chats, matches, requests) use a fixed number of queries instead of several per row.
- Password reset pages and email subject now use the Speakle templates (Django admin ones were shadowing them). Accessibility: one h1 on sign-in, sign-up and reset pages, valid heading order on Find, closed mobile menu no longer takes keyboard focus.
- Match detail page restyled to the design system (overview, stats, settings); quick match spacing and long-word wrapping fixes.
- SEO: canonical URLs, Open Graph and Twitter cards, JSON-LD, `robots.txt`, `sitemap.xml`, `noindex` on non-public pages.
- Favicons, web manifest, custom 404 and 500 pages.
- CI workflow for tests and migration checks.
- Privacy-first analytics: per-day counters by page name, referrer host and `?utm_source=` on landing, sign-up and login pages. No IPs, cookies, user ids, URLs with ids or chat content. Staff-only dashboard at `/stats/` with sign-ups, matches, calls and message counts. Turn off with `ANALYTICS_ENABLED = False`.

### Fixed
- Docker: the `web` healthcheck called `curl`, which the Python base image does not include, so the container could never report healthy. It now uses Python, with a 60 second start period for migrations.
- Mobile: sign out was unreachable on phones (header menu and footer are hidden in the app shell). The profile page now has a Sign out button. Removed two dead "#" links (Statistics, Settings) from the user menus, stopped the skip link peeking in at the top of the page, and stacked the empty-state buttons on narrow screens.
- Video room on phones: the control bar no longer covers the partner name and timer, "Start call" wraps instead of being cut, the waiting icon is centred, and the Share button is hidden when the browser cannot share a screen.
- Quick match showed Find and Cancel buttons at the same time.
- Call summary showed the other person's private star rating (it was stored in the shared call notes). Ratings are now hidden from the partner.
- Call history showed the latest call as total time and a made-up 5m average. Both are now computed from real calls.
- Call summary showed call success rate as language progress. Removed.
- Text chat: reply preview and reply quote inserted message text as HTML (script injection from a partner's message). Escaped. Also the reply button could not work because a property shadowed the method.
- Nav unread badge overlapped the Chats label.
- Blocking someone ended the match but both people could still use the text chat and video room. A block now cuts off access to both rooms for both people, including sending in an open chat or sending an offer in an open call.
- Potential matches API returned each suggested person's email address to any signed-in user. Removed.
- Find matches ran several queries per match card. Now a fixed number of queries.
- Match detail page inserted a partner's chat text as HTML in the recent-messages preview (stored script injection). Escaped. Video room messages and names are escaped too.
- Active users were marked offline after about 5 minutes because a heartbeat from an already-online user never saved its last activity. Checking a partner's availability also refreshed the partner's activity, so stale users showed online.
- Chat messages API returned 500 for a non-numeric `page` or `page_size`; reply targets that were not numbers returned 500 or dropped the message. Message edits had no length limit and blocked users could still edit.
- Notification socket crashed on `new_chat_message`, `message_edited` and `call_ended_enhanced` events sent by the HTTP views.
- Video call socket let any user with an active match open a room id that did not exist, and failed open on errors. A call start with a non-boolean media flag silently created no session. Call-end reason, notes and quality values from the client are cleaned before saving.
- Deactivated users were suggested as partners, kept in stored suggestions and the quick-match queue, and could be sent match requests. Blocking now also removes stored suggestions between the two people.
- Profile bio (1000), interests (500) and picture size (5 MB) are now limited. Find matches says which language you still need to add.

### Changed
- Settings are safe by default: `DEBUG` is off unless `DEBUG=True`, and the app refuses to start without a real `SECRET_KEY` (no hardcoded key in source). Local development now needs `DEBUG=True`; CI sets it.
- Sign-up and profile reject an email that already has an account (case-insensitive). `manage.py duplicate_emails` lists existing duplicates without changing anything.
- Partner email is no longer returned by the confirmed-match APIs unless that person turns on "Show my email to matches" in their profile.
- Sign out is a POST (form buttons), so another page cannot sign you out with a link or image.
- Login locks for 15 minutes after 10 failed attempts for the same name and address. Repeating the same report within a day no longer adds a duplicate.
- Optional sign-up cap per address (`SIGNUPS_PER_HOUR_PER_IP`, off by default).
- Text chat allows 30 messages a minute per person (HTTP and WebSocket).
- Production settings warn at startup when `SECRET_KEY` is still a placeholder.
- Tailwind CDN replaced by compiled CSS. Fonts are self-hosted.
- Matching: no duplicate or reverse requests, re-send after decline, best language pairing per partner.
- Landing page copy: removed invented statistics and testimonials.
- Requests, My Matches, chat list, Profile and Quick match pages rewritten in the new design. Chat list uses real links and shows each partner's languages.
- Text chat and video room: labelled controls, specific camera and microphone errors, auto-reconnect, input no longer hidden by the tab bar.

### Migrations
- `matches/0003_matchfeedback`, `matches/0004_quick_match`, `users/0003_userblock_userreport`, `users/0004_email_verified`, `users/0005_share_email_with_matches`, `main/0001_initial` (analytics counters). All add tables or a column with a default; none delete or rewrite data.
- If you applied the earlier `matches/0003_quick_match` locally, it was renamed to `0004_quick_match`. Remove its row from `django_migrations` and run `migrate matches 0004 --fake`, or recreate your dev database.
