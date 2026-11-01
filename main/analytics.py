"""Privacy-first, first-party analytics.

What is stored: a per-day counter for each route name, plus the referrer host and the
``utm_source`` value on public entry pages. Nothing else: no IP address, cookie, user agent,
user id, query string, URL path (paths hold ids) or chat content. Turn it off with
``ANALYTICS_ENABLED = False``.
"""
import logging
import re
from urllib.parse import urlparse

from django.conf import settings
from django.db import IntegrityError
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)

# Public entry pages where the traffic source is worth recording.
ENTRY_ROUTES = {'main:home', 'users:register', 'users:login'}
SKIP_NAMESPACES = {'admin'}
MAX_SOURCE_KEYS_PER_DAY = 200
_SRC_RE = re.compile(r'[^a-z0-9_-]+')
_BOT_RE = re.compile(r'bot|spider|crawl|slurp|preview|headless|monitor|uptime', re.I)


def _clean_source(value):
    return _SRC_RE.sub('', (value or '').lower())[:30]


def _referrer_host(request):
    ref = request.META.get('HTTP_REFERER', '')
    host = (urlparse(ref).hostname or '').lower() if ref else ''
    if not host or host == request.get_host().split(':')[0].lower():
        return ''
    return host[:60]


def _bump(day, key):
    from .models import PageStat
    updated = PageStat.objects.filter(day=day, key=key).update(count=F('count') + 1)
    if updated:
        return
    try:
        PageStat.objects.create(day=day, key=key, count=1)
    except IntegrityError:
        PageStat.objects.filter(day=day, key=key).update(count=F('count') + 1)


def record(request, response):
    """Count one successful page view. Never raises."""
    try:
        if request.method != 'GET' or response.status_code != 200:
            return
        match = getattr(request, 'resolver_match', None)
        if match is None or not match.view_name or match.namespaces and match.namespaces[0] in SKIP_NAMESPACES:
            return
        if 'text/html' not in response.get('Content-Type', ''):
            return
        if _BOT_RE.search(request.META.get('HTTP_USER_AGENT', '')):
            return
        if match.view_name in ('main:stats', 'health_check'):
            return
        day = timezone.localdate()
        _bump(day, f'view:{match.view_name}'[:80])
        if match.view_name in ENTRY_ROUTES:
            from .models import PageStat
            extra = []
            src = _clean_source(request.GET.get('utm_source'))
            if src:
                extra.append(f'src:{src}')
            host = _referrer_host(request)
            if host:
                extra.append(f'ref:{host}')
            if extra and PageStat.objects.filter(day=day).exclude(key__startswith='view:').count() < MAX_SOURCE_KEYS_PER_DAY:
                for key in extra:
                    _bump(day, key)
    except Exception:  # analytics must never break a page
        logger.exception('analytics record failed')


class AnalyticsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(settings, 'ANALYTICS_ENABLED', True):
            record(request, response)
        return response
