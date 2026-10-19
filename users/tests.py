from django.test import TestCase

# Create your tests here.


class BlockReportTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        U = get_user_model()
        self.a = U.objects.create_user('a', password='x')
        self.b = U.objects.create_user('b', password='x')
        self.client.login(username='a', password='x')

    def test_login_required(self):
        self.client.logout()
        r = self.client.post(f'/users/block/{self.b.id}/')
        self.assertEqual(r.status_code, 302)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(f'/users/block/{self.b.id}/').status_code, 405)

    def test_cannot_block_self(self):
        self.assertEqual(self.client.post(f'/users/block/{self.a.id}/').status_code, 400)

    def test_block_ends_match_and_prevents_requests(self):
        from users.models import Language, UserBlock
        from matches.models import Match, MatchRequest
        from matches.services import MatchingService
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en, user1_learns=ko, status='active')
        r = self.client.post(f'/users/block/{self.b.id}/')
        self.assertEqual(r.status_code, 200)
        m.refresh_from_db()
        self.assertEqual(m.status, 'ended')
        self.assertTrue(UserBlock.objects.filter(blocker=self.a, blocked=self.b).exists())
        # either direction is refused afterwards
        self.assertEqual(MatchingService.send_match_request(self.b, self.a, ko, en), (None, False))
        self.assertEqual(MatchingService.send_match_request(self.a, self.b, en, ko), (None, False))

    def test_report_validates_reason(self):
        from users.models import UserReport
        self.assertEqual(self.client.post(f'/users/report/{self.b.id}/', {'reason': 'nope'}).status_code, 400)
        r = self.client.post(f'/users/report/{self.b.id}/', {'reason': 'spam', 'details': 'x'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(UserReport.objects.count(), 1)


class MatchDetailSafetyPanelTests(TestCase):
    def test_panel_rendered_for_participant(self):
        from django.contrib.auth import get_user_model
        from users.models import Language
        from matches.models import Match
        U = get_user_model()
        a = U.objects.create_user('a', password='x'); b = U.objects.create_user('b', password='x')
        en = Language.objects.create(name='English', code='en'); ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=a, user2=b, user1_teaches=en, user1_learns=ko, status='active')
        self.client.login(username='a', password='x')
        r = self.client.get(f'/matches/match/{m.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="safety-panel"')
        self.assertContains(r, f'var userId = {b.id};')


from django.contrib.auth import get_user_model


class EmailVerificationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('ev', 'ev@x.com', 'pw12345!')

    def test_valid_link_verifies(self):
        from django.urls import reverse
        from .verification import make_token
        r = self.client.get(reverse('users:verify_email', args=[make_token(self.user)]))
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_bad_token_does_not_verify(self):
        from django.urls import reverse
        self.client.get(reverse('users:verify_email', args=['garbage']))
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_token_dies_when_email_changes(self):
        from django.urls import reverse
        from .verification import make_token
        token = make_token(self.user)
        self.user.email = 'new@x.com'
        self.user.save()
        self.client.get(reverse('users:verify_email', args=[token]))
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_resend_sends_mail_and_is_throttled(self):
        from django.core import mail
        from django.urls import reverse
        self.client.force_login(self.user)
        r = self.client.post(reverse('users:resend_verification'))
        self.assertTrue(r.json()['success'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('verify-email/', mail.outbox[0].body)
        r = self.client.post(reverse('users:resend_verification'))
        self.assertEqual(r.status_code, 429)

    def test_profile_email_change_resets_verified(self):
        from .forms import UserProfileForm
        self.user.email_verified = True
        self.user.save()
        form = UserProfileForm({'first_name': '', 'last_name': '', 'email': 'other@x.com', 'bio': '', 'interests': ''}, instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)
