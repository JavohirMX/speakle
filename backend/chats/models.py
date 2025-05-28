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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    message = models.TextField(blank=True, help_text="Optional message from caller")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Composite index for the most common query: receiver + status + expires_at
            models.Index(fields=['receiver', 'status', 'expires_at'], name='pending_invitations_idx'),
            # Index for cleanup operations: status + created_at
            models.Index(fields=['status', 'created_at'], name='cleanup_invitations_idx'),
            # Index for caller's sent invitations
            models.Index(fields=['caller', 'status'], name='sent_invitations_idx'),
        ]
    
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
    
    END_REASON_CHOICES = [
        ('normal', 'Normal end'),
        ('user_hangup', 'User hung up'),
        ('partner_hangup', 'Partner hung up'),
        ('connection_lost', 'Connection lost'),
        ('timeout', 'Session timeout'),
        ('technical_issue', 'Technical issue'),
        ('emergency', 'Emergency end'),
        ('network_failure', 'Network failure'),
    ]
    
    room = models.ForeignKey(VideoRoom, on_delete=models.CASCADE, related_name='sessions')
    participants = models.ManyToManyField(User, related_name='call_sessions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='starting')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    
    # Enhanced call end tracking
    ended_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name='ended_calls', help_text='User who ended the call')
    end_reason = models.CharField(max_length=20, choices=END_REASON_CHOICES, 
                                null=True, blank=True, help_text='Reason for call ending')
    end_notes = models.TextField(blank=True, help_text='Additional notes about call ending')
    
    # Analytics fields
    video_enabled = models.BooleanField(default=True)
    audio_enabled = models.BooleanField(default=True)
    connection_quality = models.CharField(max_length=20, blank=True)  # good, fair, poor
    max_participants = models.IntegerField(default=0, help_text='Maximum participants during call')
    disconnection_count = models.IntegerField(default=0, help_text='Number of disconnections during call')
    
    # Performance metrics
    average_video_quality = models.CharField(max_length=20, blank=True)  # HD, SD, Poor
    network_issues_count = models.IntegerField(default=0)
    total_data_transferred = models.BigIntegerField(default=0, help_text='Total data in bytes')
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Call session in {self.room.room_id} at {self.started_at}"
    
    def calculate_duration(self):
        """Calculate session duration when it ends."""
        if self.ended_at and self.started_at:
            self.duration = self.ended_at - self.started_at
            self.save()
    
    def get_duration_display(self):
        """Get human-readable duration."""
        if self.duration:
            total_seconds = int(self.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "Unknown"
    
    def was_successful(self):
        """Check if the call was successfully completed."""
        return self.status == 'ended' and self.end_reason in ['normal', 'user_hangup', 'partner_hangup']
    
    def get_end_reason_display(self):
        """Get human-readable end reason."""
        reason_map = dict(self.END_REASON_CHOICES)
        return reason_map.get(self.end_reason, 'Unknown')

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
