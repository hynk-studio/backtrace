"""Narrow POSIX startup observer for the pinned adk-submission 0.2.11 lifecycle.

The official start/readiness loop still runs. Its public build_cmd/is_healthy/stop
hooks add a private process group, fresh-log observation, and group cleanup.
No thread, model import, request retry, or installed-wheel modification.
"""
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


ROW = re.compile(
    r'^\((Worker_TP\d+|EngineCore(?:_DP\d+)?) pid=(\d+)\) ERROR '
    r'\d\d-\d\d \d\d:\d\d:\d\d \[(multiproc_executor|core)\.py:\d+\] (.*)$')
CAUSE = re.compile(r'^[\w.]+(?:Error|Exception|OutOfResources): .+')
MARKERS = {'multiproc_executor': {'WorkerProc hit an exception.'},
           'core': {'EngineCore failed to start.', 'EngineCore encountered a fatal error.'}}
READ_LIMIT = 256 * 1024
CONTEXT_LIMIT = 64 * 1024


class FatalTrace:
    """Accept complete structured terminal tracebacks, not arbitrary ERROR text."""
    def __init__(self):
        self.pending = b''
        self.traces = {}
        self.worker_causes = []
        self.cause = None
        self.context = None

    def feed(self, data):
        # Long/incomplete records cannot manufacture a line boundary or cause.
        self.pending += data
        while b'\n' in self.pending:
            line, self.pending = self.pending.split(b'\n', 1)
            if len(line) > CONTEXT_LIMIT:
                continue
            row = ROW.fullmatch(line.decode('utf-8', errors='replace'))
            if not row or self.cause:
                continue
            role, pid, module, message = row.groups()
            if (module == 'core') != role.startswith('EngineCore'):
                continue
            key = (role, pid, module)
            if message in MARKERS[module]:
                if len(self.traces) < 16:
                    self.traces.setdefault(key, {'text': '', 'traceback': False})
            trace = self.traces.get(key)
            if trace is None:
                continue
            trace['text'] = (trace['text'] + line.decode('utf-8', 'replace') + '\n')[-CONTEXT_LIMIT:]
            if message == 'Traceback (most recent call last):':
                trace['traceback'] = True
            elif trace['traceback'] and CAUSE.fullmatch(message):
                if module == 'multiproc_executor':
                    # Pinned worker logs this and CONTINUES: not fatal by itself.
                    if len(self.worker_causes) < 16:
                        self.worker_causes.append((message, trace['text']))
                else:
                    # Pinned EngineCore failed-to-start handler logs then raises.
                    # Keep an earlier worker cause only if the terminal engine
                    # exception actually references its message, not an unrelated
                    # recoverable failure earlier in this same startup.
                    self.cause, self.context = next(
                        ((cause, context + trace['text']) for cause, context in self.worker_causes
                         if cause.split(': ', 1)[1] in message), (message, trace['text']))
        if len(self.pending) > CONTEXT_LIMIT:
            # Keep an unmatchable prefix until this oversized record is complete.
            self.pending = b'!' * (CONTEXT_LIMIT + 1)


def group_members(pgid):
    """Only PID/group/status metadata; no command lines or other users' secrets."""
    rows = subprocess.check_output(
        ['/bin/ps', '-axo', 'pid=,pgid=,stat='], text=True, timeout=2)
    return [int(pid) for pid, group, _ in (row.split() for row in rows.splitlines())
            if int(group) == pgid]


def stop_group(process, pgid, grace=1.0):
    """TERM, bounded grace, KILL, reap our parent; fail if group members remain.

    vLLM's multiprocessing workers inherit this session/group. The private
    driver's existing UID/subreaper boundary remains responsible for descendants
    that deliberately leave it. This is not a provider-session stop mechanism.
    """
    if pgid is None:
        if process.poll() is None:
            process.terminate()
    else:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    until = time.monotonic() + grace
    while time.monotonic() < until:
        process.poll()  # Reap the Popen child as soon as it exits.
        if not (group_members(pgid) if pgid else process.poll() is None):
            return
        time.sleep(0.02)
    try:
        if pgid:
            os.killpg(pgid, signal.SIGKILL)
        elif process.poll() is None:
            process.kill()
    except ProcessLookupError:
        pass
    process.wait(timeout=2)
    until = time.monotonic() + 2
    while pgid and group_members(pgid):
        # On the Linux private driver this also reaps adopted group children.
        try:
            while os.waitpid(-pgid, os.WNOHANG)[0]:
                pass
        except ChildProcessError:
            pass
        if time.monotonic() >= until:
            raise RuntimeError('owned startup process group did not disappear')
        time.sleep(0.02)


def guarded_server(server_type, *, total_deadline, error_type=None):
    """Wrap the pinned public lifecycle hooks; total_deadline is monotonic."""
    if not math.isfinite(total_deadline):
        raise ValueError('finite monotonic total deadline required')
    if error_type is None:
        from adk_submission.errors import ServerStartupError
        error_type = ServerStartupError

    class GuardedServer(server_type):
        def start(self):
            if hasattr(self, 'startup_observation'):
                raise RuntimeError('one server start per guarded attempt')
            now = time.monotonic()
            self.startup_observation = {'started': now, 'detected': None,
                                        'ready': None, 'teardown_seconds': None}
            self._deadline = min(total_deadline, now + self.config.startup_timeout)
            self._trace = FatalTrace()
            self._offset = 0
            self._caught_up = True
            self._group = None
            self._closed = False
            self._observing = True
            if now >= self._deadline:
                raise error_type('startup total deadline already expired', output='')
            return super().start()

        def build_cmd(self):
            # exec keeps the official Popen PID; setsid prevents broad name kills.
            return [sys.executable, '-I', '-B', str(Path(__file__).resolve()),
                    '--exec', *super().build_cmd()]

        def _observe_startup(self):
            if not getattr(self, '_observing', False):
                return
            if self._group is None and self.process is not None:
                try:
                    if os.getpgid(self.process.pid) == self.process.pid:
                        self._group = self.process.pid
                except ProcessLookupError:
                    pass
            # Official start opens/truncates this log BEFORE spawning. Reading
            # that exact descriptor's inode excludes an old/replaced log path.
            writer = self._log_file_handle
            if writer is not None:
                with open(self.log_path, 'rb') as log:
                    expected = os.fstat(writer.fileno())
                    actual = os.fstat(log.fileno())
                    if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
                        raise error_type('startup log identity changed', output='')
                    log.seek(self._offset)
                    data = log.read(READ_LIMIT)
                    self._offset += len(data)
                    self._trace.feed(data)
                    self._caught_up = self._offset >= os.fstat(log.fileno()).st_size
            if self._trace.cause:
                self.startup_observation['detected'] = time.monotonic()
                # Python 3.9 macOS monotonic() has process-local origins. Use
                # the POSIX clock separately for fixture cross-process latency.
                self.startup_observation['detected_posix'] = time.clock_gettime(time.CLOCK_MONOTONIC)
                self.startup_observation['parent_alive_at_detection'] = self.process.poll() is None
                self._observing = False
                raise error_type('fatal startup worker/engine traceback: ' + self._trace.cause,
                                 output=self._trace.context)
            if time.monotonic() >= self._deadline:
                raise error_type('startup readiness/total deadline expired', output='')

        def is_healthy(self):
            self._observe_startup()
            healthy = super().is_healthy()
            # A fatal record written during the health request wins over readiness.
            self._observe_startup()
            if healthy and getattr(self, '_observing', False) and not self._caught_up:
                return False  # Drain bounded fresh records before declaring readiness.
            if healthy and getattr(self, '_observing', False):
                self.startup_observation['ready'] = time.monotonic()
                self._observing = False  # No asynchronous watcher can cancel success.
            return healthy

        def stop(self, timeout=1.0):
            if not hasattr(self, 'startup_observation'):
                return super().stop(timeout=timeout)
            if self._closed:
                return
            before = time.monotonic()
            active_cause = sys.exc_info()[1]
            self._observing = False
            process = self.process
            if process is not None:
                if self._group is None:
                    try:
                        if os.getpgid(process.pid) == process.pid:
                            self._group = process.pid
                    except ProcessLookupError:
                        pass
                if self._group is None and process.poll() is not None and group_members(process.pid):
                    self._group = process.pid
                try:
                    stop_group(process, self._group, grace=min(timeout, 1.0))
                except Exception as cleanup_error:
                    self.startup_observation['cleanup_error'] = str(cleanup_error)
                    self.startup_observation['teardown_seconds'] = time.monotonic() - before
                    # The official start calls stop from its exception handler.
                    # Retain that original causal exception if cleanup also fails.
                    if active_cause is None:
                        raise
                    return
            super().stop(timeout=timeout)
            self._closed = True
            self.startup_observation['teardown_seconds'] = time.monotonic() - before

    return GuardedServer


if __name__ == '__main__':
    if sys.argv[1:2] != ['--exec'] or len(sys.argv) < 3:
        raise SystemExit('internal launch shim requires --exec and the official command')
    os.setsid()
    os.execvpe(sys.argv[2], sys.argv[2:], os.environ)
