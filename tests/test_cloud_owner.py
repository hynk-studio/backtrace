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
        self.assert_no_owned_resource()

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
