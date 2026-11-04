"""Opening the notification socket must not precede group membership."""
import asyncio
from unittest.mock import patch
from channels.layers import get_channel_layer
from django.test import TransactionTestCase
from . import test_text_consumer_guards as guards
from .consumers import UserNotificationConsumer
from .test_api_views import _make_communicator


class NotificationConnectRaceTests(TransactionTestCase):
    setUp = guards.TextConsumerGuardTests.setUp

    async def test_notification_during_connect_is_delivered(self):
        layer = get_channel_layer()
        original_add = layer.group_add
        entered = asyncio.Event()
        release = asyncio.Event()

        async def delayed_add(group, channel):
            entered.set()
            await release.wait()
            await original_add(group, channel)

        c = _make_communicator(UserNotificationConsumer, {
            'path': '/ws/notifications/', 'user': self.a})
        with patch.object(layer, 'group_add', side_effect=delayed_add):
            connecting = asyncio.create_task(c.connect(timeout=3))
            await asyncio.wait_for(entered.wait(), 2)
            # Accept must wait for membership; otherwise the browser thinks
            # it can receive notifications while group_send still drops them.
            await asyncio.sleep(0)
            self.assertFalse(connecting.done())
            release.set()
            self.assertTrue((await connecting)[0])
        await layer.group_send(f'user_notifications_{self.a.id}', {
            'type': 'call_invitation_cancelled', 'invitation_id': 123,
            'canceller_username': 'fixture-caller'})
        frames = []
        for _ in range(3):
            frame = await c.receive_json_from(timeout=2)
            frames.append(frame)
            if frame.get('type') == 'call_invitation_cancelled':
                break
        self.assertTrue(any(f.get('invitation_id') == 123 for f in frames), frames)
        await c.disconnect()
