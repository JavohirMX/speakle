"""Weekly-goal guards and the session-decline happy path."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from users.models import Language
from .models import Match, MatchSession

User = get_user_model()


class WeeklyGoalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.a = User.objects.create_user('wg1', 'wg1@x.com', 'pw12345!')
        self.b = User.objects.create_user('wg2', 'wg2@x.com', 'pw12345!')
        self.outsider = User.objects.create_user('wg3', 'wg3@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.match = Match.objects.create(
            user1=self.a, user2=self.b,
            user1_teaches=en, user1_learns=ko, status='active')
        self.url = reverse('matches:set_weekly_goal', args=[self.match.id])

    def test_valid_goal_saved_for_both(self):
        self.client.force_login(self.a)
        self.client.post(self.url, {'weekly_goal': '3'})
        self.match.refresh_from_db()
        self.assertEqual(self.match.weekly_goal, 3)

    def test_non_numeric_goal_rejected(self):
        self.client.force_login(self.a)
        self.client.post(self.url, {'weekly_goal': 'lots'})
        self.match.refresh_from_db()
        self.assertNotEqual(self.match.weekly_goal, 0)  # untouched default

    def test_out_of_range_goal_rejected(self):
        self.client.force_login(self.a)
        self.client.post(self.url, {'weekly_goal': '9'})
        self.match.refresh_from_db()
        self.assertNotEqual(self.match.weekly_goal, 9)

    def test_outsider_cannot_set_goal(self):
        self.client.force_login(self.outsider)
        self.client.post(self.url, {'weekly_goal': '3'})
        self.match.refresh_from_db()
        self.assertNotEqual(self.match.weekly_goal, 3)


class DeclineSessionTests(TestCase):
    def test_partner_can_decline_proposal(self):
        a = User.objects.create_user('ds1', 'ds1@x.com', 'pw12345!')
        b = User.objects.create_user('ds2', 'ds2@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        match = Match.objects.create(
            user1=a, user2=b, user1_teaches=en, user1_learns=ko,
            status='active')
        session = MatchSession.objects.create(
            match=match, proposed_by=a,
            starts_at=timezone.now() + timedelta(hours=3))
        self.client.force_login(b)
        self.client.post(reverse('matches:respond_session',
                                 args=[session.id]), {'action': 'decline'})
        session.refresh_from_db()
        self.assertEqual(session.status, 'declined')
