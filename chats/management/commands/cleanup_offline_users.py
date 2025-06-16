from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chats.models import UserPresence


class Command(BaseCommand):
    help = 'Set users offline if they have been inactive for more than the specified time'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=5,
            help='Number of minutes of inactivity before marking user as offline (default: 5)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually updating the database'
        )

    def handle(self, *args, **options):
        minutes = options['minutes']
        dry_run = options['dry_run']
        
        # Calculate the cutoff time
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        
        # Find users who are marked online but have been inactive
        inactive_users = UserPresence.objects.filter(
            is_online=True,
            last_seen__lt=cutoff_time
        )
        
        count = inactive_users.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would mark {count} users as offline '
                    f'(inactive for more than {minutes} minutes)'
                )
            )
            if count > 0:
                self.stdout.write('Users that would be marked offline:')
                for presence in inactive_users:
                    last_seen = presence.last_seen.strftime('%Y-%m-%d %H:%M:%S')
                    self.stdout.write(f'  - {presence.user.username} (last seen: {last_seen})')
        else:
            # Update users to offline
            updated = inactive_users.update(is_online=False)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully marked {updated} users as offline '
                    f'(inactive for more than {minutes} minutes)'
                )
            )
            
            if updated > 0:
                self.stdout.write('Users marked offline:')
                # Re-fetch to show updated users
                offline_users = UserPresence.objects.filter(
                    is_online=False,
                    last_seen__lt=cutoff_time
                ).order_by('-last_seen')[:updated]
                
                for presence in offline_users:
                    last_seen = presence.last_seen.strftime('%Y-%m-%d %H:%M:%S')
                    self.stdout.write(f'  - {presence.user.username} (last seen: {last_seen})') 