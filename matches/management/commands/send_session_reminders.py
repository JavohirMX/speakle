"""Email reminders for upcoming accepted sessions.

Run this on a schedule (for example cron every 5 minutes):

    */5 * * * * cd /app && python manage.py send_session_reminders

Each reminder (24 hours and 1 hour before the start) is sent once per
session; the flags on the session row make re-runs safe.
"""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from matches.models import MatchSession


class Command(BaseCommand):
    help = 'Send 24h and 1h email reminders for upcoming accepted sessions.'

    def handle(self, *args, **options):
        now = timezone.now()
        sessions = MatchSession.objects.filter(
            status='accepted',
            starts_at__gte=now,
            starts_at__lte=now + timedelta(hours=24),
        ).select_related('match', 'match__user1', 'match__user2')

        sent = 0
        for session in sessions:
            delta = session.starts_at - now
            if delta <= timedelta(hours=1) and not session.reminder_1h_sent:
                flag = 'reminder_1h_sent'
                when = 'in about an hour'
            elif delta <= timedelta(hours=24) and not session.reminder_24h_sent:
                flag = 'reminder_24h_sent'
                when = 'tomorrow'
            else:
                continue

            for user in (session.match.user1, session.match.user2):
                if not user.email:
                    continue
                partner = session.match.get_partner(user)
                start_local = timezone.localtime(session.starts_at)
                base = getattr(settings, 'SITE_URL', '').rstrip('/')
                link = f'\n\nOpen your match page when it is time: {base}/matches/match/{session.match_id}/' if base else ''
                send_mail(
                    f'Speakle session with {partner.username} {when}',
                    f'Hi {user.username},\n\n'
                    f'Reminder: your practice session with {partner.username} starts '
                    f'{start_local:%A, %B %d at %H:%M} ({session.duration_minutes} minutes).'
                    f'{link}\n',
                    None, [user.email], fail_silently=True,
                )
            setattr(session, flag, True)
            session.save(update_fields=[flag])
            sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent reminders for {sent} session(s).'))
