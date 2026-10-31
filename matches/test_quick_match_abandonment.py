"""CHARACTERIZATION tests: document current quick-match abandonment behavior.

These pin down EXISTING behavior, not desired behavior. A partner who
abandons a quick match without choosing keep/skip leaves the trial open
forever, and a late decision can still activate a long-dead match.
A policy change (max decision window, enforced on result polling and on
late decisions) is proposed but NOT approved; when it lands, these tests
should be replaced with tests for the new behavior.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from users.models import Language
from .models import Match
from .quick import decide

User = get_user_model()


class AbandonedTrialCharacterizationTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('qm1', 'qm1@x.com', 'pw12345!')
        self.b = User.objects.create_user('qm2', 'qm2@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.match = Match.objects.create(
            user1=self.a, user2=self.b,
            user1_teaches=en, user1_learns=ko, status='trial',
            trial_ends_at=timezone.now() - timedelta(days=2),
            user1_keep=True)  # a decided keep; b abandoned without deciding

    def test_undecided_trial_never_expires(self):
        # No code path ends a trial whose partner never decides: two days
        # past trial_ends_at the match is still 'trial', which is what the
        # waiting user's 4s result poll sees indefinitely.
        self.assertEqual(Match.objects.get(pk=self.match.pk).status, 'trial')

    def test_late_decision_still_activates_stale_match(self):
        # The absent partner can return arbitrarily late and flip the
        # long-dead match to active.
        result = decide(self.match, self.b, True)
        self.assertEqual(result.status, 'active')
