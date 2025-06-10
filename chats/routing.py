from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/video/(?P<room_id>[^/]+)/$', consumers.VideoCallConsumer.as_asgi()),
    re_path(r'ws/notifications/$', consumers.UserNotificationConsumer.as_asgi()),
    re_path(r'ws/text-chat/(?P<room_id>[^/]+)/$', consumers.TextChatConsumer.as_asgi()),
] 