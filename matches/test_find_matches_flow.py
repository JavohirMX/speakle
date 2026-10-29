"""find_matches core flow: auto-generate once, refresh regenerates."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.models import Language, UserLanguage
from .models import PotentialMatch

User = get_user_model()


class FindMatchesFlowTests(TestCase):
    def setUp(self):
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')
        self.a = User.objects.create_user('fm_a', 'fma@x.com', 'pw12345!')
        self.b = User.objects.create_user('fm_b', 'fmb@x.com', 'pw12345!')
        for u, native, learning in ((self.a, self.en, self.ko),
                                    (self.b, self.ko, self.en)):
            UserLanguage.objects.create(
                user=u, language=native, proficiency='native',
                language_type='native')
            UserLanguage.objects.create(
                user=u, language=learning, proficiency='beginner',
                language_type='learning')
        self.client.force_login(self.a)
        self.url = reverse('matches:find_matches')

    def test_first_visit_generates_suggestions(self):
        self.assertEqual(
            PotentialMatch.objects.filter(user=self.a).count(), 0)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            PotentialMatch.objects.filter(user=self.a).count(), 1)

    def test_second_visit_does_not_regenerate(self):
        self.client.get(self.url)
        pm = PotentialMatch.objects.get(user=self.a)
        pm.compatibility_score = 1.0
        pm.save()
        self.client.get(self.url)
        pm.refresh_from_db()
        self.assertEqual(pm.compatibility_score, 1.0)  # untouched

    def test_refresh_regenerates(self):
        self.client.get(self.url)
        PotentialMatch.objects.filter(user=self.a).update(
            compatibility_score=1.0)
        self.client.get(self.url, {'refresh': '1'})
        pm = PotentialMatch.objects.get(user=self.a)
        self.assertGreater(pm.compatibility_score, 1.0)  # recomputed

    def test_user_with_only_teaching_langs_redirected(self):
        c = User.objects.create_user('fm_c', 'fmc@x.com', 'pw12345!')
        UserLanguage.objects.create(
            user=c, language=self.en, proficiency='native',
            language_type='native')
        self.client.force_login(c)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/users/', r.url)
