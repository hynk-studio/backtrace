"""Disposable CPU server payload. All vLLM-looking log records are INJECTED."""
import http.server
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def worker_trace(pid):
    prefix = f'(Worker_TP0 pid={pid}) ERROR 09-29 09:40:01 [multiproc_executor.py:949] '
    return ''.join(prefix + line + '\n' for line in (
        'WorkerProc hit an exception.', 'Traceback (most recent call last):',
        '  File "authored-fixture.py", line 1, in worker',
        'triton.runtime.errors.OutOfResources: synthetic resource limit'))


def fatal(pid):
    prefix = f'(EngineCore pid={pid}) ERROR 09-29 09:40:01 [core.py:1108] '
    return worker_trace(pid) + ''.join(prefix + line + '\n' for line in (
        'EngineCore failed to start.', 'Traceback (most recent call last):',
        "RuntimeError: Worker failed with error 'synthetic resource limit'"))


def run():
    mode, port, directory, role = sys.argv[1:]
    directory = Path(directory)
    (directory / (role + '.json')).write_text(json.dumps({'pid': os.getpid()}))
    if role == 'leaf':
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(30)
        return
    child = subprocess.Popen([sys.executable, '-I', '-B', __file__, mode, port,
                              str(directory), 'worker' if role == 'parent' else 'leaf'])

    def stop(*_):
        child.terminate()
        try:
            child.wait(timeout=0.15)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=1)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    if role == 'parent' and mode == 'stubborn':
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
    if role == 'worker':
        if mode in ('fatal', 'race'):
            if mode == 'race':
                until = time.monotonic() + 10
                while not (directory / 'health-request').exists() and time.monotonic() < until:
                    time.sleep(0.01)
            else:
                time.sleep(0.15)
            child.kill()
            child.wait(timeout=1)
            (directory / 'fatal-at.json').write_text(json.dumps(time.clock_gettime(time.CLOCK_MONOTONIC)))
            print(fatal(os.getpid()), end='', flush=True)
            raise SystemExit(17)
        time.sleep(30)
        stop()
        return

    if mode == 'harmless':
        print('ERROR recoverable fallback; WARNING compiler cache miss', flush=True)
        print(worker_trace(child.pid), end='', flush=True)
        print('quoted: ' + repr(fatal(child.pid)), flush=True)
        print('(Worker_TP0 pid=123) ERROR 09-29 09:40:01 [multiproc_executor.py:949] '
              'RuntimeError: recoverable without terminal marker', flush=True)

    class Health(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if mode == 'race':
                (directory / 'health-request').touch()
                child.wait(timeout=2)
            self.send_response(200 if mode in ('ready', 'harmless', 'stale', 'race', 'stubborn') else 503)
            self.end_headers()

        def log_message(self, *_):
            pass

    with http.server.HTTPServer(('127.0.0.1', int(port)), Health) as server:
        server.serve_forever(poll_interval=0.02)


if __name__ == '__main__':
    run()
