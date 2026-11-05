from django.core import checks
from django.test import SimpleTestCase, override_settings

from users.checks import CONSOLE_BACKEND, console_email_backend_outside_debug

SMTP = 'django.core.mail.backends.smtp.EmailBackend'


def _ids():
    return [m.id for m in checks.run_checks()]


class ConsoleEmailCheckTests(SimpleTestCase):
    @override_settings(DEBUG=False, EMAIL_BACKEND=CONSOLE_BACKEND)
    def test_warns_when_console_backend_and_debug_off(self):
        found = console_email_backend_outside_debug(None)
        self.assertEqual([m.id for m in found], ['users.W001'])
        self.assertIsInstance(found[0], checks.Warning)  # warning only, never an Error
        self.assertIn('users.W001', _ids())  # registered with the framework

    @override_settings(DEBUG=True, EMAIL_BACKEND=CONSOLE_BACKEND)
    def test_quiet_in_debug(self):
        self.assertEqual(console_email_backend_outside_debug(None), [])
        self.assertNotIn('users.W001', _ids())

    @override_settings(DEBUG=False, EMAIL_BACKEND=SMTP)
    def test_quiet_with_smtp(self):
        self.assertEqual(console_email_backend_outside_debug(None), [])
        self.assertNotIn('users.W001', _ids())
