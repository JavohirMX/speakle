"""Execute the actual request-success handler with fixture-only DOM/fetch stubs."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node is needed for the browser-script harness')
class RequestSuccessScriptTests(unittest.TestCase):
    def test_card_and_featured_success_restore_focus(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ['node', 'scripts/js-harness/request-success.cjs'], cwd=root,
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
