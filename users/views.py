from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from .forms import UserRegistrationForm, UserProfileForm, UserLanguageForm
from .models import UserLanguage, UserBlock, UserReport

def register_view(request):
    """User registration view."""
    if request.user.is_authenticated:
        return redirect('main:home')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            native_lang = form.cleaned_data.get('native_language').name
            target_lang = form.cleaned_data.get('target_language').name
            messages.success(request, f'Welcome to Speakle, {username}! Your profile is set up with {native_lang} as your native language and {target_lang} as your learning target. You can now log in and add more languages to your profile.')
            return redirect('users:login')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('main:home')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('main:home')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})

def logout_view(request):
    """User logout view."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('main:home')

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
    
    return render(request, 'users/profile.html', {
        'form': form,
        'user_languages': user_languages
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
    UserReport.objects.create(
        reporter=request.user, reported=target, reason=reason,
        details=request.POST.get('details', '')[:2000])
    return JsonResponse({'success': True})
