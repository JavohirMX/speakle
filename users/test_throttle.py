"""Boundary tests for the cache-backed throttle helpers."""
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from . import throttle


class LoginThrottleTest(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        self.request.META['REMOTE_ADDR'] = '203.0.113.9'

    def test_not_blocked_below_max(self):
        for _ in range(throttle.LOGIN_MAX_FAILURES - 1):
            throttle.record_login_failure(self.request, 'alice')
        self.assertFalse(throttle.login_blocked(self.request, 'alice'))

    def test_blocked_at_max(self):
        for _ in range(throttle.LOGIN_MAX_FAILURES):
            throttle.record_login_failure(self.request, 'alice')
        self.assertTrue(throttle.login_blocked(self.request, 'alice'))

    def test_failures_are_per_username(self):
        for _ in range(throttle.LOGIN_MAX_FAILURES):
            throttle.record_login_failure(self.request, 'alice')
        self.assertFalse(throttle.login_blocked(self.request, 'bob'))

    def test_failures_are_per_ip(self):
        for _ in range(throttle.LOGIN_MAX_FAILURES):
            throttle.record_login_failure(self.request, 'alice')
        other = self.factory.get('/')
        other.META['REMOTE_ADDR'] = '198.51.100.7'
        self.assertFalse(throttle.login_blocked(other, 'alice'))

    def test_clear_resets_block(self):
        for _ in range(throttle.LOGIN_MAX_FAILURES):
            throttle.record_login_failure(self.request, 'alice')
        throttle.clear_login_failures(self.request, 'alice')
        self.assertFalse(throttle.login_blocked(self.request, 'alice'))

    def test_username_case_and_whitespace_normalized(self):
        for _ in range(throttle.LOGIN_MAX_FAILURES):
            throttle.record_login_failure(self.request, '  Alice ')
        self.assertTrue(throttle.login_blocked(self.request, 'ALICE'))


class AllowBoundaryTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_exactly_limit_events_allowed(self):
        for i in range(1, 6):
            self.assertTrue(throttle.allow('t:key1', 5, 60), f'event {i}')
        self.assertFalse(throttle.allow('t:key1', 5, 60))

    def test_chat_allowed_boundary(self):
        for _ in range(throttle.CHAT_LIMIT):
            self.assertTrue(throttle.chat_allowed(42))
        self.assertFalse(throttle.chat_allowed(42))

    def test_different_users_have_separate_chat_limits(self):
        for _ in range(throttle.CHAT_LIMIT):
            throttle.chat_allowed(42)
        self.assertTrue(throttle.chat_allowed(43))


class SignupThrottleTest(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def _req(self, ip='192.0.2.5'):
        r = self.factory.get('/')
        r.META['REMOTE_ADDR'] = ip
        return r

    def test_off_by_default(self):
        for _ in range(20):
            self.assertTrue(throttle.signup_allowed(self._req()))

    @override_settings(SIGNUPS_PER_HOUR_PER_IP=3)
    def test_per_ip_cap_when_enabled(self):
        for _ in range(3):
            self.assertTrue(throttle.signup_allowed(self._req()))
        self.assertFalse(throttle.signup_allowed(self._req()))
        self.assertTrue(throttle.signup_allowed(self._req('192.0.2.6')))
