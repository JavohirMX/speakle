from unittest import mock
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from users.forms import UserProfileForm
from users.models import Language
from matches.models import MatchRequest

User = get_user_model()


class PartnerTimezoneTests(TestCase):
    def setUp(self):
        self.me = User.objects.create_user('tzme', 'tzme@example.com', 'pw12345!x')
        self.other = User.objects.create_user('tzother', 'tzother@example.com', 'pw12345!x')

    def _form(self, tz):
        return UserProfileForm({'email': 'tzme@example.com', 'timezone': tz}, instance=self.me)

    def test_label_is_empty_without_a_zone_or_with_a_bad_one(self):
        self.assertEqual(self.other.local_time_label(), '')
        self.other.timezone = 'Not/AZone'
        self.assertEqual(self.other.local_time_label(), '')

    def test_label_shows_local_time_and_offset(self):
        from datetime import datetime, timezone as tz
        self.other.timezone = 'Asia/Seoul'
        fake = datetime(2026, 1, 1, 5, 5, tzinfo=tz.utc)
        with mock.patch('datetime.datetime') as dt:
            dt.now.return_value = fake
            self.assertEqual(self.other.local_time_label(), '14:05 (UTC+9)')
        self.other.timezone = 'Asia/Kolkata'
        with mock.patch('datetime.datetime') as dt:
            dt.now.return_value = fake
            self.assertEqual(self.other.local_time_label(), '10:35 (UTC+5:30)')

    def test_form_accepts_a_real_zone_and_blank_and_rejects_junk(self):
        self.assertTrue(self._form('Europe/Berlin').is_valid())
        self.assertTrue(self._form('').is_valid())
        self.assertFalse(self._form('Mars/Olympus').is_valid())

    def test_request_page_shows_sender_time_only_when_set(self):
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        MatchRequest.objects.create(sender=self.other, receiver=self.me, sender_teaches=en,
                                    sender_learns=ko, status='pending')
        self.client.force_login(self.me)
        url = reverse('matches:requests')
        self.assertNotContains(self.client.get(url), 'their time')
        self.other.timezone = 'Asia/Seoul'
        self.other.save()
        self.assertContains(self.client.get(url), 'their time')
