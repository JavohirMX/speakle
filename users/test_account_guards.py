"""Leftover account guards: verified-resend, email-less resend, self-report."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class ResendVerificationGuardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'rvu', 'rvu@x.com', 'pw12345!')
        self.client.force_login(self.user)
        self.url = reverse('users:resend_verification')

    def test_already_verified_short_circuits(self):
        self.user.email_verified = True
        self.user.save()
        r = self.client.post(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['already_verified'])

    def test_user_without_email_gets_400(self):
        self.user.email = ''
        self.user.save()
        with patch('users.views.send_verification_email', return_value=False):
            r = self.client.post(self.url)
        self.assertEqual(r.status_code, 400)
        self.assertIn('email', r.json()['error'])


class SelfReportGuardTests(TestCase):
    def test_cannot_report_yourself(self):
        user = User.objects.create_user('sr1', 'sr1@x.com', 'pw12345!')
        self.client.force_login(user)
        r = self.client.post(reverse('users:report_user', args=[user.id]),
                             {'reason': 'spam'})
        self.assertEqual(r.status_code, 400)
        from .models import UserReport
        self.assertEqual(UserReport.objects.count(), 0)
