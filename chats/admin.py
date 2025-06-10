from django.contrib import admin
from .models import VideoRoom, CallSession, RoomMessage

@admin.register(VideoRoom)
class VideoRoomAdmin(admin.ModelAdmin):
    list_display = ['room_id', 'match', 'is_active', 'created_at', 'last_activity']
    list_filter = ['is_active', 'created_at']
    readonly_fields = ['room_id', 'created_at']
    search_fields = ['match__user1__username', 'match__user2__username']

@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display = ['room', 'status', 'started_at', 'duration', 'video_enabled', 'audio_enabled']
    list_filter = ['status', 'video_enabled', 'audio_enabled', 'started_at']
    readonly_fields = ['started_at', 'duration']
    filter_horizontal = ['participants']

@admin.register(RoomMessage)
class RoomMessageAdmin(admin.ModelAdmin):
    list_display = ['room', 'sender', 'content_preview', 'timestamp']
    list_filter = ['timestamp']
    readonly_fields = ['timestamp']
    search_fields = ['sender__username', 'content']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Message Preview'
