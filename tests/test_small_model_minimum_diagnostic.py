"""CPU protocol/decision controls; none of these are observed CUDA results."""
import copy
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools import small_model_minimum_remote as remote
from tools import small_model_minimum_worker as worker


def observations(passed=(True, True, False)):
    common = {'limits': {'RLIMIT_CORE': [0, 0]}, 'python': '3.12.14',
              'executable': '/opt/backtrace/venv/bin/python', 'cuda_visible_devices': 'GPU-fixture',
              'environment_sha256': 'fixture', 'Groups': '', 'NoNewPrivs': '1',
              'CapEff': '0', 'CapPrm': '0', 'CapBnd': '0', 'Seccomp': '2'}
    rows = {}
    for case, success in zip('ABC', passed):
        uid = '0' if case == 'A' else '65532'
        identity = dict(common, Uid=' '.join([uid]*4), Gid=' '.join([uid]*4),
                        Seccomp_filters='2' if case == 'C' else '1')
        rows[case] = {'exit_code': 0, 'before': {'case': case, 'phase': 'BEFORE_CUDA', 'identity': identity},
                     'result': {'case': case, 'phase': 'RESULT', 'cuda_libraries': {},
                                'status': 'PASS_ACTUAL_CUDA_KERNELS' if success else 'FAIL'}}
    return rows


class DiagnosticTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0, 'root Linux boundary control')
    def test_real_child_changes_only_the_requested_identity_and_filter_boundary(self):
        """Real processes/kernel controls with a visibly authored CPU payload."""
        if list(Path('/dev').glob('nvidia[0-9]*')):
            self.skipTest('CPU-only control')
        source = Path(__file__).resolve().parents[1]/'tools'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o755)
            shutil.copyfile(source/'small_model_container_worker.py', root/'launcher.py')
            (root/'job.json').write_text(json.dumps({'gpu': {'uuid': 'GPU-fixture', 'device_basename': 'nvidia999999'}}))
            (root/'worker.py').write_text('''import socket
def cuda_check(config):
    try:
        connection=socket.socket();connection.close();code=0
    except OSError as exc:code=exc.errno
    raise RuntimeError('AUTHORED_CPU_SOCKET_ERRNO='+str(code))
''')
            for path in root.iterdir(): path.chmod(0o444)
            program = '''import importlib.util,os,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('minimum',sys.argv[1])
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
w.ROOT=Path(sys.argv[2])
w.Path=lambda p: w.ROOT/'job.json' if str(p)=='/job.json' else Path(p)
w.child(os.getppid(),sys.argv[3])
'''
            rows = {}
            for case in 'ABC':
                completed = subprocess.run([sys.executable, '-I', '-c', program,
                    str(source/'small_model_minimum_worker.py'), str(root), 'diagnostic-'+case.lower()],
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                before = json.loads(next(line.removeprefix('BACKTRACE_CUDA_BEFORE ') for line in
                    completed.stderr.splitlines() if line.startswith('BACKTRACE_CUDA_BEFORE ')))
                result = json.loads(completed.stdout)
                self.assertEqual(result['status'], 'FAIL')
                expected_errno = 1 if case == 'C' else 0
                self.assertEqual(result['error'], 'AUTHORED_CPU_SOCKET_ERRNO='+str(expected_errno))
                rows[case] = {'before': before, 'result': result, 'exit_code': 0}
            self.assertEqual(remote.diagnostic_decision(rows, False), 'CPU_CONTROLS_ONLY')

    def test_all_eight_patterns_have_conservative_predeclared_decisions(self):
        expected = {(False, False, False): 'COMMON_PROVIDER_RUNTIME_PATH_STOP',
                    (True, False, False): 'WORKER_IDENTITY_LIMIT_LAYER',
                    (True, True, False): 'ADDED_FILTER_IMPLICATED_SYSCALL_UNRESOLVED',
                    (True, True, True): 'CUDA_PATH_WORKS_FAILURE_NOT_REPRODUCED'}
        for pattern in itertools.product((False, True), repeat=3):
            with self.subTest(pattern=pattern):
                self.assertEqual(remote.diagnostic_decision(observations(pattern), True),
                    expected.get(pattern, 'NONMONOTONIC_INCONCLUSIVE_STOP_SAME_ROUTE'))
                self.assertEqual(remote.diagnostic_decision(observations(pattern), False), 'CPU_CONTROLS_ONLY')

    def test_invalid_boundary_or_changed_runtime_cannot_implicate_filter(self):
        for field, value in [('Uid', '0 0 0 0'), ('Gid', '0 0 0 0'), ('Groups', '0'),
                             ('CapEff', '1'), ('NoNewPrivs', '0'), ('Seccomp_filters', '1'),
                             ('python', 'different'), ('limits', {}), ('environment_sha256', 'different')]:
            rows = observations(); rows['C']['before']['identity'][field] = value
            with self.subTest(field=field):
                self.assertEqual(remote.diagnostic_decision(rows, True), 'INCOMPARABLE_STOP_SAME_ROUTE')

    def test_eof_timeout_and_nonzero_exit_are_not_cuda_failure_evidence(self):
        for change in ('missing', 'exception', 'exit', 'incomplete', 'unknown_status'):
            rows = observations()
            if change == 'missing': del rows['C']
            if change == 'exception': rows['C']['error'] = {'type': 'TimeoutError'}
            if change == 'exit': rows['C']['exit_code'] = 137
            if change == 'incomplete': del rows['C']['before']
            if change == 'unknown_status': rows['C']['result']['status'] = 'INCOMPLETE'
            with self.subTest(change=change):
                self.assertEqual(remote.diagnostic_decision(rows, True), 'INCONCLUSIVE_STOP_SAME_ROUTE')

    def test_missing_post_failure_mapping_is_not_a_starting_environment_confound(self):
        rows = observations()
        rows['B']['result']['cuda_libraries'] = {'/lib/libcuda.so.1': {'sha256': 'fixed'}}
        self.assertEqual(remote.diagnostic_decision(rows, True), 'ADDED_FILTER_IMPLICATED_SYSCALL_UNRESOLVED')
        rows['C']['result']['cuda_libraries'] = {'/lib/libcuda.so.1': {'sha256': 'changed'}}
        self.assertEqual(remote.diagnostic_decision(rows, True), 'INCOMPARABLE_STOP_SAME_ROUTE')

    def test_cuda_exception_preserves_checkpoint_and_failure_in_separate_streams(self):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        fake = mock.Mock(); fake.cuda_check.side_effect = RuntimeError('CUDA error 304 fixture')
        with mock.patch.object(worker, 'module', return_value=fake), mock.patch.object(worker, 'diagnostic_identity', return_value={'fixture': True}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            worker.diagnostic_cuda({'gpu': {'device_basename': 'nvidia999999'}}, 'diagnostic-c')
        result = json.loads(out.getvalue())
        self.assertEqual(result['status'], 'FAIL'); self.assertIn('304', result['error'])
        self.assertTrue(err.getvalue().startswith('BACKTRACE_CUDA_BEFORE '))
        self.assertIn('RuntimeError: CUDA error 304 fixture', err.getvalue())

    def collect(self, directory, *, timeout=False, survived=False):
        rows = observations(); channels = []
        def channel(command, log):
            case = Path(log).stem[0]
            Path(log).write_text('BACKTRACE_CUDA_BEFORE '+json.dumps(rows[case]['before'])+'\noriginal stderr\n')
            obj = mock.Mock(partial=b'partial' if timeout and case == 'B' else json.dumps(rows[case]['result']).encode()+b'\n')
            obj.read.return_value = rows[case]['result']; obj.close.return_value = 0
            if timeout and case == 'B': obj.read.side_effect = TimeoutError('bounded timeout')
            channels.append(obj); return obj
        with mock.patch.object(remote.container, 'ContainerChannel', side_effect=channel), \
                mock.patch.object(remote, 'state', return_value={'same_process_alive': survived}):
            result = remote.diagnose(['ssh'], Path(directory)/'comparison', actual=False)
        return result, channels

    def test_partial_failure_preserves_raw_output_and_does_not_erase_other_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            result, channels = self.collect(directory, timeout=True)
            self.assertEqual(list(result['cases']), list('ABC'))
            self.assertEqual(result['cases']['B']['error']['type'], 'TimeoutError')
            self.assertEqual(result['decision'], 'INCONCLUSIVE_STOP_SAME_ROUTE')
            self.assertEqual((Path(directory)/'comparison/B-stdout.log').read_bytes(), b'partial')
            self.assertEqual(json.loads((Path(directory)/'comparison/receipt.json').read_bytes()), result)
            for channel in channels: channel.close.assert_called_once()

    def test_unconfirmed_teardown_stops_before_next_case(self):
        with tempfile.TemporaryDirectory() as directory:
            result, channels = self.collect(directory, survived=True)
            self.assertEqual(list(result['cases']), ['A'])
            self.assertEqual(len(channels), 1)
            self.assertEqual(result['decision'], 'INCONCLUSIVE_STOP_SAME_ROUTE')

    def test_diagnostic_cannot_expand_per_case_deadline_or_select_model(self):
        for mode in ('diagnostic-a', 'diagnostic-b', 'diagnostic-c'):
            self.assertIn(mode, remote.command(['ssh'], mode, 30, False)[-1])
            with self.assertRaises(ValueError): remote.command(['ssh'], mode, 31, True)
        with self.assertRaises(ValueError): remote.command(['ssh'], 'pretrained_cuda', 30, True)

    def test_comparison_entry_does_not_repeat_memory_or_interruption_campaign(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(remote, 'remote', return_value={'fixture': True}), \
                mock.patch.object(remote, 'diagnose', return_value={'decision': 'CPU_CONTROLS_ONLY'}) as diagnose, \
                mock.patch.object(remote.container, 'ContainerChannel') as channel:
            result = remote.exercise(['ssh'], directory, actual=False, comparison_only=True)
            self.assertEqual(result['status'], 'DIAGNOSTIC_RECORDED')
            self.assertEqual(result['cuda_comparison']['decision'], 'CPU_CONTROLS_ONLY')
            diagnose.assert_called_once(); channel.assert_not_called()


if __name__ == '__main__': unittest.main()
