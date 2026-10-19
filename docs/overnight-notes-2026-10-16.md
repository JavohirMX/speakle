# Overnight changes (Oct 16)

All tests pass (62). Not run: real WebRTC calls between two browsers, Postgres/Redis stack, Docker build.

## Branches (all based on main d266d02)
- `improve/matching-logic`: matching fixes + repaired tests
- `improve/ui-landing`: honest landing page
- `feature/block-report`: block and report users (built on matching-logic)
- `overnight/all`: all three merged, tests green. Use this one if you want everything.

## What changed
1. Matching (`matches/services.py`)
   - Mutual request (A asks B while B already asked A) no longer risks a duplicate Match; the existing request is returned to accept.
   - Declined/cancelled requests can be re-sent (before, the unique constraint made it impossible).
   - Accepting twice is a no-op; accept/send run in transactions.
   - Suggestions exclude people you are matched with, have pending requests with, or have blocked.
   - Only the best-scoring language pairing per partner is kept (before, the first pair found won).
   - Interests parsed on commas/semicolons, not just spaces; capped so it cannot dominate the score.
2. Landing page: removed invented numbers (10,000+ learners, 1M+ matches, 99% compatibility, 120 countries) and three fake testimonials. Stats now come from the database and only show at 10+ members. Reason: unverifiable claims hurt trust and can be a legal problem.
3. Safety: `UserBlock` and `UserReport` models, `/users/block/<id>/`, `/users/report/<id>/`, admin review screen, Safety panel in match detail > Settings tab. Needs `python manage.py migrate` (migration `users/0003`, additive only, no data touched).
4. Tests: fixed 6 failing tests (stale expectations, test harness misuse), added 13 new ones.

## Deploy
```
git fetch && git checkout overnight/all   # or merge the PR branches
docker compose up -d --build              # entrypoint runs migrate + collectstatic
```
Only schema change: two new tables. No config/env changes needed. Rollback: redeploy main; the new tables are unused by old code.
Heads up (not changed): entrypoint creates an admin with default password `admin123` if the env var is unset. Set DJANGO_SUPERUSER_PASSWORD in .env. Prod settings default SECRET_KEY is `change-me-in-production`: make sure .env sets a real one.

## Market notes (sources checked Oct 16 2026)
- Category: language exchange apps, est. ~US$1.4B in 2025 growing ~10%/yr (QY Research, paid-report summary, treat as rough): https://www.qyresearch.com/reports/6132953/language-exchange-application
- Incumbents: Tandem, HelloTalk, Speaky. Their top complaint is that they feel like dating apps and users get unwanted advances: https://www.reddit.com/r/languagelearning/comments/105qc3k/tandem_and_hellotalk_safe_users/ , https://www.trustpilot.com/review/www.hellotalk.com , Tandem app store reviews https://apps.apple.com/us/app/tandem-practice-languages/id959001619
- Newer AI-tutor apps (Praktika, Learna) compete on always-available practice: https://www.businessofapps.com/data/language-learning-app-market/
- Implication for Speakle: lead with trust and structure (safety tools, scheduled sessions, session summaries) rather than feature count. Block/report was the biggest missing piece.
- Suggested next (not built): scheduled sessions with reminders, post-call feedback/rating, verified-profile badge, conversation-topic prompts during calls, AI icebreaker/translation help, email verification at signup.
