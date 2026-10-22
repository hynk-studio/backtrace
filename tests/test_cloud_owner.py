"""Full lifecycle fault injection; no real provider or paid worker is used."""
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

from tools import cloud_owner as owner, cloud_worker as worker
from tools import cloud_state as state
from tools import runpod_control as control
from tools.runpod_job import private_json
from tests.test_cloud_state import MemoryStore, SOURCE
from tests.test_runpod_control import FakeProvider, T0, offer


class Provider(FakeProvider):
    def create(self, payload):
        result = super().create(payload)
        self.pods[result['id']]['ssh'] = {'direct': {'username': 'root', 'host': '127.0.0.1', 'port': 1234}}
        return result


class Process:
    def __init__(self, code): self.returncode = code
    def poll(self): return self.returncode


class CloudOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.store = MemoryStore(); self.api = Provider()
        self.store.write('watcher', {'run_id': '2', 'source_sha': SOURCE, 'at': T0})
        self.clock = T0

    def sleep(self, seconds): self.clock += seconds

    def run_lifecycle(self, code=0):
        return owner.execute(self.store, self.api, offer(), None, {}, self.root, '1', SOURCE,
            wall=lambda: self.clock, sleep=self.sleep, spawn=lambda *args: Process(code),
            stop=lambda process: None, emit=lambda row: None)

    def assert_no_owned_resource(self):
        self.assertEqual(set(self.api.pods), {'unrelated'})
        self.assertEqual(sum(call[0] == 'create' for call in self.api.calls), 1)

    def test_mutable_heartbeat_readback_lag_recovers_exact_value_without_rewriting(self):
        claim = {'attempt': 'a' * 32}
        prior_sha = owner.update_heartbeat(self.store, claim, 'setup', T0)
        prior = self.store.read('heartbeat')
        original = self.store.write
        def persist_then_miss(name, value, **kwargs):
            original(name, value, **kwargs)
            raise state.StateError('durable write not independently confirmed')
        reads = [0]
        def lagged(name):
            reads[0] += 1
            return prior if reads[0] < 3 else self.store.docs[name]
        with patch.object(self.store, 'write', side_effect=persist_then_miss) as write, \
                patch.object(self.store, 'read', side_effect=lagged), patch.object(owner.time, 'sleep') as sleep:
            sha = owner.update_heartbeat(self.store, claim, 'setup', T0 + 20,
                                         prior_sha, sleep=sleep)
        self.assertEqual(sha, self.store.read('heartbeat')[1])
        self.assertEqual((write.call_count, reads[0], sleep.call_count), (1, 3, 2))
        self.assertEqual(self.api.calls, [])

    def test_unconfirmed_heartbeat_exhausts_reads_without_rewriting(self):
        claim = {'attempt': 'a' * 32}
        prior_sha = owner.update_heartbeat(self.store, claim, 'setup', T0)
        prior = self.store.read('heartbeat')
        with patch.object(self.store, 'write', side_effect=state.StateError(
                'durable write not independently confirmed')) as write, \
                patch.object(self.store, 'read', return_value=prior) as read, \
                patch.object(owner.time, 'sleep') as sleep:
            with self.assertRaisesRegex(state.StateError, 'not independently confirmed'):
                owner.update_heartbeat(self.store, claim, 'setup', T0 + 20, prior_sha, sleep=sleep)
        self.assertEqual((write.call_count, read.call_count, sleep.call_count), (1, 3, 2))
        self.assertEqual(self.store.read('heartbeat'), prior)
        self.assertEqual(self.api.calls, [])

    def test_changed_attempt_or_newer_heartbeat_stops_readback_recovery(self):
        claim = {'attempt': 'a' * 32}
        for current in ({'attempt': 'b' * 32, 'at': T0, 'phase': 'setup'},
                        {'attempt': 'a' * 32, 'at': T0 + 21, 'phase': 'setup'},
                        {'attempt': 'a' * 32, 'at': T0 + 20, 'phase': 'failed'}):
            with self.subTest(current=current), patch.object(self.store, 'write',
                    side_effect=state.StateError('durable write not independently confirmed')) as write, \
                    patch.object(self.store, 'read', return_value=(current, 'f' * 40)) as read:
                with self.assertRaises(state.StateError):
                    owner.update_heartbeat(self.store, claim, 'setup', T0 + 20, 'e' * 40)
                self.assertEqual((write.call_count, read.call_count), (1, 1))

    def test_initial_heartbeat_keeps_strict_unconfirmed_write_failure(self):
        with patch.object(self.store, 'write', side_effect=state.StateError(
                'durable write not independently confirmed')) as write, \
                patch.object(self.store, 'read') as read:
            with self.assertRaises(state.StateError):
                owner.update_heartbeat(self.store, {'attempt': 'a' * 32}, 'setup', T0)
            self.assertEqual(write.call_count, 1)
            read.assert_not_called()
        self.assertEqual(self.api.calls, [])

    def test_other_heartbeat_write_failures_do_not_enter_readback_recovery(self):
        for reason in ('durable-state HTTP 503', 'durable-state HTTP 409',
                       'durable-state transport or JSON failure'):
            with self.subTest(reason=reason), patch.object(self.store, 'write',
                    side_effect=state.StateError(reason)) as write, patch.object(self.store, 'read') as read:
                with self.assertRaises(state.StateError):
                    owner.update_heartbeat(self.store, {'attempt': 'a' * 32}, 'setup', T0, 'e' * 40)
                self.assertEqual(write.call_count, 1)
                read.assert_not_called()

    def test_one_create_then_two_independent_absence_reads(self):
        result = self.run_lifecycle()
        self.assertEqual(result['status'], 'COMPLETE')
        self.assertEqual(result['cleanup']['absence_reads'], 2)
        self.assert_no_owned_resource()
        again = self.run_lifecycle()
        self.assertEqual(again['allocation_requests'], 0)
        self.assert_no_owned_resource()

    def test_create_timeout_after_allocation_is_deleted_without_retry(self):
        self.api.drop_ack = True
        result = self.run_lifecycle()
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(result['cleanup']['phase'], 'deleted')
        self.assertEqual(result['cleanup']['pod_id'], 'owned123')
        self.assert_no_owned_resource()

    def test_worker_failure_and_lost_github_writes_do_not_suppress_delete(self):
        original = self.store.write
        def write(name, value, **kwargs):
            if name == 'heartbeat' and value['phase'] == 'failed':
                raise state.StateError('fixture lost GitHub connection')
            return original(name, value, **kwargs)
        with patch.object(self.store, 'write', side_effect=write):
            result = self.run_lifecycle(code=1)
        self.assertEqual(result['cleanup']['phase'], 'deleted')
        self.assert_no_owned_resource()

    def test_lost_claim_acknowledgement_never_reaches_provider_create(self):
        self.store.fail_write = 'claim'
        result = self.run_lifecycle()
        self.assertEqual(result['allocation_requests'], 0)
        self.assertEqual(self.api.calls, [])
        self.assertIsNotNone(self.store.read('claim'))

    def test_worker_rejects_inherited_account_credentials_before_input_read(self):
        with patch.object(worker, 'check_owner_host'), patch.dict(worker.os.environ, {'RUNPOD_API_KEY': 'fixture'}):
            with self.assertRaisesRegex(ValueError, 'service credentials'):
                worker.run(self.root / 'does-not-exist')

    def test_stalled_worker_heartbeat_stops_process_and_cleans_owned_pod(self):
        process = Process(None); stopped = []
        def spawn(directory, configuration, claim, pod_id, endpoint):
            private_json(Path(directory) / 'job-status.json', {'attempt': claim['attempt'],
                'state': 'running', 'phase': 'setup', 'at': control.utc(T0)})
            return process
        def stop(value):
            stopped.append(value); value.returncode = 9
        result = owner.execute(self.store, self.api, offer(), None, {}, self.root, '1', SOURCE,
            wall=lambda: self.clock, sleep=self.sleep, spawn=spawn, stop=stop, emit=lambda row: None)
        self.assertEqual(stopped, [process])
        self.assertEqual(result['cleanup']['phase'], 'deleted')
        self.assertLess(self.clock - T0, 90)
        self.assertEqual(result['failure']['reason'], 'worker heartbeat is stale or finished')
        self.assert_no_owned_resource()

    def test_heartbeat_observation_samples_time_after_the_status_read(self):
        private_json(self.root / 'job-status.json', {})
        claim = {'attempt': 'a' * 32}
        def concurrent_read(path):
            self.clock = T0 + 1.001
            return json.dumps(dict(claim, state='running', phase='setup', at=control.utc(T0 + 1)))
        with patch.object(owner, 'read_private', side_effect=concurrent_read):
            self.assertEqual(owner.local_phase(self.root, claim, T0 + 0.999, first_at=T0,
                                               wall=lambda: self.clock), 'setup')
            for observed_at in (T0 + 0.999, T0 + 17):
                with self.assertRaises(state.StateError):
                    owner.local_phase(self.root, claim, T0, first_at=T0, wall=lambda: observed_at)

    def test_unknown_state_error_text_is_not_published(self):
        with patch.object(self.api, 'create', side_effect=state.StateError('SECRET-ERROR-CANARY')):
            result = self.run_lifecycle()
        self.assertNotIn('SECRET-ERROR-CANARY', json.dumps(result))
        self.assertEqual(result['allocation_requests'], 1)
        diagnostic = json.loads((self.root / 'controller-diagnostic.json').read_text())
        self.assertNotIn('SECRET-ERROR-CANARY', json.dumps(diagnostic))
        self.assertEqual(result['failure']['stage'], 'provider_create')
        self.assertTrue(diagnostic['frames'])

    def test_encrypted_results_keep_status_but_exclude_control_credentials(self):
        for name in ('owner-result.json', 'job-status.json', 'setup-status.json',
                     'controller-diagnostic.json', 'bootstrap-readiness.json', 'worker-plan.json'):
            private_json(self.root / name, {'fixture': name})
        with patch.object(owner.cloud_seal, 'seal', side_effect=lambda files, output: set(files)):
            retained = owner.seal_results(self.root, self.root / 'result.age')
        self.assertEqual(retained, {'owner-result.json', 'job-status.json',
                                   'setup-status.json', 'controller-diagnostic.json', 'bootstrap-readiness.json'})

    def test_finished_heartbeat_can_precede_the_child_process_exit(self):
        private_json(self.root / 'job-status.json', {'attempt': 'a' * 32, 'state': 'finished',
                                                   'phase': 'retrieval', 'at': control.utc(T0)})
        self.assertEqual(owner.local_phase(self.root, {'attempt': 'a' * 32}, T0 + 1, first_at=T0), 'retrieval')
        with self.assertRaises(state.StateError):
            owner.local_phase(self.root, {'attempt': 'a' * 32}, T0 + 16, first_at=T0)

    def test_scoped_source_maps_travel_in_stdin_not_ssh_command(self):
        argv, data = worker.direct_envelope({'requested_at': 1, 'streams': {'fixture': 'SIGNED-URL-CANARY'}})
        self.assertLess(len(' '.join(argv)), 9000)
        self.assertNotIn('SIGNED-URL-CANARY', ' '.join(argv))
        self.assertIn(b'SIGNED-URL-CANARY', data)
        self.assertNotIn('RUNPOD_API_KEY', json.loads(data)['source'])

    def test_stdin_envelope_executes_only_the_bound_code_bytes(self):
        source = 'import json,sys;print(json.load(sys.stdin)["fixture"])'
        with patch.object(worker, 'direct_program', return_value=source):
            argv, data = worker.direct_envelope({'fixture': 'private-roundtrip'})
        result = subprocess.run(argv, input=data, capture_output=True, check=True, timeout=5)
        self.assertEqual(result.stdout, b'private-roundtrip\n')
        corrupt = json.loads(data); corrupt['source'] += '\nprint("changed")'
        result = subprocess.run(argv, input=json.dumps(corrupt).encode(), capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(result.stdout)

    def test_full_activation_source_fits_actual_ssh_command_limit(self):
        source = (worker.frozen.ROOT / 'tools/pod_bootstrap.py').read_text()
        self.assertGreater(len(source), 9000)
        argv, data = worker.code_envelope(source + '\nprint("qualified-source-loaded")')
        import shlex
        self.assertLess(len(shlex.join(argv)), 9000)
        result = subprocess.run(argv, input=data, capture_output=True, check=True, timeout=5)
        self.assertEqual(result.stdout, b'qualified-source-loaded\n')


if __name__ == '__main__': unittest.main()
