from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from matches.models import Match
from users.models import Language
from .models import CallSession, ChatMessage, ChatRoom, VideoRoom

User = get_user_model()


class ChatApiBase(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('apia', 'apia@x.com', 'pw12345!')
        self.b = User.objects.create_user('apib', 'apib@x.com', 'pw12345!')
        self.outsider = User.objects.create_user('apic', 'apic@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        self.match = Match.objects.create(
            user1=self.a, user2=self.b, user1_teaches=en, user1_learns=ko, status='active'
        )
        self.chat = ChatRoom.objects.create(match=self.match)
        self.video = VideoRoom.objects.create(match=self.match)

    def client_for(self, user):
        c = Client()
        c.force_login(user)
        return c


class GetChatMessagesTests(ChatApiBase):
    def url(self, **q):
        return reverse('chats:get_chat_messages', args=[self.chat.room_id])

    def test_returns_messages_oldest_first_with_reply_preview(self):
        first = ChatMessage.objects.create(room=self.chat, sender=self.b, content='x' * 80)
        ChatMessage.objects.create(room=self.chat, sender=self.a, content='reply', reply_to=first)

        data = self.client_for(self.a).get(self.url()).json()

        self.assertTrue(data['success'])
        self.assertEqual([m['content'] for m in data['messages']][1], 'reply')
        reply = data['messages'][1]
        self.assertTrue(reply['is_own_message'])
        self.assertEqual(reply['reply_to']['sender_username'], 'apib')
        self.assertTrue(reply['reply_to']['content'].endswith('...'))
        self.assertEqual(len(reply['reply_to']['content']), 53)

    def test_pagination_flags(self):
        for i in range(5):
            ChatMessage.objects.create(room=self.chat, sender=self.b, content=f'm{i}')

        data = self.client_for(self.a).get(self.url(), {'page_size': 2, 'page': 1}).json()

        self.assertEqual(len(data['messages']), 2)
        self.assertTrue(data['has_next'])
        self.assertFalse(data['has_previous'])
        self.assertEqual(data['total_pages'], 3)

    def test_outsider_gets_403_and_unknown_room_404(self):
        self.assertEqual(self.client_for(self.outsider).get(self.url()).status_code, 403)
        import uuid
        r = self.client_for(self.a).get(reverse('chats:get_chat_messages', args=[uuid.uuid4()]))
        self.assertEqual(r.status_code, 404)

    def test_bad_page_params_do_not_500(self):
        r = self.client_for(self.a).get(self.url(), {'page': 'abc', 'page_size': 'zz'})
        self.assertEqual(r.status_code, 400)
        r = self.client_for(self.a).get(self.url(), {'page': '-3', 'page_size': '0'})
        self.assertEqual(r.status_code, 200)


class TotalUnreadCountTests(ChatApiBase):
    def test_counts_only_unread_messages_from_partner(self):
        ChatMessage.objects.create(room=self.chat, sender=self.b, content='1')
        ChatMessage.objects.create(room=self.chat, sender=self.b, content='2')
        ChatMessage.objects.create(room=self.chat, sender=self.b, content='3', is_read=True)
        ChatMessage.objects.create(room=self.chat, sender=self.a, content='mine')

        data = self.client_for(self.a).get(reverse('chats:get_total_unread_count')).json()

        self.assertEqual(data['unread_count'], 2)

    def test_match_without_chat_room_counts_zero(self):
        self.chat.delete()
        data = self.client_for(self.a).get(reverse('chats:get_total_unread_count')).json()
        self.assertEqual(data['unread_count'], 0)

    def test_requires_login(self):
        r = Client().get(reverse('chats:get_total_unread_count'))
        self.assertEqual(r.status_code, 302)


class RoomStatusAndStatisticsTests(ChatApiBase):
    def _ended_session(self, reason, seconds):
        s = CallSession.objects.create(room=self.video, status='ended', end_reason=reason)
        s.participants.add(self.a, self.b)
        CallSession.objects.filter(pk=s.pk).update(duration=timedelta(seconds=seconds))
        return s

    def test_room_status_with_and_without_active_session(self):
        url = reverse('chats:room_status', args=[self.video.room_id])
        c = self.client_for(self.a)
        self.assertEqual(c.get(url).json()['has_active_session'], False)

        s = CallSession.objects.create(room=self.video, status='active')
        s.participants.add(self.a, self.b)
        data = c.get(url).json()
        self.assertTrue(data['has_active_session'])
        self.assertEqual(data['participant_count'], 2)

    def test_room_status_denies_outsider(self):
        url = reverse('chats:room_status', args=[self.video.room_id])
        self.assertEqual(self.client_for(self.outsider).get(url).status_code, 403)

    def test_call_statistics_aggregates(self):
        self._ended_session('normal', 120)
        self._ended_session('connection_lost', 60)

        data = self.client_for(self.a).get(
            reverse('chats:get_call_statistics', args=[self.video.room_id])
        ).json()['statistics']

        self.assertEqual(data['total_sessions'], 2)
        self.assertEqual(data['successful_sessions'], 1)
        self.assertEqual(data['success_rate'], 50)
        self.assertEqual(data['total_duration_minutes'], 3)
        self.assertEqual(data['average_duration_minutes'], 1.5)

    def test_call_statistics_with_no_sessions_is_zero_not_error(self):
        data = self.client_for(self.a).get(
            reverse('chats:get_call_statistics', args=[self.video.room_id])
        ).json()['statistics']
        self.assertEqual(data['total_sessions'], 0)
        self.assertEqual(data['success_rate'], 0)

    def test_call_statistics_denies_outsider(self):
        r = self.client_for(self.outsider).get(
            reverse('chats:get_call_statistics', args=[self.video.room_id])
        )
        self.assertEqual(r.status_code, 403)


class EndCallTests(ChatApiBase):
    def test_end_call_closes_active_sessions_and_room(self):
        self.video.is_active = True
        self.video.save()
        s = CallSession.objects.create(room=self.video, status='active')
        s.participants.add(self.a, self.b)

        with patch('chats.views.send_user_notification'):
            r = self.client_for(self.a).post(
                reverse('chats:end_call_with_reason', args=[self.video.room_id]),
                {'end_reason': 'normal', 'connection_quality': 'good'},
            )

        self.assertEqual(r.status_code, 200)
        s.refresh_from_db()
        self.video.refresh_from_db()
        self.assertEqual(s.status, 'ended')
        self.assertEqual(s.ended_by, self.a)
        self.assertEqual(s.end_reason, 'normal')
        self.assertEqual(s.connection_quality, 'good')
        self.assertFalse(self.video.is_active)

    def test_outsider_cannot_end_call(self):
        s = CallSession.objects.create(room=self.video, status='active')
        with patch('chats.views.send_user_notification'):
            r = self.client_for(self.outsider).post(
                reverse('chats:end_call_with_reason', args=[self.video.room_id]), {'end_reason': 'normal'}
            )
        self.assertEqual(r.status_code, 403)
        s.refresh_from_db()
        self.assertEqual(s.status, 'active')


class SendAndEditMessageTests(ChatApiBase):
    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()

    def send(self, user, **data):
        with patch('chats.views.send_user_notification'):
            return self.client_for(user).post(
                reverse('chats:send_chat_message', args=[self.chat.room_id]), data
            )

    def test_send_creates_message_and_notifies_partner(self):
        with patch('chats.views.send_user_notification') as notify:
            r = self.client_for(self.a).post(
                reverse('chats:send_chat_message', args=[self.chat.room_id]), {'content': ' hello '}
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ChatMessage.objects.get().content, 'hello')
        self.assertEqual(notify.call_args[0][0], self.b.id)

    def test_send_validation(self):
        self.assertEqual(self.send(self.a, content='   ').status_code, 400)
        self.assertEqual(self.send(self.a, content='x' * 1001).status_code, 400)
        self.assertEqual(self.send(self.outsider, content='hi').status_code, 403)
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_reply_to_must_be_in_same_room_and_numeric(self):
        self.assertEqual(self.send(self.a, content='hi', reply_to='999999').status_code, 400)
        self.assertEqual(self.send(self.a, content='hi', reply_to='abc').status_code, 400)

    def test_edit_own_message(self):
        m = ChatMessage.objects.create(room=self.chat, sender=self.a, content='old')
        with patch('chats.views.send_user_notification'):
            r = self.client_for(self.a).post(
                reverse('chats:edit_chat_message', args=[m.id]), {'content': 'new'}
            )
        self.assertEqual(r.status_code, 200)
        m.refresh_from_db()
        self.assertEqual(m.content, 'new')
        self.assertIsNotNone(m.edited_at)

    def test_edit_respects_length_limit_and_ownership(self):
        m = ChatMessage.objects.create(room=self.chat, sender=self.a, content='old')
        url = reverse('chats:edit_chat_message', args=[m.id])
        with patch('chats.views.send_user_notification'):
            self.assertEqual(self.client_for(self.a).post(url, {'content': 'x' * 1001}).status_code, 400)
            self.assertEqual(self.client_for(self.b).post(url, {'content': 'hijack'}).status_code, 404)
        m.refresh_from_db()
        self.assertEqual(m.content, 'old')

    def test_blocked_user_cannot_edit_after_block(self):
        from users.models import UserBlock
        m = ChatMessage.objects.create(room=self.chat, sender=self.a, content='old')
        UserBlock.objects.create(blocker=self.b, blocked=self.a)
        with patch('chats.views.send_user_notification') as notify:
            r = self.client_for(self.a).post(
                reverse('chats:edit_chat_message', args=[m.id]), {'content': 'new'}
            )
        self.assertEqual(r.status_code, 403)
        notify.assert_not_called()
        m.refresh_from_db()
        self.assertEqual(m.content, 'old')

    def test_mark_read_only_marks_partner_messages(self):
        ChatMessage.objects.create(room=self.chat, sender=self.b, content='1')
        mine = ChatMessage.objects.create(room=self.chat, sender=self.a, content='2')
        r = self.client_for(self.a).post(reverse('chats:mark_messages_read', args=[self.chat.room_id]))
        self.assertEqual(r.json()['marked_read'], 1)
        mine.refresh_from_db()
        self.assertFalse(mine.is_read)


class InvitationViewTests(ChatApiBase):
    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        from .models import UserPresence
        cache.clear()
        UserPresence.objects.create(user=self.b, is_online=True)

    def send(self, user=None, **data):
        with patch('chats.views.send_user_notification'):
            return self.client_for(user or self.a).post(
                reverse('chats:send_call_invitation', args=[self.match.id]), data
            )

    def test_send_creates_pending_invitation(self):
        from .models import CallInvitation
        r = self.send(message='hi')
        self.assertEqual(r.status_code, 200)
        inv = CallInvitation.objects.get()
        self.assertEqual((inv.caller, inv.receiver, inv.status), (self.a, self.b, 'pending'))

    def test_send_rejects_second_pending_offline_partner_outsider_and_long_message(self):
        from .models import CallInvitation, UserPresence
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send().status_code, 400)  # already pending
        CallInvitation.objects.all().delete()
        self.assertEqual(self.send(message='x' * 501).status_code, 400)
        self.assertEqual(self.send(self.outsider).status_code, 403)
        UserPresence.objects.filter(user=self.b).update(is_online=False)
        self.assertEqual(self.send().status_code, 400)  # partner offline
        self.assertEqual(CallInvitation.objects.count(), 0)

    def test_send_denied_when_blocked(self):
        from users.models import UserBlock
        UserBlock.objects.create(blocker=self.b, blocked=self.a)
        self.assertEqual(self.send().status_code, 403)

    def _respond(self, inv, user, response):
        with patch('chats.views.send_user_notification'):
            return self.client_for(user).post(
                reverse('chats:respond_to_invitation', args=[inv.id]), {'response': response}
            )

    def test_accept_decline_and_invalid(self):
        from .models import CallInvitation
        self.send()
        inv = CallInvitation.objects.get()
        self.assertEqual(self._respond(inv, self.b, 'maybe').status_code, 400)
        self.assertEqual(self._respond(inv, self.a, 'accept').status_code, 404)  # caller cannot respond
        r = self._respond(inv, self.b, 'accept')
        self.assertEqual(r.json()['action'], 'accepted')
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'accepted')
        self.assertEqual(self._respond(inv, self.b, 'decline').status_code, 400)  # already answered

    def test_decline(self):
        from .models import CallInvitation
        self.send()
        inv = CallInvitation.objects.get()
        self.assertEqual(self._respond(inv, self.b, 'decline').json()['action'], 'declined')

    def test_expired_invitation_cannot_be_accepted(self):
        from .models import CallInvitation
        self.send()
        inv = CallInvitation.objects.get()
        CallInvitation.objects.filter(pk=inv.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self._respond(inv, self.b, 'accept').status_code, 400)

    def test_cancel_only_by_caller_and_only_when_pending(self):
        from .models import CallInvitation
        self.send()
        inv = CallInvitation.objects.get()
        url = reverse('chats:cancel_invitation', args=[inv.id])
        with patch('chats.views.send_user_notification'):
            self.assertEqual(self.client_for(self.b).post(url).status_code, 404)
            self.assertEqual(self.client_for(self.a).post(url).status_code, 200)
            self.assertEqual(self.client_for(self.a).post(url).status_code, 400)
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'cancelled')

    def test_pending_invitations_lists_only_live_ones_for_receiver(self):
        from .models import CallInvitation
        self.send()
        r = self.client_for(self.b).get(reverse('chats:get_pending_invitations'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('apia', r.content.decode())
        r2 = self.client_for(self.a).get(reverse('chats:get_pending_invitations'))
        self.assertNotIn('apia', r2.content.decode())


from django.test import TransactionTestCase
from channels.db import database_sync_to_async
from .tests import _make_communicator


class TextChatConsumerEditAndHistoryTests(TransactionTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.a = User.objects.create_user('ws_a', 'wsa@x.com', 'pw12345!')
        self.b = User.objects.create_user('ws_b', 'wsb@x.com', 'pw12345!')
        en = Language.objects.create(name='English', code='en')
        ko = Language.objects.create(name='Korean', code='ko')
        m = Match.objects.create(user1=self.a, user2=self.b, user1_teaches=en, user1_learns=ko, status='active')
        self.room = ChatRoom.objects.create(match=m)

    async def _connect(self, user):
        from .consumers import TextChatConsumer
        rid = str(self.room.room_id)
        scope = {'path': f'/ws/text-chat/{rid}/', 'user': user, 'url_route': {'kwargs': {'room_id': rid}}}
        c = _make_communicator(TextChatConsumer, scope)
        ok, _ = await c.connect()
        self.assertTrue(ok)
        return c

    async def _next(self, c, wanted, limit=8):
        for _ in range(limit):
            msg = await c.receive_json_from()
            if msg.get('type') == wanted:
                return msg
        self.fail(f'no {wanted} frame')

    async def test_edit_broadcasts_and_persists(self):
        msg = await database_sync_to_async(ChatMessage.objects.create)(room=self.room, sender=self.a, content='old')
        ca = await self._connect(self.a)
        await ca.send_json_to({'type': 'edit_message', 'message_id': msg.id, 'content': 'new'})
        frame = await self._next(ca, 'message_edited')
        self.assertEqual(frame['new_content'], 'new')
        saved = await database_sync_to_async(ChatMessage.objects.get)(pk=msg.pk)
        self.assertEqual(saved.content, 'new')
        await ca.disconnect()

    async def test_edit_rejects_long_content_and_other_peoples_messages(self):
        msg = await database_sync_to_async(ChatMessage.objects.create)(room=self.room, sender=self.a, content='old')
        ca = await self._connect(self.a)
        await ca.send_json_to({'type': 'edit_message', 'message_id': msg.id, 'content': 'x' * 1001})
        self.assertIn('too long', (await self._next(ca, 'error'))['message'])
        cb = await self._connect(self.b)
        await cb.send_json_to({'type': 'edit_message', 'message_id': msg.id, 'content': 'hijack'})
        await self._next(cb, 'error')
        saved = await database_sync_to_async(ChatMessage.objects.get)(pk=msg.pk)
        self.assertEqual(saved.content, 'old')
        await ca.disconnect(); await cb.disconnect()

    async def test_edit_after_block_is_refused(self):
        from users.models import UserBlock
        msg = await database_sync_to_async(ChatMessage.objects.create)(room=self.room, sender=self.a, content='old')
        ca = await self._connect(self.a)
        await database_sync_to_async(UserBlock.objects.create)(blocker=self.b, blocked=self.a)
        await ca.send_json_to({'type': 'edit_message', 'message_id': msg.id, 'content': 'new'})
        self.assertIn('no longer available', (await self._next(ca, 'error'))['message'])
        saved = await database_sync_to_async(ChatMessage.objects.get)(pk=msg.pk)
        self.assertEqual(saved.content, 'old')
        await ca.disconnect()

    async def test_load_messages_survives_bad_paging_values(self):
        await database_sync_to_async(ChatMessage.objects.create)(room=self.room, sender=self.b, content='hi')
        ca = await self._connect(self.a)
        await ca.send_json_to({'type': 'load_messages', 'page': 'abc', 'page_size': 'zz'})
        frame = await self._next(ca, 'message_history')
        self.assertEqual([m['content'] for m in frame['messages']], ['hi'])
        await ca.send_json_to({'type': 'load_messages', 'page': 1, 'page_size': 0})
        frame = await self._next(ca, 'message_history')
        self.assertEqual(len(frame['messages']), 1)
        await ca.disconnect()

    async def test_mark_read_ping_unknown_and_bad_json(self):
        msg = await database_sync_to_async(ChatMessage.objects.create)(room=self.room, sender=self.b, content='hi')
        mine = await database_sync_to_async(ChatMessage.objects.create)(room=self.room, sender=self.a, content='mine')
        ca = await self._connect(self.a)
        await ca.send_json_to({'type': 'mark_messages_read', 'message_ids': [msg.id, mine.id]})
        await ca.send_json_to({'type': 'ping', 'timestamp': 5})
        self.assertEqual((await self._next(ca, 'pong'))['timestamp'], 5)
        self.assertTrue((await database_sync_to_async(ChatMessage.objects.get)(pk=msg.pk)).is_read)
        self.assertFalse((await database_sync_to_async(ChatMessage.objects.get)(pk=mine.pk)).is_read)
        await ca.send_json_to({'type': 'nope'})
        self.assertIn('Unknown', (await self._next(ca, 'error'))['message'])
        await ca.send_to(text_data='not json')
        self.assertIn('Invalid JSON', (await self._next(ca, 'error'))['message'])
        await ca.disconnect()

    async def test_outsider_is_refused(self):
        from .consumers import TextChatConsumer
        out = await database_sync_to_async(User.objects.create_user)('ws_c', 'wsc@x.com', 'pw12345!')
        rid = str(self.room.room_id)
        c = _make_communicator(TextChatConsumer, {'path': f'/ws/text-chat/{rid}/', 'user': out,
                                                  'url_route': {'kwargs': {'room_id': rid}}})
        await c.connect()
        frame = await c.receive_json_from()
        self.assertEqual(frame['type'], 'error')
