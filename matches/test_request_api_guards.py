"""Request API guards: duplicate send, re-respond, match_detail access."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.models import Language
from .models import PotentialMatch, MatchRequest, Match
from .services import MatchingService

User = get_user_model()


class RequestApiGuardTests(TestCase):
    def setUp(self):
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')
        self.a = User.objects.create_user('ra_a', 'raa@x.com', 'pw12345!')
        self.b = User.objects.create_user('ra_b', 'rab@x.com', 'pw12345!')
        self.pm = PotentialMatch.objects.create(
            user=self.a, potential_partner=self.b,
            user_teaches=self.en, user_learns=self.ko)

    def test_duplicate_send_returns_400(self):
        self.client.force_login(self.a)
        url = reverse('matches:send_request_api', args=[self.pm.id])
        first = self.client.post(url)
        self.assertEqual(first.status_code, 200)
        second = self.client.post(url)
        self.assertEqual(second.status_code, 400)
        self.assertFalse(second.json()['success'])
        self.assertEqual(MatchRequest.objects.count(), 1)

    def test_re_respond_returns_400(self):
        req, _ = MatchingService.send_match_request(
            self.a, self.b, self.en, self.ko)
        MatchingService.respond_to_match_request(req, accept=False)
        self.client.force_login(self.b)
        r = self.client.post(
            reverse('matches:respond_request_api', args=[req.id]),
            {'action': 'accept'})
        self.assertEqual(r.status_code, 400)
        req.refresh_from_db()
        self.assertEqual(req.status, 'declined')  # unchanged

    def test_match_detail_outsider_redirected(self):
        match = Match.objects.create(
            user1=self.a, user2=self.b,
            user1_teaches=self.en, user1_learns=self.ko, status='active')
        outsider = User.objects.create_user('ra_c', 'rac@x.com', 'pw12345!')
        self.client.force_login(outsider)
        r = self.client.get(reverse('matches:match_detail', args=[match.id]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/matches/', r.url)
