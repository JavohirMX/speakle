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
