"""Expiry sweep and 10-second cache contract of get_pending_invitations."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from users.models import Language
from matches.models import Match
from .models import VideoRoom, CallInvitation

User = get_user_model()


class PendingInvitationCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.a = User.objects.create_user('ica', password='x')
        self.b = User.objects.create_user('icb', password='x')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.match = Match.objects.create(
            user1=self.a, user2=self.b,
            user1_teaches=en, user1_learns=ko, status='active')
        self.room = VideoRoom.objects.create(match=self.match)
        self.url = reverse('chats:get_pending_invitations')

    def _invite(self, expires_delta=timedelta(minutes=5)):
        return CallInvitation.objects.create(
            room=self.room, caller=self.a, receiver=self.b,
            expires_at=timezone.now() + expires_delta)

    def _get(self):
        c = Client()
        c.force_login(self.b)
        return c.get(self.url).json()['invitations']

    def test_expired_invitation_swept_and_hidden(self):
        old = self._invite(expires_delta=timedelta(minutes=-1))
        live = self._invite()
        result = self._get()
        self.assertEqual([i['id'] for i in result], [live.id])
        old.refresh_from_db()
        self.assertEqual(old.status, 'expired')

    def test_result_is_cached_for_ten_seconds(self):
        first = self._invite()
        self.assertEqual(len(self._get()), 1)
        # A new invitation is invisible while the cache entry lives.
        second = self._invite()
        self.assertEqual(len(self._get()), 1)
        cache.delete(f'pending_invitations_{self.b.id}')
        ids = [i['id'] for i in self._get()]
        self.assertEqual(sorted(ids), sorted([first.id, second.id]))

    def test_stale_cache_served_until_ttl_then_swept(self):
        # Pins the actual contract: the cache check runs before the
        # expiry sweep, so an invitation that expires behind the cache
        # is still served until the 10s TTL ends; the next cache-miss
        # request then sweeps it and returns empty.
        live = self._invite()
        self.assertEqual(len(self._get()), 1)
        CallInvitation.objects.filter(pk=live.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(len(self._get()), 1)  # stale within TTL
        cache.delete(f'pending_invitations_{self.b.id}')
        self.assertEqual(self._get(), [])
        live.refresh_from_db()
        self.assertEqual(live.status, 'expired')
