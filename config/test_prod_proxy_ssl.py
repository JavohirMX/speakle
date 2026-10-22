import importlib
import os
import sys
from unittest import mock

from django.test import SimpleTestCase


def load_prod(env):
    """Import config.settings_prod fresh with the given environment (settings only, no logging setup)."""
    sys.modules.pop('config.settings_prod', None)
    with mock.patch.dict(os.environ, env, clear=False):
        return importlib.import_module('config.settings_prod')


class ProdProxySslHeaderTests(SimpleTestCase):
    def tearDown(self):
        sys.modules.pop('config.settings_prod', None)

    def test_default_does_not_trust_forwarded_proto(self):
        s = load_prod({'TRUST_X_FORWARDED_PROTO': ''})
        self.assertIsNone(getattr(s, 'SECURE_PROXY_SSL_HEADER', None))

    def test_opt_in_trusts_forwarded_proto(self):
        s = load_prod({'TRUST_X_FORWARDED_PROTO': 'True'})
        self.assertEqual(s.SECURE_PROXY_SSL_HEADER, ('HTTP_X_FORWARDED_PROTO', 'https'))

    def test_ssl_redirect_behind_proxy_does_not_loop(self):
        from django.test import RequestFactory
        from django.middleware.security import SecurityMiddleware
        s = load_prod({'SECURE_SSL_REDIRECT': 'True', 'TRUST_X_FORWARDED_PROTO': 'True'})
        with self.settings(SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=s.SECURE_PROXY_SSL_HEADER,
                           SECURE_REDIRECT_EXEMPT=[], SECURE_SSL_HOST=None):
            mw = SecurityMiddleware(lambda r: 'passed')
            req = RequestFactory().get('/', HTTP_X_FORWARDED_PROTO='https')
            self.assertEqual(mw.process_request(req), None, 'https via proxy must not be redirected')
            plain = RequestFactory().get('/')
            self.assertEqual(mw.process_request(plain).status_code, 301)

    def test_without_header_setting_proxied_https_request_is_redirected(self):
        """Baseline behaviour that caused the loop: Django cannot see the proxy's https."""
        from django.test import RequestFactory
        from django.middleware.security import SecurityMiddleware
        with self.settings(SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=None,
                           SECURE_REDIRECT_EXEMPT=[], SECURE_SSL_HOST=None):
            mw = SecurityMiddleware(lambda r: 'passed')
            req = RequestFactory().get('/', HTTP_X_FORWARDED_PROTO='https')
            self.assertEqual(mw.process_request(req).status_code, 301)
