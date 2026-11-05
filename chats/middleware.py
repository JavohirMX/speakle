import logging

from django.utils import timezone
from django.contrib.auth.models import User
from .models import UserPresence

logger = logging.getLogger(__name__)


class UserActivityMiddleware:
    """
    Middleware to automatically track user activity and update online status.
    This middleware will:
    1. Set users online when they make requests
    2. Update their last_seen timestamp
    3. Allow automatic offline detection based on inactivity
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request before view
        if hasattr(request, 'user') and request.user.is_authenticated:
            self.update_user_presence(request.user)
        
        # Process the request through the view
        response = self.get_response(request)
        
        return response

    def update_user_presence(self, user):
        """
        Update user presence to mark them as online and update last_seen time.
        """
        try:
            # One UPDATE for the common case (row exists) instead of SELECT + UPDATE. Same end
            # state as before: online, last_seen now, last_activity untouched.
            now = timezone.now()
            updated = UserPresence.objects.filter(user=user).update(is_online=True, last_seen=now)
            if not updated:
                presence, created = UserPresence.objects.get_or_create(
                    user=user,
                    defaults={'is_online': True}
                )
                if not created:  # lost a creation race: apply the same update
                    UserPresence.objects.filter(pk=presence.pk).update(is_online=True, last_seen=now)

        except Exception as e:
            # Silently handle any database errors to avoid breaking requests
            logger.exception(f"Error updating user presence for {user.username}: {e}")