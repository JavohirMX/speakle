from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from users.models import Language, UserLanguage
from .models import PotentialMatch, Match, MatchRequest
import json

User = get_user_model()

class MatchesAPITestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create test users
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123'
        )
        
        # Create test languages
        self.english = Language.objects.create(
            name='English',
            code='en',
            flag_emoji='🇺🇸'
        )
        self.korean = Language.objects.create(
            name='Korean',
            code='ko',
            flag_emoji='🇰🇷'
        )
        
        # Set up user languages
        UserLanguage.objects.create(
            user=self.user1,
            language=self.english,
            language_type='native',
            proficiency='native'
        )
        UserLanguage.objects.create(
            user=self.user1,
            language=self.korean,
            language_type='learning',
            proficiency='beginner'
        )
        
        UserLanguage.objects.create(
            user=self.user2,
            language=self.korean,
            language_type='native',
            proficiency='native'
        )
        UserLanguage.objects.create(
            user=self.user2,
            language=self.english,
            language_type='learning',
            proficiency='intermediate'
        )
        
        self.client = Client()
        
    def test_get_potential_matches_api(self):
        """Test getting potential matches via API"""
        # Create a potential match
        PotentialMatch.objects.create(
            user=self.user1,
            potential_partner=self.user2,
            user_teaches=self.english,
            user_learns=self.korean,
            compatibility_score=85.5
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.get('/matches/api/potential-matches/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['potential_matches']), 1)
        self.assertEqual(data['potential_matches'][0]['partner']['username'], 'user2')
        
    def test_send_match_request_api(self):
        """Test sending a match request via API"""
        # Create a potential match
        potential_match = PotentialMatch.objects.create(
            user=self.user1,
            potential_partner=self.user2,
            user_teaches=self.english,
            user_learns=self.korean,
            compatibility_score=85.5
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.post(f'/matches/api/send-request/{potential_match.id}/', {
            'message': 'Hi! Would love to practice languages with you!'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('request_id', data)
        
        # Verify the request was created
        request = MatchRequest.objects.get(id=data['request_id'])
        self.assertEqual(request.sender, self.user1)
        self.assertEqual(request.receiver, self.user2)
        self.assertEqual(request.message, 'Hi! Would love to practice languages with you!')
        
    def test_respond_to_request_api(self):
        """Test responding to a match request via API"""
        # Create a match request
        match_request = MatchRequest.objects.create(
            sender=self.user2,
            receiver=self.user1,
            sender_teaches=self.korean,
            sender_learns=self.english,
            message='Hello!'
        )
        
        self.client.login(username='user1', password='testpass123')
        
        # Test accepting the request
        response = self.client.post(f'/matches/api/respond-request/{match_request.id}/', {
            'action': 'accept'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['action'], 'accepted')
        self.assertIn('match_id', data)
        
        # Verify the match was created
        match = Match.objects.get(id=data['match_id'])
        self.assertIn(self.user1, [match.user1, match.user2])
        self.assertIn(self.user2, [match.user1, match.user2])
        
        # Verify the request status was updated
        match_request.refresh_from_db()
        self.assertEqual(match_request.status, 'accepted')
        
    def test_cancel_match_request_api(self):
        """Test cancelling a match request via API"""
        # Create a match request
        match_request = MatchRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            sender_teaches=self.english,
            sender_learns=self.korean,
            message='Hello!',
            status='pending'
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.post(f'/matches/api/cancel-request/{match_request.id}/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Verify the request status was updated
        match_request.refresh_from_db()
        self.assertEqual(match_request.status, 'cancelled')
        
    def test_get_pending_requests_api(self):
        """Test getting pending requests via API"""
        # Create incoming and outgoing requests
        incoming_request = MatchRequest.objects.create(
            sender=self.user2,
            receiver=self.user1,
            sender_teaches=self.korean,
            sender_learns=self.english,
            message='Hi from user2!',
            status='pending'
        )
        
        outgoing_request = MatchRequest.objects.create(
            sender=self.user1,
            receiver=self.user2,
            sender_teaches=self.english,
            sender_learns=self.korean,
            message='Hi from user1!',
            status='pending'
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.get('/matches/api/pending-requests/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Check incoming requests
        self.assertEqual(len(data['incoming_requests']), 1)
        self.assertEqual(data['incoming_requests'][0]['sender'], 'user2')
        
        # Check outgoing requests
        self.assertEqual(len(data['outgoing_requests']), 1)
        self.assertEqual(data['outgoing_requests'][0]['receiver'], 'user2')
        
    def test_get_my_matches_api(self):
        """Test getting user's matches via API"""
        # Create a match
        match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active'
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.get('/matches/api/my-matches/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['matches']), 1)
        
        match_data = data['matches'][0]
        self.assertEqual(match_data['id'], match.id)
        self.assertEqual(match_data['partner']['username'], 'user2')
        self.assertEqual(match_data['status'], 'active')
        
    def test_end_match_api(self):
        """Test ending a match via API"""
        # Create a match
        match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active'
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.post(f'/matches/api/end-match/{match.id}/', {
            'reason': 'No longer interested in language exchange'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('ended_at', data)
        
        # Verify the match was ended
        match.refresh_from_db()
        self.assertEqual(match.status, 'ended')
        self.assertEqual(match.ended_by, self.user1)
        self.assertEqual(match.end_reason, 'No longer interested in language exchange')
        self.assertIsNotNone(match.ended_at)
        
    def test_get_match_statistics_api(self):
        """Test getting match statistics via API"""
        # Create a match
        match = Match.objects.create(
            user1=self.user1,
            user2=self.user2,
            user1_teaches=self.english,
            user1_learns=self.korean,
            status='active',
        )
        # created_at is auto_now_add, so backdate with update()
        Match.objects.filter(pk=match.pk).update(created_at=timezone.now() - timezone.timedelta(days=10))
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.get(f'/matches/api/match-statistics/{match.id}/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        stats = data['statistics']
        self.assertEqual(stats['days_active'], 10)
        self.assertEqual(stats['status'], 'active')
        self.assertEqual(stats['partner']['username'], 'user2')
        
    def test_refresh_potential_matches_api(self):
        """Test refreshing potential matches via API"""
        self.client.login(username='user1', password='testpass123')
        response = self.client.post('/matches/api/refresh-matches/')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('message', data)
        
    def test_unauthorized_access(self):
        """Test that API endpoints require authentication"""
        endpoints = [
            '/matches/api/potential-matches/',
            '/matches/api/my-matches/',
            '/matches/api/pending-requests/',
            '/matches/api/refresh-matches/',
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            # Should redirect to login or return 403/401
            self.assertIn(response.status_code, [302, 401, 403])
            
    def test_access_control(self):
        """Test that users can only access their own data"""
        # Create a match request between user2 and another user
        user3 = User.objects.create_user(
            username='user3',
            email='user3@test.com',
            password='testpass123'
        )
        
        match_request = MatchRequest.objects.create(
            sender=self.user2,
            receiver=user3,
            sender_teaches=self.korean,
            sender_learns=self.english,
            message='Hi!'
        )
        
        # User1 should not be able to respond to this request
        self.client.login(username='user1', password='testpass123')
        response = self.client.post(f'/matches/api/respond-request/{match_request.id}/', {
            'action': 'accept'
        })
        
        self.assertEqual(response.status_code, 404)  # Should not find the request



class MatchingLogicTests(TestCase):
    """Regression tests for the matching service logic."""

    def setUp(self):
        from users.models import Language, UserLanguage
        from .services import MatchingService
        self.S = MatchingService
        U = get_user_model()
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')
        self.a = U.objects.create_user('a', password='x', interests='music, travel, coding')
        self.b = U.objects.create_user('b', password='x', interests='Travel;Coding')
        for u, native, learning in ((self.a, self.en, self.ko), (self.b, self.ko, self.en)):
            UserLanguage.objects.create(user=u, language=native, proficiency='native', language_type='native')
            UserLanguage.objects.create(user=u, language=learning, proficiency='beginner', language_type='learning')

    def test_interest_tokenizer_handles_punctuation(self):
        self.assertEqual(self.S._tokenize_interests('Music, travel;Coding'), {'music', 'travel', 'coding'})

    def test_finds_mutual_partner_once(self):
        found = self.S.find_potential_matches(self.a, refresh=True)
        self.assertEqual([m.potential_partner for m in found], [self.b])
        self.assertGreaterEqual(found[0].compatibility_score, 60)

    def test_excludes_active_match_and_pending_request(self):
        req, created = self.S.send_match_request(self.a, self.b, self.en, self.ko)
        self.assertTrue(created)
        self.assertEqual(self.S.find_potential_matches(self.a, refresh=True), [])

    def test_self_request_rejected(self):
        self.assertEqual(self.S.send_match_request(self.a, self.a, self.en, self.ko), (None, False))

    def test_reverse_request_does_not_create_duplicate(self):
        req, _ = self.S.send_match_request(self.a, self.b, self.en, self.ko)
        again, created = self.S.send_match_request(self.b, self.a, self.ko, self.en)
        self.assertFalse(created)
        self.assertEqual(again.pk, req.pk)

    def test_resend_after_decline_reopens(self):
        req, _ = self.S.send_match_request(self.a, self.b, self.en, self.ko)
        self.S.respond_to_match_request(req, accept=False)
        again, created = self.S.send_match_request(self.a, self.b, self.en, self.ko, 'hi')
        self.assertTrue(created)
        self.assertEqual(again.status, 'pending')

    def test_accept_twice_is_idempotent(self):
        req, _ = self.S.send_match_request(self.a, self.b, self.en, self.ko)
        m1 = self.S.respond_to_match_request(req, accept=True)
        m2 = self.S.respond_to_match_request(req, accept=True)
        self.assertIsNotNone(m1)
        self.assertIsNone(m2)
        self.assertEqual(Match.objects.count(), 1)


class ConversationPromptsTests(TestCase):
    def test_prompts_are_mixed_levels_and_deterministic(self):
        from .prompts import conversation_prompts
        a = conversation_prompts(seed=1)
        b = conversation_prompts(seed=1)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 6)
        self.assertEqual({p['level'] for p in a}, {'warmup', 'everyday', 'deeper'})

    def test_match_detail_shows_prompts(self):
        U = get_user_model()
        u1 = U.objects.create_user('pa', 'pa@x.com', 'pw12345!')
        u2 = U.objects.create_user('pb', 'pb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=u1, user2=u2, user1_teaches=en, user1_learns=ko, status='active')
        c = Client(); c.force_login(u1)
        r = c.get(reverse('matches:match_detail', args=[m.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Not sure what to talk about?')


class MatchFeedbackTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.u1 = U.objects.create_user('fa', 'fa@x.com', 'pw12345!')
        self.u2 = U.objects.create_user('fb', 'fb@x.com', 'pw12345!')
        self.u3 = U.objects.create_user('fc', 'fc@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.m = Match.objects.create(user1=self.u1, user2=self.u2, user1_teaches=en, user1_learns=ko, status='active')
        self.url = reverse('matches:submit_feedback', args=[self.m.id])

    def test_create_and_update(self):
        from .models import MatchFeedback
        c = Client(); c.force_login(self.u1)
        r = c.post(self.url, {'rating': '4', 'comment': 'nice', 'helpful': 'true'})
        self.assertEqual(r.json()['created'], True)
        r = c.post(self.url, {'rating': '2', 'helpful': 'false'})
        self.assertEqual(r.json()['created'], False)
        fb = MatchFeedback.objects.get(match=self.m, author=self.u1)
        self.assertEqual((fb.rating, fb.helpful), (2, False))
        self.assertEqual(MatchFeedback.objects.count(), 1)

    def test_validation_and_access(self):
        c = Client(); c.force_login(self.u1)
        for bad in ('0', '6', 'x', ''):
            self.assertEqual(c.post(self.url, {'rating': bad}).status_code, 400)
        c3 = Client(); c3.force_login(self.u3)
        self.assertEqual(c3.post(self.url, {'rating': '5'}).status_code, 403)

    def test_detail_renders_panel_and_hides_partner_feedback(self):
        from .models import MatchFeedback
        MatchFeedback.objects.create(match=self.m, author=self.u2, rating=1, comment='SECRETCOMMENT')
        c = Client(); c.force_login(self.u1)
        r = c.get(reverse('matches:match_detail', args=[self.m.id]))
        self.assertContains(r, 'feedback-panel')
        self.assertNotContains(r, 'SECRETCOMMENT')


class QuickMatchTests(TestCase):
    def setUp(self):
        from . import quick
        self.quick = quick
        U = get_user_model()
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')
        self.fr = Language.objects.create(name='French', code='fr')

        def mk(name, teach, learn):
            u = U.objects.create_user(name, f'{name}@x.com', 'pw12345!', email_verified=True)
            UserLanguage.objects.create(user=u, language=teach, language_type='native', proficiency='native')
            UserLanguage.objects.create(user=u, language=learn, language_type='learning', proficiency='beginner')
            return u
        self.mk = mk
        self.a = mk('qa', self.en, self.ko)
        self.b = mk('qb', self.ko, self.en)

    def test_pairs_mirrored_users(self):
        self.assertIsNone(self.quick.join_queue(self.a))
        m = self.quick.join_queue(self.b)
        self.assertEqual(m.status, 'trial')
        self.assertEqual({m.user1, m.user2}, {self.a, self.b})
        self.assertEqual(self.quick.poll(self.a), m)
        self.assertIsNone(self.quick.poll(self.a))  # consumed

    def test_no_pair_when_languages_do_not_mirror(self):
        c = self.mk('qc', self.fr, self.en)
        self.assertIsNone(self.quick.join_queue(self.a))
        self.assertIsNone(self.quick.join_queue(c))
        self.assertEqual(Match.objects.count(), 0)

    def test_never_pairs_blocked_users(self):
        from users.models import UserBlock
        UserBlock.objects.create(blocker=self.a, blocked=self.b)
        self.quick.join_queue(self.a)
        self.assertIsNone(self.quick.join_queue(self.b))
        self.assertEqual(Match.objects.count(), 0)

    def test_never_pairs_existing_partners(self):
        Match.objects.create(user1=self.a, user2=self.b, user1_teaches=self.en, user1_learns=self.ko, status='ended')
        self.quick.join_queue(self.a)
        self.assertIsNone(self.quick.join_queue(self.b))

    def test_decide_requires_timer_then_both_keep(self):
        from datetime import timedelta
        self.quick.join_queue(self.a)
        m = self.quick.join_queue(self.b)
        with self.assertRaises(self.quick.QuickMatchError):
            self.quick.decide(m, self.a, True)
        Match.objects.filter(pk=m.pk).update(trial_ends_at=timezone.now() - timedelta(seconds=1))
        m = self.quick.decide(m, self.a, True)
        self.assertEqual(m.status, 'trial')
        m = self.quick.decide(m, self.b, True)
        self.assertEqual(m.status, 'active')

    def test_skip_ends_match(self):
        from datetime import timedelta
        self.quick.join_queue(self.a)
        m = self.quick.join_queue(self.b)
        Match.objects.filter(pk=m.pk).update(trial_ends_at=timezone.now() - timedelta(seconds=1))
        m = self.quick.decide(m, self.b, False)
        self.assertEqual(m.status, 'ended')

    def test_http_flow_and_access(self):
        ca, cb = Client(), Client()
        ca.force_login(self.a); cb.force_login(self.b)
        r = ca.post(reverse('matches:quick_match_join'))
        self.assertEqual(r.json()['status'], 'waiting')
        r = cb.post(reverse('matches:quick_match_join'))
        self.assertEqual(r.json()['status'], 'matched')
        r = ca.get(reverse('matches:quick_match_status'))
        self.assertEqual(r.json()['status'], 'matched')
        mid = r.json()['match_id']
        c3 = Client(); c3.force_login(self.mk('qz', self.en, self.ko))
        self.assertEqual(c3.post(reverse('matches:quick_match_decide', args=[mid]), {'choice': 'keep'}).status_code, 403)
        self.assertEqual(ca.get(reverse('matches:quick_match_call', args=[mid])).status_code, 200)
        self.assertEqual(ca.get(reverse('matches:quick_match')).status_code, 200)

    def test_http_decide_and_result(self):
        from datetime import timedelta
        ca, cb, cx = Client(), Client(), Client()
        ca.force_login(self.a); cb.force_login(self.b); cx.force_login(self.mk('qy', self.en, self.ko))
        self.quick.join_queue(self.a)
        m = self.quick.join_queue(self.b)
        dec = reverse('matches:quick_match_decide', args=[m.id])
        res = reverse('matches:quick_match_result', args=[m.id])
        # timer still running
        self.assertEqual(ca.post(dec, {'choice': 'keep'}).status_code, 400)
        Match.objects.filter(pk=m.pk).update(trial_ends_at=timezone.now() - timedelta(seconds=1))
        # bad choice, non-participant, GET not allowed
        self.assertEqual(ca.post(dec, {'choice': 'maybe'}).status_code, 400)
        self.assertEqual(cx.get(res).status_code, 403)
        self.assertEqual(ca.get(dec).status_code, 405)
        r = ca.post(dec, {'choice': 'keep'})
        self.assertEqual(r.json()['status'], 'trial')
        self.assertEqual(cb.get(res).json()['status'], 'trial')
        r = cb.post(dec, {'choice': 'keep'})
        self.assertEqual(r.json()['status'], 'active')
        self.assertEqual(ca.get(res).json()['status'], 'active')

    def test_user_without_languages_gets_clear_error(self):
        u = get_user_model().objects.create_user('nolang', 'n@x.com', 'pw12345!', email_verified=True)
        c = Client(); c.force_login(u)
        r = c.post(reverse('matches:quick_match_join'))
        self.assertEqual(r.status_code, 400)

    def test_block_during_trial_ends_it(self):
        self.quick.join_queue(self.a)
        m = self.quick.join_queue(self.b)
        c = Client(); c.force_login(self.a)
        c.post(reverse('users:block_user', args=[self.b.id]))
        m.refresh_from_db()
        self.assertEqual(m.status, 'ended')


class QuickMatchEmailGateTests(TestCase):
    def test_unverified_user_cannot_join(self):
        from . import quick
        u = get_user_model().objects.create_user('uv', 'uv@x.com', 'pw12345!')
        c = Client(); c.force_login(u)
        r = c.post(reverse('matches:quick_match_join'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('Verify your email', r.json()['error'])
        self.assertContains(c.get(reverse('matches:quick_match')), 'Verify your email')

    def test_gate_can_be_disabled(self):
        from . import quick
        u = get_user_model().objects.create_user('uv2', 'uv2@x.com', 'pw12345!')
        with self.settings(QUICK_MATCH_REQUIRE_VERIFIED_EMAIL=False):
            self.assertTrue(quick.can_quick_match(u))


class RequestsPageTests(TestCase):
    def test_requests_page_lists_incoming_and_outgoing(self):
        from .models import MatchRequest
        U = get_user_model()
        a = U.objects.create_user('ra', 'ra@x.com', 'pw12345!')
        b = U.objects.create_user('rb', 'rb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        MatchRequest.objects.create(sender=b, receiver=a, sender_teaches=ko, sender_learns=en, message='hi there')
        MatchRequest.objects.create(sender=a, receiver=b, sender_teaches=en, sender_learns=ko)
        c = Client(); c.force_login(a)
        r = c.get(reverse('matches:requests'))
        self.assertContains(r, 'data-respond="accept"')
        self.assertContains(r, 'hi there')
        self.assertContains(r, 'data-cancel')


class MyMatchesPageTests(TestCase):
    def test_empty_and_filled(self):
        U = get_user_model()
        a = U.objects.create_user('ma', 'ma@x.com', 'pw12345!')
        b = U.objects.create_user('mb', 'mb@x.com', 'pw12345!')
        c = Client(); c.force_login(a)
        self.assertContains(c.get(reverse('matches:my_matches')), 'No matches yet')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=a, user2=b, user1_teaches=en, user1_learns=ko, status='active')
        r = c.get(reverse('matches:my_matches'))
        self.assertContains(r, 'mb')
        self.assertContains(r, reverse('matches:match_detail', args=[m.id]))
        self.assertNotContains(r, 'No matches yet')


class SendRequestPageTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.a = U.objects.create_user('sra', 'sra@x.com', 'pw12345!')
        self.b = U.objects.create_user('srb', 'srb@x.com', 'pw12345!', bio='Hello there', interests='chess')
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')
        self.pm = PotentialMatch.objects.create(user=self.a, potential_partner=self.b, user_teaches=self.en, user_learns=self.ko, compatibility_score=82)
        self.client.force_login(self.a)
        self.url = reverse('matches:send_request', args=[self.pm.id])

    def test_page_shows_partner_and_languages(self):
        r = self.client.get(self.url)
        self.assertContains(r, 'Say hi to srb')
        self.assertContains(r, 'Hello there')
        self.assertContains(r, 'English')
        self.assertContains(r, '82% match')

    def test_post_creates_request_with_message(self):
        r = self.client.post(self.url, {'message': 'hi!'})
        self.assertEqual(r.status_code, 302)
        mr = MatchRequest.objects.get(sender=self.a, receiver=self.b)
        self.assertEqual(mr.message, 'hi!')

    def test_other_users_potential_match_is_404(self):
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(self.url).status_code, 404)
