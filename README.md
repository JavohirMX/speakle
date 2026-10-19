# Speakle

Free two-way language exchange in the browser. You speak English and want Korean, someone speaks Korean and wants English, and Speakle puts you on a call to teach each other.

Live: https://speakle.javohirmx.com/

## What it does

- Accounts with email verification, password reset, and a profile of languages you speak and are learning.
- Partner suggestions ranked by language fit and shared interests. Send, accept, decline and cancel match requests.
- Quick match: a short timed trial call with a stranger, then both people choose keep or skip.
- Video calls (WebRTC) and text chat, with presence and incoming-call notifications over WebSockets.
- Conversation prompts on each match, and private post-call feedback.
- Safety: block and report users, with an admin review screen. Blocked users never appear in matching.
- SEO and PWA basics: canonical URLs, Open Graph cards, sitemap, robots, web manifest, custom 404 and 500.

## Stack

Django 5.2, Django Channels (Daphne), SQLite for development and Postgres plus Redis in Docker, vanilla JavaScript, Tailwind CSS compiled to `static/css/tailwind.css`, self-hosted fonts.

Apps: `users` (accounts, languages, blocks and reports), `matches` (matching, requests, quick match, feedback), `chats` (rooms, video, text chat, presence), `main` (landing page, SEO endpoints, error pages).

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # optional
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

Use Daphne rather than `runserver` if you want WebSockets (calls, chat, notifications). `manage.py runserver` is fine for pages that do not need them.

Outgoing email prints to the console in development, so verification and password-reset links show up in the server log.

## Tests

```bash
python manage.py test
```

CI runs the same tests plus `manage.py check` and `makemigrations --check` on every pull request (`.github/workflows/ci.yml`). Not covered by automated tests: real camera and microphone calls on devices, and the Postgres and Redis stack.

## Front-end CSS

Tailwind is built ahead of time. After you add new utility classes to a template, rebuild:

```bash
npm i -D tailwindcss@3
npx tailwindcss -c tailwind.config.js -i static/css/tailwind.src.css -o static/css/tailwind.css --minify
```

Design tokens and shared components live in `main/templates/partials/design_css.html`.

## Configuration

Copy `env.example` to `.env` for Docker and production. Key settings:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Required in production. Use a long random value. |
| `DEBUG` | `False` in production. |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Your domain(s). |
| `SITE_URL` | Public origin, for example `https://speakle.example.com`. Used for canonical URLs, the sitemap, share images and email links. |
| `DATABASE_URL`, `REDIS_URL` | Postgres and Redis. |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | SMTP for verification and password reset. |
| `QUICK_MATCH_REQUIRE_VERIFIED_EMAIL` | Require a verified email for quick match (default on). |
| `DJANGO_SUPERUSER_*` | Admin created by the Docker entrypoint. Set a strong password. |

## Deploy

See [DEPLOYMENT.md](DEPLOYMENT.md). Short version: `docker compose up -d --build`. The entrypoint runs migrations and `collectstatic`. Pushes to `main` trigger the deploy workflow.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md). Older, longer docs are kept in `docs/`.

## License

No license file is present yet, so by default all rights are reserved. The previous README said MIT; add a `LICENSE` file if that is the intent.
