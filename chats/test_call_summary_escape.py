"""Regression: partner-controlled call-summary fields must be escaped
before they are interpolated into innerHTML in the video room.

end_notes arrives raw over the call_end websocket frame (server truncates
to 500 chars but never escapes) and connection_quality is a short
unvalidated string, so both must go through escapeHtml in
showCallSummary. The assertions run against the actually served page.
"""
from django.urls import reverse

from .test_api_views import ChatApiBase


class CallSummaryEscapeTests(ChatApiBase):
    def page(self):
        r = self.client_for(self.a).get(
            reverse('chats:video_room', args=[self.video.room_id]))
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_end_notes_is_escaped_before_innerhtml(self):
        html = self.page()
        self.assertIn('${escapeHtml(callDetails.endNotes)}', html)
        self.assertNotIn('<span class="value">${callDetails.endNotes}</span>', html)

    def test_connection_quality_is_escaped_before_innerhtml(self):
        html = self.page()
        self.assertIn(
            "${escapeHtml(callDetails.connectionQuality).charAt(0).toUpperCase()\n                        + escapeHtml(callDetails.connectionQuality).slice(1)}"
            .replace('\n                        + ', ' + '), html)
        self.assertNotIn(
            '${callDetails.connectionQuality.charAt(0).toUpperCase() + callDetails.connectionQuality.slice(1)}',
            html)

    def test_escape_helper_is_defined_in_summary_scope(self):
        html = self.page()
        self.assertIn('const escapeHtml = (value) =>', html)
