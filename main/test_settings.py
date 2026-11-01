import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent
KEY = 'k' * 50


def _load(**env):
    clean = {k: v for k, v in os.environ.items() if k not in ('DEBUG', 'SECRET_KEY', 'DJANGO_SETTINGS_MODULE')}
    clean.update(env)
    code = ('import os; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); '
            'import django.conf as c; s = c.settings; print(s.DEBUG, s.SECRET_KEY == %r)' % KEY)
    return subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=clean, capture_output=True, text=True)


class SettingsSafetyTests(SimpleTestCase):
    def test_refuses_to_start_without_a_secret_key(self):
        r = _load()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('SECRET_KEY is not set', r.stderr)

    def test_placeholder_key_is_refused(self):
        r = _load(SECRET_KEY='change-me-in-production')
        self.assertNotEqual(r.returncode, 0)

    def test_debug_is_off_by_default_and_env_key_is_used(self):
        r = _load(SECRET_KEY=KEY)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split(), ['False', 'True'])

    def test_local_dev_can_opt_in_with_debug_true(self):
        r = _load(DEBUG='True')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split()[0], 'True')
