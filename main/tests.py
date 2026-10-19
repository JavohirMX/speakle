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
