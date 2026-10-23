import unittest

from tools.cloud_launch import validate_context, wait_for_availability
from tools.cloud_state import REPOSITORY, StateError
from tests.test_cloud_state import MemoryStore, SOURCE
from tests.test_runpod_control import T0


class LaunchContextTests(unittest.TestCase):
    def context(self, branch, attempt):
        return {'GITHUB_REPOSITORY': REPOSITORY, 'GITHUB_REF_NAME': branch,
                'GITHUB_RUN_ATTEMPT': attempt}

    def test_free_preflight_can_repeat_only_on_its_review_branch(self):
        for attempt in ('1', '2'):
            validate_context('preflight', self.context('bt-001-qualified-gpu-20261023', attempt))
        with self.assertRaises(StateError):
            validate_context('preflight', self.context('bt-001-a100-start-qualified-20261023', '1'))

    def test_paid_mode_still_requires_first_run_on_the_exact_start_branch(self):
        validate_context('paid', self.context('bt-001-a100-start-qualified-20261023', '1'))
        for branch, attempt in (('bt-001-a100-start-qualified-20261023', '2'),
                                ('bt-001-qualified-gpu-20261023', '1'),
                                ('bt-001-a100-start-qualified-20261023', '0'),
                                ('bt-001-a100-start-20261019', '1'),
                                ('bt-001-a100-start-20261020b', '1'),
                                ('bt-001-a100-start-20261020c', '1'),
                                ('bt-001-a100-start-20261021a', '1'),
                                ('bt-001-a100-start-20261021b', '1'),
                                ('bt-001-a100-start-20261021c', '1'),
                                ('bt-001-a100-start-api-recovery', '1'),
                                ('bt-001-a100-start-connected-gpu', '1'),
                                ('bt-001-a100-start-bootstrap-probe', '1')):
            with self.assertRaises(StateError):
                validate_context('paid', self.context(branch, attempt))


class StockWaitTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.store.write('watcher', {'run_id': '2', 'source_sha': SOURCE, 'at': T0})
        self.elapsed = 0
        self.polls = 0
        self.events = []

    def sleep(self, seconds):
        self.elapsed += seconds

    def wait(self, inspect, timeout=40):
        return wait_for_availability(self.store, SOURCE,
            {'status': 'NO_QUALIFIED_REGION'}, self.events.append, inspect=inspect,
            timeout=timeout, wall=lambda: T0 + self.elapsed,
            monotonic=lambda: self.elapsed, sleep=self.sleep)

    def test_stock_return_uses_fresh_offer_without_consuming_a_claim(self):
        fresh = {'status': 'QUALIFIED', 'offer': {'observed_at': 'fresh'}}
        result, elapsed = self.wait(lambda: fresh)
        self.assertEqual((result, elapsed), (fresh, 20))
        self.assertIsNone(self.store.read('claim'))
        self.assertEqual(self.events[0]['allocation_requests'], 0)

    def test_no_stock_wait_is_bounded_and_leaves_authorization_unused(self):
        def inspect():
            self.polls += 1
            return {'status': 'NO_QUALIFIED_REGION'}
        result, elapsed = self.wait(inspect)
        self.assertEqual((result['status'], elapsed, self.polls), ('NO_QUALIFIED_REGION', 40, 2))
        self.assertIsNone(self.store.read('claim'))

    def test_concurrent_claim_stops_before_another_inventory_read(self):
        self.store.docs['claim'] = ({'already': 'claimed'}, 'a' * 40)
        with self.assertRaisesRegex(StateError, 'consumed'):
            self.wait(lambda: self.fail('must not poll after a claim'))
        self.assertEqual(self.elapsed, 0)

    def test_wrong_source_watcher_stops_before_inventory_or_sleep(self):
        self.store.docs['watcher'][0]['source_sha'] = 'b' * 40
        with self.assertRaisesRegex(StateError, 'source'):
            self.wait(lambda: self.fail('must not poll without the source-bound watcher'))
        self.assertEqual(self.elapsed, 0)


if __name__ == '__main__':
    unittest.main()
