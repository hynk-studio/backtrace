import hashlib
import io
import json
import os
import shutil
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import pod_bootstrap as pod
from tools import runpod_job as job
from tools import ssh_bootstrap as ssh
from tools.a100_task import consume_permit
from tools.private_delivery import emit, receive


class VenvSeedTests(unittest.TestCase):
    def test_real_venv_is_seeded_offline_from_the_frozen_wheel(self):
        import ensurepip
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheels = root / 'wheels'; wheels.mkdir()
            shutil.copyfile(Path(ensurepip.__file__).parent / '_bundled' / pod.PIP_WHEEL,
                            wheels / pod.PIP_WHEEL)
            stdlib = root / 'stdlib'; stdlib.mkdir()
            seed = root / 'seed'
            receipt = pod.ensure_venv_seed(wheels, stdlib=stdlib, seed_root=seed)
            self.assertEqual(pod.ensure_venv_seed(wheels, stdlib=stdlib, seed_root=seed), receipt)
            venv = root / 'venv'
            subprocess.run([sys.executable, '-I', '-m', 'venv', '--without-pip', str(venv)],
                           check=True, capture_output=True, timeout=30)
            python = venv / 'bin/python'
            subprocess.run([str(python), '-I', str(stdlib / 'ensurepip.py'),
                            '--upgrade', '--default-pip'], check=True, capture_output=True, timeout=60)
            output = subprocess.check_output([str(python), '-I', '-c',
                                             'import pip;print(pip.__version__)'], text=True, timeout=10)
            self.assertEqual(output.strip(), '25.0.1')
            (seed / 'bootstrap.lock').chmod(0o600)
            (seed / 'bootstrap.lock').write_text('changed')
            refused = subprocess.run([str(python), '-I', str(stdlib / 'ensurepip.py')],
                                     capture_output=True, timeout=10)
            self.assertNotEqual(refused.returncode, 0)
            for p in root.rglob('*'):
                if p.is_dir() and not p.is_symlink(): p.chmod(0o700)

    def test_changed_wheel_and_existing_ensurepip_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / pod.PIP_WHEEL).write_bytes(b'wrong wheel')
            with self.assertRaises(ValueError):
                pod.ensure_venv_seed(root, stdlib=root, seed_root=root / 'seed')
            (root / 'ensurepip').mkdir()
            with self.assertRaises(ValueError):
                pod.ensure_venv_seed(root, stdlib=root, seed_root=root / 'seed')
            self.assertFalse((root / 'ensurepip.py').exists())


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stage = self.root / 'staging'; self.stage.mkdir(mode=0o700)
        self.input = self.root / 'input'
        self.work = self.root / 'working'
        self.manifests = {}
        for kind in ('driver', 'wheels', 'task', 'model'):
            source = self.root / ('source-' + kind); source.mkdir(mode=0o700)
            content = (kind + '-fixture').encode(); (source / 'payload').write_bytes(content)
            data = json.dumps({'schema_version': 1, 'phase': 'task', 'files': [
                {'path': 'payload', 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}]}).encode()
            stream = io.BytesIO(); emit(source, data, stream); stream.seek(0)
            sha = hashlib.sha256(data).hexdigest()
            receive(self.stage / kind, sha, stream)
            self.manifests[kind] = sha

    def activate(self):
        with patch.multiple(pod, STAGING=self.stage, INPUT=self.input, WORKING=self.work):
            return pod.activate(self.manifests, time.time(), runtime=False)

    def test_corruption_aborts_before_any_logical_input_exists(self):
        (self.stage / 'model/payload').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.activate()
        self.assertFalse(self.input.exists())

    def test_generation_inputs_activate_once_without_transport_metadata(self):
        result = self.activate()
        self.assertEqual(result['activation'], 'PASS')
        for destination in (self.input / 'r0-inputs', self.input / pod.MODEL):
            self.assertEqual({p.name for p in destination.iterdir()}, {'payload'})
            self.assertFalse(destination.stat().st_mode & 0o222)
            self.assertFalse((destination / 'payload').stat().st_mode & 0o222)
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.activate()

    def test_private_ssh_umask_does_not_hide_logical_inputs_from_workload_uid(self):
        previous = os.umask(0o077)
        try:
            self.activate()
        finally:
            os.umask(previous)
        for destination in (self.input / 'r0-inputs', self.input / pod.MODEL):
            for parent in (destination, *destination.parents):
                if not parent.is_relative_to(self.input.parent):
                    break
                self.assertEqual(parent.stat().st_mode & 0o005, 0o005)
                self.assertFalse(parent.stat().st_mode & 0o022)
        self.assertEqual(self.stage.stat().st_mode & 0o077, 0)

    def test_cloud_activation_requires_explicit_policy_and_keeps_absolute_deadline(self):
        with (patch.multiple(pod, STAGING=self.stage, INPUT=self.input, WORKING=self.work),
              patch.object(pod.time, 'time', return_value=2300)):
            with self.assertRaises(ValueError):
                pod.activate(self.manifests, 1000, runtime=False)
            self.assertFalse(self.input.exists())
            result = pod.activate(self.manifests, 1000, runtime=False, policy='prepaid10-actions-v1')
            self.assertEqual(result['activation'], 'PASS')

    def test_expired_cloud_setup_never_activates(self):
        with (patch.multiple(pod, STAGING=self.stage, INPUT=self.input, WORKING=self.work),
              patch.object(pod.time, 'time', return_value=6400)):
            with self.assertRaises(ValueError):
                pod.activate(self.manifests, 1000, runtime=False, policy='prepaid10-actions-v1')
            self.assertFalse(self.input.exists())

    def test_unknown_input_and_symlink_are_not_activated(self):
        (self.stage / 'task/answer').write_text('evaluation-only fixture')
        with self.assertRaises(ValueError):
            self.activate()
        (self.stage / 'task/answer').unlink()
        (self.stage / 'task/payload').unlink()
        (self.stage / 'task/payload').symlink_to(self.root / 'source-task/payload')
        with self.assertRaises(ValueError):
            self.activate()


class PermitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.driver = self.root / 'driver.py'; self.driver.write_text('fixture, never executed')
        self.path = self.root / 'launch-permit.json'
        self.value = {'policy': 'prepaid10-external-v2',
                      'run': 'R0-clean-v2-one-public-task/A10080-TP1',
                      'attempt': 'a' * 32, 'pod_id': 'owned123', 'requested_at': 1000,
                      'driver_sha256': hashlib.sha256(self.driver.read_bytes()).hexdigest()}
        self.write()
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {'BACKTRACE_ALLOCATION_REQUESTED_AT': '1000'}).start()

    def write(self):
        self.path.write_text(json.dumps(self.value)); self.path.chmod(0o600)

    def test_permit_is_consumed_before_a_second_start_can_enter(self):
        consume_permit(self.path, self.driver, now=1001)
        with self.assertRaises(FileExistsError):
            consume_permit(self.path, self.driver, now=1002)

    def test_cloud_policy_cannot_extend_a_legacy_permit(self):
        with self.assertRaises(ValueError):
            consume_permit(self.path, self.driver, now=2300, policy='prepaid10-actions-v1', setup_seconds=5400)
        self.value['policy'] = 'prepaid10-actions-v1'; self.write()
        with self.assertRaises(ValueError):
            consume_permit(self.path, self.driver, now=1001)
        with self.assertRaises(ValueError):
            consume_permit(self.path, self.driver, now=2300, setup_seconds=5400)
        self.assertFalse(self.path.with_suffix('.consumed').exists())
        consume_permit(self.path, self.driver, now=2300, policy='prepaid10-actions-v1', setup_seconds=5400)
        with self.assertRaises(FileExistsError):
            consume_permit(self.path, self.driver, now=2301, policy='prepaid10-actions-v1', setup_seconds=5400)

    def test_cloud_permit_expires_from_allocation(self):
        self.value['policy'] = 'prepaid10-actions-v1'; self.write()
        for now in (999, 6400, float('nan')):
            with self.subTest(now=now), self.assertRaises(ValueError):
                consume_permit(self.path, self.driver, now=now, policy='prepaid10-actions-v1', setup_seconds=5400)
        self.assertFalse(self.path.with_suffix('.consumed').exists())

    def test_deadline_drift_and_changed_driver_consume_no_permit(self):
        for now in (999, 2200, float('nan')):
            with self.subTest(now=now), self.assertRaises(ValueError):
                consume_permit(self.path, self.driver, now=now)
        self.driver.write_text('changed')
        with self.assertRaises(ValueError):
            consume_permit(self.path, self.driver, now=1001)
        self.assertFalse(self.path.with_suffix('.consumed').exists())

    def test_world_readable_or_linked_permit_is_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaises(ValueError):
            consume_permit(self.path, self.driver, now=1001)
        self.path.unlink(); self.path.symlink_to(self.driver)
        with self.assertRaises(ValueError):
            consume_permit(self.path, self.driver, now=1001)


class OwnerBoundaryTests(unittest.TestCase):
    def test_oversized_transport_cannot_prepare_or_run_or_load_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {'driver': str(root), 'wheels': str(root), 'task': str(root), 'model': str(root),
                      'ssh_directory': str(root), 'controller_host': 'existing-linux-host',
                      'state_directory': str(root / 'state'), 'files_persist': True}
            job.private_json(root / 'initializer.json', {'env': {'transport': 'x' * 863192}})
            job.private_json(root / 'plan.json', {'policy': job.control.POLICY, 'configuration': config})
            with patch.object(job, 'check_owner_host'), \
                    patch.object(ssh, 'validate_initializer'), \
                    patch.object(job, 'verify') as verify, \
                    patch.object(job.control, 'RunpodAPI') as api:
                with self.assertRaisesRegex(ValueError, 'exceeds 102400 bytes'):
                    job.prepare(config, root / 'new-plan')
                with self.assertRaisesRegex(ValueError, 'exceeds 102400 bytes'):
                    job.run(root, root / 'missing-offer', root / 'missing-api-key', root / 'state')
                verify.assert_not_called()
                api.assert_not_called()
            self.assertFalse((root / 'new-plan').exists())
            self.assertFalse((root / 'state').exists())

    def test_bootstrap_program_compiles_and_modified_initializer_is_refused(self):
        compile(ssh.START, '<literal-initializer>', 'exec')
        with self.assertRaises(ValueError):
            ssh.validate_initializer({'entrypoint': ['/bin/sh'], 'cmd': ['curl unsafe'], 'env': {}})

    def test_preparation_cannot_invoke_a_provider_api(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {'driver': str(root), 'wheels': str(root), 'task': str(root), 'model': str(root),
                      'ssh_directory': str(root), 'controller_host': 'kaggle-free-cpu',
                      'state_directory': '/kaggle/working/backtrace-a100-owner-state', 'files_persist': True}
            with patch.object(job, 'check_owner_host'), patch.object(job.control, 'RunpodAPI') as api:
                with self.assertRaises((ValueError, FileNotFoundError)):
                    job.prepare(config, root / 'plan')
                api.assert_not_called()

    def test_changed_attempt_directory_blocks_before_provider_access(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job.private_json(root / 'plan.json', {'policy': job.control.POLICY,
                'configuration': {'files_persist': True, 'state_directory': str(root / 'original')}})
            with patch.object(job, 'check_owner_host'), patch.object(job.control, 'RunpodAPI') as api:
                with self.assertRaisesRegex(ValueError, 'state directory changed'):
                    job.run(root, root / 'offer', root / 'key', root / 'replacement')
                api.assert_not_called()

    def test_invalid_run_host_blocks_before_loading_credentials_or_creating(self):
        with patch.object(job, 'check_owner_host', side_effect=ValueError('unqualified host')):
            with patch.object(job.control, 'RunpodAPI') as api, self.assertRaises(ValueError):
                job.run('/missing', '/missing', '/missing', '/missing')
            api.assert_not_called()

    def test_atomic_heartbeat_is_private_and_attempt_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            job.heartbeat(directory, 'a' * 32, 'running', 'setup')
            p = Path(directory) / 'job-status.json'
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
            self.assertEqual(json.loads(p.read_text())['attempt'], 'a' * 32)
            self.assertEqual(set(Path(directory).iterdir()), {p})


if __name__ == '__main__':
    unittest.main()
