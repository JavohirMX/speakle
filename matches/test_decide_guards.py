"""quick.decide: only valid on a trial whose timer has run out."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from users.models import Language
from .models import Match
from .quick import decide, QuickMatchError

User = get_user_model()


class DecideGuardTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('qd1', 'qd1@x.com', 'pw12345!')
        self.b = User.objects.create_user('qd2', 'qd2@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.match = Match.objects.create(
            user1=self.a, user2=self.b,
            user1_teaches=en, user1_learns=ko, status='trial',
            trial_ends_at=timezone.now() - timedelta(minutes=1))

    def test_decide_on_non_trial_match_is_noop(self):
        self.match.status = 'active'
        self.match.save()
        result = decide(self.match, self.a, True)
        self.assertEqual(result.status, 'active')

    def test_decide_before_timer_raises(self):
        self.match.trial_ends_at = timezone.now() + timedelta(minutes=5)
        self.match.save()
        with self.assertRaises(QuickMatchError):
            decide(self.match, self.a, True)
