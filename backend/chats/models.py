from django.db import models
from django.contrib.auth import get_user_model
from matches.models import Match
from django.utils import timezone
import uuid

User = get_user_model()

class VideoRoom(models.Model):
    """Model for video chat rooms linked to matches."""
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='video_room')
    room_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Room {self.room_id} for {self.match}"
    
    def get_participants(self):
        """Get the two users who can access this room."""
        return [self.match.user1, self.match.user2]
    
    def can_user_access(self, user):
        """Check if a user has access to this room."""
        return user in self.get_participants()

class CallInvitation(models.Model):
    """Model for video call invitations between matched users."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'), 
        ('declined', 'Declined'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    room = models.ForeignKey(VideoRoom, on_delete=models.CASCADE, related_name='invitations')
    caller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_call_invitations')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_call_invitations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    message = models.TextField(blank=True, help_text="Optional message from caller")
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Call invitation from {self.caller.username} to {self.receiver.username}"
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Invitations expire after 2 minutes
            self.expires_at = timezone.now() + timezone.timedelta(minutes=2)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at and self.status == 'pending'
    
    def can_accept(self):
        return self.status == 'pending' and not self.is_expired()

class UserPresence(models.Model):
    """Track user online presence for better video chat UX."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='presence')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    current_room = models.ForeignKey(VideoRoom, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        status = "Online" if self.is_online else f"Last seen {self.last_seen}"
        return f"{self.user.username} - {status}"
    
    @classmethod
    def update_presence(cls, user, is_online=True, room=None):
        """Update user presence status."""
        presence, created = cls.objects.get_or_create(user=user)
        presence.is_online = is_online
        if room:
            presence.current_room = room
        elif not is_online:
            presence.current_room = None
        presence.save()
        return presence

class CallSession(models.Model):
    """Model to track video call sessions and analytics."""
    STATUS_CHOICES = [
        ('starting', 'Starting'),
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('failed', 'Failed'),
    ]
    
    room = models.ForeignKey(VideoRoom, on_delete=models.CASCADE, related_name='sessions')
    participants = models.ManyToManyField(User, related_name='call_sessions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='starting')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    
    # Analytics fields
    video_enabled = models.BooleanField(default=True)
    audio_enabled = models.BooleanField(default=True)
    connection_quality = models.CharField(max_length=20, blank=True)  # good, fair, poor
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Call session in {self.room.room_id} at {self.started_at}"
    
    def calculate_duration(self):
        """Calculate session duration when it ends."""
        if self.ended_at and self.started_at:
            self.duration = self.ended_at - self.started_at
            self.save()

class RoomMessage(models.Model):
    """Model for chat messages within video rooms."""
    room = models.ForeignKey(VideoRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"Message from {self.sender.username} in {self.room.room_id}"
