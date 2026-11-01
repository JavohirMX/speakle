from django.test import TestCase

# Create your tests here.


class HomePageHonestyTests(TestCase):
    def test_home_shows_real_counts_not_invented_ones(self):
        from django.core.cache import cache
        cache.delete('home_community_stats')
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['stats'], {'languages': 0, 'members': 0, 'matches': 0})
        html = r.content.decode()
        for fake in ('10,000+', '1M+', '99%', 'Maria Rodriguez'):
            self.assertNotIn(fake, html)


from django.test import TestCase, override_settings


class SeoTests(TestCase):
    def test_robots_and_sitemap(self):
        r = self.client.get('/robots.txt')
        self.assertContains(r, 'Sitemap: http://testserver/sitemap.xml')
        self.assertNotIn('X-Robots-Tag', r)
        s = self.client.get('/sitemap.xml')
        self.assertContains(s, '<loc>http://testserver/</loc>')
        self.assertNotContains(s, '/matches/')

    def test_home_is_indexable_with_meta(self):
        r = self.client.get('/')
        self.assertNotIn('X-Robots-Tag', r)
        self.assertContains(r, '<link rel="canonical" href="http://testserver/">')
        self.assertContains(r, 'og:image')
        self.assertContains(r, 'application/ld+json')

    def test_private_pages_are_noindex(self):
        for path in ('/users/login/', '/matches/', '/chats/'):
            self.assertEqual(self.client.get(path)['X-Robots-Tag'], 'noindex', path)

    @override_settings(DEBUG=False, ALLOWED_HOSTS=['testserver'])
    def test_custom_404(self):
        r = self.client.get('/does-not-exist/')
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "We can't find that page", status_code=404)
        self.assertEqual(r['X-Robots-Tag'], 'noindex')

    def test_manifest(self):
        r = self.client.get('/manifest.webmanifest')
        self.assertEqual(r.json()['short_name'], 'Speakle')


class StaticCssTests(TestCase):
    def test_base_css_is_linked_with_content_hash_not_inlined(self):
        import re
        r = self.client.get('/users/login/')
        html = r.content.decode()
        for name in ('tailwind', 'app', 'design', 'fonts'):
            self.assertRegex(html, r'/static/css/%s\.css\?v=[0-9a-f]{10}' % name)
        self.assertLess(len(html), 60000)
        self.assertNotIn('sticker pop', html)

    def test_linked_css_files_exist_and_have_content(self):
        from django.contrib.staticfiles import finders
        for name in ('app', 'design'):
            path = finders.find('css/%s.css' % name)
            self.assertTrue(path)
            self.assertGreater(len(open(path).read()), 10000)


class AuthPageMetaTests(TestCase):
    def test_login_and_register_have_their_own_meta(self):
        seen = set()
        for path, word in (('/users/login/', 'Sign In'), ('/users/register/', 'Sign Up')):
            html = self.client.get(path).content.decode()
            self.assertIn('<meta property="og:title" content="%s - Speakle">' % word, html)
            self.assertIn('<meta name="twitter:title" content="%s - Speakle">' % word, html)
            import re
            desc = re.search(r'<meta name="description" content="([^"]+)"', html).group(1)
            self.assertNotIn(desc, seen)
            seen.add(desc)
