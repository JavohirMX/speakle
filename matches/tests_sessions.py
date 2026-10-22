"""Tests for scheduled practice sessions (MatchSession + reminder command)."""
import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from unittest import mock
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from matches.models import Match, MatchSession
from users.models import Language

User = get_user_model()


def make_match(user1, user2, status='active'):
    lang, _ = Language.objects.get_or_create(code='en-x', defaults={'name': 'Testlang'})
    return Match.objects.create(
        user1=user1, user2=user2,
        user1_teaches=lang, user1_learns=lang,
        status=status,
    )


def future(hours=48):
    return (timezone.now() + datetime.timedelta(hours=hours)).replace(second=0, microsecond=0)


def local_input(dt):
    return timezone.localtime(dt).strftime('%Y-%m-%dT%H:%M')


class SessionModelTests(TestCase):
    def setUp(self):
        self.u1 = User.objects.create_user('anna', password='pw')
        self.u2 = User.objects.create_user('boris', password='pw')
        self.match = make_match(self.u1, self.u2)

    def test_only_one_proposal_per_match(self):
        MatchSession.objects.create(match=self.match, proposed_by=self.u1, starts_at=future())
        with self.assertRaises(IntegrityError):
            MatchSession.objects.create(match=self.match, proposed_by=self.u2, starts_at=future(72))

    def test_second_proposal_allowed_after_decline(self):
        s = MatchSession.objects.create(match=self.match, proposed_by=self.u1, starts_at=future())
        s.status = 'declined'
        s.save()
        MatchSession.objects.create(match=self.match, proposed_by=self.u2, starts_at=future(72))
        self.assertEqual(self.match.sessions.count(), 2)


class SessionViewTests(TestCase):
    def setUp(self):
        self.u1 = User.objects.create_user('anna', password='pw')
        self.u2 = User.objects.create_user('boris', password='pw')
        self.outsider = User.objects.create_user('cora', password='pw')
        self.match = make_match(self.u1, self.u2)

    def propose(self, user, hours=48, duration='30', match=None):
        self.client.force_login(user)
        return self.client.post(
            reverse('matches:propose_session', args=[(match or self.match).id]),
            {'starts_at': local_input(future(hours)), 'duration_minutes': duration, 'note': ''},
        )

    def test_propose_creates_session(self):
        resp = self.propose(self.u1)
        self.assertEqual(resp.status_code, 302)
        session = self.match.sessions.get()
        self.assertEqual(session.status, 'proposed')
        self.assertEqual(session.proposed_by, self.u1)
        self.assertTrue(timezone.is_aware(session.starts_at))

    def test_propose_rejects_past_time(self):
        self.client.force_login(self.u1)
        past = timezone.localtime(timezone.now() - datetime.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M')
        self.client.post(reverse('matches:propose_session', args=[self.match.id]),
                         {'starts_at': past, 'duration_minutes': '30'})
        self.assertEqual(self.match.sessions.count(), 0)

    def test_propose_rejects_invalid_duration(self):
        self.propose(self.u1, duration='37')
        self.assertEqual(self.match.sessions.count(), 0)

    def test_propose_rejects_garbage_datetime(self):
        self.client.force_login(self.u1)
        self.client.post(reverse('matches:propose_session', args=[self.match.id]),
                         {'starts_at': 'not-a-date', 'duration_minutes': '30'})
        self.assertEqual(self.match.sessions.count(), 0)

    def test_propose_blocked_for_outsider(self):
        self.propose(self.outsider)
        self.assertEqual(self.match.sessions.count(), 0)

    def test_propose_blocked_on_ended_match(self):
        ended = make_match(
            User.objects.create_user('dave', password='pw'),
            User.objects.create_user('erin', password='pw'),
            status='ended',
        )
        self.propose(ended.user1, match=ended)
        self.assertEqual(ended.sessions.count(), 0)

    def test_partner_can_accept(self):
        session = MatchSession.objects.create(match=self.match, proposed_by=self.u1, starts_at=future())
        self.client.force_login(self.u2)
        self.client.post(reverse('matches:respond_session', args=[session.id]), {'action': 'accept'})
        session.refresh_from_db()
        self.assertEqual(session.status, 'accepted')

    def test_proposer_cannot_accept_own_proposal(self):
        session = MatchSession.objects.create(match=self.match, proposed_by=self.u1, starts_at=future())
        self.client.force_login(self.u1)
        self.client.post(reverse('matches:respond_session', args=[session.id]), {'action': 'accept'})
        session.refresh_from_db()
        self.assertEqual(session.status, 'proposed')

    def test_outsider_cannot_respond(self):
        session = MatchSession.objects.create(match=self.match, proposed_by=self.u1, starts_at=future())
        self.client.force_login(self.outsider)
        self.client.post(reverse('matches:respond_session', args=[session.id]), {'action': 'accept'})
        session.refresh_from_db()
        self.assertEqual(session.status, 'proposed')

    def test_cannot_respond_twice(self):
        session = MatchSession.objects.create(
            match=self.match, proposed_by=self.u1, starts_at=future(), status='declined')
        self.client.force_login(self.u2)
        self.client.post(reverse('matches:respond_session', args=[session.id]), {'action': 'accept'})
        session.refresh_from_db()
        self.assertEqual(session.status, 'declined')

    def test_either_partner_can_cancel(self):
        session = MatchSession.objects.create(
            match=self.match, proposed_by=self.u1, starts_at=future(), status='accepted')
        self.client.force_login(self.u2)
        self.client.post(reverse('matches:cancel_session', args=[session.id]))
        session.refresh_from_db()
        self.assertEqual(session.status, 'cancelled')

    def test_match_detail_shows_upcoming(self):
        MatchSession.objects.create(match=self.match, proposed_by=self.u1, starts_at=future())
        self.client.force_login(self.u2)
        resp = self.client.get(reverse('matches:match_detail', args=[self.match.id]))
        self.assertContains(resp, 'Practice sessions')
        self.assertContains(resp, 'Accept')

    def test_responder_sees_answer_copy_not_waiting(self):
        MatchSession.objects.create(match=self.match, proposed_by=self.u1, starts_at=future())
        self.client.force_login(self.u2)
        resp = self.client.get(reverse('matches:match_detail', args=[self.match.id]))
        self.assertContains(resp, 'Answer anna')
        self.assertNotContains(resp, 'Waiting for boris')
        self.client.force_login(self.u1)
        resp = self.client.get(reverse('matches:match_detail', args=[self.match.id]))
        self.assertContains(resp, 'Waiting for boris')


class ReminderCommandTests(TestCase):
    def setUp(self):
        self.u1 = User.objects.create_user('anna', email='anna@example.com', password='pw')
        self.u2 = User.objects.create_user('boris', email='boris@example.com', password='pw')
        self.match = make_match(self.u1, self.u2)

    def run_command(self):
        out = StringIO()
        call_command('send_session_reminders', stdout=out)
        return out.getvalue()

    def test_24h_reminder_sent_once(self):
        session = MatchSession.objects.create(
            match=self.match, proposed_by=self.u1, starts_at=future(12), status='accepted')
        self.run_command()
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual({m.to[0] for m in mail.outbox}, {'anna@example.com', 'boris@example.com'})
        session.refresh_from_db()
        self.assertEqual(set(session.reminders_sent['24h']), {self.u1.id, self.u2.id})
        mail.outbox.clear()
        self.run_command()
        self.assertEqual(len(mail.outbox), 0)

    def test_1h_reminder_for_imminent_session(self):
        session = MatchSession.objects.create(
            match=self.match, proposed_by=self.u1,
            starts_at=timezone.now() + datetime.timedelta(minutes=45), status='accepted')
        self.run_command()
        self.assertEqual(len(mail.outbox), 2)
        session.refresh_from_db()
        self.assertEqual(set(session.reminders_sent['1h']), {self.u1.id, self.u2.id})

    def test_no_reminder_for_proposed_or_far_future(self):
        MatchSession.objects.create(
            match=self.match, proposed_by=self.u1, starts_at=future(12), status='proposed')
        MatchSession.objects.create(
            match=self.match, proposed_by=self.u1, starts_at=future(72), status='accepted')
        self.run_command()
        self.assertEqual(len(mail.outbox), 0)

    def test_partial_failure_retries_only_failed_recipient(self):
        session = MatchSession.objects.create(
            match=self.match, proposed_by=self.u1, starts_at=future(12), status='accepted')
        real_send = __import__('django.core.mail', fromlist=['send_mail']).send_mail
        calls = []

        def flaky(subject, body, from_email, recipients, **kwargs):
            calls.append(recipients[0])
            if recipients[0] == 'boris@example.com':
                raise OSError('SMTP down')
            return 1

        with mock.patch('matches.management.commands.send_session_reminders.send_mail', flaky):
            self.run_command()
        session.refresh_from_db()
        self.assertEqual(set(session.reminders_sent['24h']), {self.u1.id})
        mail.outbox.clear()

        with mock.patch('matches.management.commands.send_session_reminders.send_mail', real_send):
            self.run_command()
        self.assertEqual([m.to[0] for m in mail.outbox], ['boris@example.com'])
        session.refresh_from_db()
        self.assertEqual(set(session.reminders_sent['24h']), {self.u1.id, self.u2.id})

    def test_no_reminder_without_email(self):
        self.u1.email = ''
        self.u1.save()
        self.u2.email = ''
        self.u2.save()
        MatchSession.objects.create(
            match=self.match, proposed_by=self.u1, starts_at=future(12), status='accepted')
        self.run_command()
        self.assertEqual(len(mail.outbox), 0)
