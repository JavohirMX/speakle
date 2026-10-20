from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.shortcuts import render, redirect


def _community_stats():
    """Real, cached community numbers for the landing page (no invented figures)."""
    stats = cache.get('home_community_stats')
    if stats is None:
        from users.models import Language
        from matches.models import Match
        stats = {
            'languages': Language.objects.count(),
            'members': get_user_model().objects.filter(is_active=True).count(),
            'matches': Match.objects.filter(status='active').count(),
        }
        cache.set('home_community_stats', stats, 300)
    return stats


def home(request):
    """Main landing page for Speakle. Signed-in users go straight to Find."""
    if request.user.is_authenticated:
        return redirect('matches:find_matches')
    return render(request, 'main/home.html', {'stats': _community_stats()})


def error_404(request, exception=None):
    return render(request, '404.html', status=404)


def error_500(request):
    return render(request, '500.html', status=500)


def stats(request):
    """Staff-only dashboard: aggregate counts only, no personal data or chat content."""
    from datetime import timedelta
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate
    from django.http import Http404
    from django.utils import timezone
    from chats.models import CallSession, ChatMessage
    from matches.models import Match
    from .models import PageStat

    if not (request.user.is_authenticated and request.user.is_staff):
        raise Http404()
    today = timezone.localdate()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    since = days[0]

    def per_day(qs, field):
        rows = qs.filter(**{f'{field}__date__gte': since}).annotate(d=TruncDate(field)).values('d').annotate(n=Count('id'))
        got = {r['d']: r['n'] for r in rows}
        return [got.get(d, 0) for d in days]

    views = {}
    for row in PageStat.objects.filter(day__gte=since, key__startswith='view:').values('key', 'day').annotate(n=Sum('count')):
        views.setdefault(row['key'][5:], {})[row['day']] = row['n']
    def view_series(name):
        return [views.get(name, {}).get(d, 0) for d in days]

    series = [
        ('Landing page views', view_series('main:home')),
        ('Sign-up page views', view_series('users:register')),
        ('New members', per_day(get_user_model().objects.all(), 'date_joined')),
        ('Matches created', per_day(Match.objects.all(), 'created_at')),
        ('Calls started', per_day(CallSession.objects.all(), 'started_at')),
        ('Text messages sent', per_day(ChatMessage.objects.all(), 'timestamp')),
    ]
    rows = [{'label': label, 'values': vals, 'total': sum(vals)} for label, vals in series]
    sources = list(PageStat.objects.filter(day__gte=since).exclude(key__startswith='view:')
                   .values('key').annotate(n=Sum('count')).order_by('-n')[:20])
    top_pages = sorted(((k, sum(v.values())) for k, v in views.items()), key=lambda x: -x[1])[:15]
    return render(request, 'main/stats.html', {
        'days': days, 'rows': rows, 'sources': sources, 'top_pages': top_pages,
        'members': get_user_model().objects.filter(is_active=True).count(),
    })
