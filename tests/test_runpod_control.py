import copy
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
        pod = {'id': 'owned123', 'name': payload['name'], 'imageName': control.BASE,
               'gpuCount': 1, 'volumeInGb': 0, 'networkVolumeId': None, 'costPerHr': 1.79}
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

    def test_request_freezes_utc_and_authorized_scope(self):
        request = control.make_request('a' * 32, T0)
        self.assertEqual(control.timestamp(request['stopAfter']), T0 + 2880)
        self.assertEqual(control.timestamp(request['terminateAfter']), T0 + 3000)
        self.assertEqual(request['ports'], '22/tcp')
        self.assertFalse(request['startJupyter'])
        self.assertNotIn('env', request)

    def test_offer_counts_storage_tax_and_refuses_bad_scope(self):
        self.assertLess(control.money(control.validate_offer(offer(), T0)['maximum_all_in']), control.CAP)
        for key, value in [('compute_per_hour', '2.50'), ('credit_balance', '0'),
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

    def test_missing_native_readback_blocks_before_consumption(self):
        self.api.contract = False
        with self.assertRaises(control.ProviderError):
            self.begin()
        self.assertFalse(self.journal.path.exists())
        self.assertFalse(self.api.calls)

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

    def test_second_controller_cannot_claim_journal(self):
        with self.assertRaises(BlockingIOError):
            with control.Journal(self.root):
                pass

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

    def test_expiry_mismatch_deletes_before_any_work(self):
        self.api.bad_expiry = True
        with self.assertRaises(RuntimeError):
            self.begin()
        value = self.journal.read()
        self.assertFalse(value['native_expiry_verified'])
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
        self.api.pods['owned123']['costPerHr'] = 5
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

    def test_real_client_serializes_native_datetimes_in_single_create(self):
        requests = []
        def opener(request, timeout):
            requests.append(request)
            self.assertEqual(timeout, 10)
            return self.response({'data': {'podFindAndDeployOnDemand': {'id': 'one', 'name': 'test'}}})
        api = control.RunpodAPI('fake-fixture-secret', opener=opener)
        payload = control.make_request('a' * 32, T0)
        api.create(payload)
        self.assertEqual(len(requests), 1)
        self.assertEqual(json.loads(requests[0].data)['variables']['input'], payload)
        self.assertNotIn('fake-fixture-secret', requests[0].full_url)

    def test_input_fields_without_pod_readback_fail(self):
        value = {'data': {'input': {'inputFields': [
            {'name': n, 'type': {'kind': 'SCALAR', 'name': 'DateTime'}}
            for n in ('stopAfter', 'terminateAfter')]}, 'pod': {'fields': [{'name': 'id'}]}}}
        api = control.RunpodAPI('fixture', opener=lambda *a, **kw: self.response(value))
        with self.assertRaises(control.ProviderError):
            api.check_native_contract()

    def test_provider_errors_redact_tokens_and_bodies(self):
        def opener(*args, **kwargs):
            raise urllib.error.HTTPError('https://example/?key=fake-secret', 403, 'fake-secret', {}, io.BytesIO(b'fake-secret'))
        api = control.RunpodAPI('fake-secret', opener=opener)
        with self.assertRaises(control.ProviderError) as context:
            api.list()
        self.assertNotIn('fake-secret', str(context.exception))

    def test_graphql_partial_data_is_not_success(self):
        api = control.RunpodAPI('fixture', opener=lambda *a, **kw: self.response({'data': {}, 'errors': [{'message': 'secret'}]}))
        with self.assertRaises(control.ProviderError):
            api.graphql('query { pod { id } }')

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
                    if self.path == '/v1/pods':
                        self.send(api.list())
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
    target = 'http://127.0.0.1:' + sys.argv[2] + request.full_url.split('rest.runpod.io')[1]
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
