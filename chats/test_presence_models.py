"""UserPresence/TypingStatus/ChatMessage model query behavior."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from users.models import Language
from matches.models import Match
from .models import UserPresence, ChatRoom, ChatMessage, TypingStatus

User = get_user_model()


class PresenceQueryTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('pm_a', 'pma@x.com', 'pw12345!')
        self.b = User.objects.create_user('pm_b', 'pmb@x.com', 'pw12345!')

    def test_online_users_excludes_stale_activity(self):
        UserPresence.objects.create(user=self.a, is_online=True)
        # last_activity is auto_now: backdate it behind the ORM.
        UserPresence.objects.filter(user=self.a).update(
            last_activity=timezone.now() - timedelta(minutes=30))
        UserPresence.objects.create(
            user=self.b, is_online=True, last_activity=timezone.now())
        online = UserPresence.get_online_users()
        self.assertEqual([p.user for p in online], [self.b])

    def test_offline_user_never_listed(self):
        UserPresence.objects.create(
            user=self.a, is_online=False, last_activity=timezone.now())
        self.assertEqual(list(UserPresence.get_online_users()), [])


class MarkAsReadTests(TestCase):
    def test_mark_as_read_flips_once(self):
        a = User.objects.create_user('mr_a', 'mra@x.com', 'pw12345!')
        b = User.objects.create_user('mr_b', 'mrb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        match = Match.objects.create(user1=a, user2=b, user1_teaches=en,
                                     user1_learns=ko, status='active')
        room = ChatRoom.objects.create(match=match)
        msg = ChatMessage.objects.create(room=room, sender=a, content='hi')
        msg.mark_as_read()
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)
        msg.mark_as_read()  # idempotent, no error
        self.assertTrue(msg.is_read)


class TypingUsersTests(TestCase):
    def test_get_typing_users_with_exclusion(self):
        a = User.objects.create_user('ty_a', 'tya@x.com', 'pw12345!')
        b = User.objects.create_user('ty_b', 'tyb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        match = Match.objects.create(user1=a, user2=b, user1_teaches=en,
                                     user1_learns=ko, status='active')
        room = ChatRoom.objects.create(match=match)
        TypingStatus.set_typing(room, a, True)
        TypingStatus.set_typing(room, b, True)
        self.assertEqual(TypingStatus.get_typing_users(room), [a, b])
        self.assertEqual(
            TypingStatus.get_typing_users(room, exclude_user=a), [b])
        TypingStatus.set_typing(room, b, False)
        self.assertEqual(TypingStatus.get_typing_users(room), [a])
