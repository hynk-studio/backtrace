import base64
import copy
import hashlib
import io
import json
import unittest

from tools import cloud_state as state
from tools import cloud_watch
from tools import runpod_control as control
from tests.test_runpod_control import FakeProvider, T0, offer

SOURCE = 'a' * 40


class MemoryStore:
    def __init__(self):
        self.docs = {}
        self.runs = {str(n): {'id': n, 'status': 'in_progress', 'conclusion': None,
                              'head_sha': SOURCE, 'head_branch': branch, 'run_attempt': 1}
                     for n, branch in ((1, 'bt-001-a100-start-20261019'),
                                       (2, 'bt-001-a100-watch-20261019'))}
        self.fail_write = None

    def read(self, name):
        return copy.deepcopy(self.docs.get(name))

    def write(self, name, value, *, previous_sha=None):
        state.validate_document(name, value)
        if (self.docs.get(name) or (None, None))[1] != previous_sha:
            raise state.StateError('CAS conflict')
        if name in ('claim', 'pod') and previous_sha is not None:
            raise state.StateError('immutable')
        sha = hashlib.sha1(state.encoded(value)).hexdigest()
        self.docs[name] = (copy.deepcopy(value), sha)
        if self.fail_write == name:
            raise state.StateError('acknowledgement lost after durable write')
        return sha

    def run(self, run_id):
        return copy.deepcopy(self.runs[str(run_id)])


class CloudStateTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore(); self.api = FakeProvider()
        self.store.write('watcher', {'run_id': '2', 'source_sha': SOURCE, 'at': T0})

    def claim(self):
        return state.claim_before_create(self.store, self.api, offer(), None, '1', SOURCE,
                                         wall=lambda: T0)

    def allocate_fixture(self):
        claim, request = self.claim()
        self.api.create(request)
        return claim

    def test_claim_is_durable_before_caller_can_send_request(self):
        claim, request = self.claim()
        self.assertEqual(self.store.read('claim')[0], claim)
        self.assertEqual(request['name'], claim['name'])
        self.assertFalse(any(c[0] == 'create' for c in self.api.calls))
        self.assertEqual(claim['total_seconds'], 7200)
        self.assertEqual(claim['setup_seconds'], 5400)
        self.assertNotIn('env', json.dumps(claim))
        with self.assertRaisesRegex(state.StateError, 'consumed'):
            self.claim()

    def test_write_timeout_cannot_be_retried_as_new_authorization(self):
        self.store.fail_write = 'claim'
        with self.assertRaises(state.StateError):
            self.claim()
        self.assertIsNotNone(self.store.read('claim'))
        self.store.fail_write = None
        with self.assertRaisesRegex(state.StateError, 'consumed'):
            self.claim()
        self.assertEqual(self.api.calls, [])

    def test_two_hour_quote_includes_prior_wallet_spend(self):
        fresh = offer(); fresh['credit_balance'] = '4.00'
        # Fits the old 50-minute quote, but not this two-hour policy.
        control.validate_offer(fresh, T0)
        with self.assertRaisesRegex(ValueError, 'two-hour'):
            state.cloud_costs(fresh, T0)

    def test_missing_stale_cancelled_or_other_source_watcher_blocks_claim(self):
        for failure in ('missing', 'stale', 'cancelled', 'source'):
            with self.subTest(failure=failure):
                self.setUp()
                if failure == 'missing': self.store.docs.pop('watcher')
                if failure == 'stale': self.store.docs['watcher'][0]['at'] = T0 - 61
                if failure == 'cancelled': self.store.runs['2']['status'] = 'completed'
                if failure == 'source': self.store.runs['2']['head_sha'] = 'b' * 40
                with self.assertRaises(state.StateError): self.claim()
                self.assertIsNone(self.store.read('claim'))

    def test_workflow_rerun_never_claims(self):
        self.store.runs['1']['run_attempt'] = 2
        with self.assertRaises(state.StateError): self.claim()
        self.assertIsNone(self.store.read('claim'))

    def test_public_state_rejects_keys_urls_and_unknown_fields(self):
        claim, _ = self.claim()
        claim['bootstrap'] = {'env': {'SECRET': 'never-public'}}
        with self.assertRaises(ValueError): state.validate_claim(claim)
        with self.assertRaises(ValueError):
            state.validate_document('heartbeat', {'attempt': 'a' * 32, 'at': T0,
                                                   'phase': 'https://private?SECRET'})

    def test_owner_cancellation_cleanup_survives_loss_of_local_journal(self):
        claim = self.allocate_fixture()
        self.store.runs['1'].update(status='completed', conclusion='cancelled')
        clock = [T0 + 1]
        def sleep(seconds): clock[0] += seconds
        result = cloud_watch.watch(self.store, self.api, '2', SOURCE,
                                   wall=lambda: clock[0], sleep=sleep)
        self.assertEqual(result['phase'], 'deleted')
        self.assertEqual(result['absence_reads'], 2)
        self.assertEqual(result['reason'], 'owner_cancelled')
        self.assertEqual(set(self.api.pods), {'unrelated'})
        self.assertEqual(sum(c[0] == 'create' for c in self.api.calls), 1)

    def test_completed_unclaimed_free_watcher_can_hand_over_with_cas(self):
        previous = self.store.read('watcher')
        self.store.runs['2'].update(status='completed', conclusion='success',
                                   path='.github/workflows/a100-watch.yml')
        next_source = 'b' * 40
        clock = [T0 + 700]
        result = cloud_watch.watch(self.store, self.api, '3', next_source,
            wall=lambda: clock[0], sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
        self.assertEqual(result['phase'], 'no_claim')
        self.assertEqual(self.store.read('watcher')[0]['run_id'], '3')
        self.assertEqual(self.store.read('watcher')[0]['source_sha'], next_source)
        self.assertEqual(previous[0]['run_id'], '2')
        self.assertIsNone(self.store.read('claim'))
        self.assertEqual(self.api.calls, [])

    def test_free_watcher_handover_cannot_replace_active_or_unmatched_run(self):
        for change in ({}, {'status': 'completed', 'head_sha': 'b' * 40},
                       {'status': 'completed', 'head_branch': 'other'},
                       {'status': 'completed', 'run_attempt': 2},
                       {'status': 'completed', 'path': 'other.yml'}):
            with self.subTest(change=change):
                self.setUp()
                self.store.runs['2']['path'] = '.github/workflows/a100-watch.yml'
                self.store.runs['2'].update(change)
                before = self.store.read('watcher')
                with self.assertRaises(state.StateError):
                    cloud_watch.starting_lease(self.store, '3', 'b' * 40)
                self.assertEqual(self.store.read('watcher'), before)

    def test_free_watcher_handover_never_resets_even_unallocated_claim(self):
        self.claim()
        self.store.runs['2'].update(status='completed', path='.github/workflows/a100-watch.yml')
        before = copy.deepcopy(self.store.docs)
        with self.assertRaisesRegex(state.StateError, 'claimed'):
            cloud_watch.starting_lease(self.store, '3', 'b' * 40)
        self.assertEqual(self.store.docs, before)
        self.assertEqual(self.api.calls, [])

    def test_claim_appearing_during_free_watcher_handover_blocks_it(self):
        self.store.runs['2'].update(status='completed', path='.github/workflows/a100-watch.yml')
        original = self.store.read
        reads = [0]
        def race(name):
            if name == 'claim':
                reads[0] += 1
                if reads[0] == 2:
                    return ({'appeared': True}, 'f' * 40)
            return original(name)
        self.store.read = race
        with self.assertRaisesRegex(state.StateError, 'claimed'):
            cloud_watch.starting_lease(self.store, '3', 'b' * 40)
        self.assertEqual(original('watcher')[0]['run_id'], '2')

    def test_free_watcher_handover_retains_exact_cas_lease(self):
        self.store.runs['2'].update(status='completed', path='.github/workflows/a100-watch.yml')
        lease = cloud_watch.starting_lease(self.store, '3', 'b' * 40)
        self.store.write('watcher', {'run_id': '4', 'source_sha': 'c' * 40, 'at': T0 + 1},
                         previous_sha=lease)
        with self.assertRaisesRegex(state.StateError, 'CAS'):
            self.store.write('watcher', {'run_id': '3', 'source_sha': 'b' * 40, 'at': T0 + 2},
                             previous_sha=lease)
        self.assertEqual(self.store.read('watcher')[0]['run_id'], '4')

    def test_lost_create_response_is_reconciled_by_exact_random_name(self):
        claim, request = self.claim()
        self.api.drop_ack = True
        with self.assertRaises(control.ProviderError): self.api.create(request)
        first = state.reconcile(self.api, claim, None, None, 'owner_finished', T0 + 1)
        final = state.reconcile(self.api, claim, None, first, 'owner_finished', T0 + 21)
        self.assertEqual(final['phase'], 'deleted')
        self.assertEqual(final['pod_id'], 'owned123')
        self.assertIn('unrelated', self.api.pods)

    def test_no_resource_does_not_mean_confirmed_deletion(self):
        claim, _ = self.claim()
        first = state.reconcile(self.api, claim, None, None, 'owner_finished', T0 + 90)
        final = state.reconcile(self.api, claim, None, first, 'owner_finished', T0 + 110)
        self.assertEqual(final['phase'], 'no_resource_observed')
        self.assertIsNone(final['pod_id'])
        with self.assertRaisesRegex(state.StateError, 'consumed'): self.claim()

    def test_contradictory_pod_identity_is_not_deleted(self):
        claim = self.allocate_fixture()
        self.api.pods['owned123']['name'] = 'someone-else'
        with self.assertRaisesRegex(state.StateError, 'no longer belongs'):
            state.reconcile(self.api, claim, {'attempt': claim['attempt'], 'pod_id': 'owned123'},
                            None, 'owner_finished', T0 + 1)
        self.assertFalse(any(c[0] == 'delete' for c in self.api.calls))

    def test_stop_failure_still_attempts_delete(self):
        claim = self.allocate_fixture(); self.api.fail_stop = True
        result = state.reconcile(self.api, claim, None, None, 'owner_finished', T0 + 1)
        self.assertEqual(result['absence_reads'], 1)
        self.assertNotIn('owned123', self.api.pods)

    def test_setup_and_absolute_deadlines_are_allocation_inclusive(self):
        claim, _ = self.claim(); run = self.store.run('1')
        for phase, elapsed, reason in (('setup', 5400, 'setup_deadline'),
                                       ('workload', 6900, 'useful_deadline')):
            beat = {'attempt': claim['attempt'], 'at': T0 + elapsed, 'phase': phase}
            self.assertEqual(state.cleanup_reason(claim, run, beat, T0 + elapsed), reason)

    def test_github_request_claim_is_create_only_and_read_back(self):
        claim, _ = self.claim()
        requests = []
        class Response(io.BytesIO):
            status = 200
        def open_request(request, timeout):
            requests.append(request)
            if request.method == 'PUT':
                body = json.loads(request.data)
                self.assertNotIn('sha', body)
                self.assertEqual(body['branch'], state.BRANCH)
                return Response(b'{}')
            return Response(json.dumps({'type': 'file', 'encoding': 'base64', 'sha': 'f' * 40,
                'content': base64.b64encode(state.encoded(claim)).decode()}).encode())
        store = state.GitHubState('TEST-ONLY-TOKEN', opener=open_request)
        self.assertEqual(store.write('claim', claim), 'f' * 40)
        self.assertEqual([r.method for r in requests], ['PUT', 'GET'])
        with self.assertRaises(ValueError): store.write('claim', claim, previous_sha='f' * 40)


if __name__ == '__main__':
    unittest.main()
