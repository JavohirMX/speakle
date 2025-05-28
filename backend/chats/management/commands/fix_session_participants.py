from django.core.management.base import BaseCommand
from chats.models import CallSession, VideoRoom

class Command(BaseCommand):
    help = 'Fix existing call sessions that might not have proper participants assigned'

    def handle(self, *args, **options):
        fixed_count = 0
        total_sessions = CallSession.objects.all().count()
        
        self.stdout.write(f"Checking {total_sessions} call sessions...")
        
        for session in CallSession.objects.all():
            room = session.room
            match = room.match
            
            # Get current participants count
            current_participants = session.participants.count()
            
            # Add both match users as participants if not already added
            added_users = []
            for user in [match.user1, match.user2]:
                if not session.participants.filter(id=user.id).exists():
                    session.participants.add(user)
                    added_users.append(user.username)
            
            if added_users:
                fixed_count += 1
                self.stdout.write(
                    f"Session {session.id}: Added participants {', '.join(added_users)} "
                    f"(was {current_participants}, now {session.participants.count()})"
                )
        
        if fixed_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Fixed {fixed_count} sessions with missing participants")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("All sessions already have proper participants assigned")
            ) 