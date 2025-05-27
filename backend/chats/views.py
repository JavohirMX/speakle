from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from matches.models import Match
from .models import VideoRoom, CallSession
import uuid

# Create your views here.

@login_required
def create_video_room(request, match_id):
    """Create or get existing video room for a match."""
    match = get_object_or_404(Match, id=match_id)
    
    # Check if user is part of this match
    if request.user not in [match.user1, match.user2]:
        messages.error(request, 'You do not have access to this match.')
        return redirect('matches:my_matches')
    
    # Get or create video room
    video_room, created = VideoRoom.objects.get_or_create(match=match)
    
    if created:
        messages.success(request, 'Video room created successfully!')
    
    return redirect('chats:video_room', room_id=video_room.room_id)

@login_required
def video_room(request, room_id):
    """Main video chat room view."""
    try:
        room = VideoRoom.objects.get(room_id=room_id)
    except VideoRoom.DoesNotExist:
        messages.error(request, 'Video room not found.')
        return redirect('matches:my_matches')
    
    # Check if user has access to this room
    if not room.can_user_access(request.user):
        messages.error(request, 'You do not have access to this room.')
        return redirect('matches:my_matches')
    
    # Get partner and language info
    partner = room.match.get_partner(request.user)
    user_teaches = room.match.get_user_teaches(request.user)
    user_learns = room.match.get_user_learns(request.user)
    
    # Get recent messages
    recent_messages = room.messages.all()[:50]
    
    # Get call history
    call_history = room.sessions.filter(status='ended')[:10]
    
    context = {
        'room': room,
        'match': room.match,
        'partner': partner,
        'user_teaches': user_teaches,
        'user_learns': user_learns,
        'recent_messages': recent_messages,
        'call_history': call_history,
        'room_id_str': str(room.room_id),
    }
    
    return render(request, 'chats/video_room.html', context)

@login_required
def room_status(request, room_id):
    """API endpoint to get room status (AJAX)."""
    try:
        room = VideoRoom.objects.get(room_id=room_id)
        
        if not room.can_user_access(request.user):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        active_session = room.sessions.filter(status='active').first()
        
        return JsonResponse({
            'is_active': room.is_active,
            'has_active_session': bool(active_session),
            'participant_count': active_session.participants.count() if active_session else 0,
            'last_activity': room.last_activity.isoformat(),
        })
        
    except VideoRoom.DoesNotExist:
        return JsonResponse({'error': 'Room not found'}, status=404)

@login_required
def call_history(request, room_id):
    """View call history for a room."""
    try:
        room = VideoRoom.objects.get(room_id=room_id)
    except VideoRoom.DoesNotExist:
        messages.error(request, 'Video room not found.')
        return redirect('matches:my_matches')
    
    if not room.can_user_access(request.user):
        messages.error(request, 'You do not have access to this room.')
        return redirect('matches:my_matches')
    
    sessions = room.sessions.filter(status='ended').order_by('-started_at')
    
    context = {
        'room': room,
        'sessions': sessions,
        'partner': room.match.get_partner(request.user),
    }
    
    return render(request, 'chats/call_history.html', context)
