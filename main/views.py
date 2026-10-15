from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.shortcuts import render


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
    """Main landing page for Speakle."""
    return render(request, 'main/home.html', {'stats': _community_stats()})
