from django.urls import path
from . import views

app_name = 'chats'

urlpatterns = [
    # Video room management
    path('create-room/<int:match_id>/', views.create_video_room, name='create_video_room'),
    path('room/<uuid:room_id>/', views.video_room, name='video_room'),
    path('api/room-url/<int:match_id>/', views.get_video_room_url, name='get_video_room_url'),
    path('api/room-status/<uuid:room_id>/', views.room_status, name='room_status'),
    path('api/recent-messages/<uuid:room_id>/', views.get_recent_messages, name='get_recent_messages'),
    
    # Call management
    path('api/send-invitation/<int:match_id>/', views.send_call_invitation, name='send_call_invitation'),
    path('api/respond-invitation/<int:invitation_id>/', views.respond_to_invitation, name='respond_to_invitation'),
    path('api/cancel-invitation/<int:invitation_id>/', views.cancel_invitation, name='cancel_invitation'),
    path('api/pending-invitations/', views.get_pending_invitations, name='get_pending_invitations'),
    path('api/invitation-status/<int:invitation_id>/', views.check_invitation_status, name='check_invitation_status'),
    
    # Enhanced call end features
    path('api/end-call/<uuid:room_id>/', views.end_call_with_reason, name='end_call_with_reason'),
    path('api/call-statistics/<uuid:room_id>/', views.get_call_statistics, name='get_call_statistics'),
    path('api/submit-feedback/', views.submit_feedback, name='submit_feedback'),
    
    # Partner availability
    path('api/partner-availability/<int:match_id>/', views.check_partner_availability, name='check_partner_availability'),
    path('api/set-online-status/', views.set_online_status, name='set_online_status'),
    
    # Call history
    path('history/<uuid:room_id>/', views.call_history, name='call_history'),
    
    # Call summary
    path('summary/<uuid:room_id>/<int:session_id>/', views.call_summary, name='call_summary'),
] 