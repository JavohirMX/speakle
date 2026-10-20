from django.contrib.auth import get_user_model
from users.models import Language, UserLanguage, UserReport
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


class UxFlowTests(TestCase):
    """Sign-up and sign-in flow behaviour (NN/g efficiency and error recovery)."""

    def test_username_check(self):
        from django.contrib.auth import get_user_model
        get_user_model().objects.create_user('taken', 'a@x.com', 'pw12345!x')
        self.assertEqual(self.client.get('/users/check-username/?username=taken').json()['available'], False)
        self.assertEqual(self.client.get('/users/check-username/?username=freeone').json()['available'], True)
        self.assertIsNone(self.client.get('/users/check-username/?username=ab').json()['available'])

    def test_login_follows_safe_next_only(self):
        from django.contrib.auth import get_user_model
        get_user_model().objects.create_user('nx', 'n@x.com', 'pw12345!x')
        r = self.client.post('/users/login/', {'username': 'nx', 'password': 'pw12345!x', 'next': '/matches/requests/'})
        self.assertEqual(r.url, '/matches/requests/')
        self.client.logout()
        r = self.client.post('/users/login/', {'username': 'nx', 'password': 'pw12345!x', 'next': 'https://evil.example/'})
        self.assertEqual(r.url, '/matches/')

    def test_password_reset_page_exists(self):
        self.assertEqual(self.client.get('/users/password-reset/').status_code, 200)


from django.test import Client
from django.urls import reverse


class ProfilePageTests(TestCase):
    def test_profile_renders_and_saves(self):
        U = get_user_model()
        u = U.objects.create_user('pp', 'pp@x.com', 'pw12345!')
        c = Client(); c.force_login(u)
        r = c.get(reverse('users:profile'))
        self.assertContains(r, 'Profile information')
        self.assertContains(r, 'No languages yet')
        r = c.post(reverse('users:profile'), {'first_name': 'Pat', 'last_name': '', 'email': 'pp@x.com', 'bio': 'hello', 'interests': 'tea'})
        self.assertEqual(r.status_code, 302)
        u.refresh_from_db()
        self.assertEqual((u.first_name, u.bio), ('Pat', 'hello'))

    def test_profile_has_sign_out_form(self):
        # On phones the header menu and footer are hidden, so the profile page
        # must carry a working POST sign-out.
        U = get_user_model()
        u = U.objects.create_user('so', 'so@x.com', 'pw12345!')
        c = Client(); c.force_login(u)
        r = c.get(reverse('users:profile'))
        self.assertContains(r, 'id="acct-h"')
        r = c.post(reverse('users:logout'))
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('_auth_user_id', c.session)


class LanguagePagesTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.u = U.objects.create_user('lpu', 'lpu@x.com', 'pw12345!')
        self.ko = Language.objects.create(name='Korean', code='ko')
        self.ul = UserLanguage.objects.create(user=self.u, language=self.ko, proficiency='beginner', language_type='learning')
        self.client.force_login(self.u)

    def test_add_page_renders_and_adds(self):
        en = Language.objects.create(name='English', code='en')
        r = self.client.get(reverse('users:add_language'))
        self.assertContains(r, 'page-head')
        r = self.client.post(reverse('users:add_language'), {'language': en.id, 'proficiency': 'native', 'language_type': 'native'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(UserLanguage.objects.filter(user=self.u, language=en).exists())

    def test_delete_page_confirms_then_removes(self):
        url = reverse('users:delete_language', args=[self.ul.id])
        self.assertContains(self.client.get(url), 'Korean')
        self.client.post(url)
        self.assertFalse(UserLanguage.objects.filter(id=self.ul.id).exists())

    def test_cannot_delete_other_users_language(self):
        o = get_user_model().objects.create_user('lpo', 'lpo@x.com', 'pw12345!')
        self.client.force_login(o)
        self.client.post(reverse('users:delete_language', args=[self.ul.id]))
        self.assertTrue(UserLanguage.objects.filter(id=self.ul.id).exists())


class ThrottleTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = get_user_model().objects.create_user('thr', 'thr@x.com', 'pw12345!')

    def test_login_locks_after_repeated_failures(self):
        from users.throttle import LOGIN_MAX_FAILURES
        for _ in range(LOGIN_MAX_FAILURES):
            r = self.client.post(reverse('users:login'), {'username': 'thr', 'password': 'wrong'})
            self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse('users:login'), {'username': 'thr', 'password': 'pw12345!'})
        self.assertEqual(r.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_success_resets_counter(self):
        for _ in range(3):
            self.client.post(reverse('users:login'), {'username': 'thr', 'password': 'wrong'})
        r = self.client.post(reverse('users:login'), {'username': 'thr', 'password': 'pw12345!'})
        self.assertEqual(r.status_code, 302)

    def test_same_report_not_duplicated_but_new_reason_is_kept(self):
        other = get_user_model().objects.create_user('thr2', 'thr2@x.com', 'pw12345!')
        self.client.force_login(self.user)
        url = reverse('users:report_user', args=[other.id])
        self.assertTrue(self.client.post(url, {'reason': 'spam'}).json()['success'])
        self.assertTrue(self.client.post(url, {'reason': 'spam'}).json()['success'])
        self.assertEqual(UserReport.objects.count(), 1)
        self.client.post(url, {'reason': 'harassment'})
        self.assertEqual(UserReport.objects.count(), 2)


class SignupLimitTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')

    def _post(self, n):
        return self.client.post(reverse('users:register'), {
            'username': 'su%d' % n, 'email': 'su%d@x.com' % n, 'first_name': 'Su',
            'native_language': self.en.id, 'target_language': self.ko.id,
            'target_proficiency': 'beginner',
            'password1': 'Sup3r-secret-pw', 'password2': 'Sup3r-secret-pw'})

    def test_off_by_default(self):
        for n in range(3):
            self.client.logout()
            self.assertEqual(self._post(n).status_code, 302)

    def test_cap_applies_when_set(self):
        from django.test import override_settings
        with override_settings(SIGNUPS_PER_HOUR_PER_IP=2):
            for n in range(2):
                self.client.logout()
                self.assertEqual(self._post(n).status_code, 302)
            self.client.logout()
            self.assertEqual(self._post(9).status_code, 429)
            self.assertFalse(get_user_model().objects.filter(username='su9').exists())


class ProfileFormLimitsTests(TestCase):
    def _form(self, **over):
        from .forms import UserProfileForm
        data = {'first_name': 'A', 'last_name': '', 'email': 'pf@x.com', 'bio': '', 'interests': ''}
        data.update(over)
        return UserProfileForm(data)

    def test_overlong_bio_and_interests_are_rejected(self):
        self.assertIn('bio', self._form(bio='x' * 1001).errors)
        self.assertIn('interests', self._form(interests='y' * 501).errors)

    def test_limits_are_inclusive(self):
        f = self._form(bio='x' * 1000, interests='y' * 500)
        self.assertNotIn('bio', f.errors)
        self.assertNotIn('interests', f.errors)

    def test_oversized_picture_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .forms import UserProfileForm
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (4, 4)).save(buf, 'PNG')
        big = SimpleUploadedFile('a.png', buf.getvalue() + b'0' * (5 * 1024 * 1024 + 1), content_type='image/png')
        f = UserProfileForm({'first_name': 'A', 'email': 'pf@x.com', 'bio': '', 'interests': ''}, {'profile_picture': big})
        self.assertIn('under 5 MB', str(f.errors.get('profile_picture')))


class BlockClearsSuggestionsTests(TestCase):
    def test_blocking_removes_stored_suggestions_both_ways(self):
        from django.contrib.auth import get_user_model
        from matches.models import PotentialMatch
        U = get_user_model()
        a = U.objects.create_user('bs_a', 'bsa@x.com', 'pw12345!')
        b = U.objects.create_user('bs_b', 'bsb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        for u, p in ((a, b), (b, a)):
            PotentialMatch.objects.create(user=u, potential_partner=p, user_teaches=en, user_learns=ko, compatibility_score=70)
        self.client.force_login(a)
        r = self.client.post(f'/users/block/{b.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(PotentialMatch.objects.exists())


class PasswordResetFlowTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.U = get_user_model()
        self.u = self.U.objects.create_user('pr_user', 'pr@x.com', 'OldPw12345!')

    def test_unknown_email_looks_the_same_and_sends_nothing(self):
        from django.core import mail
        r = self.client.post('/users/password-reset/', {'email': 'nobody@x.com'})
        self.assertRedirects(r, '/users/password-reset/sent/')
        self.assertEqual(len(mail.outbox), 0)

    def test_full_flow_sets_new_password(self):
        import re
        from django.core import mail
        r = self.client.post('/users/password-reset/', {'email': 'pr@x.com'})
        self.assertRedirects(r, '/users/password-reset/sent/')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['pr@x.com'])
        link = re.search(r'/users/password-reset/[\w-]+/[\w-]+/', mail.outbox[0].body).group(0)
        r = self.client.get(link, follow=True)
        r = self.client.post(r.redirect_chain[-1][0], {'new_password1': 'BrandNew-98765!', 'new_password2': 'BrandNew-98765!'})
        self.assertRedirects(r, '/users/password-reset/done/')
        self.assertTrue(self.client.login(username='pr_user', password='BrandNew-98765!'))
        self.assertFalse(self.client.login(username='pr_user', password='OldPw12345!'))

    def test_deactivated_account_gets_no_reset_email(self):
        from django.core import mail
        self.U.objects.filter(pk=self.u.pk).update(is_active=False)
        self.client.post('/users/password-reset/', {'email': 'pr@x.com'})
        self.assertEqual(len(mail.outbox), 0)


class UniqueEmailTests(TestCase):
    def _reg(self, email, username='newbie'):
        from users.models import Language
        en, _ = Language.objects.get_or_create(code='en', defaults={'name': 'English'})
        ko, _ = Language.objects.get_or_create(code='ko', defaults={'name': 'Korean'})
        return self.client.post('/users/register/', {
            'username': username, 'first_name': 'N', 'email': email, 'native_language': en.id,
            'target_language': ko.id, 'target_proficiency': 'beginner',
            'password1': 'Zx9!kqpwoeiR', 'password2': 'Zx9!kqpwoeiR'})

    def test_registration_rejects_an_email_in_use_ignoring_case(self):
        from django.contrib.auth import get_user_model
        get_user_model().objects.create_user('first', 'Taken@Example.com', 'pw12345!x')
        r = self._reg('taken@example.com')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'already has an account')
        self.assertFalse(get_user_model().objects.filter(username='newbie').exists())

    def test_registration_accepts_a_new_email(self):
        from django.contrib.auth import get_user_model
        r = self._reg('fresh@example.com')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(get_user_model().objects.filter(username='newbie').exists())

    def test_profile_cannot_take_someone_elses_email_but_can_keep_its_own(self):
        from django.contrib.auth import get_user_model
        from users.forms import UserProfileForm
        U = get_user_model()
        a = U.objects.create_user('pa', 'pa@x.com', 'pw12345!x')
        U.objects.create_user('pb', 'pb@x.com', 'pw12345!x')
        base = {'first_name': 'A', 'last_name': '', 'bio': '', 'interests': ''}
        self.assertIn('email', UserProfileForm({**base, 'email': 'PB@x.com'}, instance=a).errors)
        self.assertNotIn('email', UserProfileForm({**base, 'email': 'pa@x.com'}, instance=a).errors)

    def test_duplicate_report_command_is_read_only(self):
        from io import StringIO
        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        U = get_user_model()
        U.objects.create_user('d1', 'dup@x.com', 'pw12345!x')
        U.objects.create_user('d2', 'DUP@x.com', 'pw12345!x')
        out = StringIO()
        call_command('duplicate_emails', stdout=out)
        self.assertIn('d1', out.getvalue()); self.assertIn('d2', out.getvalue())
        self.assertEqual(U.objects.filter(email__iexact='dup@x.com').count(), 2)


class LogoutPostOnlyTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        get_user_model().objects.create_user('lo', 'lo@x.com', 'pw12345!x')
        self.client.login(username='lo', password='pw12345!x')

    def test_get_does_not_sign_out(self):
        self.assertEqual(self.client.get('/users/logout/').status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)

    def test_post_signs_out(self):
        r = self.client.post('/users/logout/')
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_pages_render_logout_as_a_post_form_not_a_link(self):
        html = self.client.get('/users/profile/').content.decode()
        self.assertIn('method="post" action="/users/logout/"', html)
        self.assertNotIn('href="/users/logout/"', html)


class RegistrationAtomicTests(TestCase):
    def test_failed_language_creation_leaves_no_half_account(self):
        from unittest import mock
        from users.forms import UserRegistrationForm
        en = Language.objects.create(name='English', code='en')
        es = Language.objects.create(name='Spanish', code='es')
        form = UserRegistrationForm({
            'username': 'atomic1', 'first_name': 'A', 'email': 'atomic1@example.com',
            'native_language': en.pk, 'target_language': es.pk, 'target_proficiency': 'beginner',
            'password1': 'Str0ng-pass-123', 'password2': 'Str0ng-pass-123',
        })
        self.assertTrue(form.is_valid(), form.errors)
        with mock.patch.object(UserLanguage.objects, 'create', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                form.save()
        self.assertFalse(get_user_model().objects.filter(username='atomic1').exists())


class ProfilePictureCleanupTests(TestCase):
    def test_replaced_picture_file_is_deleted(self):
        import io, shutil, tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image

        def png(name):
            buf = io.BytesIO(); Image.new('RGB', (4, 4), 'red').save(buf, 'PNG')
            return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')

        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        with override_settings(MEDIA_ROOT=media):
            user = get_user_model().objects.create_user('pic1', 'pic1@example.com', 'pw12345!x')
            self.client.force_login(user)
            base = {'first_name': 'P', 'last_name': '', 'email': 'pic1@example.com',
                    'bio': '', 'interests': ''}
            self.client.post('/users/profile/', {**base, 'profile_picture': png('a.png')})
            user.refresh_from_db()
            first = user.profile_picture.path
            self.assertTrue(__import__('os').path.exists(first))
            self.client.post('/users/profile/', {**base, 'profile_picture': png('b.png')})
            user.refresh_from_db()
            self.assertNotEqual(user.profile_picture.path, first)
            self.assertFalse(__import__('os').path.exists(first))
            self.assertTrue(__import__('os').path.exists(user.profile_picture.path))
