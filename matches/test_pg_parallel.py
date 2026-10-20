import threading
from django.db import connection, connections
import unittest
from django.test import TransactionTestCase, override_settings
from django.contrib.auth import get_user_model
from users.models import Language
from matches.services import MatchingService, RequestLimitReached
from matches.models import MatchRequest

User = get_user_model()


@unittest.skipUnless(connection.vendor == 'postgresql', 'needs PostgreSQL (row locks); skipped on SQLite')
class ParallelCap(TransactionTestCase):
    """12 simultaneous sends with a cap of 3 must create exactly 3 requests."""

    @override_settings(MATCH_REQUESTS_PER_DAY=3)
    def test_parallel_sends_do_not_overshoot(self):
        en = Language.objects.create(name='English', code='en'); ko = Language.objects.create(name='Korean', code='ko')
        me = User.objects.create_user('pme', 'pme@e.com', 'x12345!yz')
        others = [User.objects.create_user('po%d' % i, 'po%d@e.com' % i, 'x12345!yz') for i in range(12)]
        barrier = threading.Barrier(len(others)); res = []
        def go(o):
            try:
                barrier.wait()
                MatchingService.send_match_request(me, o, en, ko, 'hi'); res.append('ok')
            except RequestLimitReached:
                res.append('limit')
            except Exception as e:
                res.append('err:' + type(e).__name__)
            finally:
                connections.close_all()
        ts = [threading.Thread(target=go, args=(o,)) for o in others]
        [t.start() for t in ts]; [t.join() for t in ts]
        n = MatchRequest.objects.filter(sender=me).count()
        self.assertEqual(n, 3)
