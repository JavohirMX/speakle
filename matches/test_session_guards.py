"""Guard-branch tests for the session proposal/response/cancel flows.

Pins the previously uncovered error branches: bad date/time, too-soon
start, invalid duration, duplicate proposal, answering your own
proposal, unknown response action, and the cancel guardrails.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from users.models import Language
from .models import Match, MatchSession

User = get_user_model()


class SessionGuardTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='sg1', email='sg1@example.com', password='x')
        self.user2 = User.objects.create_user(
            username='sg2', email='sg2@example.com', password='x')
        self.outsider = User.objects.create_user(
            username='sg3', email='sg3@example.com', password='x')
        en = Language.objects.create(name='English', code='en', flag_emoji='US')
        ko = Language.objects.create(name='Korean', code='ko', flag_emoji='KR')
        self.match = Match.objects.create(
            user1=self.user1, user2=self.user2,
            user1_teaches=en, user1_learns=ko, status='active')
        self.propose_url = reverse('matches:propose_session',
                                   args=[self.match.id])
        self.future = timezone.localtime(
            timezone.now() + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M')

    def _propose(self, **overrides):
        data = {'starts_at': self.future, 'duration_minutes': '30'}
        data.update(overrides)
        return self.client.post(self.propose_url, data)

    def test_outsider_cannot_propose(self):
        self.client.force_login(self.outsider)
        self._propose()
        self.assertEqual(MatchSession.objects.count(), 0)

    def test_garbage_datetime_rejected(self):
        self.client.force_login(self.user1)
        self._propose(starts_at='not-a-date')
        self.assertEqual(MatchSession.objects.count(), 0)

    def test_too_soon_rejected(self):
        self.client.force_login(self.user1)
        soon = timezone.localtime(
            timezone.now() + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M')
        self._propose(starts_at=soon)
        self.assertEqual(MatchSession.objects.count(), 0)

    def test_non_numeric_duration_falls_back_to_30(self):
        self.client.force_login(self.user1)
        self._propose(duration_minutes='abc')
        session = MatchSession.objects.get()
        self.assertEqual(session.duration_minutes, 30)

    def test_out_of_choices_duration_rejected(self):
        self.client.force_login(self.user1)
        self._propose(duration_minutes='42')
        self.assertEqual(MatchSession.objects.count(), 0)

    def test_second_proposal_blocked_while_one_pending(self):
        self.client.force_login(self.user1)
        self._propose()
        self._propose()
        self.assertEqual(MatchSession.objects.count(), 1)


class RespondGuardTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='rg1', email='rg1@example.com', password='x')
        self.user2 = User.objects.create_user(
            username='rg2', email='rg2@example.com', password='x')
        en = Language.objects.create(name='English', code='en', flag_emoji='US')
        ko = Language.objects.create(name='Korean', code='ko', flag_emoji='KR')
        self.match = Match.objects.create(
            user1=self.user1, user2=self.user2,
            user1_teaches=en, user1_learns=ko, status='active')
        self.session = MatchSession.objects.create(
            match=self.match, proposed_by=self.user1,
            starts_at=timezone.now() + timedelta(hours=3))
        self.url = reverse('matches:respond_session', args=[self.session.id])

    def test_proposer_cannot_answer_own_proposal(self):
        self.client.force_login(self.user1)
        self.client.post(self.url, {'action': 'accept'})
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'proposed')

    def test_unknown_action_leaves_status_unchanged(self):
        self.client.force_login(self.user2)
        self.client.post(self.url, {'action': 'maybe'})
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'proposed')

    def test_answered_proposal_cannot_be_answered_again(self):
        self.session.status = 'accepted'
        self.session.save()
        self.client.force_login(self.user2)
        self.client.post(self.url, {'action': 'decline'})
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'accepted')


class CancelGuardTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='cg1', email='cg1@example.com', password='x')
        self.user2 = User.objects.create_user(
            username='cg2', email='cg2@example.com', password='x')
        self.outsider = User.objects.create_user(
            username='cg3', email='cg3@example.com', password='x')
        en = Language.objects.create(name='English', code='en', flag_emoji='US')
        ko = Language.objects.create(name='Korean', code='ko', flag_emoji='KR')
        self.match = Match.objects.create(
            user1=self.user1, user2=self.user2,
            user1_teaches=en, user1_learns=ko, status='active')
        self.session = MatchSession.objects.create(
            match=self.match, proposed_by=self.user1,
            starts_at=timezone.now() + timedelta(hours=3))
        self.url = reverse('matches:cancel_session', args=[self.session.id])

    def test_outsider_cannot_cancel(self):
        self.client.force_login(self.outsider)
        self.client.post(self.url)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'proposed')

    def test_non_proposer_told_to_decline_instead(self):
        self.client.force_login(self.user2)
        self.client.post(self.url)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'proposed')

    def test_declined_session_cannot_be_cancelled(self):
        self.session.status = 'declined'
        self.session.save()
        self.client.force_login(self.user1)
        self.client.post(self.url)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'declined')
