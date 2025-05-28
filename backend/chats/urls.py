from django.urls import path
from . import views

app_name = 'chats'

urlpatterns = [
    path('create-room/<int:match_id>/', views.create_video_room, name='create_room'),
    path('api/room-url/<int:match_id>/', views.get_video_room_url, name='get_room_url'),
    path('room/<uuid:room_id>/', views.video_room, name='video_room'),
    path('room/<uuid:room_id>/status/', views.room_status, name='room_status'),
    path('room/<uuid:room_id>/history/', views.call_history, name='call_history'),
    
    # Call invitation endpoints
    path('invite/<int:match_id>/', views.send_call_invitation, name='send_invitation'),
    path('invitation/<int:invitation_id>/respond/', views.respond_to_invitation, name='respond_invitation'),
    path('invitation/<int:invitation_id>/cancel/', views.cancel_invitation, name='cancel_invitation'),
    path('invitation/<int:invitation_id>/status/', views.check_invitation_status, name='invitation_status'),
    path('api/pending-invitations/', views.get_pending_invitations, name='pending_invitations'),
    path('api/partner-availability/<int:match_id>/', views.check_partner_availability, name='partner_availability'),
    path('api/set-online-status/', views.set_online_status, name='set_online_status'),
] 