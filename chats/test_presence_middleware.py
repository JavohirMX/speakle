import datetime as dt

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .models import UserPresence

User = get_user_model()


class PresenceMiddlewareTests(TestCase):
    """Pins the presence semantics the middleware has always had."""

    def setUp(self):
        self.u = User.objects.create_user('pm_u', email='pm@x.com', password='pw')
        self.client.force_login(self.u)
        self.url = reverse('main:home')

    def _presence_sql(self, ctx):
        return [q['sql'] for q in ctx.captured_queries if 'chats_userpresence' in q['sql']]

    def test_first_request_creates_online_row(self):
        self.client.get(self.url)
        self.assertTrue(UserPresence.objects.get(user=self.u).is_online)

    def test_every_request_sets_online_and_last_seen_but_not_last_activity(self):
        self.client.get(self.url)
        old = timezone.now() - dt.timedelta(minutes=10)
        UserPresence.objects.filter(user=self.u).update(is_online=False, last_seen=old, last_activity=old)
        self.client.get(self.url)  # immediately again: no throttle window
        p = UserPresence.objects.get(user=self.u)
        self.assertTrue(p.is_online, 'a request flips an offline user back online right away')
        self.assertGreater(p.last_seen, old + dt.timedelta(minutes=9))
        self.assertEqual(p.last_activity, old, 'last_activity (the 5-minute online rule) is not touched')

    def test_existing_row_costs_one_presence_query(self):
        self.client.get(self.url)
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(self.url)
        sql = self._presence_sql(ctx)
        self.assertEqual(len(sql), 1, sql)
        self.assertTrue(sql[0].startswith('UPDATE'))

    def test_database_error_does_not_break_the_request_and_next_request_retries(self):
        from unittest import mock
        with mock.patch.object(UserPresence.objects, 'filter', side_effect=Exception('db blip')):
            self.assertIn(self.client.get(self.url).status_code, (200, 302))
        self.client.get(self.url)
        self.assertTrue(UserPresence.objects.filter(user=self.u, is_online=True).exists())
