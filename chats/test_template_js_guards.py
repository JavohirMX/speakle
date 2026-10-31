"""Regression guards for async race fixes in template JavaScript.

These tests statically verify the specific guard code that fixes proven
async race defects. They intentionally scope to changed JS behavior only;
they do not prove runtime behavior (the browser harness under
scripts/js-harness does that) and they cover no Python logic.
Each assertion names the defect it locks in.
"""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BASE = Path(settings.BASE_DIR)


def _read(rel):
    return (BASE / rel).read_text(encoding='utf-8')


def _norm(s):
    """Whitespace-insensitive source for substring assertions."""
    return ' '.join(s.split())


class BaseTemplateQuickCallGuardTests(SimpleTestCase):
    """base.html quick-call / incoming-call modal race guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.src = _norm(_read('main/templates/base.html'))

    def test_availability_fetch_bails_when_modal_closed(self):
        # Defect: fetch callback ran after the modal was closed and
        # currentCallData cleared -> null destructuring TypeError.
        self.assertIn('if (!window.currentCallData) return;', self.src)

    def test_orphan_invitation_cancelled_when_partner_gone(self):
        # Defect: availability result null after clear left a pending
        # invitation server-side (ghost incoming call for the partner).
        self.assertIn('cancel-invitation/${data.invitation_id}/', self.src)

    def test_late_invitation_accepted_bails(self):
        self.assertIn('window.invitationAccepted = function(roomUrl) { // Late event after the modal was closed: nothing to act on if (!window.currentCallData) return;', self.src)

    def test_quick_message_captures_ids_before_clear(self):
        # Defect: sendQuickMessage cleared currentGlobalIncomingInvitation
        # before the async callback read it -> navigation to nowhere.
        self.assertIn('const quickMessageInvitationId = currentGlobalIncomingInvitation.id;', self.src)
        self.assertIn('const quickMessageMatchId = currentGlobalIncomingInvitation.match_id;', self.src)
        self.assertIn('respond-invitation/${quickMessageInvitationId}/', self.src)
        self.assertIn('`/chats/match/${quickMessageMatchId}/`', self.src)


class VideoRoomGuardTests(SimpleTestCase):
    """video_room.html call-teardown race guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.src = _norm(_read('chats/templates/chats/video_room.html'))

    def test_user_left_uses_full_reset(self):
        # Defect: user_left called resetPeerConnection only -> call timer
        # kept counting and isAutoStarting stuck after abrupt partner leave.
        self.assertIn("this.addChatMessage(`${data.username} left the room`, 'system');", self.src)
        # full reset (includes stopTimer) directly follows the leave message
        self.assertIn("// timer running and isAutoStarting stuck after an abrupt leave. this.resetCall();", self.src)

    def test_offer_captures_connection_identity(self):
        # Defect: teardown or replacement connection mid-await -> stale
        # continuation dereferenced null / acted on the new connection.
        self.assertIn('const pc = this.pc;', self.src)
        self.assertIn('await pc.setRemoteDescription(new RTCSessionDescription(data.offer));', self.src)
        self.assertIn('if (this.pc !== pc) return;', self.src)
        self.assertIn('await pc.createAnswer()', self.src)

    def test_answer_captures_connection_identity(self):
        self.assertIn('await pc.setRemoteDescription(new RTCSessionDescription(data.answer));', self.src)

    def test_offer_answer_both_guarded(self):
        # Both handlers must capture identity independently.
        self.assertGreaterEqual(self.src.count('const pc = this.pc;'), 2)


class TextChatGuardTests(SimpleTestCase):
    """text_chat.html typing-signal WebSocket readyState guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.src = _norm(_read('chats/templates/chats/text_chat.html'))

    def test_handle_typing_requires_open_socket(self):
        # Defect: ws.send during reconnect (CONNECTING) threw uncaught
        # InvalidStateError on the keystroke handler.
        self.assertIn('handleTyping() { if (this.ws.readyState !== WebSocket.OPEN) return;', self.src)

    def test_stop_typing_requires_open_socket(self):
        self.assertIn("this.isTyping = false; if (this.ws.readyState === WebSocket.OPEN) { this.ws.send(JSON.stringify({ type: 'typing_stop' })); }", self.src)
