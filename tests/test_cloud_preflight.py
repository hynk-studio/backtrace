"""Failure boundaries for staged installation before large model transfer."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import cloud_worker, pod_bootstrap, pod_preflight


class EarlyPreparationTests(unittest.TestCase):
    def streams(self):
        return {kind: {'manifest': json.dumps({'files': [{'bytes': 10}]}),
                       'sha256': 'a' * 64, 'sources': [{'url': 'PRIVATE-URL-CANARY'}]}
                for kind in ('wheels', 'task', 'model')}

    def test_environment_installation_and_hardware_failures_never_transfer_model(self):
        for fail_at in ('base_environment', 'runtime_inputs', 'runtime_installation', 'runtime_hardware'):
            with self.subTest(fail_at=fail_at):
                events = []; transferred = []
                def remote(argv, *, input):
                    envelope = json.loads(input)
                    self.assertNotIn('PRIVATE-URL-CANARY', ' '.join(argv))
                    value = json.loads(envelope['input']) if envelope['input'] else {}
                    transferred.extend(value.get('streams', {}))
                    if events[-1]['stage'] == fail_at:
                        raise subprocess.CalledProcessError(1, ['fixture'])
                with self.assertRaises(subprocess.CalledProcessError):
                    cloud_worker.setup_remote(remote, self.streams(), b'driver', 1, emit=events.append)
                self.assertNotIn('model', transferred)
                self.assertNotIn('activation', [r['stage'] for r in events])

    def test_success_transfers_model_only_after_installed_runtime_check(self):
        events = []; transferred = []
        def remote(argv, *, input):
            envelope = json.loads(input)
            if envelope['input']:
                kinds = list(json.loads(envelope['input'])['streams'])
                if kinds == ['model']:
                    self.assertIn({'stage': 'runtime_hardware', 'status': 'PASS'}, events)
                transferred.extend(kinds)
        cloud_worker.setup_remote(remote, self.streams(), b'driver', 1, emit=events.append)
        self.assertEqual(transferred, ['wheels', 'task', 'model'])
        self.assertEqual(events[-1], {'stage': 'activation', 'status': 'PASS'})

    def test_final_activation_rejects_prepared_runtime_from_other_inputs_or_request(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            hashes = {'driver': 'a' * 64, 'wheels': 'b' * 64}
            receipt = root / 'runtime-ready.json'
            receipt.write_text(json.dumps({'manifests': hashes, 'requested_at': 123,
                                           'inventory_sha256': 'c' * 64})); receipt.chmod(0o600)
            with patch.object(pod_bootstrap, 'STAGING', root), patch.object(pod_bootstrap, 'digest', return_value='c' * 64):
                pod_bootstrap.require_prepared_runtime(hashes, 123)
                with self.assertRaises(ValueError): pod_bootstrap.require_prepared_runtime(hashes, 124)
                with self.assertRaises(ValueError):
                    pod_bootstrap.require_prepared_runtime(dict(hashes, wheels='d' * 64), 123)

    def test_cpu_runtime_mode_does_not_initialize_or_query_cuda_devices(self):
        result = subprocess.CompletedProcess([], 0, stdout=b'{"status":"PASS"}', stderr=b'')
        with patch.object(pod_preflight.subprocess, 'run', return_value=result) as run:
            self.assertEqual(pod_preflight.runtime(require_gpu=False), {'status': 'PASS'})
        command = run.call_args.args[0]
        self.assertNotIn('import torch', command[-1])
        self.assertNotIn('check_gpu(torch.cuda)', command[-1])


if __name__ == '__main__': unittest.main()
