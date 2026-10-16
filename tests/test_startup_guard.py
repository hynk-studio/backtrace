"""Real CPU subprocesses with an explicitly authored lifecycle stand-in.

official_startup_guard.py reuses these cases with the REAL pinned lifecycle.
"""
import json
import ctypes
import os
from pathlib import Path
import socket
import select
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.startup_guard import FatalTrace, group_members, guarded_server, stop_group
from startup_fixture import fatal, worker_trace


class FixtureError(RuntimeError):
    def __init__(self, message, output=''):
        super().__init__(message)
        self.output = output


class AuthoredLifecycle:
    """Minimal dependency-free stand-in; NOT evidence of official wrapper behavior."""
    def __init__(self, config):
        self.config = config
        self.process = None
        self.log_path = str(config.directory / 'server.log')
        self._log_file_handle = None

    def start(self):
        self._log_file_handle = open(self.log_path, 'w')
        self.process = subprocess.Popen(self.build_cmd(), env=self.build_env(),
                                        stdout=self._log_file_handle, stderr=subprocess.STDOUT)
        try:
            until = time.monotonic() + self.config.startup_timeout
            while time.monotonic() < until:
                if self.is_healthy():
                    return self
                time.sleep(self.config.health_check_interval)
            raise FixtureError('authored readiness timeout')
        except BaseException:
            self.stop()
            raise

    def is_healthy(self):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{self.config.port}/health', timeout=0.5) as reply:
                return reply.status == 200
        except (OSError, urllib.error.URLError):
            return False

    def stop(self, timeout=1):
        if self._log_file_handle:
            self._log_file_handle.close()
            self._log_file_handle = None
        if self.process:
            self.process.wait(timeout=timeout)
            self.process = None


class LifecycleCases:
    lifecycle = AuthoredLifecycle
    error_type = FixtureError
    boundary = 'authored lifecycle and CPU payload; NOT official vLLM'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Container PID 1 need not reap orphaned grandchildren. This test-owned
        # subreaper is separate from fixture boot timing and production policy.
        cls._previous_subreaper = None
        if sys.platform == 'linux':
            cls._libc = ctypes.CDLL(None, use_errno=True)
            previous = ctypes.c_int()
            if cls._libc.prctl(37, ctypes.byref(previous), 0, 0, 0) != 0:
                raise OSError(ctypes.get_errno(), 'PR_GET_CHILD_SUBREAPER')
            if cls._libc.prctl(36, 1, 0, 0, 0) != 0:
                raise OSError(ctypes.get_errno(), 'PR_SET_CHILD_SUBREAPER')
            cls._previous_subreaper = previous.value

    @classmethod
    def tearDownClass(cls):
        try:
            if cls._previous_subreaper is not None:
                if cls._libc.prctl(36, cls._previous_subreaper, 0, 0, 0) != 0:
                    raise OSError(ctypes.get_errno(), 'restore child subreaper')
        finally:
            super().tearDownClass()

    def exercise(self, mode, total=12, startup=12, boot_delay=0):
        # Reserve a loopback port, then relinquish it immediately before launch.
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory(prefix='backtrace-startup-') as directory:
            directory = Path(directory)
            config = self.configuration(port, directory)
            config.startup_timeout = startup

            class Payload(self.lifecycle):
                def build_cmd(self):
                    return [sys.executable, '-I', '-B', str(Path(__file__).with_name('startup_fixture.py')),
                            mode, str(port), str(directory), 'parent', str(boot_delay)]

                def build_env(self):
                    # No inherited credentials, external network configuration or telemetry.
                    return {'PATH': '/usr/bin:/bin', 'HOME': str(directory), 'LANG': 'C'}

            server = guarded_server(Payload, total_deadline=time.monotonic() + total,
                                    error_type=self.error_type)(config)
            Path(server.log_path).write_text(fatal(999999))  # MUST be truncated, not observed.
            try:
                if mode in ('fatal', 'race', 'timeout'):
                    with self.assertRaises(self.error_type) as caught:
                        server.start()
                    message = str(caught.exception)
                    if mode != 'timeout':
                        self.assertIn('synthetic resource limit', message)
                        self.assertIn('Traceback', caught.exception.output)
                        emitted = json.loads((directory / 'fatal-at.json').read_text())
                        latency = server.startup_observation['detected_posix'] - emitted
                        self.assertGreaterEqual(latency, 0)
                        self.assertLess(latency, 5)
                        self.assertIsNone(server.startup_observation['ready'])
                        self.assertTrue(server.startup_observation['parent_alive_at_detection'])
                    else:
                        latency = None
                        self.assertTrue(any(word in message for word in ('deadline', 'timeout', 'healthy')))
                        self.assertIsNone(server.startup_observation['detected'])
                else:
                    self.assertIs(server.start(), server)
                    self.assertIsNotNone(server.startup_observation['ready'])
                    self.assertIsNone(server.startup_observation['detected'])
                    # A post-readiness terminal-looking line cannot retroactively cancel startup.
                    with open(server.log_path, 'a') as log:
                        log.write(fatal(999999))
                    self.assertTrue(server.is_healthy())
                    latency = None
            finally:
                server.stop()
                before = dict(server.startup_observation)
                server.stop()  # Cleanup must be idempotent, including its measurement.
                self.assertEqual(before, server.startup_observation)
                self.assertIsNone(server.process)
                if server._group is not None:
                    self.assertEqual(group_members(server._group), [])
                for name in ('parent', 'worker', 'leaf'):
                    path = directory / (name + '.json')
                    if path.exists():
                        pid = json.loads(path.read_text())['pid']
                        with self.assertRaises(ProcessLookupError):
                            os.kill(pid, 0)
                Path(server.log_path).unlink(missing_ok=True)
            print(json.dumps({'case': mode, 'boundary': self.boundary,
                              'detection_seconds': latency,
                              'parent_alive_at_detection': before.get('parent_alive_at_detection'),
                              'teardown_seconds': before['teardown_seconds'],
                              'readiness_seconds': None if before['ready'] is None else before['ready'] - before['started'],
                              'owned_processes_remaining': 0}))
            if mode == 'stubborn':
                self.assertGreaterEqual(before['teardown_seconds'], 0.9)

    def configuration(self, port, directory):
        return SimpleNamespace(port=port, directory=directory, startup_timeout=12,
                               health_check_interval=0.05)

    def test_fatal_worker_parent_alive(self):
        self.exercise('fatal')

    def test_slow_fixture_boot_preserves_post_evidence_bound(self):
        # Deliberately exceed the old four-second fixture allowance. Detection
        # still has the same <5s assertion measured from emitted evidence.
        self.exercise('fatal', boot_delay=4.2)

    def test_fatal_during_health_wins(self):
        self.exercise('race')

    def test_successful_readiness(self):
        self.exercise('ready')

    def test_harmless_recoverable_and_quoted(self):
        self.exercise('harmless')

    def test_stale_previous_log(self):
        self.exercise('stale')

    def test_total_deadline_without_readiness(self):
        start = time.monotonic()
        self.exercise('timeout', total=0.6)
        self.assertLess(time.monotonic() - start, 5)

    def test_readiness_deadline_without_health(self):
        self.exercise('timeout', total=4, startup=0.6)

    def test_kill_fallback_and_idempotent_cleanup(self):
        self.exercise('stubborn')


@unittest.skipUnless(os.name == 'posix', 'POSIX launch/session guard')
class StartupGuardTests(LifecycleCases, unittest.TestCase):
    pass


@unittest.skipUnless(sys.platform == 'linux', 'Linux process metadata and cleanup')
class GroupCleanupTests(unittest.TestCase):
    def test_foreign_procfs_namespace_cannot_prove_group_absence(self):
        with patch('tools.startup_guard.os.getpid', return_value=-1):
            with self.assertRaisesRegex(OSError, 'PID namespace'):
                group_members(123)

    def test_linux_group_observation_does_not_launch_ps(self):
        with patch('tools.startup_guard.subprocess.check_output', side_effect=AssertionError('ps launched')):
            self.assertIn(os.getpid(), group_members(os.getpgrp()))

    def test_observation_failure_still_kills_and_reaps_owned_process(self):
        for persistent in (False, True):
            with self.subTest(persistent=persistent):
                process = subprocess.Popen(
                    [sys.executable, '-I', '-c',
                     'import signal,time,ctypes; ctypes.CDLL(None).prctl(15, b"odd ) \\xff name", 0, 0, 0); '
                     'signal.signal(signal.SIGTERM, signal.SIG_IGN); '
                     'print("ready", flush=True); time.sleep(60)'],
                    start_new_session=True, stdout=subprocess.PIPE, text=True)
                try:
                    self.assertTrue(select.select([process.stdout], [], [], 5)[0])
                    self.assertEqual(process.stdout.readline().strip(), 'ready')
                    self.assertIn(process.pid, group_members(process.pid))
                    calls = []

                    def observe(pgid):
                        calls.append(pgid)
                        if persistent or len(calls) == 1:
                            raise PermissionError('authored metadata failure')
                        return group_members(pgid)

                    with patch('tools.startup_guard.group_members', side_effect=observe):
                        if persistent:
                            with self.assertRaises(PermissionError):
                                stop_group(process, process.pid, grace=0.1)
                        else:
                            stop_group(process, process.pid, grace=0.1)
                    self.assertEqual(process.returncode, -signal.SIGKILL)
                    self.assertEqual(group_members(process.pid), [])
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=2)
                    process.stdout.close()


class TraceTests(unittest.TestCase):
    def test_complete_trace_only_and_earliest_cause(self):
        parser = FatalTrace()
        data = fatal(123).encode()
        parser.feed(data[:-1])
        self.assertIsNone(parser.cause)
        parser.feed(b'\n')
        parser.feed(fatal(124).replace('synthetic', 'later').encode())
        self.assertEqual(parser.cause, 'triton.runtime.errors.OutOfResources: synthetic resource limit')

    def test_error_and_quoted_trace_are_not_terminal(self):
        parser = FatalTrace()
        parser.feed(('ERROR: unstructured\n' + repr(fatal(123)) + '\n').encode())
        self.assertIsNone(parser.cause)

    def test_complete_recoverable_worker_trace_is_not_terminal(self):
        parser = FatalTrace()
        parser.feed(worker_trace(123).encode())
        self.assertIsNone(parser.cause)

    def test_unrelated_old_worker_cause_does_not_replace_engine_error(self):
        parser = FatalTrace()
        parser.feed(worker_trace(123).replace('synthetic resource limit', 'old recoverable error').encode())
        engine = fatal(124).split('(EngineCore', 1)[1]
        parser.feed(('(EngineCore' + engine).encode())
        self.assertEqual(parser.cause, "RuntimeError: Worker failed with error 'synthetic resource limit'")

    def test_partial_oversized_line_is_not_a_new_record(self):
        parser = FatalTrace()
        parser.feed(b'x' * 70000)
        parser.feed(worker_trace(123).encode())
        self.assertIsNone(parser.cause)
