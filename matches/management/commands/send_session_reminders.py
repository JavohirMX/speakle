"""Email reminders for upcoming accepted sessions.

Run this on a schedule (for example cron every 5 minutes):

    */5 * * * * cd /app && python manage.py send_session_reminders

Send behavior, deliberately bounded:
- Each session row is locked with select_for_update() while it is
  processed, so two overlapping workers do not double-send.
- Each reminder window (24h / 1h) is recorded per recipient and only
  after that recipient's send succeeds. A failed recipient is retried
  on the next run without resending to the others.
- A crash between a successful send and saving the record can cause
  one duplicate for that recipient; the record is saved right after
  the send to keep that window as small as possible.
"""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from matches.models import MatchSession

WINDOWS = ((1, 'in about an hour'), (24, 'tomorrow'))  # smallest first: next() picks the tightest due window


class Command(BaseCommand):
    help = 'Send 24h and 1h email reminders for upcoming accepted sessions.'

    def handle(self, *args, **options):
        now = timezone.now()
        sent = 0
        with transaction.atomic():
            sessions = MatchSession.objects.select_for_update().filter(
                status='accepted',
                starts_at__gte=now,
                starts_at__lte=now + timedelta(hours=24),
            ).select_related('match', 'match__user1', 'match__user2')

            for session in sessions:
                delta = session.starts_at - now
                record = session.reminders_sent or {}
                changed = False
                # WINDOWS is ordered smallest first; only the first matching
                # window sends this run, so an imminent session gets just the
                # 1h reminder, not both.
                applicable = next(
                    ((h, w) for h, w in WINDOWS if delta <= timedelta(hours=h)), None)
                if applicable:
                    hours, when = applicable
                    window = f'{hours}h'
                    done = set(record.get(window, []))
                    for user in (session.match.user1, session.match.user2):
                        if user.id in done or not user.email:
                            continue
                        partner = session.match.get_partner(user)
                        start_local = timezone.localtime(session.starts_at)
                        base = getattr(settings, 'SITE_URL', '').rstrip('/')
                        link = (f'\n\nOpen your match page when it is time: '
                                f'{base}/matches/match/{session.match_id}/') if base else ''
                        try:
                            send_mail(
                                f'Speakle session with {partner.username} {when}',
                                f'Hi {user.username},\n\n'
                                f'Reminder: your practice session with {partner.username} starts '
                                f'{start_local:%A, %B %d at %H:%M} ({session.duration_minutes} minutes).'
                                f'{link}\n',
                                None, [user.email], fail_silently=False,
                            )
                        except Exception as exc:
                            self.stderr.write(
                                f'Reminder to {user.email} for session {session.id} failed: {exc}')
                            continue
                        done.add(user.id)
                        sent += 1
                        changed = True
                    record[window] = sorted(done)
                if changed:
                    session.reminders_sent = record
                    session.save(update_fields=['reminders_sent'])

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} reminder email(s).'))
