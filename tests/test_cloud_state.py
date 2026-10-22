import base64
import copy
import hashlib
import io
import json
import unittest
import urllib.error
from unittest.mock import patch

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
                     for n, branch in ((1, state.OWNER_BRANCH), (2, state.WATCH_BRANCH))}
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
        # Match the real GitHubState projection, rather than inventing fields
        # (such as workflow path) that production callers cannot observe.
        value = self.runs[str(run_id)]
        return {k: copy.deepcopy(value.get(k)) for k in
                ('id', 'status', 'conclusion', 'head_sha', 'head_branch', 'run_attempt')}


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

    def test_previous_consumed_claim_is_not_valid_for_new_owner_authorization(self):
        claim, _ = self.claim()
        self.assertEqual(claim['authorization'], 'owner-connected-gpu-20261022')
        self.assertEqual(state.DIRECTORY, 'a100-state/owner-connected-gpu-20261022')
        for prior in ('owner-cloud-20261019-203126', 'owner-cloud-20261020-155445',
                      'owner-cloud-20261020-211134', 'owner-cloud-20261021-003938',
                      'owner-cloud-20261021-160757', 'owner-cloud-20261021-192529',
                      'owner-api-recovery-20261021'):
            with self.subTest(authorization=prior):
                claim['authorization'] = prior
                with self.assertRaises(ValueError):
                    state.validate_claim(claim)

    def test_two_hour_quote_includes_prior_wallet_spend(self):
        fresh = offer(); fresh['credit_balance'] = '4.00'
        # Fits the old 50-minute quote, but not this two-hour policy.
        control.validate_offer(fresh, T0)
        with self.assertRaisesRegex(ValueError, 'two-hour'):
            state.cloud_costs(fresh, T0)

    def test_missing_stale_cancelled_or_other_source_watcher_blocks_claim(self):
        for failure in ('missing', 'stale', 'cancelled', 'source', 'previous_branch'):
            with self.subTest(failure=failure):
                self.setUp()
                if failure == 'missing': self.store.docs.pop('watcher')
                if failure == 'stale': self.store.docs['watcher'][0]['at'] = T0 - 61
                if failure == 'cancelled': self.store.runs['2']['status'] = 'completed'
                if failure == 'source': self.store.runs['2']['head_sha'] = 'b' * 40
                if failure == 'previous_branch': self.store.runs['2']['head_branch'] = 'bt-001-a100-watch-20261021b'
                with self.assertRaises(state.StateError): self.claim()
                self.assertIsNone(self.store.read('claim'))

    def test_workflow_rerun_never_claims(self):
        self.store.runs['1']['run_attempt'] = 2
        with self.assertRaises(state.StateError): self.claim()
        self.assertIsNone(self.store.read('claim'))

    def test_watcher_observes_time_after_a_concurrently_refreshed_heartbeat(self):
        claim = self.allocate_fixture()
        clock = [T0]
        original_read = self.store.read
        checked = []
        def read(name):
            if name == 'heartbeat':
                clock[0] = T0 + 1
                return ({'attempt': claim['attempt'], 'at': T0 + 1, 'phase': 'setup'}, 'c' * 40)
            return original_read(name)
        def sleep(seconds):
            if not checked:
                self.assertFalse(any(c[0] in ('stop', 'delete') for c in self.api.calls))
                checked.append(True)
                self.store.runs['1']['status'] = 'completed'
            clock[0] += seconds
        with patch.object(self.store, 'read', side_effect=read):
            result = cloud_watch.watch(self.store, self.api, '2', SOURCE,
                wall=lambda: clock[0], sleep=sleep, emit=lambda row: None)
        self.assertTrue(checked)
        self.assertEqual((result['phase'], result['reason']), ('deleted', 'owner_finished'))

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
                       {'status': 'completed', 'run_attempt': 2}):
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

    def test_mutable_lease_lost_ack_is_confirmed_without_second_put(self):
        before = self.store.read('watcher')
        self.store.fail_write = 'watcher'
        writes = [0]
        original = self.store.write
        def once(*args, **kwargs):
            writes[0] += 1
            return original(*args, **kwargs)
        self.store.write = once
        value = {'run_id': '2', 'source_sha': SOURCE, 'at': T0 + 20}
        sha = cloud_watch.write_lease(self.store, value, before[1], sleep=lambda _: None)
        self.assertEqual((value, sha), self.store.read('watcher'))
        self.assertEqual(writes[0], 1)
        self.assertIsNone(self.store.read('claim'))
        self.assertEqual(self.api.calls, [])

    def test_unconfirmed_mutable_lease_is_not_rewritten(self):
        before = self.store.read('watcher')
        writes, reads = [0], [0]
        original_read = self.store.read
        def reject(*args, **kwargs):
            writes[0] += 1
            raise state.StateError('durable-state transport or JSON failure')
        def read(name):
            reads[0] += 1
            return original_read(name)
        self.store.write, self.store.read = reject, read
        with self.assertRaises(state.StateError):
            cloud_watch.write_lease(self.store, {'run_id': '2', 'source_sha': SOURCE, 'at': T0 + 20},
                                    before[1], sleep=lambda _: None)
        self.assertEqual((writes[0], reads[0]), (1, 3))
        self.assertEqual(original_read('watcher'), before)
        self.assertEqual(self.api.calls, [])

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

    def github_conflict_fixture(self, value, *, previous=None, changed=None,
                                status=409, conflicts=1, lost_ack=False):
        calls, documents = [], {}
        if previous is not None:
            documents['value'] = previous
        class Response(io.BytesIO):
            status = 200
        def open_request(request, timeout):
            calls.append(request)
            if request.method == 'PUT':
                count = sum(r.method == 'PUT' for r in calls)
                if count <= conflicts:
                    if changed is not None:
                        documents['value'] = changed
                    if lost_ack:
                        documents['value'] = (value, 'f' * 40)
                        raise TimeoutError('lost acknowledgement')
                    raise urllib.error.HTTPError(request.full_url, status, 'fixture', {}, None)
                documents['value'] = (value, 'f' * 40)
                return Response(b'{}')
            current = documents.get('value')
            if current is None:
                raise urllib.error.HTTPError(request.full_url, 404, 'absent', {}, None)
            body, sha = current
            return Response(json.dumps({'type': 'file', 'encoding': 'base64', 'sha': sha,
                'content': base64.b64encode(state.encoded(body)).decode()}).encode())
        return state.GitHubState('TEST-ONLY-TOKEN', opener=open_request), calls, documents

    def test_explicit_branch_conflict_retries_identical_create_only_claim(self):
        claim, _ = self.claim()
        store, calls, docs = self.github_conflict_fixture(claim)
        with patch.object(state.time, 'sleep'):
            self.assertEqual(store.write('claim', claim), 'f' * 40)
        puts = [r for r in calls if r.method == 'PUT']
        self.assertEqual(len(puts), 2)
        self.assertEqual(puts[0].data, puts[1].data)
        self.assertNotIn('sha', json.loads(puts[1].data))
        self.assertEqual(docs['value'][0], claim)

    def test_conflicting_claim_that_already_exists_never_gets_second_put(self):
        claim, _ = self.claim()
        store, calls, _ = self.github_conflict_fixture(claim, changed=(claim, 'e' * 40))
        with self.assertRaises(state.StateConflictError):
            store.write('claim', claim)
        self.assertEqual(sum(r.method == 'PUT' for r in calls), 1)

    def test_mutable_conflict_preserves_original_cas_and_refuses_changed_file(self):
        prior = ({'run_id': '2', 'source_sha': SOURCE, 'at': T0}, 'a' * 40)
        value = dict(prior[0], at=T0 + 1)
        for changed in (None, (dict(value, run_id='3'), 'b' * 40)):
            with self.subTest(changed=changed):
                store, calls, _ = self.github_conflict_fixture(value, previous=prior, changed=changed)
                with patch.object(state.time, 'sleep'):
                    if changed:
                        with self.assertRaises(state.StateConflictError):
                            store.write('watcher', value, previous_sha=prior[1])
                    else:
                        self.assertEqual(store.write('watcher', value, previous_sha=prior[1]), 'f' * 40)
                puts = [r for r in calls if r.method == 'PUT']
                self.assertEqual(len(puts), 1 if changed else 2)
                self.assertTrue(all(json.loads(r.data)['sha'] == prior[1] for r in puts))

    def test_conflict_retry_is_bounded_and_does_not_create_claim(self):
        claim, _ = self.claim()
        store, calls, docs = self.github_conflict_fixture(claim, conflicts=10)
        with patch.object(state.time, 'sleep'), self.assertRaises(state.StateConflictError):
            store.write('claim', claim)
        self.assertEqual(sum(r.method == 'PUT' for r in calls), 3)
        self.assertFalse(docs)

    def test_ambiguous_or_other_http_errors_never_retry_claim_put(self):
        claim, _ = self.claim()
        for kwargs in ({'lost_ack': True}, {'status': 503}, {'status': 403}, {'status': 422}):
            with self.subTest(kwargs=kwargs):
                store, calls, _ = self.github_conflict_fixture(claim, **kwargs)
                with self.assertRaises(state.StateError):
                    store.write('claim', claim)
                self.assertEqual(sum(r.method == 'PUT' for r in calls), 1)

    def test_conflict_followed_by_unreadable_state_does_not_retry_put(self):
        claim, _ = self.claim()
        store, calls, _ = self.github_conflict_fixture(claim)
        with patch.object(store, 'read', side_effect=state.StateError('unobservable')):
            with self.assertRaisesRegex(state.StateError, 'unobservable'):
                store.write('claim', claim)
        self.assertEqual(sum(r.method == 'PUT' for r in calls), 1)


if __name__ == '__main__':
    unittest.main()
