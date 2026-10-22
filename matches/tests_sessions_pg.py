"""Overlapping-worker reminder test. Runs only when SPEAKLE_TEST_PG=1 AND
DATABASE_URL points at a real Postgres (sqlite does not enforce
select_for_update, so the single-worker CI run skips this).

Example:
    DJANGO_SETTINGS_MODULE=config.settings_prod SPEAKLE_TEST_PG=1 \
        DATABASE_URL=postgres://postgres@/speakle_test?host=/tmp/pgdata-rest \
        python manage.py test matches.tests_sessions_pg
"""
import datetime
import os
import threading
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone

from matches.models import Match, MatchSession
from users.models import Language

User = get_user_model()
PG = os.environ.get('SPEAKLE_TEST_PG') == '1'


@skipUnless(PG, 'needs SPEAKLE_TEST_PG=1 and DATABASE_URL pointing at real Postgres')
class ReminderConcurrencyTests(TransactionTestCase):
    def test_overlapping_workers_send_once_per_recipient(self):
        import matches.management.commands.send_session_reminders as cmd_mod

        lang, _ = Language.objects.get_or_create(code='en-x', defaults={'name': 'Testlang'})
        a = User.objects.create_user('wa', email='wa@x.com', password='pw')
        b = User.objects.create_user('wb', email='wb@x.com', password='pw')
        m = Match.objects.create(user1=a, user2=b, user1_teaches=lang, user1_learns=lang, status='active')
        MatchSession.objects.create(
            match=m, proposed_by=a,
            starts_at=timezone.now() + datetime.timedelta(hours=12), status='accepted')

        sent_log = []
        log_lock = threading.Lock()

        def fake_send(subject, body, from_email, recipients, **kwargs):
            with log_lock:
                sent_log.append(recipients[0])
            return 1

        cmd_mod.send_mail = fake_send
        barrier = threading.Barrier(2)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=10)
                call_command('send_session_reminders', verbosity=0)
            except Exception as exc:
                errors.append(repr(exc))

        t1, t2 = threading.Thread(target=worker), threading.Thread(target=worker)
        t1.start(); t2.start(); t1.join(30); t2.join(30)

        self.assertEqual(errors, [])
        self.assertEqual(sorted(sent_log), ['wa@x.com', 'wb@x.com'])
