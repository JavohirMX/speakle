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
