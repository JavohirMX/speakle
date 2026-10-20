from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from .forms import UserRegistrationForm, UserProfileForm, UserLanguageForm
from .models import UserLanguage, UserBlock, UserReport

from django.urls import reverse
import logging
from datetime import timedelta
from django.utils import timezone
import time
from django.contrib.auth import get_user_model as _get_user_model
from .throttle import signup_allowed, login_blocked, record_login_failure, clear_login_failures
from .verification import send_verification_email, check_token

RESEND_COOLDOWN_SECONDS = 60


def verify_email_view(request, token):
    user = check_token(token, _get_user_model())
    if not user:
        messages.error(request, 'That verification link is invalid or has expired. Request a new one from your profile.')
        return redirect('main:home')
    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=['email_verified'])
    messages.success(request, 'Email verified. You can use Quick match now.')
    return redirect('users:profile' if request.user.is_authenticated else 'users:login')


@login_required
@require_POST
def resend_verification_view(request):
    if request.user.email_verified:
        return JsonResponse({'success': True, 'already_verified': True})
    last = request.session.get('verification_sent_at', 0)
    if time.time() - last < RESEND_COOLDOWN_SECONDS:
        return JsonResponse({'success': False, 'error': 'Please wait a minute before asking again.'}, status=429)
    try:
        sent = send_verification_email(request, request.user)
    except Exception:
        logging.getLogger(__name__).exception('Could not send verification email')
        return JsonResponse({'success': False, 'error': 'Could not send the email. Try again later.'}, status=500)
    if not sent:
        return JsonResponse({'success': False, 'error': 'Add an email address to your profile first.'}, status=400)
    request.session['verification_sent_at'] = time.time()
    return JsonResponse({'success': True})

def _safe_next(request):
    target = request.POST.get('next') or request.GET.get('next') or ''
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return ''


def check_username_view(request):
    """Inline availability check for the sign-up form."""
    name = (request.GET.get('username') or '').strip()
    if len(name) < 3:
        return JsonResponse({'available': None})
    taken = get_user_model().objects.filter(username__iexact=name).exists()
    return JsonResponse({'available': not taken})


def register_view(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect('matches:find_matches')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid() and not signup_allowed(request):
            form.add_error(None, 'Too many sign-ups from this address. Try again later.')
            return render(request, 'registration/register.html', {'form': form}, status=429)
        if form.is_valid():
            user = form.save()
            try:
                send_verification_email(request, user)
            except Exception:
                logging.getLogger(__name__).exception('Could not send verification email')
            # Sign the new user straight in: no second form to fill.
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'Welcome, {user.username}! We sent a link to {user.email}. Confirm it to unlock Quick match.')
            return redirect('matches:find_matches')
    else:
        form = UserRegistrationForm()

    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('matches:find_matches')

    next_url = _safe_next(request)
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        username = request.POST.get('username', '')
        if login_blocked(request, username):
            form.add_error(None, 'Too many failed attempts. Try again in 15 minutes.')
            return render(request, 'registration/login.html', {'form': form, 'next': next_url}, status=429)
        if form.is_valid():
            clear_login_failures(request, username)
            login(request, form.get_user())
            return redirect(next_url or 'matches:find_matches')
        record_login_failure(request, username)
    else:
        form = AuthenticationForm()

    return render(request, 'registration/login.html', {'form': form, 'next': next_url})

@require_POST
def logout_view(request):
    """User logout view."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('main:home')

def profile_checklist(user, user_languages):
    """Steps that make a profile ready for matching. Returns (steps, done_count).

    Each step is (label, done, link). Only facts we can read from the account.
    """
    types = {ul.language_type for ul in user_languages}
    steps = [
        ('Add a language you speak', bool(types & {'native', 'fluent'}), reverse('users:add_language')),
        ('Add a language you want to learn', 'learning' in types, reverse('users:add_language')),
        ('Confirm your email', bool(user.email_verified), None),
        ('Add a profile picture', bool(user.profile_picture), '#infoTitle'),
        ('Write a short bio', bool((user.bio or '').strip()), '#infoTitle'),
        ('Add your interests', bool((user.interests or '').strip()), '#infoTitle'),
    ]
    return steps, sum(1 for _, done, _ in steps if done)


@login_required
def profile_view(request):
    """User profile view."""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('users:profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    # Get user's languages
    user_languages = request.user.userlanguage_set.all().order_by('language__name')
    
    steps, done_count = profile_checklist(request.user, user_languages)
    return render(request, 'users/profile.html', {
        'form': form,
        'user_languages': user_languages,
        'checklist': steps,
        'checklist_done': done_count,
        'checklist_total': len(steps),
        'checklist_complete': done_count == len(steps),
    })

@login_required
def add_language_view(request):
    """Add a new language to user's profile."""
    if request.method == 'POST':
        form = UserLanguageForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Added {form.cleaned_data["language"].name} to your languages!')
            return redirect('users:profile')
    else:
        form = UserLanguageForm(user=request.user)
    
    return render(request, 'users/add_language.html', {'form': form})

@login_required
def edit_language_view(request, language_id):
    """Edit an existing user language."""
    user_language = get_object_or_404(UserLanguage, id=language_id, user=request.user)
    
    if request.method == 'POST':
        form = UserLanguageForm(request.POST, instance=user_language, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Updated {form.cleaned_data["language"].name} in your languages!')
            return redirect('users:profile')
    else:
        form = UserLanguageForm(instance=user_language, user=request.user)
    
    return render(request, 'users/edit_language.html', {'form': form, 'user_language': user_language})

@login_required
def delete_language_view(request, language_id):
    """Delete a user language."""
    user_language = get_object_or_404(UserLanguage, id=language_id, user=request.user)
    
    if request.method == 'POST':
        language_name = user_language.language.name
        user_language.delete()
        messages.success(request, f'Removed {language_name} from your languages.')
        return redirect('users:profile')
    
    return render(request, 'users/delete_language.html', {'user_language': user_language})



@login_required
@require_POST
def block_user_view(request, user_id):
    """Block a user: ends any active match, cancels pending requests, hides them from matching."""
    from django.db.models import Q
    from django.utils import timezone
    from matches.models import Match, MatchRequest
    target = get_object_or_404(get_user_model(), id=user_id)
    if target.id == request.user.id:
        return JsonResponse({'success': False, 'error': 'You cannot block yourself.'}, status=400)
    UserBlock.objects.get_or_create(blocker=request.user, blocked=target)
    pair = Q(user1=request.user, user2=target) | Q(user1=target, user2=request.user)
    Match.objects.filter(pair, status__in=['active', 'pending', 'accepted', 'trial']).update(
        status='ended', ended_at=timezone.now(), ended_by=request.user,
        end_reason='Blocked', updated_at=timezone.now())
    MatchRequest.objects.filter(
        Q(sender=request.user, receiver=target) | Q(sender=target, receiver=request.user),
        status='pending').update(status='cancelled', responded_at=timezone.now())
    from matches.models import PotentialMatch
    PotentialMatch.objects.filter(
        Q(user=request.user, potential_partner=target) | Q(user=target, potential_partner=request.user)).delete()
    from chats.models import close_rooms_for_pair
    close_rooms_for_pair(request.user, target)
    return JsonResponse({'success': True})


@login_required
@require_POST
def report_user_view(request, user_id):
    """File a report about a user for admin review."""
    target = get_object_or_404(get_user_model(), id=user_id)
    if target.id == request.user.id:
        return JsonResponse({'success': False, 'error': 'You cannot report yourself.'}, status=400)
    reason = request.POST.get('reason', '')
    if reason not in dict(UserReport.REASON_CHOICES):
        return JsonResponse({'success': False, 'error': 'Choose a valid reason.'}, status=400)
    since = timezone.now() - timedelta(hours=24)
    if UserReport.objects.filter(reporter=request.user, reported=target, reason=reason, created_at__gte=since).exists():
        # Same report already filed today: succeed quietly instead of flooding the review queue.
        return JsonResponse({'success': True})
    UserReport.objects.create(
        reporter=request.user, reported=target, reason=reason,
        details=request.POST.get('details', '')[:2000])
    return JsonResponse({'success': True})
