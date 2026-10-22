"""Regressions for the boundary between short diagnostic and full setup."""
import json
import shlex
import subprocess
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import cloud_worker as worker, ssh_bootstrap as ssh


class InitialSSHTests(unittest.TestCase):
    def test_hung_first_command_uses_the_short_budget(self):
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            ssh.wait_for_command([sys.executable, '-I', '-c', 'import time;time.sleep(30)'], ['true'], .1)
        self.assertLess(time.monotonic() - started, 3)

    def test_transient_ssh_failure_can_recover_inside_one_shared_deadline(self):
        clock = [0]
        calls = []
        def run(*args, **kwargs):
            calls.append(kwargs['timeout']); clock[0] += 20
            return SimpleNamespace(returncode=255 if len(calls) == 1 else 0, stdout=b'ok', stderr=b'')
        with patch.object(ssh.subprocess, 'run', side_effect=run):
            result = ssh.wait_for_command(['ssh'], ['true'], 45,
                clock=lambda: clock[0], sleep=lambda n: clock.__setitem__(0, clock[0] + n))
        self.assertEqual(result.stdout, b'ok')
        self.assertEqual(calls, [25, 24])

    def test_late_exit_zero_does_not_extend_the_deadline(self):
        clock = iter([0, 0, 61])
        with patch.object(ssh.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=b'', stderr=b'')):
            with self.assertRaises(TimeoutError):
                ssh.wait_for_command(['ssh'], ['true'], 60, clock=lambda: next(clock))

    def test_identity_failures_and_remote_exit_codes_are_never_retried(self):
        for code, stderr in ((255, b'Permission denied'), (255, b'REMOTE HOST IDENTIFICATION HAS CHANGED'),
                             (1, b'remote error')):
            with self.subTest(code=code, stderr=stderr), patch.object(ssh.subprocess, 'run',
                    return_value=SimpleNamespace(returncode=code, stdout=b'', stderr=stderr)) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    ssh.wait_for_command(['ssh'], ['true'], 60)
                run.assert_called_once()


class SetupBoundaryTests(unittest.TestCase):
    def test_large_remote_source_uses_verified_stdin_and_rejects_tampering(self):
        source = '# large private payload\n' * 3000 + 'print(input())\n'
        argv, data = worker.code_envelope(source, 'fixture-input')
        self.assertGreater(len(data), 9000)
        self.assertLess(len(shlex.join(argv).encode()), 9000)
        result = subprocess.run(argv, input=data, capture_output=True, check=True, timeout=10)
        self.assertEqual(result.stdout, b'fixture-input\n')
        changed = json.loads(data); changed['source'] += "print('unexpected')\n"
        result = subprocess.run(argv, input=json.dumps(changed).encode(), capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')

    def test_setup_failure_retains_the_specific_stage_and_stops_before_later_inputs(self):
        rows = [{'path': 'fixture', 'bytes': 1, 'sha256': 'a' * 64}]
        streams = {k: {'manifest': json.dumps({'files': rows}), 'sha256': 'b' * 64, 'sources': {}}
                   for k in ('wheels', 'task', 'model')}
        events = []; calls = []
        def remote(argv, **kwargs):
            calls.append(argv)
            if len(calls) == 3:
                raise subprocess.CalledProcessError(17, 'PRIVATE-CANARY', stderr=b'PRIVATE-CANARY')
        with self.assertRaises(subprocess.CalledProcessError):
            worker.setup_remote(remote, streams, b'manifest', 1, emit=events.append)
        self.assertEqual(len(calls), 3)
        self.assertEqual(events[-1], {'stage': 'runtime_inputs', 'status': 'FAIL',
                                    'error_type': 'CalledProcessError', 'returncode': 17})
        self.assertNotIn('PRIVATE-CANARY', json.dumps(events))

    def test_failed_status_write_preserves_the_original_remote_failure(self):
        streams = {k: {'manifest': '{"files":[]}', 'sha256': 'b' * 64, 'sources': {}}
                   for k in ('wheels', 'task', 'model')}
        primary = subprocess.CalledProcessError(17, 'remote-command')
        def emit(row):
            if row['status'] == 'FAIL':
                raise OSError('private status-write details')
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            worker.setup_remote(lambda *a, **kw: (_ for _ in ()).throw(primary),
                                streams, b'manifest', 1, emit=emit)
        self.assertIs(caught.exception, primary)
        self.assertEqual(primary.__notes__, ['Setup status retention also failed: OSError'])


if __name__ == '__main__': unittest.main()
