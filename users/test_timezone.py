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


class PartnerTimezoneMatchAndPrivacyTests(TestCase):
    def setUp(self):
        from matches.models import Match
        self.en = Language.objects.create(name='English', code='en')
        self.ko = Language.objects.create(name='Korean', code='ko')
        self.me = User.objects.create_user('pme', 'pme@example.com', 'pw12345!x')
        self.partner = User.objects.create_user('ppart', 'ppart@example.com', 'pw12345!x', timezone='Asia/Seoul')
        self.stranger = User.objects.create_user('pstr', 'pstr@example.com', 'pw12345!x')
        self.match = Match.objects.create(user1=self.me, user2=self.partner, status='active',
                                          user1_teaches=self.en, user1_learns=self.ko)

    def test_match_page_shows_partner_time_to_a_participant(self):
        self.client.force_login(self.me)
        r = self.client.get(reverse('matches:match_detail', args=[self.match.id]))
        self.assertContains(r, 'their time')
        self.assertContains(r, 'UTC+9')

    def test_stranger_cannot_see_it_and_blank_zone_shows_nothing(self):
        self.client.force_login(self.stranger)
        r = self.client.get(reverse('matches:match_detail', args=[self.match.id]), follow=True)
        self.assertNotContains(r, 'UTC+9')
        self.partner.timezone = ''
        self.partner.save()
        self.client.force_login(self.me)
        r = self.client.get(reverse('matches:match_detail', args=[self.match.id]))
        self.assertNotContains(r, 'their time')

    def test_offset_follows_daylight_saving(self):
        from datetime import datetime, timezone as tz
        u = User(username='dst', timezone='Europe/Berlin')
        for when, expect in ((datetime(2026, 1, 15, 12, 0, tzinfo=tz.utc), '13:00 (UTC+1)'),
                             (datetime(2026, 7, 15, 12, 0, tzinfo=tz.utc), '14:00 (UTC+2)')):
            with mock.patch('datetime.datetime') as dt:
                dt.now.return_value = when
                self.assertEqual(u.local_time_label(), expect)

    def test_time_is_computed_at_render_not_stored(self):
        from datetime import datetime, timezone as tz
        u = User(username='clk', timezone='Asia/Seoul')
        with mock.patch('datetime.datetime') as dt:
            dt.now.return_value = datetime(2026, 1, 1, 0, 0, tzinfo=tz.utc)
            a = u.local_time_label()
            dt.now.return_value = datetime(2026, 1, 1, 1, 30, tzinfo=tz.utc)
            b = u.local_time_label()
        self.assertEqual((a, b), ('09:00 (UTC+9)', '10:30 (UTC+9)'))
