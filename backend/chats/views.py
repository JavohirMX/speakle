from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from matches.models import Match
from .models import VideoRoom, CallSession, CallInvitation, UserPresence
import uuid

# Utility function for sending WebSocket notifications
def send_user_notification(user_id, notification_type, data):
    """Send a WebSocket notification to a specific user."""
    channel_layer = get_channel_layer()
    group_name = f'user_notifications_{user_id}'
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': notification_type,
            **data
        }
    )

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
def get_video_room_url(request, match_id):
    """API endpoint to get video room URL for a match."""
    match = get_object_or_404(Match, id=match_id)
    
    # Check if user is part of this match
    if request.user not in [match.user1, match.user2]:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get or create video room
    video_room, created = VideoRoom.objects.get_or_create(match=match)
    
    return JsonResponse({
        'success': True,
        'room_url': f'/chats/room/{video_room.room_id}/',
        'room_id': str(video_room.room_id),
        'created': created
    })

@login_required 
@require_POST
def send_call_invitation(request, match_id):
    """Send a call invitation to the match partner."""
    match = get_object_or_404(Match, id=match_id)
    
    # Check if user is part of this match
    if request.user not in [match.user1, match.user2]:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get partner
    partner = match.get_partner(request.user)
    
    # Check if partner is online (create presence if doesn't exist)
    partner_presence, created = UserPresence.objects.get_or_create(
        user=partner,
        defaults={'is_online': False}
    )
    
    if not partner_presence.is_online:
        return JsonResponse({
            'error': 'Partner is not online',
            'last_seen': partner_presence.last_seen.isoformat()
        }, status=400)
    
    # Get or create video room
    video_room, created = VideoRoom.objects.get_or_create(match=match)
    
    # Check for existing pending invitation
    existing_invitation = CallInvitation.objects.filter(
        room=video_room,
        caller=request.user,
        status='pending'
    ).first()
    
    if existing_invitation and not existing_invitation.is_expired():
        return JsonResponse({'error': 'You already have a pending invitation'}, status=400)
    
    # Create new invitation
    invitation = CallInvitation.objects.create(
        room=video_room,
        caller=request.user,
        receiver=partner,
        message=request.POST.get('message', ''),
    )
    
    # Send real-time notification to partner via WebSocket
    send_user_notification(partner.id, 'call_invitation_received', {
        'invitation_id': invitation.id,
        'caller_username': request.user.username,
        'caller_id': request.user.id,
        'message': invitation.message,
        'match_id': match.id,
        'expires_at': invitation.expires_at.isoformat(),
        'room_url': f'/chats/room/{video_room.room_id}/'
    })
    
    return JsonResponse({
        'success': True,
        'invitation_id': invitation.id,
        'expires_at': invitation.expires_at.isoformat()
    })

@login_required
@require_POST
def respond_to_invitation(request, invitation_id):
    """Accept or decline a call invitation."""
    invitation = get_object_or_404(CallInvitation, id=invitation_id, receiver=request.user)
    
    if not invitation.can_accept():
        return JsonResponse({'error': 'Invitation expired or already responded'}, status=400)
    
    response = request.POST.get('response')  # 'accept' or 'decline'
    
    if response == 'accept':
        invitation.status = 'accepted'
        invitation.responded_at = timezone.now()
        invitation.save()
        
        # Notify caller via WebSocket
        send_user_notification(invitation.caller.id, 'call_invitation_accepted', {
            'invitation_id': invitation.id,
            'accepter_username': request.user.username,
            'room_url': f'/chats/room/{invitation.room.room_id}/'
        })
        
        return JsonResponse({
            'success': True,
            'action': 'accepted',
            'room_url': f'/chats/room/{invitation.room.room_id}/'
        })
    
    elif response == 'decline':
        invitation.status = 'declined'
        invitation.responded_at = timezone.now()
        invitation.save()
        
        # Notify caller via WebSocket
        send_user_notification(invitation.caller.id, 'call_invitation_declined', {
            'invitation_id': invitation.id,
            'decliner_username': request.user.username
        })
        
        return JsonResponse({
            'success': True,
            'action': 'declined'
        })
    
    else:
        return JsonResponse({'error': 'Invalid response'}, status=400)

@login_required
def get_pending_invitations(request):
    """Get pending call invitations for the current user."""
    invitations = CallInvitation.objects.filter(
        receiver=request.user,
        status='pending'
    ).select_related('caller', 'room__match')
    
    # Filter out expired invitations
    valid_invitations = [inv for inv in invitations if not inv.is_expired()]
    
    # Mark expired ones
    expired_ids = [inv.id for inv in invitations if inv.is_expired()]
    if expired_ids:
        CallInvitation.objects.filter(id__in=expired_ids).update(status='expired')
    
    invitation_data = []
    for invitation in valid_invitations:
        invitation_data.append({
            'id': invitation.id,
            'caller': invitation.caller.username,
            'caller_id': invitation.caller.id,
            'message': invitation.message,
            'created_at': invitation.created_at.isoformat(),
            'expires_at': invitation.expires_at.isoformat(),
            'match_id': invitation.room.match.id
        })
    
    return JsonResponse({'invitations': invitation_data})

@login_required
def check_invitation_status(request, invitation_id):
    """Check the status of a sent invitation."""
    invitation = get_object_or_404(CallInvitation, id=invitation_id, caller=request.user)
    
    return JsonResponse({
        'status': invitation.status,
        'responded_at': invitation.responded_at.isoformat() if invitation.responded_at else None,
        'is_expired': invitation.is_expired()
    })

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

@login_required
def check_partner_availability(request, match_id):
    """Check if the partner in a match is online and available."""
    match = get_object_or_404(Match, id=match_id)
    
    # Check if user is part of this match
    if request.user not in [match.user1, match.user2]:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    # Get partner
    partner = match.get_partner(request.user)
    
    # Get or create partner presence
    partner_presence, created = UserPresence.objects.get_or_create(
        user=partner,
        defaults={'is_online': False}
    )
    
    # Also ensure current user has presence record
    user_presence, created = UserPresence.objects.get_or_create(
        user=request.user,
        defaults={'is_online': True}  # Assume online since they're making this request
    )
    user_presence.is_online = True
    user_presence.save()
    
    return JsonResponse({
        'is_online': partner_presence.is_online,
        'last_seen': partner_presence.last_seen.isoformat(),
        'partner_username': partner.username
    })

@login_required
@require_POST
def set_online_status(request):
    """Set current user's online status (for testing purposes)."""
    is_online = request.POST.get('is_online', 'true').lower() == 'true'
    
    presence, created = UserPresence.objects.get_or_create(
        user=request.user,
        defaults={'is_online': is_online}
    )
    presence.is_online = is_online
    presence.save()
    
    return JsonResponse({
        'success': True,
        'is_online': is_online,
        'message': f'Status set to {"online" if is_online else "offline"}'
    })

@login_required
@require_POST
def cancel_invitation(request, invitation_id):
    """Cancel a pending call invitation."""
    invitation = get_object_or_404(CallInvitation, id=invitation_id, caller=request.user)
    
    if invitation.status != 'pending':
        return JsonResponse({'error': 'Can only cancel pending invitations'}, status=400)
    
    invitation.status = 'cancelled'
    invitation.responded_at = timezone.now()
    invitation.save()
    
    # Notify receiver via WebSocket that invitation was cancelled
    send_user_notification(invitation.receiver.id, 'call_invitation_cancelled', {
        'invitation_id': invitation.id,
        'canceller_username': request.user.username
    })
    
    return JsonResponse({
        'success': True,
        'message': 'Invitation cancelled successfully'
    })

@login_required
def get_recent_messages(request, room_id):
    """API endpoint to get recent messages for a room."""
    try:
        room = VideoRoom.objects.get(room_id=room_id)
        
        if not room.can_user_access(request.user):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get recent messages (last 50)
        messages = room.messages.select_related('sender').order_by('-timestamp')[:50]
        messages = list(reversed(messages))  # Reverse to get chronological order
        
        message_data = []
        for message in messages:
            message_data.append({
                'id': message.id,
                'content': message.content,
                'sender_id': message.sender.id,
                'sender_username': message.sender.username,
                'timestamp': message.timestamp.isoformat(),
                'is_own_message': message.sender == request.user
            })
        
        return JsonResponse({
            'success': True,
            'messages': message_data
        })
        
    except VideoRoom.DoesNotExist:
        return JsonResponse({'error': 'Room not found'}, status=404)

@login_required
@require_POST
def end_call_with_reason(request, room_id):
    """End a call with specified reason and optional feedback."""
    try:
        room = VideoRoom.objects.get(room_id=room_id)
        
        if not room.can_user_access(request.user):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get form data
        end_reason = request.POST.get('end_reason', 'user_hangup')
        end_notes = request.POST.get('end_notes', '')
        connection_quality = request.POST.get('connection_quality', '')
        
        # End active sessions
        active_sessions = room.sessions.filter(status='active')
        session_summaries = []
        
        for session in active_sessions:
            session.status = 'ended'
            session.ended_at = timezone.now()
            session.ended_by = request.user
            session.end_reason = end_reason
            session.end_notes = end_notes
            if connection_quality:
                session.connection_quality = connection_quality
            session.calculate_duration()
            session.save()
            
            session_summaries.append({
                'session_id': session.id,
                'duration': session.get_duration_display(),
                'was_successful': session.was_successful(),
                'participants': [user.username for user in session.participants.all()]
            })
        
        # Update room status
        room.is_active = False
        room.save()
        
        # Send WebSocket notification to other participants
        send_user_notification(
            room.match.get_partner(request.user).id,
            'call_ended_enhanced',
            {
                'ended_by': request.user.username,
                'end_reason': end_reason,
                'session_summaries': session_summaries
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Call ended successfully',
            'session_summaries': session_summaries
        })
        
    except VideoRoom.DoesNotExist:
        return JsonResponse({'error': 'Room not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_call_statistics(request, room_id):
    """Get call statistics for a room."""
    try:
        room = VideoRoom.objects.get(room_id=room_id)
        
        if not room.can_user_access(request.user):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get session statistics
        sessions = room.sessions.filter(status='ended')
        total_sessions = sessions.count()
        successful_sessions = sessions.filter(
            end_reason__in=['normal', 'user_hangup', 'partner_hangup']
        ).count()
        
        # Calculate total call time
        total_duration = sum(
            [session.duration.total_seconds() for session in sessions if session.duration],
            0
        )
        
        # Average session duration
        avg_duration = total_duration / total_sessions if total_sessions > 0 else 0
        
        # Most common end reasons
        end_reasons = sessions.values('end_reason').annotate(
            count=Count('end_reason')
        ).order_by('-count')
        
        statistics = {
            'total_sessions': total_sessions,
            'successful_sessions': successful_sessions,
            'success_rate': (successful_sessions / total_sessions * 100) if total_sessions > 0 else 0,
            'total_duration_minutes': total_duration / 60,
            'average_duration_minutes': avg_duration / 60,
            'end_reasons': list(end_reasons),
            'recent_sessions': [
                {
                    'id': session.id,
                    'started_at': session.started_at.isoformat(),
                    'duration': session.get_duration_display(),
                    'end_reason': session.get_end_reason_display() if session.end_reason else 'Unknown',
                    'was_successful': session.was_successful(),
                    'ended_by': session.ended_by.username if session.ended_by else 'Unknown'
                }
                for session in sessions[:5]
            ]
        }
        
        return JsonResponse({
            'success': True,
            'statistics': statistics
        })
        
    except VideoRoom.DoesNotExist:
        return JsonResponse({'error': 'Room not found'}, status=404)

@login_required
def call_summary(request, room_id, session_id):
    """Display call summary and statistics after a call ends."""
    try:
        room = VideoRoom.objects.get(room_id=room_id)
        session = CallSession.objects.get(id=session_id, room=room)
        
        # Check if user has access to this room and session
        if not room.can_user_access(request.user):
            messages.error(request, 'You do not have access to this room.')
            return redirect('matches:my_matches')
        
        # Check if user was a participant in this session
        # If they weren't but have room access, add them as a participant (retroactive fix)
        if not session.participants.filter(id=request.user.id).exists():
            if room.can_user_access(request.user):
                # User has room access but wasn't marked as participant - fix this
                session.participants.add(request.user)
                print(f"Retroactively added {request.user.username} as participant to session {session.id}")
            else:
                messages.error(request, 'You were not a participant in this call.')
                return redirect('matches:my_matches')
        
        # Get partner and language info
        partner = room.match.get_partner(request.user)
        user_teaches = room.match.get_user_teaches(request.user)
        user_learns = room.match.get_user_learns(request.user)
        
        # Get session statistics
        total_sessions = room.sessions.filter(status='ended').count()
        successful_sessions = room.sessions.filter(
            status='ended',
            end_reason__in=['normal', 'user_hangup', 'partner_hangup']
        ).count()
        
        # Calculate success rate
        success_rate = (successful_sessions / total_sessions * 100) if total_sessions > 0 else 0
        
        # Get recent call history (last 5 calls excluding current)
        recent_calls = room.sessions.filter(status='ended').exclude(id=session.id)[:5]
        
        context = {
            'room': room,
            'session': session,
            'match': room.match,
            'partner': partner,
            'user_teaches': user_teaches,
            'user_learns': user_learns,
            'total_sessions': total_sessions,
            'successful_sessions': successful_sessions,
            'success_rate': success_rate,
            'recent_calls': recent_calls,
        }
        
        return render(request, 'chats/call_summary.html', context)
        
    except VideoRoom.DoesNotExist:
        messages.error(request, 'Video room not found.')
        return redirect('matches:my_matches')
    except CallSession.DoesNotExist:
        messages.error(request, 'Call session not found.')
        return redirect('matches:my_matches')
    except Exception as e:
        messages.error(request, f'Error loading call summary: {str(e)}')
        return redirect('matches:my_matches')

@login_required
@require_POST
def submit_feedback(request):
    """Submit feedback for a call session."""
    try:
        import json
        data = json.loads(request.body)
        
        session_id = data.get('session_id')
        rating = data.get('rating')
        room_id = data.get('room_id')
        
        if not all([session_id, rating, room_id]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        # Validate rating
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return JsonResponse({'error': 'Invalid rating'}, status=400)
        
        # Get session and verify user access
        session = CallSession.objects.get(id=session_id)
        room = VideoRoom.objects.get(room_id=room_id)
        
        if not room.can_user_access(request.user):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        if not session.participants.filter(id=request.user.id).exists():
            return JsonResponse({'error': 'You were not a participant in this call'}, status=403)
        
        # For now, we can store this in the session's end_notes or create a separate model
        # Let's append it to end_notes for simplicity
        feedback_text = f"User {request.user.username} rated this call: {rating}/5 stars"
        
        if session.end_notes:
            session.end_notes += f"\n{feedback_text}"
        else:
            session.end_notes = feedback_text
        
        session.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Feedback submitted successfully'
        })
        
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except CallSession.DoesNotExist:
        return JsonResponse({'error': 'Call session not found'}, status=404)
    except VideoRoom.DoesNotExist:
        return JsonResponse({'error': 'Room not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
