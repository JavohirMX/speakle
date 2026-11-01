"""Scoring tiers and exclusion branches in MatchingService."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from users.models import Language, UserLanguage, UserBlock
from .models import Match, MatchRequest
from .services import MatchingService

User = get_user_model()


class ScoreTierTests(TestCase):
    def setUp(self):
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')

    def _teacher(self, name, teach_prof, teach_type,
                 interests='', bio=''):
        u = User.objects.create_user(name, password='x',
                                     interests=interests, bio=bio)
        UserLanguage.objects.create(
            user=u, language=self.en, proficiency=teach_prof,
            language_type=teach_type)
        return u

    def _learner(self, name, learn_prof, interests='', bio=''):
        u = User.objects.create_user(name, password='x',
                                     interests=interests, bio=bio)
        UserLanguage.objects.create(
            user=u, language=self.en, proficiency=learn_prof,
            language_type='learning')
        return u

    def test_native_teacher_beginner_learner_gets_top_tier(self):
        a = self._teacher('a', 'native', 'native')
        b = self._learner('b', 'beginner')
        score = MatchingService.calculate_compatibility_score(
            a, b, self.en, self.ko)
        self.assertEqual(score, 80.0)  # 50 base + 30 tier

    def test_advanced_teacher_intermediate_learner_still_top_tier(self):
        # The first tier already covers advanced + intermediate.
        a = self._teacher('a', 'advanced', 'fluent')
        b = self._learner('b', 'intermediate')
        score = MatchingService.calculate_compatibility_score(
            a, b, self.en, self.ko)
        self.assertEqual(score, 80.0)  # 50 + 30

    def test_advanced_teacher_advanced_learner_gets_mid_tier(self):
        a = self._teacher('a', 'advanced', 'fluent')
        b = self._learner('b', 'advanced')
        score = MatchingService.calculate_compatibility_score(
            a, b, self.en, self.ko)
        self.assertEqual(score, 70.0)  # 50 + 20

    def test_other_combinations_get_base_tier(self):
        a = self._teacher('a', 'intermediate', 'fluent')
        b = self._learner('b', 'advanced')
        score = MatchingService.calculate_compatibility_score(
            a, b, self.en, self.ko)
        self.assertEqual(score, 60.0)  # 50 + 10

    def test_interest_bonus_capped_at_six_shared(self):
        shared = 'aa bb cc dd ee ff gg hh'
        a = self._teacher('a', 'native', 'native', interests=shared)
        b = self._learner('b', 'beginner', interests=shared)
        score = MatchingService.calculate_compatibility_score(
            a, b, self.en, self.ko)
        self.assertEqual(score, 100.0)  # 50+30+6*5 = 110, capped

    def test_bio_bonus_requires_both_detailed(self):
        long_bio = 'x' * 60
        a = self._teacher('a', 'native', 'native', bio=long_bio)
        b = self._learner('b', 'beginner', bio=long_bio)
        both = MatchingService.calculate_compatibility_score(
            a, b, self.en, self.ko)
        c = self._learner('c', 'beginner')
        one_sided = MatchingService.calculate_compatibility_score(
            a, c, self.en, self.ko)
        self.assertEqual(both - one_sided, 10.0)


class FindPotentialMatchesBranchTests(TestCase):
    def setUp(self):
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')
        self.a = User.objects.create_user('a', password='x')
        self.b = User.objects.create_user('b', password='x')
        for u, native, learning in ((self.a, self.en, self.ko),
                                    (self.b, self.ko, self.en)):
            UserLanguage.objects.create(
                user=u, language=native, proficiency='native',
                language_type='native')
            UserLanguage.objects.create(
                user=u, language=learning, proficiency='beginner',
                language_type='learning')

    def test_user_without_languages_gets_empty_list(self):
        lonely = User.objects.create_user('lonely', password='x')
        self.assertEqual(
            MatchingService.find_potential_matches(lonely, refresh=True),
            [])

    def test_blocked_users_never_suggested(self):
        UserBlock.objects.create(blocker=self.a, blocked=self.b)
        self.assertEqual(
            MatchingService.find_potential_matches(self.a, refresh=True),
            [])

    def test_existing_potential_match_not_duplicated(self):
        first = MatchingService.find_potential_matches(self.a, refresh=True)
        again = MatchingService.find_potential_matches(self.a)
        self.assertEqual(len(first), 1)
        self.assertEqual(again, [])


class SendRequestGuardTests(TestCase):
    def setUp(self):
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')
        self.a = User.objects.create_user('a', password='x')
        self.b = User.objects.create_user('b', password='x')

    def test_duplicate_pending_request_returns_existing(self):
        req, created = MatchingService.send_match_request(
            self.a, self.b, self.en, self.ko)
        self.assertTrue(created)
        again, created = MatchingService.send_match_request(
            self.a, self.b, self.en, self.ko)
        self.assertFalse(created)
        self.assertEqual(again.pk, req.pk)
        self.assertEqual(MatchRequest.objects.count(), 1)

    def test_request_blocked_when_active_match_exists(self):
        Match.objects.create(
            user1=self.a, user2=self.b,
            user1_teaches=self.en, user1_learns=self.ko, status='active')
        req, created = MatchingService.send_match_request(
            self.a, self.b, self.en, self.ko)
        self.assertIsNone(req)
        self.assertFalse(created)

    def test_accept_reactivates_ended_match(self):
        old = Match.objects.create(
            user1=self.a, user2=self.b,
            user1_teaches=self.en, user1_learns=self.ko,
            status='ended', ended_at=timezone.now())
        req, created = MatchingService.send_match_request(
            self.a, self.b, self.en, self.ko)
        self.assertTrue(created)
        match = MatchingService.respond_to_match_request(req, accept=True)
        self.assertEqual(match.pk, old.pk)
        match.refresh_from_db()
        self.assertEqual(match.status, 'active')
        self.assertIsNone(match.ended_at)
        self.assertEqual(Match.objects.count(), 1)
