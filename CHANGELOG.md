# Changelog

## Unreleased (dev)

### Added
- Redesign: "sticker pop" design system, app shell with side rail and mobile tab bar, new landing page.
- UX pass: toasts for server messages, inline sign-up validation, auto-login after sign-up, working password reset, safe `?next=` redirect, nav badges and correct active states.
- Email verification (signed, expiring tokens). Quick match can require a verified email.
- Quick match: timed trial call with keep or skip.
- Conversation prompts and private post-call feedback on matches.
- Block and report users, with admin review.
- SEO: canonical URLs, Open Graph and Twitter cards, JSON-LD, `robots.txt`, `sitemap.xml`, `noindex` on non-public pages.
- Favicons, web manifest, custom 404 and 500 pages.
- CI workflow for tests and migration checks.

### Fixed
- Quick match showed Find and Cancel buttons at the same time.
- Call summary showed the other person's private star rating (it was stored in the shared call notes). Ratings are now hidden from the partner.
- Call history showed the latest call as total time and a made-up 5m average. Both are now computed from real calls.
- Call summary showed call success rate as language progress. Removed.
- Text chat: reply preview and reply quote inserted message text as HTML (script injection from a partner's message). Escaped. Also the reply button could not work because a property shadowed the method.
- Nav unread badge overlapped the Chats label.
- Potential matches API returned each suggested person's email address to any signed-in user. Removed.
- Find matches ran several queries per match card. Now a fixed number of queries.

### Changed
- Production settings warn at startup when `SECRET_KEY` is still a placeholder.
- Tailwind CDN replaced by compiled CSS. Fonts are self-hosted.
- Matching: no duplicate or reverse requests, re-send after decline, best language pairing per partner.
- Landing page copy: removed invented statistics and testimonials.
- Requests, My Matches, chat list, Profile and Quick match pages rewritten in the new design. Chat list uses real links and shows each partner's languages.
- Text chat and video room: labelled controls, specific camera and microphone errors, auto-reconnect, input no longer hidden by the tab bar.

### Migrations
- `matches/0003_matchfeedback`, `matches/0004_quick_match`, `users/0003_userblock_userreport`, `users/0004_email_verified`.
- If you applied the earlier `matches/0003_quick_match` locally, it was renamed to `0004_quick_match`. Remove its row from `django_migrations` and run `migrate matches 0004 --fake`, or recreate your dev database.
