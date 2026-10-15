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
