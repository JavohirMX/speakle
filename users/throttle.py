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
