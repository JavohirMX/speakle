from django.db import models
from django.contrib.auth import get_user_model
from users.models import Language

User = get_user_model()

class PotentialMatch(models.Model):
    """Model to store potential matches between users based on their language preferences."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='potential_matches')
    potential_partner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='potential_for')
    user_teaches = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='taught_in_matches')
    user_learns = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='learned_in_matches')
    compatibility_score = models.FloatField(default=0.0)  # Score based on proficiency levels and interests
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'potential_partner']
        ordering = ['-compatibility_score', '-created_at']
    
    def __str__(self):
        return f"{self.user.username} ↔ {self.potential_partner.username} ({self.compatibility_score:.2f})"

class Match(models.Model):
    """Model to store confirmed matches between users."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('ended', 'Ended'),
        ('trial', 'Quick match trial'),
    ]
    
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='matches_as_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='matches_as_user2')
    user1_teaches = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='matches_taught_by_user1')
    user1_learns = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='matches_learned_by_user1')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(blank=True, null=True)
    
    # Enhanced call end features
    ended_at = models.DateTimeField(blank=True, null=True)
    ended_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ended_matches')
    end_reason = models.TextField(blank=True, help_text="Reason for ending the match")

    # Quick match: timed first call, then both choose keep or skip
    trial_ends_at = models.DateTimeField(blank=True, null=True)
    user1_keep = models.BooleanField(null=True, blank=True)
    user2_keep = models.BooleanField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user1', 'user2']
        ordering = ['-created_at']
    
    def get_partner(self, user):
        """Get the partner user for a given user in this match."""
        if user == self.user1:
            return self.user2
        return self.user1
    
    def get_user_teaches(self, user):
        """Get what language the user teaches in this match."""
        if user == self.user1:
            return self.user1_teaches
        return self.user1_learns  # user2 learns what user1 teaches
    
    def get_user_learns(self, user):
        """Get what language the user learns in this match."""
        if user == self.user1:
            return self.user1_learns
        return self.user1_teaches  # user2 teaches what user1 learns
    
    def __str__(self):
        return f"Match: {self.user1.username} ↔ {self.user2.username} ({self.status})"

class MatchRequest(models.Model):
    """Model to handle match requests before they become confirmed matches."""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_match_requests')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_match_requests')
    sender_teaches = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='taught_in_requests')
    sender_learns = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='learned_in_requests')
    message = models.TextField(blank=True, help_text="Optional message from sender")
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        unique_together = ['sender', 'receiver']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Request: {self.sender.username} → {self.receiver.username} ({self.status})"


class MatchFeedback(models.Model):
    """Private post-call feedback from one partner about a match.

    Only the author (and staff, via admin) can see it. It is not shown to the
    partner, so people can be honest.
    """
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='feedback')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='match_feedback_given')
    rating = models.PositiveSmallIntegerField(help_text="1 (poor) to 5 (great)")
    helpful = models.BooleanField(default=True, help_text="Was the partner a good practice fit?")
    comment = models.TextField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['match', 'author']
        ordering = ['-updated_at']

    def __str__(self):
        return f"Feedback {self.author.username} on match {self.match_id}: {self.rating}/5"
class QuickMatchEntry(models.Model):
    """A user waiting for a quick match. `match` is set when someone pairs with them."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='quick_match_entry')
    teaches = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='+')
    learns = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='+')
    match = models.ForeignKey(Match, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} waiting ({self.teaches} -> {self.learns})"


class MatchSession(models.Model):
    """A scheduled practice session between matched partners.

    One partner proposes a time; the other accepts or declines. Reminders are
    sent by the ``send_session_reminders`` management command (run it on a
    schedule, e.g. cron every 5 minutes).
    """
    STATUS_CHOICES = [
        ('proposed', 'Proposed'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    DURATION_CHOICES = [(15, '15 minutes'), (30, '30 minutes'), (45, '45 minutes'),
                        (60, '1 hour'), (90, '1.5 hours'), (120, '2 hours')]

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='sessions')
    proposed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proposed_sessions')
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(choices=DURATION_CHOICES, default=30)
    note = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='proposed')
    reminder_24h_sent = models.BooleanField(default=False)
    reminder_1h_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['starts_at']
        constraints = [
            models.UniqueConstraint(
                fields=['match'],
                condition=models.Q(status='proposed'),
                name='one_proposed_session_per_match',
            ),
        ]

    def is_participant(self, user):
        return user in (self.match.user1, self.match.user2)

    @property
    def ends_at(self):
        from datetime import timedelta
        return self.starts_at + timedelta(minutes=self.duration_minutes)

    def __str__(self):
        return f"Session: {self.match} at {self.starts_at:%Y-%m-%d %H:%M} ({self.status})"
