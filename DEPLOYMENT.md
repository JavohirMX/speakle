# Deployment

Speakle runs as three containers from `docker-compose.yml`:

| Service | Image | Host port | Role |
|---|---|---|---|
| `web` | built from `Dockerfile` (Python 3.11) | 8001 | Daphne serving HTTP and WebSockets |
| `db` | `postgres:15-alpine` | 5433 | Postgres |
| `redis` | `redis:7-alpine` | 6380 | Channels layer, cache, sessions |

There is no reverse proxy in this repository. Put one (nginx, Caddy, a load balancer) in front for HTTPS, `/static/` and `/media/`. See [Reverse proxy](#reverse-proxy).

This guide was checked against the repo files. The Docker stack itself was not built or run while writing it, so test it on a staging host first.

## Prerequisites

- Docker with Compose v2 (`docker compose`).
- A domain and an HTTPS terminator for anything public. Camera and microphone access needs HTTPS outside `localhost`.
- An SMTP account if you want real verification and password-reset emails.

## First deploy

```bash
git clone https://github.com/JavohirMX/speakle.git
cd speakle
cp env.example .env
```

Edit `.env`. At minimum:

```bash
SECRET_KEY=<long random value>          # python -c "import secrets; print(secrets.token_urlsafe(64))"
DEBUG=False
ALLOWED_HOSTS=speakle.example.com
CSRF_TRUSTED_ORIGINS=https://speakle.example.com
SITE_URL=https://speakle.example.com
DJANGO_SETTINGS_MODULE=config.settings_prod
POSTGRES_PASSWORD=<strong password>
DATABASE_URL=postgres://speakle_user:<same password>@db:5432/speakle
DJANGO_SUPERUSER_PASSWORD=<strong password>
```

`DJANGO_SETTINGS_MODULE=config.settings_prod` matters. Without it the app runs the development settings: in-memory channel layer, console email, SQLite, and no HTTPS or HSTS settings. `env.example` already sets it.

Then:

```bash
docker compose up -d --build
docker compose exec web python manage.py populate_languages   # once; migrations do not create the language list
docker compose ps
```

The entrypoint waits for Postgres and Redis, runs `migrate` and `collectstatic`, and creates the admin user only when `DJANGO_SUPERUSER_PASSWORD` is set. Check the app at `http://<host>:8001/health/`, which returns `{"status": "healthy"}`.

All variables are described in the [README configuration table](README.md#configuration).

## Reverse proxy

The proxy must:

1. Terminate HTTPS and forward to `web:8000` (host port 8001).
2. Pass WebSocket upgrades for `/ws/` (video signaling, notifications, text chat). Without this, calls and chat do not work.
3. Serve `/static/` from `./staticfiles` and `/media/` from `./media`. `docker-compose.yml` mounts both folders into the `web` container. Daphne does not serve them when `DEBUG=False`.
4. Send `X-Forwarded-*` headers as usual. `SIGNUPS_PER_HOUR_PER_IP` and the login throttle use the client address Django sees, so leave `SIGNUPS_PER_HOUR_PER_IP=0` if your proxy hides it.

Static files use content-hashed URLs for the app CSS (`?v=...`), so you can send long `Cache-Control` headers for `/static/`.

Once HTTPS works, turn on the hardening flags in `.env`:

```bash
TRUST_X_FORWARDED_PROTO=True
SECURE_SSL_REDIRECT=True
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
```

`TRUST_X_FORWARDED_PROTO=True` makes Django trust the proxy's `X-Forwarded-Proto` header. Only set it if your proxy sets or overwrites that header on every request. Without it, `SECURE_SSL_REDIRECT=True` behind a TLS-terminating proxy redirects every request to https again, and HSTS is never sent.

HSTS is on by default in `settings_prod.py` (one year, with subdomains and preload), so only deploy this settings module on a host that will keep serving HTTPS.

## Everyday commands

```bash
docker compose logs -f web                              # app logs (email links too, while EMAIL_BACKEND is the console backend)
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py migrate
docker compose exec web python manage.py duplicate_emails   # read-only report of accounts sharing an email
docker compose restart web
```

Backup and restore of the database:

```bash
docker compose exec -T db pg_dump -U speakle_user speakle > backup.sql
docker compose exec -T db psql -U speakle_user speakle < backup.sql
```

Use the `POSTGRES_USER` and `POSTGRES_DB` from your `.env` if you changed them. Uploaded profile pictures live in `./media`, so back that folder up too.

## Updating

```bash
git pull
docker compose up -d --build
```

The entrypoint applies new migrations on start. Read the Unreleased section of [CHANGELOG.md](CHANGELOG.md) first.

## Automatic deploy

`.github/workflows/deploy.yml` runs on every push to `main` or `master`. It connects over SSH using the repository secrets `DO_HOST`, `DO_USERNAME`, `DO_SSH_KEY` and `DO_PORT`, pulls `main` in a fixed folder on the server, rebuilds the containers with `docker-compose`, and checks that port 8001 answers. Treat a merge to `main` as a production release. `.github/workflows/ci.yml` runs the tests on pull requests and on pushes to `dev`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `web` exits at start with "SECRET_KEY is not set" | `SECRET_KEY` is missing or still a placeholder in `.env`. |
| "CSRF verification failed" on forms | `CSRF_TRUSTED_ORIGINS` is missing your `https://` origin, or the proxy is not sending the right host. |
| Pages work but calls, chat or notifications do not | The proxy does not pass WebSocket upgrades for `/ws/`, or `REDIS_URL` is wrong. |
| Styles or fonts missing | The proxy is not serving `./staticfiles` at `/static/`, or `collectstatic` did not run. |
| No users appear in matching, language list is empty | `populate_languages` was not run. |
| Verification and reset emails never arrive | `EMAIL_BACKEND` is still the console backend. Set the `EMAIL_*` variables to a real SMTP server. The container's startup `migrate` prints warning `users.W001` in `docker compose logs web` when this is the case, and `python manage.py check` shows it too. The web server itself does not run checks. |
| Cannot reach the admin | `DJANGO_SUPERUSER_PASSWORD` was empty on first start. Run `createsuperuser`. |
| Calls connect on some networks and not others | There is no TURN relay, only public STUN servers. |
