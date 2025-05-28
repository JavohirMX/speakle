from django.core.management.base import BaseCommand
from django.utils import timezone
from chats.models import CallInvitation
from datetime import timedelta

class Command(BaseCommand):
    help = 'Cleanup expired call invitations from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Delete invitations older than this many days (default: 7)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        # Calculate cutoff time
        cutoff_time = timezone.now() - timedelta(days=days)
        
        # Find expired invitations
        expired_invitations = CallInvitation.objects.filter(
            created_at__lt=cutoff_time
        ).exclude(status='pending')  # Don't delete pending ones, just mark them expired
        
        # Find pending invitations that should be marked as expired
        pending_expired = CallInvitation.objects.filter(
            status='pending',
            expires_at__lt=timezone.now()
        )
        
        expired_count = expired_invitations.count()
        pending_count = pending_expired.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN - Would delete {expired_count} old invitations")
            )
            self.stdout.write(
                self.style.WARNING(f"DRY RUN - Would mark {pending_count} pending invitations as expired")
            )
            
            if expired_count > 0:
                self.stdout.write("Old invitations to delete:")
                for invitation in expired_invitations[:10]:  # Show first 10
                    self.stdout.write(f"  - ID {invitation.id}: {invitation.caller.username} -> {invitation.receiver.username} ({invitation.status}) - {invitation.created_at}")
                if expired_count > 10:
                    self.stdout.write(f"  ... and {expired_count - 10} more")
            
            if pending_count > 0:
                self.stdout.write("Pending invitations to mark as expired:")
                for invitation in pending_expired[:10]:  # Show first 10
                    self.stdout.write(f"  - ID {invitation.id}: {invitation.caller.username} -> {invitation.receiver.username} - expired {invitation.expires_at}")
                if pending_count > 10:
                    self.stdout.write(f"  ... and {pending_count - 10} more")
        else:
            # Mark pending invitations as expired
            if pending_count > 0:
                pending_expired.update(status='expired')
                self.stdout.write(
                    self.style.SUCCESS(f"Marked {pending_count} pending invitations as expired")
                )
            
            # Delete old invitations
            if expired_count > 0:
                expired_invitations.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"Deleted {expired_count} old invitations (older than {days} days)")
                )
            
            if expired_count == 0 and pending_count == 0:
                self.stdout.write(
                    self.style.SUCCESS("No invitations to clean up")
                )
        
        # Show current statistics
        total_invitations = CallInvitation.objects.count()
        pending_invitations = CallInvitation.objects.filter(status='pending').count()
        
        self.stdout.write(f"\nCurrent statistics:")
        self.stdout.write(f"  Total invitations: {total_invitations}")
        self.stdout.write(f"  Pending invitations: {pending_invitations}")
        
        # Show status breakdown
        status_counts = {}
        for status, _ in CallInvitation.STATUS_CHOICES:
            count = CallInvitation.objects.filter(status=status).count()
            if count > 0:
                status_counts[status] = count
        
        if status_counts:
            self.stdout.write(f"  Status breakdown: {status_counts}") 