from django.shortcuts import render, redirect, get_object_or_404
from .prompts import conversation_prompts, swap_tip
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.urls import reverse
from .models import PotentialMatch, Match, MatchRequest, MatchFeedback, QuickMatchEntry
from .services import MatchingService
from . import quick
from users.models import Language

@login_required
def find_matches(request):
    """View to find and display potential language exchange partners."""
    # Check if user has languages set up
    user_languages = request.user.userlanguage_set.all()
    has_teaching_langs = user_languages.filter(language_type__in=['native', 'fluent']).exists()
    has_learning_langs = user_languages.filter(language_type='learning').exists()
    
    if not has_teaching_langs or not has_learning_langs:
        messages.warning(request, 'Please set up your languages in your profile to find matches.')
        return redirect('users:profile')
    
    # Get or generate potential matches
    refresh = request.GET.get('refresh', False)
    if refresh:
        MatchingService.find_potential_matches(request.user, refresh=True)
        messages.success(request, 'Matches refreshed!')
    else:
        # Only generate if no existing matches
        existing_matches = PotentialMatch.objects.filter(user=request.user)
        if not existing_matches.exists():
            MatchingService.find_potential_matches(request.user)
    
    # Get potential matches
    potential_matches = PotentialMatch.objects.filter(user=request.user).select_related(
        'potential_partner', 'user_teaches', 'user_learns')[:20]  # Limit to 20
    
    # Get existing match requests to avoid duplicates
    sent_requests = MatchRequest.objects.filter(
        sender=request.user,
        status='pending'
    ).values_list('receiver_id', flat=True)
    sent_requests = set(sent_requests)
    
    # Get confirmed matches to avoid showing them again
    confirmed_matches = Match.objects.filter(
        Q(user1=request.user) | Q(user2=request.user),
        status='active'
    ).select_related('user1', 'user2')
    confirmed_partner_ids = []
    for match in confirmed_matches:
        partner = match.get_partner(request.user)
        confirmed_partner_ids.append(partner.id)
    
    context = {
        'potential_matches': potential_matches,
        'sent_requests': sent_requests,
        'confirmed_partner_ids': confirmed_partner_ids,
    }
    
    return render(request, 'matches/find_matches.html', context)

@login_required
def send_match_request(request, potential_match_id):
    """Send a match request to a potential partner."""
    potential_match = get_object_or_404(PotentialMatch, id=potential_match_id, user=request.user)
    
    if request.method == 'POST':
        message = request.POST.get('message', '')
        
        match_request, created = MatchingService.send_match_request(
            sender=request.user,
            receiver=potential_match.potential_partner,
            sender_teaches_lang=potential_match.user_teaches,
            sender_learns_lang=potential_match.user_learns,
            message=message
        )
        
        if created:
            messages.success(request, f'Match request sent to {potential_match.potential_partner.username}!')
        else:
            messages.info(request, 'Match request already exists.')
        
        return redirect('matches:find_matches')
    
    context = {
        'potential_match': potential_match,
    }
    
    return render(request, 'matches/send_request.html', context)

@login_required
def match_requests(request):
    """View to show incoming and outgoing match requests."""
    incoming_requests = MatchRequest.objects.filter(
        receiver=request.user,
        status='pending'
    ).order_by('-created_at')
    
    outgoing_requests = MatchRequest.objects.filter(
        sender=request.user
    ).order_by('-created_at')
    
    context = {
        'incoming_requests': incoming_requests,
        'outgoing_requests': outgoing_requests,
    }
    
    return render(request, 'matches/requests.html', context)

@login_required
def respond_to_request(request, request_id):
    """Respond to a match request (accept or decline)."""
    match_request = get_object_or_404(MatchRequest, id=request_id, receiver=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'accept':
            match = MatchingService.respond_to_match_request(match_request, accept=True)
            if match:
                messages.success(request, f'Match accepted! You can now chat with {match_request.sender.username}.')
                return redirect('matches:my_matches')
        elif action == 'decline':
            MatchingService.respond_to_match_request(match_request, accept=False)
            messages.info(request, 'Match request declined.')
        
        return redirect('matches:requests')
    
    context = {
        'match_request': match_request,
    }
    
    return render(request, 'matches/respond_request.html', context)

@login_required
def my_matches(request):
    """View to show user's confirmed matches."""
    matches = MatchingService.get_user_matches(request.user, status='active')
    
    # Prepare match data with partner info
    match_data = []
    for match in matches:
        partner = match.get_partner(request.user)
        user_teaches = match.get_user_teaches(request.user)
        user_learns = match.get_user_learns(request.user)
        
        match_data.append({
            'match': match,
            'partner': partner,
            'user_teaches': user_teaches,
            'user_learns': user_learns,
        })
    
    context = {
        'match_data': match_data,
    }
    
    return render(request, 'matches/my_matches.html', context)

@login_required
def match_detail(request, match_id):
    """View to show details of a specific match."""
    match = get_object_or_404(Match, id=match_id)
    
    # Check if user is part of this match
    if request.user not in [match.user1, match.user2]:
        messages.error(request, 'You do not have access to this match.')
        return redirect('matches:my_matches')
    
    partner = match.get_partner(request.user)
    user_teaches = match.get_user_teaches(request.user)
    user_learns = match.get_user_learns(request.user)
    
    context = {
        'match': match,
        'partner': partner,
        'user_teaches': user_teaches,
        'user_learns': user_learns,
        'conversation_prompts': conversation_prompts(),
        'swap_tip': swap_tip(),
        'my_feedback': MatchFeedback.objects.filter(match=match, author=request.user).first(),
    }
    
    return render(request, 'matches/match_detail.html', context)

# ===============================
# API ENDPOINTS (JSON Responses)
# ===============================

@login_required
@require_POST
def send_match_request_api(request, potential_match_id):
    """API endpoint to send a match request to a potential partner."""
    potential_match = get_object_or_404(PotentialMatch, id=potential_match_id, user=request.user)
    
    message = request.POST.get('message', '')
    
    match_request, created = MatchingService.send_match_request(
        sender=request.user,
        receiver=potential_match.potential_partner,
        sender_teaches_lang=potential_match.user_teaches,
        sender_learns_lang=potential_match.user_learns,
        message=message
    )
    
    if created:
        return JsonResponse({
            'success': True,
            'message': f'Match request sent to {potential_match.potential_partner.username}!',
            'request_id': match_request.id,
            'receiver': potential_match.potential_partner.username
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Match request already exists'
        }, status=400)

@login_required
@require_POST
def respond_to_request_api(request, request_id):
    """API endpoint to respond to a match request (accept or decline)."""
    match_request = get_object_or_404(MatchRequest, id=request_id, receiver=request.user)
    
    if match_request.status != 'pending':
        return JsonResponse({'error': 'Request already responded to or expired'}, status=400)
    
    action = request.POST.get('action')  # 'accept' or 'decline'
    
    if action == 'accept':
        match = MatchingService.respond_to_match_request(match_request, accept=True)
        if match:
            return JsonResponse({
                'success': True,
                'action': 'accepted',
                'message': f'Match accepted! You can now chat with {match_request.sender.username}.',
                'match_id': match.id,
                'partner': match_request.sender.username
            })
        else:
            return JsonResponse({'error': 'Failed to create match'}, status=500)
    
    elif action == 'decline':
        MatchingService.respond_to_match_request(match_request, accept=False)
        return JsonResponse({
            'success': True,
            'action': 'declined',
            'message': 'Match request declined.'
        })
    
    else:
        return JsonResponse({'error': 'Invalid action'}, status=400)

@login_required
@require_POST
def cancel_match_request(request, request_id):
    """API endpoint to cancel a pending match request."""
    match_request = get_object_or_404(MatchRequest, id=request_id, sender=request.user)
    
    if match_request.status != 'pending':
        return JsonResponse({'error': 'Request cannot be cancelled'}, status=400)
    
    match_request.status = 'cancelled'
    match_request.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Match request cancelled successfully'
    })

@login_required
def get_pending_requests(request):
    """API endpoint to get pending match requests for the current user."""
    incoming_requests = MatchRequest.objects.filter(
        receiver=request.user,
        status='pending'
    ).select_related('sender').order_by('-created_at')
    
    outgoing_requests = MatchRequest.objects.filter(
        sender=request.user,
        status='pending'
    ).select_related('receiver').order_by('-created_at')
    
    incoming_data = []
    for req in incoming_requests:
        incoming_data.append({
            'id': req.id,
            'sender': req.sender.username,
            'sender_id': req.sender.id,
            'message': req.message,
            'sender_teaches': req.sender_teaches.name if req.sender_teaches else None,
            'sender_learns': req.sender_learns.name if req.sender_learns else None,
            'created_at': req.created_at.isoformat(),
        })
    
    outgoing_data = []
    for req in outgoing_requests:
        outgoing_data.append({
            'id': req.id,
            'receiver': req.receiver.username,
            'receiver_id': req.receiver.id,
            'message': req.message,
            'sender_teaches': req.sender_teaches.name if req.sender_teaches else None,
            'sender_learns': req.sender_learns.name if req.sender_learns else None,
            'created_at': req.created_at.isoformat(),
        })
    
    return JsonResponse({
        'success': True,
        'incoming_requests': incoming_data,
        'outgoing_requests': outgoing_data
    })

@login_required
def check_request_status(request, request_id):
    """API endpoint to check the status of a match request."""
    match_request = get_object_or_404(MatchRequest, id=request_id)
    
    # Check if user has access to this request
    if request.user not in [match_request.sender, match_request.receiver]:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    return JsonResponse({
        'success': True,
        'status': match_request.status,
        'created_at': match_request.created_at.isoformat(),
        'responded_at': match_request.responded_at.isoformat() if match_request.responded_at else None
    })

@login_required
def get_my_matches(request):
    """API endpoint to get user's confirmed matches."""
    matches = MatchingService.get_user_matches(request.user, status='active')
    
    match_data = []
    for match in matches:
        partner = match.get_partner(request.user)
        user_teaches = match.get_user_teaches(request.user)
        user_learns = match.get_user_learns(request.user)
        
        match_data.append({
            'id': match.id,
            'partner': {
                'id': partner.id,
                'username': partner.username,
                'email': partner.email,
            },
            'user_teaches': user_teaches.name if user_teaches else None,
            'user_learns': user_learns.name if user_learns else None,
            'created_at': match.created_at.isoformat(),
            'status': match.status,
        })
    
    return JsonResponse({
        'success': True,
        'matches': match_data
    })

@login_required
def get_match_detail(request, match_id):
    """API endpoint to get details of a specific match."""
    match = get_object_or_404(Match, id=match_id)
    
    # Check if user is part of this match
    if request.user not in [match.user1, match.user2]:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    partner = match.get_partner(request.user)
    user_teaches = match.get_user_teaches(request.user)
    user_learns = match.get_user_learns(request.user)
    
    return JsonResponse({
        'success': True,
        'match': {
            'id': match.id,
            'partner': {
                'id': partner.id,
                'username': partner.username,
                'email': partner.email,
            },
            'user_teaches': user_teaches.name if user_teaches else None,
            'user_learns': user_learns.name if user_learns else None,
            'created_at': match.created_at.isoformat(),
            'status': match.status,
        }
    })

@login_required
@require_POST
def end_match(request, match_id):
    """API endpoint to end/deactivate a match."""
    match = get_object_or_404(Match, id=match_id)
    
    # Check if user is part of this match
    if request.user not in [match.user1, match.user2]:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    reason = request.POST.get('reason', 'No reason provided')
    
    # Update match status
    match.status = 'ended'
    match.ended_at = timezone.now()
    match.ended_by = request.user
    match.end_reason = reason
    match.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Match ended successfully',
        'ended_at': match.ended_at.isoformat()
    })

@login_required
def get_potential_matches(request):
    """API endpoint to get potential matches for the user."""
    # Check if user has languages set up
    user_languages = request.user.userlanguage_set.all()
    has_teaching_langs = user_languages.filter(language_type__in=['native', 'fluent']).exists()
    has_learning_langs = user_languages.filter(language_type='learning').exists()
    
    if not has_teaching_langs or not has_learning_langs:
        return JsonResponse({
            'error': 'Please set up your languages in your profile to find matches'
        }, status=400)
    
    # Get potential matches
    potential_matches = PotentialMatch.objects.filter(user=request.user).select_related(
        'potential_partner', 'user_teaches', 'user_learns')[:20]
    
    # Get existing match requests to avoid duplicates
    sent_requests = MatchRequest.objects.filter(
        sender=request.user,
        status='pending'
    ).values_list('receiver_id', flat=True)
    sent_requests = set(sent_requests)
    
    # Get confirmed matches to avoid showing them again
    confirmed_matches = Match.objects.filter(
        Q(user1=request.user) | Q(user2=request.user),
        status='active'
    ).select_related('user1', 'user2')
    confirmed_partner_ids = [match.get_partner(request.user).id for match in confirmed_matches]
    
    matches_data = []
    for potential_match in potential_matches:
        partner = potential_match.potential_partner
        matches_data.append({
            'id': potential_match.id,
            'partner': {
                'id': partner.id,
                'username': partner.username,
            },
            'user_teaches': potential_match.user_teaches.name if potential_match.user_teaches else None,
            'user_learns': potential_match.user_learns.name if potential_match.user_learns else None,
            'compatibility_score': potential_match.compatibility_score,
            'has_sent_request': partner.id in sent_requests,
            'is_confirmed_partner': partner.id in confirmed_partner_ids,
        })
    
    return JsonResponse({
        'success': True,
        'potential_matches': matches_data
    })

@login_required
@require_POST
def refresh_potential_matches(request):
    """API endpoint to refresh potential matches for the user."""
    # Check if user has languages set up
    user_languages = request.user.userlanguage_set.all()
    has_teaching_langs = user_languages.filter(language_type__in=['native', 'fluent']).exists()
    has_learning_langs = user_languages.filter(language_type='learning').exists()
    
    if not has_teaching_langs or not has_learning_langs:
        return JsonResponse({
            'error': 'Please set up your languages in your profile to find matches'
        }, status=400)
    
    # Refresh matches
    MatchingService.find_potential_matches(request.user, refresh=True)
    
    return JsonResponse({
        'success': True,
        'message': 'Matches refreshed successfully!'
    })

@login_required
def get_match_statistics(request, match_id):
    """API endpoint to get statistics for a specific match."""
    match = get_object_or_404(Match, id=match_id)
    
    # Check if user is part of this match
    if request.user not in [match.user1, match.user2]:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Calculate basic statistics
    partner = match.get_partner(request.user)
    days_active = (timezone.now() - match.created_at).days
    
    # You can extend this with more statistics from related models
    # For example, call sessions, messages exchanged, etc.
    
    statistics = {
        'days_active': days_active,
        'created_at': match.created_at.isoformat(),
        'status': match.status,
        'partner': {
            'username': partner.username,
            'id': partner.id
        }
    }
    
    # Add call statistics if chats app is available
    try:
        from chats.models import VideoRoom, CallSession
        video_room = VideoRoom.objects.filter(match=match).first()
        if video_room:
            call_sessions = CallSession.objects.filter(room=video_room)
            statistics.update({
                'total_calls': call_sessions.count(),
                'total_call_duration': sum(
                    (session.ended_at - session.started_at).total_seconds() 
                    for session in call_sessions if session.ended_at
                ) / 60,  # in minutes
            })
    except ImportError:
        pass
    
    return JsonResponse({
        'success': True,
        'statistics': statistics
    })


@login_required
@require_POST
def submit_feedback(request, match_id):
    """Save (or update) the current user's private feedback for a match."""
    match = get_object_or_404(Match, id=match_id)
    if request.user not in [match.user1, match.user2]:
        return JsonResponse({'error': 'Access denied'}, status=403)

    try:
        rating = int(request.POST.get('rating', ''))
    except ValueError:
        return JsonResponse({'error': 'Rating must be a number from 1 to 5'}, status=400)
    if not 1 <= rating <= 5:
        return JsonResponse({'error': 'Rating must be a number from 1 to 5'}, status=400)

    helpful = request.POST.get('helpful', 'true').lower() not in ('false', '0', 'no')
    comment = request.POST.get('comment', '').strip()[:500]

    fb, created = MatchFeedback.objects.update_or_create(
        match=match, author=request.user,
        defaults={'rating': rating, 'helpful': helpful, 'comment': comment},
    )
    return JsonResponse({'success': True, 'created': created, 'rating': fb.rating})
# ===============================
# QUICK MATCH
# ===============================

def _quick_payload(match):
    return {'status': 'matched', 'match_id': match.id,
            'url': reverse('matches:quick_match_call', args=[match.id])}


@login_required
def quick_match_page(request):
    pair = quick.default_language_pair(request.user)
    return render(request, 'matches/quick_match.html', {
        'pair': pair,
        'can_use': quick.can_quick_match(request.user),
        'has_email': bool(request.user.email),
    })


@login_required
@require_POST
def quick_match_join(request):
    try:
        match = quick.join_queue(request.user)
    except quick.QuickMatchError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    if match:
        return JsonResponse({'success': True, **_quick_payload(match)})
    return JsonResponse({'success': True, 'status': 'waiting'})


@login_required
def quick_match_status(request):
    match = quick.poll(request.user)
    if match:
        return JsonResponse({'success': True, **_quick_payload(match)})
    waiting = QuickMatchEntry.objects.filter(user=request.user, match__isnull=True).exists()
    return JsonResponse({'success': True, 'status': 'waiting' if waiting else 'idle'})


@login_required
@require_POST
def quick_match_leave(request):
    quick.leave_queue(request.user)
    return JsonResponse({'success': True})


@login_required
def quick_match_call(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.user not in [match.user1, match.user2]:
        messages.error(request, 'You do not have access to this match.')
        return redirect('matches:my_matches')
    mine = match.user1_keep if request.user == match.user1 else match.user2_keep
    ends_at = match.trial_ends_at
    remaining = max(0, int((ends_at - timezone.now()).total_seconds())) if ends_at else 0
    return render(request, 'matches/quick_match_call.html', {
        'match': match,
        'partner': match.get_partner(request.user),
        'remaining_seconds': remaining,
        'my_choice': mine,
    })


@login_required
@require_POST
def quick_match_decide(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.user not in [match.user1, match.user2]:
        return JsonResponse({'error': 'Access denied'}, status=403)
    if request.POST.get('choice') not in ('keep', 'skip'):
        return JsonResponse({'error': 'choice must be keep or skip'}, status=400)
    try:
        match = quick.decide(match, request.user, request.POST['choice'] == 'keep')
    except quick.QuickMatchError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': True, 'status': match.status})


@login_required
def quick_match_result(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.user not in [match.user1, match.user2]:
        return JsonResponse({'error': 'Access denied'}, status=403)
    return JsonResponse({'status': match.status})
