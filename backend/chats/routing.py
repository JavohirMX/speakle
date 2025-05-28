from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/video/(?P<room_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/$', consumers.VideoCallConsumer.as_asgi()),
    re_path(r'ws/notifications/$', consumers.UserNotificationConsumer.as_asgi()),
] 