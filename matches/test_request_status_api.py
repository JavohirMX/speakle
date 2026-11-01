"""Tests for the check_request_status API endpoint."""
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from users.models import Language
from .models import MatchRequest

User = get_user_model()


class CheckRequestStatusApiTest(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username='crs1', email='crs1@x.com', password='x')
        self.receiver = User.objects.create_user(
            username='crs2', email='crs2@x.com', password='x')
        self.outsider = User.objects.create_user(
            username='crs3', email='crs3@x.com', password='x')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.req = MatchRequest.objects.create(
            sender=self.sender, receiver=self.receiver,
            sender_teaches=en, sender_learns=ko)
        self.url = reverse('matches:check_request_status',
                           args=[self.req.id])

    def test_outsider_gets_403(self):
        self.client.force_login(self.outsider)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['error'], 'Access denied')

    def test_sender_sees_pending_status(self):
        self.client.force_login(self.sender)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['status'], 'pending')
        self.assertIsNone(body['responded_at'])

    def test_receiver_sees_answered_status_and_timestamp(self):
        self.req.status = 'accepted'
        self.req.responded_at = timezone.now()
        self.req.save()
        self.client.force_login(self.receiver)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['status'], 'accepted')
        self.assertIsNotNone(body['responded_at'])

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/users/login/', r.url)
