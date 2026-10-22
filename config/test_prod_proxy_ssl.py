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


class ProxyHeaderOutcomeTests(SimpleTestCase):
    """Representative middleware outcomes. Not real-proxy certification."""

    def tearDown(self):
        sys.modules.pop('config.settings_prod', None)

    def _run(self, header_setting, xfp, redirect=True):
        from django.http import HttpResponse
        from django.middleware.security import SecurityMiddleware
        from django.test import RequestFactory
        extra = {'HTTP_X_FORWARDED_PROTO': xfp} if xfp else {}
        req = RequestFactory().get('/', **extra)
        with self.settings(SECURE_SSL_REDIRECT=redirect, SECURE_PROXY_SSL_HEADER=header_setting,
                           SECURE_HSTS_SECONDS=31536000, SECURE_REDIRECT_EXEMPT=[], SECURE_SSL_HOST=None):
            mw = SecurityMiddleware(lambda r: HttpResponse('ok'))
            resp = mw(req)
            secure = req.is_secure()
        return secure, resp

    def test_default_off_ignores_spoofed_forwarded_proto(self):
        s = load_prod({'TRUST_X_FORWARDED_PROTO': ''})
        secure, resp = self._run(getattr(s, 'SECURE_PROXY_SSL_HEADER', None), 'https')
        self.assertFalse(secure)
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp['Location'], 'https://testserver/')

    def test_enabled_https_is_secure_and_gets_hsts(self):
        s = load_prod({'TRUST_X_FORWARDED_PROTO': 'True'})
        secure, resp = self._run(s.SECURE_PROXY_SSL_HEADER, 'https')
        self.assertTrue(secure)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('max-age=31536000', resp['Strict-Transport-Security'])

    def test_enabled_http_is_redirected_and_has_no_hsts(self):
        s = load_prod({'TRUST_X_FORWARDED_PROTO': 'True'})
        secure, resp = self._run(s.SECURE_PROXY_SSL_HEADER, 'http')
        self.assertFalse(secure)
        self.assertEqual(resp.status_code, 301)
        self.assertNotIn('Strict-Transport-Security', resp)

    def test_enabled_without_header_is_treated_as_http(self):
        s = load_prod({'TRUST_X_FORWARDED_PROTO': 'True'})
        secure, resp = self._run(s.SECURE_PROXY_SSL_HEADER, None)
        self.assertFalse(secure)
        self.assertEqual(resp.status_code, 301)

    def test_enabled_trusts_any_client_sent_header(self):
        """Documents the risk: if the origin is reachable directly, a client can claim https.
        The flag is only safe when the proxy overwrites the header and the origin is not exposed."""
        s = load_prod({'TRUST_X_FORWARDED_PROTO': 'True'})
        secure, resp = self._run(s.SECURE_PROXY_SSL_HEADER, 'https')
        self.assertTrue(secure)
