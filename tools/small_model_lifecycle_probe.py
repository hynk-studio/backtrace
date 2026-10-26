"""Native CPU qualification through the real cleanup wire client and process tree.

Only a loopback replica and owned CPU sleep processes exist. No credentials,
POST/create endpoint, hardware emulation, pretrained outputs or paid operations.
"""
import argparse
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid

from tools import small_model_lifecycle as life, small_model_precheck as pre
from tools import small_model_resources as resources, exact_teacher as exact
from tools.runpod_control import RunpodAPI, NoRedirect


def resource(port, identity):
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open
    def local(request, timeout):
        url = urllib.parse.urlsplit(request.full_url)
        if (url.scheme != 'https' or url.netloc != 'api.runpod.io'
                or request.get_header('Authorization') != 'Bearer cpu-replica'
                or request.method not in ('GET', 'DELETE')):
            raise ValueError('replica forbids all allocations and external requests')
        rewritten = urllib.request.Request('http://127.0.0.1:'+str(port)+url.path+
            ('?'+url.query if url.query else ''), method=request.method)
        return direct(rewritten, timeout=min(timeout, 2))
    return life.RunpodResource(RunpodAPI('cpu-replica', opener=local), identity)


class Replica:
    def __init__(self, scenario):
        self.scenario = scenario; self.identity = {'id': 'cpu-owned', 'name': 'backtrace-small-'+uuid.uuid4().hex}
        self.process = subprocess.Popen([sys.executable, '-I', '-c', 'import time;time.sleep(900)'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.present = True; self.deletes = 0; self.requests = []; self.lock = threading.RLock()
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self): self.reply()
            def do_DELETE(self): self.reply()
            def reply(self):
                with owner.lock:
                    owner.requests.append({'at': time.time(), 'method': self.command, 'path': self.path})
                    if owner.scenario == 'provider_reads_fail' and self.command == 'GET':
                        code, value = 503, {}
                    elif self.command == 'GET' and self.path.startswith('/v2/pods?'):
                        code, value = 200, {'pods': ([owner.identity] if owner.present else [])+
                            [{'id': 'unrelated', 'name': 'unrelated'}], 'pagination': {'hasNextPage': False}}
                    elif self.command == 'GET' and self.path == '/v2/pods/cpu-owned':
                        code, value = (200, owner.identity) if owner.present else (404, {})
                    elif self.command == 'DELETE' and self.path == '/v2/pods/cpu-owned':
                        owner.deletes += 1
                        if not (owner.scenario == 'false_delete_ack' and owner.deletes == 1):
                            life.stop(owner.process); owner.present = False
                        if owner.scenario == 'lost_delete_ack' and owner.deletes == 1:
                            self.close_connection = True; return
                        code, value = 204, {}
                    else: code, value = 400, {}
                    data = b'' if code == 204 else life.encoded(value)
                    self.send_response(code); self.send_header('Content-Length', str(len(data))); self.end_headers()
                    with contextlib.suppress(BrokenPipeError, ConnectionResetError): self.wfile.write(data)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.port = self.server.server_port

    def close(self):
        life.stop(self.process); self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=3)


WORK = r'''
import json,os,subprocess,sys,time
from pathlib import Path
root=Path(sys.argv[1]);scenario=sys.argv[2]
root.joinpath('entered').write_text('yes')
root.joinpath('receipt.json').write_text(json.dumps({'kind':'AUTHORED_CPU_CONTROL','pid':os.getpid()}))
root.joinpath('prompt.json').write_text('must not be exported')
if scenario=='export_failure': root.joinpath('forbidden').symlink_to('/etc/hosts')
child="import time;from pathlib import Path;time.sleep(6);Path("+repr(str(root/'late-child'))+").write_text('survived')"
subprocess.Popen([sys.executable,'-I','-c',child],start_new_session=True)
root.joinpath('detached-started').write_text('yes')
if scenario in ('deadline','owner_loss','watcher_loss','state_loss'):time.sleep(60)
elif scenario=='worker_failure':sys.exit(2)
else:time.sleep(.3)
'''


def wait_file(path, process=None, seconds=5):
    end = time.monotonic()+seconds
    while not path.exists():
        if (process and process.poll() is not None) or time.monotonic() >= end:
            raise RuntimeError('expected control checkpoint missing: '+path.name)
        time.sleep(.02)


def actor(config, role):
    value = json.loads(Path(config).read_bytes()); journal = life.Journal(value['journal'])
    api = resource(value['port'], value['identity'])
    if role == 'watch':
        result = life.watch(journal, api, interval=.04)
    else:
        result = life.supervise(journal, api, value['command'], Path(value['output']), interval=.04)
    life.write(value[role+'_result'], result)


def scenario(name, root, source, *, command=None):
    root.mkdir(mode=0o700); api = Replica(name); owner = watcher = None; logs = []
    try:
        total, export, cleanup = (600, 30, 30) if command else (10, 2, 3)
        requested = time.time()-(total-export-cleanup+.1 if name == 'insufficient_window' else 0)
        journal = life.Journal.create(root, source, api.identity, requested, total=total,
            export_seconds=export, cleanup_seconds=cleanup, stale_seconds=1, replica=True)
        journal.heartbeat('owner-heartbeat', 'starting')
        output = root/'work'
        config = {'journal': str(journal.root), 'port': api.port, 'identity': api.identity,
                  'command': command or [sys.executable, '-I', '-c', WORK, str(output), name],
                  'output': str(output), 'owner_result': str(root/'owner.json'), 'watch_result': str(root/'watch.json')}
        path = root/'config.json'; life.write(path, config)
        def start(role):
            log = (root/(role+'.log')).open('xb'); logs.append(log)
            return subprocess.Popen([sys.executable, '-m', 'tools.small_model_lifecycle_probe',
                'actor', str(path), role], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                start_new_session=True, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'})
        watcher = start('watch'); wait_file(journal.path('watcher-heartbeat'), watcher)
        owner = start('owner')
        if name in ('owner_loss', 'watcher_loss', 'state_loss'):
            wait_file(output/'detached-started', owner)
            if name == 'owner_loss': life.stop(owner)
            elif name == 'watcher_loss': life.stop(watcher)
            else: journal.path('claim').unlink()
        owner.wait(timeout=total+5); watcher.wait(timeout=total+5)
        owner_result = json.loads((root/'owner.json').read_bytes()) if (root/'owner.json').exists() else None
        watch_result = json.loads((root/'watch.json').read_bytes()) if (root/'watch.json').exists() else None
        unresolved = name == 'provider_reads_fail'
        if unresolved:
            assert owner_result['cleanup']['status'] == 'UNRESOLVED' and watch_result['status'] == 'UNRESOLVED'
            assert api.deletes == 0 and api.present
        else:
            assert not api.present and api.process.poll() is not None, 'owned CPU resource survived'
            if name != 'owner_loss': assert owner_result['cleanup']['absence_reads'] == 2
            if name != 'watcher_loss': assert watch_result['absence_reads'] == 2
        if name in ('normal', 'false_delete_ack', 'lost_delete_ack', 'connected'):
            assert owner_result['status'] == 'PASS_LOCAL_SUPERVISION', owner_result
            assert owner_result['export']['completed_at'] <= owner_result['cleanup']['started_at']
            assert owner_result['export']['completed_at'] <= watch_result['started_at']
        elif owner_result:
            assert owner_result['status'] == 'INCOMPLETE', owner_result
        if name == 'insufficient_window': assert not (output/'entered').exists()
        if name == 'export_failure': assert 'export_error' in owner_result
        if name == 'false_delete_ack': assert api.deletes >= 2
        # Wait past the detached child's authored write time; no process should
        # survive normal PID-1 exit, timeout, or death of the supervisor itself.
        entered = output/'detached-started'
        if entered.exists():
            end = entered.stat().st_mtime+6.3
            while time.time() < end: time.sleep(.05)
            assert not (output/'late-child').exists(), 'detached descendant escaped teardown'
        assert not any(r['method'] == 'POST' for r in api.requests)
        return {'scenario': name, 'status': 'PASS', 'owner': owner_result, 'watcher': watch_result,
                'wire_requests': len(api.requests), 'deletes': api.deletes, 'provider_create_requests': 0,
                'actual_cpu_resource_reaped': api.process.poll() is not None,
                'provider_absence': 'UNRESOLVED_EXPECTED' if unresolved else 'TWO_READS_PER_SURVIVING_CONTROLLER',
                'detached_late_write': False, 'replica': True}
    finally:
        life.stop(owner); life.stop(watcher)
        for log in logs: log.close()
        api.close()


def qualify(output, *, connected=None):
    output = exact._local_path(output); output.mkdir(mode=0o700, exist_ok=False)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    result = {'status': 'INCOMPLETE', 'source_sha': source, 'source_hashes': pre.sources(),
              'paid_operations': 0, 'gpu_minimum': 'NOT_RUN', 'pretrained_inference': 'NOT_RUN',
              'provider': 'LOOPBACK_HTTP_REPLICA', 'watcher': 'SEPARATE_LOCAL_PROCESS', 'cases': []}
    try:
        # Actual native memory observation is evidence, not a fabricated 32-GiB
        # pass on a smaller CI machine.
        try: result['memory_observation'] = resources.inspect()
        except ValueError as error: result['memory_observation'] = {'status': 'UNQUALIFIED', 'reason': str(error)}
        for name in ('normal', 'worker_failure', 'deadline', 'owner_loss', 'watcher_loss',
                     'state_loss', 'export_failure', 'false_delete_ack', 'lost_delete_ack',
                     'insufficient_window', 'provider_reads_fail'):
            row = scenario(name, output/name, source); result['cases'].append(row)
            life.write(output/(name+'.json'), row)
        if connected:
            python, sources, packets, tokens, scope = connected
            # This is the unchanged actual tokenizer/random-model/oracle/fault
            # pipeline, now inside the allocation-clock process boundary.
            command = [str(python), '-m', 'tools.small_model_runner_probe', *map(str, (sources, packets, tokens, scope)),
                       str(output/'connected/work/runner')]
            row = scenario('connected', output/'connected', source, command=command)
            receipt = json.loads((output/'connected/work/runner/receipt.json').read_bytes())
            assert receipt['status'] == 'PASS_CPU_PIPELINE_ONLY' and all(receipt['checks'].values())
            row['pipeline'] = {k: receipt[k] for k in ('status', 'checks', 'source_hashes', 'scope_sha256', 'runs')}
            result['cases'].append(row); life.write(output/'connected.json', row)
        pre.prepare(output/'prepared.json')
        result['status'] = 'PASS_CPU_PRECHECK_PREPARATION_ONLY'
        return result
    except BaseException as error:
        result['failure'] = {'type': type(error).__name__}
        raise
    finally:
        life.write(output/'receipt.json', result)


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('actor'); a.add_argument('config', type=Path); a.add_argument('role', choices=('owner', 'watch'))
    a = sub.add_parser('qualify'); a.add_argument('output', type=Path)
    a.add_argument('--connected', nargs=5, type=Path)
    args = p.parse_args()
    if args.command == 'actor': actor(args.config, args.role)
    else: print(json.dumps(qualify(args.output, connected=args.connected), sort_keys=True))


if __name__ == '__main__': main()
