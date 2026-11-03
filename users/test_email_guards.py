"""Email actions must not crash the site when the email backend is
misconfigured (bad API keys, dead SMTP host): register, resend
verification and password reset all degrade gracefully."""
import smtplib
from django.core.mail.backends.base import BaseEmailBackend
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class RaisingEmailBackend(BaseEmailBackend):
    """Simulates a broken provider: every send raises, like smtplib does
    on connection/auth failure."""
    def send_messages(self, email_messages):
        raise smtplib.SMTPException('535 authentication failed')


BROKEN = 'users.test_email_guards.RaisingEmailBackend'


@override_settings(EMAIL_BACKEND=BROKEN)
class EmailGuardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('guarduser', 'guard@example.com', 'pw12345!')

    def test_register_still_signs_up_when_email_fails(self):
        from users.models import Language
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        r = self.client.post(reverse('users:register'), {
            'username': 'newbie', 'email': 'newbie@example.com',
            'first_name': 'New',
            'native_language': en.pk, 'target_language': ko.pk,
            'target_proficiency': 'beginner',
            'password1': 'Str0ng!Pass', 'password2': 'Str0ng!Pass',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username='newbie').exists())
        page = self.client.get(reverse('matches:find_matches'))
        self.assertContains(page, 'could not send the confirmation email', status_code=200)

    def test_resend_verification_returns_json_error_not_crash(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse('users:resend_verification'))
        self.assertEqual(r.status_code, 500)  # handled JSON error, not an unhandled crash
        self.assertEqual(r['Content-Type'], 'application/json')
        self.assertFalse(r.json()['success'])

    def test_password_reset_does_not_crash_when_email_fails(self):
        r = self.client.post(reverse('users:password_reset'), {'email': 'guard@example.com'})
        # Same response as success: never reveal whether the email exists or the backend broke.
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('users:password_reset_done').rstrip('/'), r.url.rstrip('/'))


class EmailTimeoutWiringTests(TestCase):
    def test_smtp_backend_honours_email_timeout_setting(self):
        from django.core.mail.backends.smtp import EmailBackend
        with override_settings(EMAIL_TIMEOUT=10):
            self.assertEqual(EmailBackend().timeout, 10)
