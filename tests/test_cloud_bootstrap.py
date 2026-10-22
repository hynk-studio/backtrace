"""Exercise delayed provider states, exact owner loop, diagnostics and cleanup."""
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest.mock import patch

from tools import cloud_bootstrap as bootstrap, cloud_owner as owner
from tools import runpod_control as control
from tests.test_cloud_state import MemoryStore, SOURCE
from tests.test_cloud_owner import Provider, Process
from tests.test_runpod_control import offer, T0


CANARY = 'SECRET-BOOTSTRAP-CANARY'


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = MemoryStore(); self.api = Provider(); self.clock = T0
        self.store.write('watcher', {'run_id': '2', 'source_sha': SOURCE, 'at': T0})
        self.rows = []; self.spawned = []

    def run_owner(self):
        def spawn(*args):
            self.spawned.append(args[-1]); return Process(0)
        return owner.execute(self.store, self.api, offer(), None, {}, self.root, '1', SOURCE,
                             wall=lambda: self.clock, sleep=self.sleep, spawn=spawn,
                             stop=lambda p: None, emit=self.rows.append)

    def sleep(self, seconds): self.clock += seconds

    def set_states(self, states):
        original = self.api.get
        values = iter(states)
        current = [states[-1]]
        def get(pod_id):
            pod = original(pod_id)
            if pod_id == 'owned123' and pod is not None:
                current[0] = next(values, current[0])
                status, direct = current[0]
                pod.update(status=status, env={'secret': CANARY}, args=CANARY)
                pod['ssh'] = {'direct': pod['ssh']['direct'] if direct else None}
            return pod
        self.api.get = get

    def assert_clean(self):
        self.assertEqual(set(self.api.pods), {'unrelated'})
        self.assertEqual(sum(x[0] == 'create' for x in self.api.calls), 1)

    def test_delayed_provider_and_port_observed_before_single_worker_start(self):
        self.set_states([('PROVISIONING', False), ('STARTING', False),
                         ('RUNNING', False), ('RUNNING', True)])
        result = self.run_owner()
        reasons = [x['readiness'] for x in result['bootstrap']['history']]
        self.assertEqual(reasons, ['WAIT_PROVIDER_RUNNING', 'WAIT_PROVIDER_RUNNING',
                                  'WAIT_DIRECT_ENDPOINT', 'READY'])
        self.assertEqual(len(self.spawned), 1)
        self.assertEqual(result['status'], 'COMPLETE')
        self.assertNotIn(CANARY, json.dumps(result) + json.dumps(self.rows))
        self.assertNotIn('host', json.dumps(result['bootstrap']))
        self.assert_clean()

    def test_full_deadline_wait_retains_last_observation_and_original_failure(self):
        self.set_states([('STARTING', False)])
        self.api.bootstrap_logs = lambda pod_id: bootstrap.log_summary(
            ('data: ' + json.dumps({'source': 'system', 'line': 'failed to pull image ' + CANARY}) + '\n').encode())
        result = self.run_owner()
        self.assertEqual(result['failure']['stage'], 'bootstrap_deadline')
        self.assertEqual(result['failure']['error_type'], 'TimeoutError')
        self.assertEqual(result['bootstrap']['polls'], 60)
        self.assertEqual(result['bootstrap']['last']['provider_status'], 'STARTING')
        self.assertEqual(result['bootstrap']['log_sample']['signals']['image_pull_error'], 1)
        evidence = (self.root / 'bootstrap-readiness.json').read_text()
        self.assertNotIn(CANARY, evidence + json.dumps(result) + json.dumps(self.rows))
        self.assertLess(self.clock - T0, 1230)
        self.assertFalse(self.spawned)
        self.assert_clean()

    def test_running_without_endpoint_is_distinct_from_provider_starting(self):
        self.set_states([('RUNNING', False)])
        result = self.run_owner()
        self.assertEqual(result['bootstrap']['last']['readiness'], 'WAIT_DIRECT_ENDPOINT')
        self.assertFalse(self.spawned)
        self.assert_clean()

    def test_terminal_provider_and_bad_endpoint_fail_before_worker(self):
        for status in ('ERROR', 'EXITED', 'TERMINATED'):
            with self.subTest(status=status):
                self.setUp()
                self.set_states([(status, False)])
                result = self.run_owner()
                self.assertEqual(result['bootstrap']['last']['readiness'], 'PROVIDER_TERMINAL')
                self.assertEqual(result['failure']['reason'], 'bootstrap provider reached a terminal state')
                self.assertFalse(self.spawned)
                self.assertLess(self.clock - T0, 30)
                self.assert_clean()
        self.setUp()
        original = self.api.create
        def create(payload):
            result = original(payload)
            self.api.pods[result['id']]['ssh']['direct']['port'] = True
            return result
        self.api.create = create
        result = self.run_owner()
        self.assertEqual(result['failure']['reason'], 'invalid exact bootstrap endpoint')
        self.assertFalse(self.spawned)
        self.assert_clean()

    def test_watcher_exit_during_bootstrap_cleans_without_waiting_for_readiness(self):
        self.set_states([('STARTING', False)])
        def sleep(seconds):
            self.clock += seconds
            self.store.runs['2'].update(status='completed', conclusion='failure')
        self.sleep = sleep
        result = self.run_owner()
        self.assertEqual(result['failure']['stage'], 'bootstrap_watcher_status')
        self.assertLess(self.clock - T0, 60)
        self.assertFalse(self.spawned)
        self.assert_clean()

    def test_slow_provider_response_cannot_start_worker_after_deadline(self):
        original = self.api.get
        def get(pod_id):
            value = original(pod_id)
            self.clock = T0 + 1201
            return value
        self.api.get = get
        result = self.run_owner()
        self.assertEqual(result['failure']['stage'], 'bootstrap_deadline')
        self.assertFalse(self.spawned)
        self.assert_clean()

    def test_owner_cancellation_and_mismatched_watcher_stop_bootstrap(self):
        for actor, changes, stage in (
            ('1', {'status': 'completed', 'conclusion': 'cancelled'}, 'bootstrap_owner_status'),
            ('2', {'head_sha': 'b' * 40}, 'bootstrap_watcher_status')):
            with self.subTest(actor=actor):
                self.setUp()
                self.set_states([('STARTING', False)])
                def sleep(seconds):
                    self.clock += seconds; self.store.runs[actor].update(changes)
                self.sleep = sleep
                result = self.run_owner()
                self.assertEqual(result['failure']['stage'], stage)
                self.assertFalse(self.spawned)
                self.assert_clean()

    def test_slow_heartbeat_cannot_start_worker_past_deadline(self):
        original = owner.update_heartbeat
        def update(*args, **kwargs):
            value = original(*args, **kwargs)
            if len(args) > 4 and args[4] is not None: self.clock = T0 + 1201
            return value
        with patch.object(owner, 'update_heartbeat', side_effect=update):
            result = self.run_owner()
        self.assertEqual(result['failure']['stage'], 'bootstrap_deadline')
        self.assertFalse(self.spawned)
        self.assert_clean()

    def test_log_error_does_not_replace_primary_failure_or_prevent_cleanup(self):
        self.set_states([('STARTING', False)])
        def logs(pod_id): raise control.ProviderError(CANARY, http_status=403)
        self.api.bootstrap_logs = logs
        result = self.run_owner()
        self.assertEqual(result['failure']['error_type'], 'TimeoutError')
        self.assertEqual(result['bootstrap']['log_sample'], {'status': 'UNAVAILABLE', 'http_status': 403})
        self.assertNotIn(CANARY, json.dumps(result))
        self.assert_clean()

    def test_malformed_fields_and_log_canaries_only_yield_allowlisted_projections(self):
        for pod in (None, [], {'status': [CANARY]}, {'status': CANARY},
                    {'status': 'RUNNING', 'ssh': None},
                    {'status': 'RUNNING', 'ssh': {'direct': {'host': CANARY, 'port': True}}}):
            self.assertNotIn(CANARY, json.dumps(bootstrap.observe(pod, 4)))
        raw = b'data: []\ndata: invalid\ndata: {"source":"SECRET", "line":"SECRET"}\n'
        result = bootstrap.log_summary(raw)
        self.assertEqual(result['malformed_events'], 2)
        self.assertEqual(result['signals'], {'unclassified': 1})
        self.assertNotIn('SECRET', json.dumps(result))


class LogAPITests(unittest.TestCase):
    def response(self, payload):
        value = io.BytesIO(payload); value.status = 200
        value.headers = {'Content-Type': 'text/event-stream'}
        return value

    def test_sse_sample_is_read_only_size_bounded_and_discards_raw_text(self):
        requests = []
        def opener(request, timeout):
            requests.append((request, timeout))
            return self.response(('data: '+json.dumps({'source':'container','line':'Traceback (most recent call last): '+CANARY})+'\n').encode() + b'x' * 40000)
        result = control.RunpodAPI('FIXTURE-KEY', opener=opener).bootstrap_logs('owned123')
        self.assertEqual(len(requests), 1)
        request, timeout = requests[0]
        self.assertEqual(request.method, 'GET')
        self.assertTrue(request.full_url.endswith('/pods/owned123/logs?tail=50'))
        self.assertEqual(timeout, 2)
        self.assertEqual(result['bytes'], bootstrap.MAX_LOG_BYTES)
        self.assertEqual(result['stopped'], 'BYTE_LIMIT')
        self.assertEqual(result['signals']['python_traceback'], 1)
        self.assertNotIn(CANARY, json.dumps(result))

    def test_sse_read_timeout_retains_completed_events(self):
        response = self.response(b'')
        response.read1 = unittest.mock.Mock(side_effect=[
            b'data: {"source":"system","line":"pull complete"}\n', TimeoutError()])
        result = control.RunpodAPI('FIXTURE-KEY', opener=lambda *a, **k: response).bootstrap_logs('owned123')
        self.assertEqual(result['stopped'], 'READ_TIMEOUT')
        self.assertEqual(result['events'], 1)

    def test_log_http_failure_excludes_body_and_error_text(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 403, CANARY, {}, io.BytesIO(CANARY.encode()))
        with self.assertRaises(control.ProviderError) as error:
            control.RunpodAPI('FIXTURE-KEY', opener=opener).bootstrap_logs('owned123')
        self.assertEqual(error.exception.http_status, 403)
        self.assertNotIn(CANARY, str(error.exception))

    def test_stalled_log_fetch_releases_the_cleanup_caller(self):
        release = threading.Event(); completed = threading.Event()
        class API:
            def bootstrap_logs(self, pod_id):
                release.wait(3); completed.set(); return {'status': 'LATE'}
        started = time.monotonic()
        try:
            result = bootstrap.sample_logs(API(), 'owned123', timeout=.03)
            self.assertEqual(result['status'], 'TIME_LIMIT')
            self.assertLess(time.monotonic() - started, 1)
            self.assertFalse(completed.is_set())
        finally:
            release.set(); self.assertTrue(completed.wait(1))


if __name__ == '__main__': unittest.main()
