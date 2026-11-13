from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent


class ComposePortSafetyTests(SimpleTestCase):
    """db and redis carry non-secret (sample) or no credentials, so their host
    ports must stay bound to loopback. Services reach them over the compose
    network regardless; only web needs to be reachable from outside."""

    def setUp(self):
        self.content = (ROOT / 'docker-compose.yml').read_text()

    def test_db_and_redis_ports_bind_to_loopback(self):
        for mapping in ('5433:5432', '6380:6379'):
            self.assertIn('127.0.0.1:' + mapping, self.content)
            # Every occurrence of the mapping must be the loopback-bound form.
            self.assertEqual(
                self.content.count(mapping),
                self.content.count('127.0.0.1:' + mapping),
                f'{mapping} is published without a 127.0.0.1 bind',
            )

    def test_web_stays_published(self):
        self.assertIn('8001:8000', self.content)
