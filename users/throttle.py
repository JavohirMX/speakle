"""Small cache-backed throttle for failed logins and repeat reports.

Uses Django's cache, so with the production Redis cache the limit is shared by all
workers. With the default per-process cache it is per worker, which is weaker but
still stops a simple guessing loop.
"""
from django.core.cache import cache

LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW = 15 * 60


def _login_key(request, username):
    ip = request.META.get('REMOTE_ADDR', '')
    return 'login-fail:%s:%s' % (ip, (username or '').strip().lower()[:150])


def login_blocked(request, username):
    return cache.get(_login_key(request, username), 0) >= LOGIN_MAX_FAILURES


def record_login_failure(request, username):
    key = _login_key(request, username)
    cache.add(key, 0, LOGIN_WINDOW)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, LOGIN_WINDOW)


def clear_login_failures(request, username):
    cache.delete(_login_key(request, username))


def allow(key, limit, window):
    """Count one event under `key`. Returns False once more than `limit` happened in `window` seconds."""
    cache.add(key, 0, window)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
        count = 1
    return count <= limit


CHAT_LIMIT = 30
CHAT_WINDOW = 60


def chat_allowed(user_id):
    return allow('chat-send:%s' % user_id, CHAT_LIMIT, CHAT_WINDOW)


def signup_allowed(request):
    """Per-address signup cap. Off unless SIGNUPS_PER_HOUR_PER_IP is set above 0.

    Off by default because behind a reverse proxy REMOTE_ADDR can be the proxy's
    address, which would turn this into a site-wide cap.
    """
    from django.conf import settings
    limit = getattr(settings, 'SIGNUPS_PER_HOUR_PER_IP', 0)
    if not limit:
        return True
    return allow('signup:%s' % request.META.get('REMOTE_ADDR', ''), limit, 3600)
