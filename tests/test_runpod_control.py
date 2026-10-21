import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from tools import runpod_control as control

T0 = 1792200000


def offer(now=T0):
    return {'gpu': control.GPU, 'gpu_count': 1, 'cloud': 'SECURE', 'region': 'EU-RO-1',
            'container_disk_gb': 100, 'volume_gb': 0, 'network_volume': None,
            'interruptible': False, 'stock_available': True, 'auto_pay': False,
            'authenticated': True, 'image': control.BASE, 'vcpus': 8, 'ram_gb': 117,
            'observed_at': control.utc(now), 'compute_per_hour': '1.79',
            'storage_per_hour': '0.014', 'tax_rate': '0.10', 'other_total': '0.00',
            'credit_balance': '10.00'}


class FakeProvider:
    def __init__(self):
        self.pods = {'unrelated': {'id': 'unrelated', 'name': 'keep-me'}}
        self.calls = []
        self.request = None
        self.contract = True
        self.drop_ack = False
        self.bad_expiry = False
        self.fail_stop = False
        self.fail_delete = False
        self.fail_read = False

    def check_native_contract(self):
        if not self.contract:
            raise control.ProviderError('missing contract')

    def create(self, payload):
        self.calls.append(('create', None))
        self.request = payload
        pod = {'id': 'owned123', 'name': payload['name'], 'image': control.BASE,
               'gpu': {'id': control.GPU, 'count': 1, 'memory': 117, 'vcpuCount': 8},
               'mounts': {}, 'cost': 1.804, 'cloud': 'SECURE', 'disk': 100,
               'ports': ['22/tcp'], 'dataCenterId': payload['dataCenterIds'][0], 'locked': False,
               'status': 'RUNNING', 'env': {}}
        self.pods[pod['id']] = pod
        if self.drop_ack:
            raise control.ProviderError('lost create response')
        return copy.deepcopy(pod)

    def native_expiry(self, pod_id):
        return {'id': pod_id, 'stopAfter': self.request['stopAfter'],
                'terminateAfter': control.utc(T0 + 9000) if self.bad_expiry else self.request['terminateAfter']}

    def get(self, pod_id):
        if self.fail_read:
            raise control.ProviderError('network unavailable')
        return copy.deepcopy(self.pods.get(pod_id))

    def list(self):
        if self.fail_read:
            raise control.ProviderError('network unavailable')
        return copy.deepcopy(list(self.pods.values()))

    def stop(self, pod_id):
        self.calls.append(('stop', pod_id))
        if self.fail_stop:
            raise control.ProviderError('stop failed')
        if pod_id in self.pods:
            self.pods[pod_id]['desiredStatus'] = 'EXITED'

    def delete(self, pod_id):
        self.calls.append(('delete', pod_id))
        if self.fail_delete:
            raise control.ProviderError('delete failed')
        self.pods.pop(pod_id, None)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.api = FakeProvider()
        self.journal = control.Journal(self.root).__enter__()
        self.addCleanup(self.journal.__exit__)

    def begin(self):
        return control.begin(self.api, self.journal, offer(), wall=lambda: T0)

    def test_request_freezes_v2_scope_without_nonfunctional_timers(self):
        request = control.make_request('a' * 32, T0)
        self.assertNotIn('stopAfter', request)
        self.assertNotIn('terminateAfter', request)
        self.assertEqual(request['dataCenterIds'], ['EU-RO-1'])
        self.assertEqual(request['gpu']['count'], 1)
        self.assertEqual(request['ports'], ['22/tcp'])
        self.assertFalse(request['startJupyter'])
        self.assertNotIn('env', request)

    def test_offer_counts_storage_tax_and_refuses_bad_scope(self):
        self.assertLess(control.money(control.validate_offer(offer(), T0)['maximum_all_in']), control.CAP)
        for key, value in [('compute_per_hour', '12.50'), ('credit_balance', '0'), ('credit_balance', '10.01'),
                           ('tax_rate', 'NaN'), ('region', 'US-CA-1'), ('gpu_count', 2),
                           ('volume_gb', 10), ('auto_pay', True), ('authenticated', False),
                           ('ram_gb', 116), ('stock_available', False), ('gpu_count', True)]:
            with self.subTest(key=key, value=value):
                data = offer(); data[key] = value
                with self.assertRaises(ValueError):
                    control.validate_offer(data, T0)
        for now in (T0 - 1, T0 + 301):
            with self.assertRaises(ValueError):
                control.validate_offer(offer(), now)

    def test_revised_plan_does_not_call_native_expiry(self):
        self.api.contract = False
        self.api.native_expiry = lambda _: self.fail('unavailable native timers must not be called')
        value = self.begin()
        self.assertEqual(value['policy'], 'prepaid10-external-v2')
        self.assertFalse(value['native_expiry_verified'])

    def test_equivalent_region_is_bound_in_request_journal_and_readback(self):
        data = offer(); data.update(region='US-MO-1', region_policy=control.REGION_POLICY)
        value = control.begin(self.api, self.journal, data, wall=lambda: T0)
        self.assertEqual(value['request']['dataCenterIds'], ['US-MO-1'])
        self.assertEqual(self.journal.read()['region'], 'US-MO-1')
        self.assertTrue(control.resource_matches(self.api.get('owned123'), value))
        self.api.pods['owned123']['dataCenterId'] = 'EU-RO-1'
        self.assertFalse(control.resource_matches(self.api.get('owned123'), value))
        with self.assertRaises(ValueError):
            control.begin(self.api, self.journal, data, wall=lambda: T0)
        self.assertEqual(sum(a == 'create' for a, _ in self.api.calls), 1)

    def test_region_amendment_does_not_allow_broad_or_malformed_location(self):
        for region in (None, '', ['US-MO-1'], 'any', 'US-MO-1,EU-RO-1', '../US-MO-1'):
            data = offer(); data.update(region=region, region_policy=control.REGION_POLICY)
            with self.subTest(region=region), self.assertRaises(ValueError):
                control.validate_offer(data, T0)

    def failed_prior(self):
        self.api.create = lambda _: (_ for _ in ()).throw(control.ProviderError('failed'))
        with self.assertRaises(RuntimeError):
            self.begin()
        raw = self.journal.path.read_bytes()
        return raw, {'id': 'owner-followup', 'at_utc': control.utc(T0 + 3600),
                     'previous_sha256': hashlib.sha256(raw).hexdigest()}

    def test_explicit_followup_archives_exact_bytes_under_same_lock_only_once(self):
        raw, authorization = self.failed_prior()
        old = json.loads(raw)
        control.archive_unallocated_attempt(self.api, self.journal, authorization, wall=lambda: T0 + 3601)
        archive = self.root / 'history' / old['attempt']
        self.assertEqual((archive / 'a100-attempt.json').read_bytes(), raw)
        self.assertEqual(len(json.loads((archive / 'transition.json').read_text())['live_absence']), 2)
        self.assertFalse(self.journal.path.exists())
        self.assertEqual(json.loads(raw)['phase'], 'cleanup_unresolved')
        with self.assertRaises(ValueError):
            control.archive_unallocated_attempt(self.api, self.journal, authorization, wall=lambda: T0 + 3602)

    def test_followup_refuses_changed_digest_or_not_new_authorization(self):
        raw, authorization = self.failed_prior()
        for changes in ({'previous_sha256': '0' * 64}, {'at_utc': control.utc(T0)},
                        {'at_utc': control.utc(T0 + 5000)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                control.archive_unallocated_attempt(self.api, self.journal,
                                                   dict(authorization, **changes), wall=lambda: T0 + 3601)
        self.assertEqual(self.journal.path.read_bytes(), raw)
        self.assertFalse((self.root / 'history').exists())

    def test_followup_refuses_existing_pod_or_incomplete_provider_observation(self):
        raw, authorization = self.failed_prior()
        self.api.pods['prior'] = {'id': 'prior', 'name': json.loads(raw)['request']['name']}
        with self.assertRaises(ValueError):
            control.archive_unallocated_attempt(self.api, self.journal, authorization, wall=lambda: T0 + 3601)
        self.api.pods.pop('prior'); self.api.fail_read = True
        with self.assertRaises(control.ProviderError):
            control.archive_unallocated_attempt(self.api, self.journal, authorization, wall=lambda: T0 + 3601)
        self.assertEqual(self.journal.path.read_bytes(), raw)

    def test_restored_old_checkpoint_with_consumed_allocation_receipt_cannot_retry(self):
        raw, authorization = self.failed_prior()
        guard = self.root / 'allocated-attempt-consumed.json'
        guard.write_text(json.dumps({'confirmed_allocations': 1, 'phase': 'deleted',
                                     'source': 'observed output after checkpoint rollback'}))
        guard.chmod(0o600)
        with self.assertRaises(ValueError):
            control.archive_unallocated_attempt(self.api, self.journal, authorization,
                                               wall=lambda: T0 + 3601)
        self.assertEqual(self.journal.path.read_bytes(), raw)
        self.assertTrue(guard.is_file())
        self.assertFalse((self.root / 'history').exists())
        self.assertFalse(self.api.calls)

    def test_followup_cannot_archive_confirmed_allocation_or_symlink_history(self):
        raw, authorization = self.failed_prior()
        value = json.loads(raw); value['pod_id'] = 'owned123'
        self.journal.write(value)
        authorization['previous_sha256'] = hashlib.sha256(self.journal.path.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            control.archive_unallocated_attempt(self.api, self.journal, authorization, wall=lambda: T0 + 3601)
        self.journal.path.write_bytes(raw)
        authorization['previous_sha256'] = hashlib.sha256(raw).hexdigest()
        (self.root / 'history').symlink_to(self.root)
        with self.assertRaises(ValueError):
            control.archive_unallocated_attempt(self.api, self.journal, authorization, wall=lambda: T0 + 3601)
        self.assertEqual(self.journal.path.read_bytes(), raw)

    def test_spent_wallet_counts_toward_total_eight_dollar_threshold(self):
        data = offer(); data['credit_balance'] = '3.50'
        with self.assertRaises(ValueError):
            control.validate_offer(data, T0)
        data['credit_balance'] = '5.00'
        costs = control.validate_offer(data, T0)
        self.assertEqual(costs['spent_before'], '5.00')

    def test_marker_is_durable_before_create_and_no_retry(self):
        original = self.api.create
        def observed(payload):
            value = self.journal.read()
            self.assertEqual(value['phase'], 'requested')
            self.assertEqual(value['request'], payload)
            return original(payload)
        self.api.create = observed
        value = self.begin()
        with self.assertRaises(ValueError):
            self.begin()
        self.assertEqual(sum(a == 'create' for a, _ in self.api.calls), 1)
        self.assertEqual(value['phase'], 'allocated')

    def test_oversized_initializer_blocks_before_network_and_attempt_marker(self):
        payload = control.make_request('a' * 32, T0)
        payload['env'] = {'transport': 'x' * 863192}
        with patch.object(control, 'make_request', return_value=payload), \
                patch.object(self.api, 'list') as listing:
            with self.assertRaisesRegex(ValueError, 'exceeds 102400 bytes'):
                self.begin()
        listing.assert_not_called()
        self.assertFalse(self.journal.path.exists())
        self.assertFalse(self.api.calls)

    def test_create_error_keeps_status_without_response_body(self):
        self.api.create = lambda payload: (_ for _ in ()).throw(
            control.ProviderError('provider HTTP 413', http_status=413))
        with self.assertRaises(RuntimeError):
            self.begin()
        value = self.journal.read()
        self.assertEqual(value['events'][0],
                         {'event': 'create_failed', 'type': 'ProviderError', 'http_status': 413})
        self.assertEqual(value['phase'], 'cleanup_unresolved')
        self.assertIsNone(value['pod_id'])

    def test_second_controller_cannot_claim_journal(self):
        with self.assertRaises(BlockingIOError):
            with control.Journal(self.root):
                pass

    def test_existing_project_pod_blocks_create_even_without_local_journal(self):
        self.api.pods['older'] = {'id': 'older', 'name': 'backtrace-a100-' + 'b' * 32}
        with self.assertRaisesRegex(ValueError, 'earlier Backtrace Pod'):
            self.begin()
        self.assertFalse(self.journal.path.exists())
        self.assertFalse(self.api.calls)

    def test_lost_create_response_reconciles_without_second_create(self):
        self.api.drop_ack = True
        with self.assertRaises(RuntimeError):
            self.begin()
        value = self.journal.read()
        self.assertEqual(value['pod_id'], 'owned123')
        self.assertNotIn('owned123', self.api.pods)
        self.assertIn('unrelated', self.api.pods)
        self.assertEqual(sum(a == 'create' for a, _ in self.api.calls), 1)

    def test_empty_reconciliation_never_asserts_no_allocation(self):
        def timeout(payload):
            self.api.calls.append(('create', None))
            raise control.ProviderError('response lost')
        self.api.create = timeout
        with self.assertRaises(RuntimeError):
            self.begin()
        value = self.journal.read()
        self.assertEqual(value['phase'], 'cleanup_unresolved')
        self.assertIsNone(value['pod_id'])
        self.assertEqual(self.api.calls, [('create', None)])

    def test_unapproved_persistent_mount_triggers_cleanup(self):
        value = self.begin(); self.heartbeat(value, T0 + 1)
        self.api.pods['owned123']['mounts'] = {'persistent': {'size': 20, 'path': '/workspace'}}
        value = control.watchdog(self.api, self.journal, wall=lambda: T0 + 1,
                                 monotonic=lambda: 10, sleep=lambda _: None)
        self.assertEqual(value['phase'], 'deleted')
        self.assertNotIn('owned123', self.api.pods)

    def test_stop_failure_still_deletes_and_requires_two_readbacks(self):
        value = self.begin(); self.api.fail_stop = True
        self.assertFalse(control.cleanup_once(self.api, self.journal, value))
        self.assertTrue(control.cleanup_once(self.api, self.journal, value))
        self.assertEqual(value['phase'], 'deleted')
        self.assertIn(('delete', 'owned123'), self.api.calls)
        self.assertIn('unrelated', self.api.pods)

    def test_stopped_or_delete_ack_is_not_deletion(self):
        value = self.begin(); self.api.fail_delete = True
        self.assertFalse(control.cleanup_once(self.api, self.journal, value))
        self.assertEqual(self.api.pods['owned123']['desiredStatus'], 'EXITED')
        self.api.delete = lambda pod_id: {}  # 204 acknowledged but still listed.
        self.assertFalse(control.cleanup_once(self.api, self.journal, value))
        self.assertEqual(value['absence_reads'], 0)

    def test_read_failure_does_not_suppress_known_id_deletion(self):
        value = self.begin(); self.api.fail_read = True
        self.assertFalse(control.cleanup_once(self.api, self.journal, value))
        self.assertIn(('delete', 'owned123'), self.api.calls)
        self.assertNotEqual(value['phase'], 'deleted')

    def test_ownership_conflict_never_mutates_foreign_resource(self):
        value = self.begin(); self.api.pods['owned123']['name'] = 'somebody-else'
        before = list(self.api.calls)
        self.assertFalse(control.cleanup_once(self.api, self.journal, value))
        self.assertEqual(self.api.calls, before)

    def test_missing_worker_heartbeat_cleans_up(self):
        self.begin()
        value = control.watchdog(self.api, self.journal, wall=lambda: T0 + 1,
                                 monotonic=lambda: 10, sleep=lambda _: None)
        self.assertEqual(value['phase'], 'deleted')
        self.assertEqual(value['billing'], 'PENDING separate actual billing evidence')

    def test_deadline_cleans_up_even_with_running_heartbeat(self):
        value = self.begin()
        self.heartbeat(value, T0 + 2700)
        result = control.watchdog(self.api, self.journal, wall=lambda: T0 + 2700,
                                  monotonic=lambda: 10, sleep=lambda _: None)
        self.assertEqual(result['phase'], 'deleted')
        self.assertTrue(any(e.get('reason') == 'useful_deadline' for e in result['events']))

    def test_setup_deadline_includes_transfer_and_installation(self):
        value = self.begin(); self.heartbeat(value, T0 + 1200)
        p = self.root / 'job-status.json'; data = json.loads(p.read_text())
        data['phase'] = 'setup'; p.write_text(json.dumps(data))
        result = control.watchdog(self.api, self.journal, wall=lambda: T0 + 1200,
                                  monotonic=lambda: 10, sleep=lambda _: None)
        self.assertEqual(result['phase'], 'deleted')
        self.assertTrue(any(e.get('reason') == 'setup_deadline' for e in result['events']))

    def heartbeat(self, value, at):
        p = self.root / 'job-status.json'
        p.write_text(json.dumps({'attempt': value['attempt'], 'state': 'running', 'at': control.utc(at)}))
        p.chmod(0o600)

    def test_slow_deletion_is_counted_after_final_readback(self):
        self.begin()
        clock = [T0 + 2999]
        original = self.api.list
        def slow_list():
            clock[0] += 2
            return original()
        self.api.list = slow_list
        result = control.watchdog(self.api, self.journal, wall=lambda: clock[0],
                                  monotonic=lambda: 10, sleep=lambda _: None)
        self.assertTrue(result['deadline_exceeded'])
        self.assertEqual(result['request_to_deletion_seconds'], 3003)

    def test_clock_rollback_does_not_extend_work(self):
        value = self.begin(); self.heartbeat(value, T0 + 10)
        values = iter([T0 + 10, T0 + 5, T0 + 5, T0 + 5, T0 + 5])
        result = control.watchdog(self.api, self.journal, wall=lambda: next(values),
                                  monotonic=lambda: 10, sleep=lambda _: None)
        self.assertEqual(result['phase'], 'deleted')
        self.assertTrue(any(e.get('reason') == 'clock_regression' for e in result['events']))

    def test_provider_price_change_triggers_cleanup(self):
        value = self.begin(); self.heartbeat(value, T0 + 1)
        self.api.pods['owned123']['cost'] = 5
        result = control.watchdog(self.api, self.journal, wall=lambda: T0 + 1,
                                  monotonic=lambda: 10, sleep=lambda _: None)
        self.assertEqual(result['phase'], 'deleted')

    def test_cleanup_outage_remains_explicit_failure(self):
        self.begin(); self.api.fail_read = True; self.api.fail_delete = True
        with self.assertRaises(RuntimeError):
            control.watchdog(self.api, self.journal, wall=lambda: T0 + 3180,
                              monotonic=lambda: 10, sleep=lambda _: None)
        value = self.journal.read()
        self.assertNotEqual(value['phase'], 'deleted')
        self.assertTrue(value['deadline_exceeded'])


class APIContractTests(unittest.TestCase):
    def response(self, value, status=200):
        result = io.BytesIO(json.dumps(value).encode())
        result.status = status
        return result

    def test_real_client_serializes_one_v2_create_without_retry(self):
        requests = []
        def opener(request, timeout):
            requests.append(request)
            self.assertEqual(timeout, 10)
            return self.response({'id': 'one', 'name': 'test'})
        api = control.RunpodAPI('fake-fixture-secret', opener=opener)
        payload = control.make_request('a' * 32, T0)
        api.create(payload)
        self.assertEqual(len(requests), 1)
        self.assertEqual(json.loads(requests[0].data), payload)
        self.assertEqual(requests[0].full_url, 'https://api.runpod.io/v2/pods')
        self.assertNotIn('fake-fixture-secret', requests[0].full_url)

    def test_exact_wire_limit_and_escaped_unicode_are_checked_before_http(self):
        empty = {'env': {'transport': ''}}
        room = control.MAX_CREATE_BYTES - len(json.dumps(empty).encode())
        requests = []
        def opener(request, timeout):
            requests.append(request)
            return self.response({'id': 'one'})
        api = control.RunpodAPI('fixture', opener=opener)
        api.create({'env': {'transport': 'x' * room}})
        self.assertEqual(len(requests[0].data), control.MAX_CREATE_BYTES)
        for text in ('x' * (room + 1), '\uac00' * (room // 6 + 1)):
            with self.assertRaisesRegex(ValueError, 'exceeds 102400 bytes'):
                api.create({'env': {'transport': text}})
        self.assertEqual(len(requests), 1)

    def test_v2_list_follows_every_page_and_encodes_opaque_cursor(self):
        paths = []
        def opener(request, timeout):
            paths.append(request.full_url)
            first = len(paths) == 1
            return self.response({'pods': [{'id': 'one' if first else 'two'}],
                'pagination': {'hasNextPage': first, 'nextCursor': 'opaque+/=' if first else None}})
        api = control.RunpodAPI('fixture', opener=opener)
        self.assertEqual([p['id'] for p in api.list()], ['one', 'two'])
        self.assertTrue(paths[1].endswith('cursor=opaque%2B%2F%3D'))

    def test_v2_repeated_cursor_or_missing_pagination_is_inconclusive(self):
        for value in ({'pods': []}, {'pods': [], 'pagination': {'hasNextPage': True, 'nextCursor': 'same'}}):
            api = control.RunpodAPI('fixture', opener=lambda *a, **kw: self.response(value))
            with self.assertRaises(control.ProviderError):
                api.list()

    def test_provider_errors_redact_tokens_and_bodies(self):
        def opener(*args, **kwargs):
            raise urllib.error.HTTPError('https://example/?key=fake-secret', 403, 'fake-secret', {}, io.BytesIO(b'fake-secret'))
        api = control.RunpodAPI('fake-secret', opener=opener)
        with self.assertRaises(control.ProviderError) as context:
            api.list()
        self.assertNotIn('fake-secret', str(context.exception))
        self.assertEqual(context.exception.http_status, 403)

    def test_flat_v1_response_is_not_v2_success(self):
        api = control.RunpodAPI('fixture', opener=lambda *a, **kw: self.response({'data': {}, 'errors': [{'message': 'secret'}]}))
        with self.assertRaises(control.ProviderError):
            api.list()

    def test_v2_stop_action_and_delete_keep_the_exact_id(self):
        calls = []
        def opener(request, timeout):
            calls.append((request.method, request.full_url, request.data))
            return self.response({})
        api = control.RunpodAPI('fixture', opener=opener)
        api.stop('owned123'); api.delete('owned123')
        self.assertEqual(calls[0][:2], ('POST', 'https://api.runpod.io/v2/pods/owned123/action'))
        self.assertEqual(json.loads(calls[0][2]), {'action': 'stop'})
        self.assertEqual(calls[1][:2], ('DELETE', 'https://api.runpod.io/v2/pods/owned123'))

    def test_404_allowed_only_on_exact_get(self):
        def missing(*args, **kwargs):
            raise urllib.error.HTTPError('https://rest.runpod.io/v1/pods/one', 404, '', {}, io.BytesIO())
        api = control.RunpodAPI('fixture', opener=missing)
        self.assertIsNone(api.get('one'))
        with self.assertRaises(control.ProviderError):
            api.list()
        with self.assertRaises(ValueError):
            api.delete('../unrelated')

    def test_real_http_and_fresh_watchdog_process_after_launcher_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); api = FakeProvider()
            with control.Journal(root) as journal:
                control.begin(api, journal, offer(int(time.time())), wall=time.time)
            # No launcher process or heartbeat remains. A new process reads the
            # durable journal and drives the real HTTP adapter against loopback.
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def send(self, data, status=200):
                    raw = json.dumps(data).encode()
                    self.send_response(status); self.end_headers(); self.wfile.write(raw)

                def do_GET(self):
                    if self.path.startswith('/v2/pods?'):
                        self.send({'pods': api.list(), 'pagination': {'hasNextPage': False, 'nextCursor': None}})
                    else:
                        pod = api.get(self.path.split('/')[-1])
                        self.send(pod, 200 if pod else 404)

                def do_POST(self):
                    api.stop(self.path.split('/')[-2]); self.send({})

                def do_DELETE(self):
                    api.delete(self.path.split('/')[-1]); self.send({})

            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                code = '''import sys, urllib.request
from tools.runpod_control import Journal, RunpodAPI, watchdog
def local(request, timeout):
    target = 'http://127.0.0.1:' + sys.argv[2] + request.full_url.split('api.runpod.io')[1]
    return urllib.request.urlopen(urllib.request.Request(target, data=request.data, method=request.method), timeout=timeout)
with Journal(sys.argv[1]) as journal:
    result = watchdog(RunpodAPI('local-fixture-only', opener=local), journal)
    assert result['phase'] == 'deleted'
'''
                result = subprocess.run([sys.executable, '-c', code, str(root), str(server.server_port)],
                                        cwd=Path(__file__).resolve().parents[1],
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('owned123', api.pods)
                self.assertIn('unrelated', api.pods)
                self.assertEqual(sum(a == 'create' for a, _ in api.calls), 1)
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
