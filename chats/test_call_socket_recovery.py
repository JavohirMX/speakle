from pathlib import Path
import subprocess
from django.test import SimpleTestCase


class CallSocketRecoveryTests(SimpleTestCase):
    def test_actual_socket_close_handler_resets_call_before_reconnect(self):
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(['node', 'scripts/js-harness/call-socket-recovery.cjs'],
                                cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
