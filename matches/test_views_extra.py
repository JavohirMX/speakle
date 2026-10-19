from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from users.models import Language, UserLanguage
from .models import Match, MatchRequest

User = get_user_model()


class MatchViewExtraBase(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('mva', 'mva@x.com', 'pw12345!')
        self.b = User.objects.create_user('mvb', 'mvb@x.com', 'pw12345!')
        self.c = User.objects.create_user('mvc', 'mvc@x.com', 'pw12345!')
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')

    def login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def pending_request(self):
        return MatchRequest.objects.create(
            sender=self.a, receiver=self.b, sender_teaches=self.en, sender_learns=self.ko,
            message='hi',
        )


class RespondToRequestWebTests(MatchViewExtraBase):
    def test_accept_creates_active_match_and_redirects(self):
        req = self.pending_request()
        r = self.login(self.b).post(reverse('matches:respond_request', args=[req.id]), {'action': 'accept'})
        self.assertRedirects(r, reverse('matches:my_matches'), fetch_redirect_response=False)
        self.assertTrue(Match.objects.filter(user1=self.a, user2=self.b, status='active').exists())

    def test_decline_does_not_create_match(self):
        req = self.pending_request()
        r = self.login(self.b).post(reverse('matches:respond_request', args=[req.id]), {'action': 'decline'})
        self.assertRedirects(r, reverse('matches:requests'), fetch_redirect_response=False)
        req.refresh_from_db()
        self.assertEqual(req.status, 'declined')
        self.assertFalse(Match.objects.exists())

    def test_unknown_action_changes_nothing(self):
        req = self.pending_request()
        self.login(self.b).post(reverse('matches:respond_request', args=[req.id]), {'action': 'zzz'})
        req.refresh_from_db()
        self.assertEqual(req.status, 'pending')

    def test_sender_and_strangers_cannot_respond(self):
        req = self.pending_request()
        url = reverse('matches:respond_request', args=[req.id])
        self.assertEqual(self.login(self.a).post(url, {'action': 'accept'}).status_code, 404)
        self.assertEqual(self.login(self.c).post(url, {'action': 'accept'}).status_code, 404)
        self.assertFalse(Match.objects.exists())

    def test_get_redirects_to_requests_page_instead_of_missing_template(self):
        req = self.pending_request()
        r = self.login(self.b).get(reverse('matches:respond_request', args=[req.id]))
        self.assertRedirects(r, reverse('matches:requests'), fetch_redirect_response=False)

    def test_double_accept_is_idempotent(self):
        req = self.pending_request()
        c = self.login(self.b)
        url = reverse('matches:respond_request', args=[req.id])
        c.post(url, {'action': 'accept'})
        c.post(url, {'action': 'accept'})
        self.assertEqual(Match.objects.count(), 1)

    def test_api_invalid_action_is_400(self):
        req = self.pending_request()
        r = self.login(self.b).post(reverse('matches:respond_request_api', args=[req.id]), {'action': 'zzz'})
        self.assertEqual(r.status_code, 400)


class MatchDetailAndStatsApiTests(MatchViewExtraBase):
    def setUp(self):
        super().setUp()
        self.match = Match.objects.create(
            user1=self.a, user2=self.b, user1_teaches=self.en, user1_learns=self.ko, status='active'
        )

    def test_detail_api_for_participant_and_outsider(self):
        url = reverse('matches:get_match_detail', args=[self.match.id])
        r = self.login(self.a).get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['match']['id'], self.match.id)
        self.assertEqual(self.login(self.c).get(url).status_code, 403)

    def test_statistics_api_counts_calls(self):
        from datetime import timedelta
        from django.utils import timezone
        from chats.models import VideoRoom, CallSession
        room = VideoRoom.objects.create(match=self.match)
        s = CallSession.objects.create(room=room, status='ended')
        CallSession.objects.filter(pk=s.pk).update(ended_at=timezone.now() + timedelta(minutes=3))
        r = self.login(self.a).get(reverse('matches:get_match_statistics', args=[self.match.id]))
        self.assertEqual(r.status_code, 200)
        stats = r.json()['statistics']
        self.assertEqual(stats['total_calls'], 1)
        self.assertGreaterEqual(stats['total_call_duration'], 2.9)

    def test_statistics_api_denies_outsider(self):
        r = self.login(self.c).get(reverse('matches:get_match_statistics', args=[self.match.id]))
        self.assertEqual(r.status_code, 403)


class EditLanguageTests(MatchViewExtraBase):
    def test_edit_own_language_and_not_others(self):
        ul = UserLanguage.objects.create(user=self.a, language=self.en, language_type='native', proficiency='native')
        url = reverse('users:edit_language', args=[ul.id])
        self.assertEqual(self.login(self.b).get(url).status_code, 404)
        self.assertEqual(self.login(self.a).get(url).status_code, 200)


class FindMatchesOnboardingMessageTests(TestCase):
    def test_message_says_which_language_is_missing(self):
        from django.contrib.auth import get_user_model
        from users.models import Language, UserLanguage
        U = get_user_model()
        u = U.objects.create_user('onb', 'onb@x.com', 'pw12345!')
        self.client.force_login(u)
        r = self.client.get(reverse('matches:find_matches'), follow=True)
        self.assertContains(r, 'a language you speak and one you want to learn')
        en = Language.objects.create(name='English', code='en')
        UserLanguage.objects.create(user=u, language=en, language_type='native', proficiency='native')
        r = self.client.get(reverse('matches:find_matches'), follow=True)
        self.assertContains(r, 'Add a language you want to learn')


class InactiveUsersNotSuggestedTests(TestCase):
    def test_deactivated_user_is_not_suggested(self):
        from .services import MatchingService
        U = get_user_model()
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        me = U.objects.create_user('me_a', 'mea@x.com', 'pw12345!')
        UserLanguage.objects.create(user=me, language=en, language_type='native', proficiency='native')
        UserLanguage.objects.create(user=me, language=ko, language_type='learning', proficiency='beginner')
        def partner(name):
            p = U.objects.create_user(name, name + '@x.com', 'pw12345!')
            UserLanguage.objects.create(user=p, language=ko, language_type='native', proficiency='native')
            UserLanguage.objects.create(user=p, language=en, language_type='learning', proficiency='beginner')
            return p
        ok = partner('active_p')
        gone = partner('gone_p')
        U.objects.filter(pk=gone.pk).update(is_active=False)
        got = {m.potential_partner_id for m in MatchingService.find_potential_matches(me)}
        self.assertEqual(got, {ok.id})


class DeactivatedUsersHiddenTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')
        self.me = U.objects.create_user('dh_me', 'dhme@x.com', 'pw12345!')
        self.other = U.objects.create_user('dh_other', 'dhother@x.com', 'pw12345!')
        UserLanguage.objects.create(user=self.me, language=self.en, language_type='native', proficiency='native')
        UserLanguage.objects.create(user=self.me, language=self.ko, language_type='learning', proficiency='beginner')

    def test_stored_suggestion_of_a_since_deactivated_user_is_hidden(self):
        from .models import PotentialMatch
        PotentialMatch.objects.create(user=self.me, potential_partner=self.other, user_teaches=self.en,
                                      user_learns=self.ko, compatibility_score=80)
        self.client.force_login(self.me)
        self.assertContains(self.client.get(reverse('matches:find_matches')), 'dh_other')
        get_user_model().objects.filter(pk=self.other.pk).update(is_active=False)
        self.assertNotContains(self.client.get(reverse('matches:find_matches')), 'dh_other')

    def test_quick_match_skips_a_deactivated_waiting_user(self):
        from django.test import override_settings
        from . import quick
        UserLanguage.objects.create(user=self.other, language=self.ko, language_type='native', proficiency='native')
        UserLanguage.objects.create(user=self.other, language=self.en, language_type='learning', proficiency='beginner')
        with override_settings(QUICK_MATCH_REQUIRE_VERIFIED_EMAIL=False):
            self.assertIsNone(quick.join_queue(self.other))
            get_user_model().objects.filter(pk=self.other.pk).update(is_active=False)
            self.assertIsNone(quick.join_queue(self.me))
