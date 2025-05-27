from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import PotentialMatch, Match, MatchRequest
from .services import MatchingService
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
    potential_matches = PotentialMatch.objects.filter(user=request.user)[:20]  # Limit to 20
    
    # Get existing match requests to avoid duplicates
    sent_requests = MatchRequest.objects.filter(
        sender=request.user,
        status='pending'
    ).values_list('receiver_id', flat=True)
    
    # Get confirmed matches to avoid showing them again
    confirmed_matches = Match.objects.filter(
        Q(user1=request.user) | Q(user2=request.user),
        status='active'
    )
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
    }
    
    return render(request, 'matches/match_detail.html', context)
