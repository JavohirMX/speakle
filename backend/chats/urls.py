from django.urls import path
from . import views

app_name = 'chats'

urlpatterns = [
    path('create-room/<int:match_id>/', views.create_video_room, name='create_room'),
    path('room/<uuid:room_id>/', views.video_room, name='video_room'),
    path('room/<uuid:room_id>/status/', views.room_status, name='room_status'),
    path('room/<uuid:room_id>/history/', views.call_history, name='call_history'),
] 