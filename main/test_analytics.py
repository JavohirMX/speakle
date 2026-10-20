from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import PageStat

U = get_user_model()


class AnalyticsTests(TestCase):
    def test_counts_a_view_by_route_name_without_personal_data(self):
        self.client.get('/', HTTP_USER_AGENT='Mozilla/5.0')
        self.client.get('/', HTTP_USER_AGENT='Mozilla/5.0')
        stat = PageStat.objects.get(key='view:main:home')
        self.assertEqual(stat.count, 2)
        self.assertEqual({f.name for f in PageStat._meta.get_fields()}, {'id', 'day', 'key', 'count'})

    def test_records_utm_source_and_external_referrer_only_on_entry_pages(self):
        self.client.get('/?utm_source=Reddit!&secret=1', HTTP_REFERER='https://www.reddit.com/r/x?token=abc')
        keys = set(PageStat.objects.values_list('key', flat=True))
        self.assertIn('src:reddit', keys)
        self.assertIn('ref:www.reddit.com', keys)
        self.assertFalse(any('token' in k or 'secret' in k or 'abc' in k for k in keys))

    def test_ignores_bots_posts_errors_and_admin(self):
        self.client.get('/', HTTP_USER_AGENT='Googlebot/2.1')
        self.client.get('/nope-404/')
        self.client.post(reverse('users:login'), {})
        self.client.get('/admin/login/')
        self.assertFalse(PageStat.objects.exists())

    @override_settings(ANALYTICS_ENABLED=False)
    def test_can_be_disabled(self):
        self.client.get('/')
        self.assertFalse(PageStat.objects.exists())

    def test_dashboard_is_staff_only(self):
        u = U.objects.create_user('plain', 'p@x.com', 'pw12345!x')
        self.assertEqual(self.client.get('/stats/').status_code, 404)
        self.client.force_login(u)
        self.assertEqual(self.client.get('/stats/').status_code, 404)
        s = U.objects.create_user('boss', 'b@x.com', 'pw12345!x', is_staff=True)
        self.client.force_login(s)
        r = self.client.get('/stats/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'New members')
        self.assertContains(r, 'no IP addresses')

    def test_dashboard_view_is_not_counted(self):
        s = U.objects.create_user('boss2', 'b2@x.com', 'pw12345!x', is_staff=True)
        self.client.force_login(s)
        self.client.get('/stats/')
        self.assertFalse(PageStat.objects.filter(key='view:main:stats').exists())
