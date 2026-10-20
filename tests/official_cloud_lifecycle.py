"""Concurrent real owner/watcher loops with HTTP state and a real CPU child.

GitHub and RunPod are loopback/in-memory fixtures. This cannot allocate a GPU,
qualify the network providers, or stand in for an actual model/task execution.
"""
import base64
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import cloud_owner, cloud_state as state, cloud_watch
from tools.runpod_job import check_owner_host
from tests.test_cloud_state import MemoryStore, SOURCE
from tests.test_cloud_owner import Provider
from tests.test_runpod_control import offer


class Backend:
    def __init__(self, scenario):
        self.lock = threading.RLock()
        self.memory = MemoryStore()
        self.scenario = scenario
        self.requests = self.heartbeat_writes = 0
        self.fault_sent = False

    def request(self, method, path, body):
        with self.lock:
            self.requests += 1
            path = urllib.parse.urlsplit(path).path
            if path.startswith('/actions/runs/') and method == 'GET':
                return 200, copy.deepcopy(self.memory.runs[path.rsplit('/', 1)[1]])
            prefix = '/contents/' + state.DIRECTORY + '/'
            if not path.startswith(prefix) or not path.endswith('.json'):
                return 404, {}
            name = path[len(prefix):-5]
            if name not in state.DOCUMENTS:
                return 404, {}
            if method == 'PUT':
                if name == 'heartbeat':
                    self.heartbeat_writes += 1
                    if (self.scenario == 'state_http_failure' and self.heartbeat_writes == 3):
                        self.fault_sent = True
                        return 503, {}
                try:
                    value = json.loads(base64.b64decode(body['content']))
                    self.memory.write(name, value, previous_sha=body.get('sha'))
                except state.StateError:
                    return 409, {}
                return 201, {}
            document = self.memory.read(name)
            if document is None:
                return 404, {}
            value, sha = document
            return 200, {'type': 'file', 'encoding': 'base64', 'sha': sha,
                         'content': base64.b64encode(state.encoded(value)).decode()}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle_request(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length']))) if self.command == 'PUT' else None
        status, value = self.server.backend.request(self.command, self.path, body)
        data = json.dumps(value).encode()
        self.send_response(status); self.send_header('Content-Length', str(len(data))); self.end_headers()
        self.wfile.write(data)

    do_GET = do_PUT = handle_request


class LockedProvider(Provider):
    def __init__(self):
        super().__init__(); self.lock = threading.RLock(); self.deleted_at = None

    def create(self, value):
        with self.lock: return super().create(value)

    def get(self, value):
        with self.lock: return super().get(value)

    def list(self):
        with self.lock: return super().list()

    def stop(self, value):
        with self.lock: return super().stop(value)

    def delete(self, value):
        with self.lock:
            self.deleted_at = time.monotonic()
            return super().delete(value)


CHILD = '''import sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from tools.runpod_job import heartbeat
root=Path(sys.argv[2]);attempt=sys.argv[3];scenario=sys.argv[4]
start=time.monotonic()
heartbeat(root,attempt,'running','setup')
while time.monotonic()-start < (25 if scenario=='success' else 60):
 if scenario=='worker_failure' and time.monotonic()-start>2:sys.exit(2)
 if scenario!='stale_worker':heartbeat(root,attempt,'running','setup')
 time.sleep(0.2)
heartbeat(root,attempt,'finished','retrieval')
(root/'child-finished').write_text(str(time.monotonic()))
'''


def scenario(name):
    backend = Backend(name); api = LockedProvider()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); server.backend = backend
    http_thread = threading.Thread(target=server.serve_forever, daemon=True); http_thread.start()
    base = 'https://api.github.com/repos/' + state.REPOSITORY
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def local_open(request, timeout):
        if not request.full_url.startswith(base + '/'):
            raise ValueError('fixture forbids external network requests')
        url = 'http://127.0.0.1:' + str(server.server_port) + request.full_url[len(base):]
        return opener.open(urllib.request.Request(url, data=request.data, method=request.method), timeout=timeout)
    owner_store = state.GitHubState('fixture-only', opener=local_open)
    watcher_store = state.GitHubState('fixture-only', opener=local_open)
    watcher_result = {}
    def watch():
        try:
            watcher_result.update(cloud_watch.watch(watcher_store, api, '2', SOURCE, emit=lambda row: None))
        except Exception as error:
            watcher_result.update(error=type(error).__name__)
        finally:
            with backend.lock:
                backend.memory.runs['2'].update(status='completed', conclusion='success' if 'error' not in watcher_result else 'failure')
    watch_thread = threading.Thread(target=watch, daemon=True)
    process = None
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix='backtrace-concurrent-') as directory:
            root = Path(directory)
            watch_thread.start()
            deadline = time.monotonic() + 5
            while owner_store.read('watcher') is None:
                if time.monotonic() > deadline: raise TimeoutError('fixture watcher lease missing')
                time.sleep(.05)
            def spawn(directory, configuration, claim, pod_id, endpoint):
                nonlocal process
                process = subprocess.Popen([sys.executable, '-I', '-c', CHILD, str(ROOT),
                    str(directory), claim['attempt'], name], stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, start_new_session=True)
                if name == 'owner_cancelled':
                    def cancel():
                        time.sleep(3)
                        with backend.lock:
                            backend.memory.runs['1'].update(status='completed', conclusion='cancelled')
                    threading.Thread(target=cancel, daemon=True).start()
                return process
            result = cloud_owner.execute(owner_store, api, offer(time.time()), None, {}, root,
                '1', SOURCE, spawn=spawn, emit=lambda row: None)
            with backend.lock:
                backend.memory.runs['1'].update(status='completed', conclusion='success')
            watch_thread.join(timeout=35)
            assert not watch_thread.is_alive(), 'watcher did not independently finish'
            assert watcher_result.get('phase') == 'deleted', watcher_result
            assert watcher_result['absence_reads'] == 2
            assert result['cleanup']['phase'] == 'deleted', result
            assert result['status'] == ('COMPLETE' if name == 'success' else 'INCOMPLETE'), result
            assert set(api.pods) == {'unrelated'}
            assert sum(row[0] == 'create' for row in api.calls) == 1
            assert process is not None and process.poll() is not None
            if name == 'success':
                assert float((root / 'child-finished').read_text()) <= api.deleted_at
                assert backend.heartbeat_writes >= 5, 'healthy concurrent polling was not exercised'
            if name == 'state_http_failure':
                assert backend.fault_sent and result['failure']['http_status'] == 503
                assert result['failure']['stage'] == 'publish_heartbeat'
            claim_before = owner_store.read('claim')
            repeated = cloud_owner.execute(owner_store, api, offer(time.time()), None, {}, root,
                '1', SOURCE, spawn=spawn, emit=lambda row: None)
            assert repeated['allocation_requests'] == 0 and owner_store.read('claim') == claim_before
            assert sum(row[0] == 'create' for row in api.calls) == 1
            return {'scenario': name, 'status': 'PASS', 'owner': result['status'],
                    'watcher': watcher_result['phase'], 'loopback_http_requests': backend.requests,
                    'elapsed_seconds': round(time.monotonic() - started, 2),
                    'child_reaped': True, 'recreate_blocked': True}
    finally:
        if process is not None:
            cloud_owner.stop_worker(process)
            if process.stderr: process.stderr.close()
        server.shutdown(); server.server_close(); http_thread.join(timeout=5)


if __name__ == '__main__':
    check_owner_host()
    rows = [scenario(name) for name in ('success', 'worker_failure', 'stale_worker',
                                       'state_http_failure', 'owner_cancelled')]
    print(json.dumps({'status': 'PASS', 'cases': rows, 'paid_operations': 0,
                      'provider': 'SIMULATED', 'state_api': 'LOOPBACK HTTP',
                      'owner_watcher': 'CONCURRENT ACTUAL LOOPS', 'worker': 'REAL CPU FIXTURE PROCESS'}))
