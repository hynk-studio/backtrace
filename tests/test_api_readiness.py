"""Error classification and cleanup causality, distinct from real API checks."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.startup_guard import HTTPFailureTrace, guarded_server


def request(status=500, cause="AttributeError: '_IncludedRouter' object has no attribute 'path'", prefix=''):
    lines = [f'INFO:     127.0.0.1:3456 - "GET /health HTTP/1.1" {status} Status']
    if status == 500:
        lines += ['ERROR:    Exception in ASGI application', 'Traceback (most recent call last):',
                  '  File "/runtime/prometheus_fastapi_instrumentator/routing.py", line 55, in get_route_name',
                  cause]
    return ''.join(prefix + line + '\n' for line in lines).encode()


class HTTPTraceTests(unittest.TestCase):
    def test_three_matching_complete_http_failures_required(self):
        trace = HTTPFailureTrace()
        trace.feed(request(prefix='(APIServer pid=42) ') * 2)
        self.assertIsNone(trace.cause)
        third = request(prefix='(APIServer pid=42) ')
        trace.feed(third[:-1])
        self.assertIsNone(trace.cause)
        trace.feed(third[-1:])
        self.assertIn('_IncludedRouter', trace.cause)
        self.assertEqual(trace.http_500s, 3)

    def test_warmup_success_unrelated_and_incomplete_traces_do_not_accumulate(self):
        for separator in (request(503), request(200), request(cause='ValueError: unrelated')):
            trace = HTTPFailureTrace()
            trace.feed(request() * 2 + separator + request() * 2)
            self.assertIsNone(trace.cause)
        trace = HTTPFailureTrace()
        trace.feed((repr(request()) + '\n').encode() * 5)
        trace.feed(b'ERROR:    Exception in ASGI application\n' * 5)
        self.assertIsNone(trace.cause)

    def test_duplicate_exception_without_new_request_and_oversized_line_are_ignored(self):
        trace = HTTPFailureTrace()
        trace.feed(request())
        trace.feed(request().split(b'\n', 1)[1] * 4)
        self.assertIsNone(trace.cause)
        trace.feed(b'x' * 70000 + request() * 2)
        self.assertIsNone(trace.cause)


class StartupError(RuntimeError):
    def __init__(self, message, output=''):
        super().__init__(message)
        self.output = output


class CleanupCauseTests(unittest.TestCase):
    def test_timeout_stop_outside_except_and_later_finally_preserve_primary(self):
        class Lifecycle:
            config = SimpleNamespace(startup_timeout=1200)
            process = SimpleNamespace(pid=999, poll=lambda: None)
            _log_file_handle = None

            def start(self):
                self.stop()  # Reproduce official timeout cleanup outside except.
                raise StartupError('wrapper readiness timeout')

            def stop(self, timeout=1):
                raise AssertionError('must not reach superclass on failed group cleanup')

        server = guarded_server(Lifecycle, total_deadline=time.monotonic() + 30,
                                error_type=StartupError)()
        with patch('tools.startup_guard.os.getpgid', return_value=999), \
             patch('tools.startup_guard.stop_group', side_effect=RuntimeError('cleanup failed')):
            with self.assertRaisesRegex(StartupError, 'before HTTP readiness'):
                server.start()
            server.stop()  # Caller finally has no active exception; still no masking.
        self.assertEqual(server.startup_observation['cleanup_error'], 'cleanup failed')
        self.assertIn('before HTTP readiness', server.startup_observation['primary_error'])

    def test_observed_api_failure_is_not_masked_by_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / 'server.log'

            class Lifecycle:
                config = SimpleNamespace(startup_timeout=1200)
                process = SimpleNamespace(pid=999, poll=lambda: None)

                def start(self):
                    self._log_file_handle = log_path.open('w')
                    self._log_file_handle.write((request() * 3).decode())
                    self._log_file_handle.flush()
                    try:
                        self.is_healthy()
                    except BaseException:
                        self.stop()
                        raise

                def is_healthy(self):
                    raise AssertionError('fatal log should win before another request')

            Lifecycle.log_path = str(log_path)
            server = guarded_server(Lifecycle, total_deadline=time.monotonic() + 30,
                                    error_type=StartupError)()
            try:
                with patch('tools.startup_guard.os.getpgid', return_value=999), \
                     patch('tools.startup_guard.stop_group', side_effect=RuntimeError('cleanup failed')):
                    with self.assertRaisesRegex(StartupError, 'repeated HTTP 500') as caught:
                        server.start()
                    server.stop()
                self.assertIn('_IncludedRouter', caught.exception.output)
                self.assertEqual(server.startup_observation['repeated_asgi_tracebacks'], 3)
                self.assertEqual(server.startup_observation['cleanup_error'], 'cleanup failed')
            finally:
                server._log_file_handle.close()
