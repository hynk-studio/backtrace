"""Thin owner-host orchestration of the frozen single A100 experiment.

`prepare` is read-only with respect to RunPod and never needs an API key.
`run` is the paid entry: use only after owner funding and a fresh qualified offer.
The controller stays outside the Pod; a separate worker only transports/runs the
frozen driver. A host outage is covered by the prepaid-wallet fallback, not by a
claim of durable provider timers. A transient chat executor is not a run host.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time

from tools import a100_delivery as frozen
from tools import runpod_control as control
from tools import ssh_bootstrap
from tools.private_delivery import digest, parse_manifest, push, receive, remote_python, ssh_command, verify


def private_json(path, value):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, sort_keys=True); stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_private(path):
    path = Path(path).absolute()
    if (path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid()
            or path.stat().st_mode & 0o077):
        raise ValueError('private owner file required')
    return path.read_text()


def prepare(config, output):
    """Hash all four source streams in place; no 29GB duplicate staging."""
    required = {'driver', 'wheels', 'task', 'model', 'ssh_directory', 'controller_host',
                'state_directory', 'files_persist'}
    if set(config) != required or config['controller_host'] not in ('kaggle-free-cpu', 'existing-linux-host'):
        raise ValueError('explicit external owner host and exact input paths required')
    if (config['files_persist'] is not True or not Path(config['state_directory']).is_absolute()
            or (config['controller_host'] == 'kaggle-free-cpu'
                and config['state_directory'] != '/kaggle/working/backtrace-a100-owner-state')):
        raise ValueError('persistent fixed attempt directory required; Kaggle needs Files only')
    check_owner_host()
    root = Path(config['ssh_directory'])
    init = json.loads(read_private(root / 'initializer.json'))
    ssh_bootstrap.validate_initializer(init)
    request_bytes = len(control.encode_create_request(control.make_request('0' * 32, 0, init)))
    transport = ssh_bootstrap.validate_material(root)
    read_private(root / 'owner-key')
    output = Path(output).absolute()
    output.mkdir(mode=0o700)
    manifests = {}
    for kind in ('driver', 'wheels', 'task', 'model'):
        data = frozen.manifest(kind, Path(config['driver']) if kind == 'driver' else None)
        receipt = verify(Path(config[kind]), data)
        target = output / (kind + '-manifest.json')
        target.write_bytes(data); target.chmod(0o600)
        manifests[kind] = receipt
    result = {'policy': control.POLICY, 'configuration': config, 'streams': manifests,
              'wallet_usd': str(control.WALLET), 'stop_total_usd': str(control.CAP),
              'first_attempt_seconds': control.TOTAL, 'native_timer': 'NOT USED',
              'provider_authentication': 'NOT CHECKED', 'allocation': 'NOT RUN',
              'transport': dict(transport, create_request_bytes=request_bytes)}
    private_json(output / 'plan.json', result)
    return result


def check_owner_host():
    if (sys.platform != 'linux' or os.getuid() != 0
            or int(Path('/proc/self/stat').read_bytes().split(b' ', 1)[0]) != os.getpid()):
        raise ValueError('real root Linux PID namespace required for the owner run host')


def heartbeat(directory, attempt, state, phase='setup'):
    private_json(Path(directory) / 'job-status.json',
                 {'attempt': attempt, 'state': state, 'phase': phase, 'at': control.utc(time.time())})


def remaining(value, limit=1200):
    result = value['requested_at'] + limit - time.time()
    if result <= 0:
        raise TimeoutError('allocation-inclusive phase deadline reached')
    return result


def connection(config, endpoint, known):
    return ssh_command(endpoint['host'], endpoint['port'],
                       Path(config['ssh_directory']) / 'owner-key', known,
                       '/root/backtrace/unused', '0' * 64)[:-1]


def remote(prefix, argv, value, log, limit=1200):
    return subprocess.run(prefix + [shlex.join(argv)], stdin=subprocess.DEVNULL,
                          stdout=log, stderr=log, check=True,
                          timeout=min(1200, remaining(value, limit)),
                          env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})


def retrieve(prefix, value, directory, log):
    """Only bounded experiment receipts; never root control files or keys."""
    root = '/kaggle/working/backtrace-a100-receipts'
    program = r'''import hashlib,json,os
from pathlib import Path
r=Path('/kaggle/working/backtrace-a100-receipts')
allowed={'execution.log','agent.patch','task-result.json','wire.jsonl','server.log','server-error.log','model-files.json'}
rows=[]
if r.is_dir():
 for p in sorted(r.rglob('*')):
  name=p.relative_to(r).as_posix()
  if p.is_file() and (name in allowed or name.startswith('results/')):
   assert not p.is_symlink() and p.resolve()==p
   with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
   rows.append({'path':name,'bytes':p.stat().st_size,'sha256':sha})
assert 0<len(rows)<=1024 and sum(x['bytes'] for x in rows)<=1024**3
print(json.dumps({'schema_version':1,'phase':'task','files':rows},sort_keys=True))
'''
    result = subprocess.run(prefix + [shlex.join(['python3', '-I', '-c', program])],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                            check=True, timeout=min(30, remaining(value, control.USEFUL)),
                            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
    data = result.stdout
    parse_manifest(data)
    source = (Path(__file__).with_name('private_delivery.py')).read_text()
    sender = ("import types,sys\nm=types.ModuleType('private_delivery')\n"
              + "exec(" + repr(source) + ",m.__dict__)\n"
              + "m.emit(" + repr(root) + ",sys.stdin.buffer.read(m.MAX_MANIFEST_BYTES+1),sys.stdout.buffer)\n")
    with tempfile.TemporaryFile() as stream:
        subprocess.run(prefix + [shlex.join(remote_python(sender))],
                       input=data, stdout=stream, stderr=log, check=True,
                       timeout=min(120, remaining(value, control.USEFUL)),
                       env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        stream.seek(0)
        return receive(Path(directory) / 'receipts', hashlib.sha256(data).hexdigest(), stream)


def worker(plan_directory, key_file, state_directory):
    plan_directory, state_directory = Path(plan_directory), Path(state_directory)
    plan = json.loads(read_private(plan_directory / 'plan.json'))
    config = plan['configuration']
    value = json.loads(read_private(state_directory / 'a100-attempt.json'))
    api = control.RunpodAPI(read_private(key_file).strip())
    finished = threading.Event()
    phase = ['setup']
    def beat():
        while not finished.is_set():
            heartbeat(state_directory, value['attempt'], 'running', phase[0])
            finished.wait(2)
    thread = threading.Thread(target=beat, daemon=True); thread.start()
    state, prefix = 'failed', None
    with (state_directory / 'worker.log').open('x') as log:
        os.fchmod(log.fileno(), 0o600)
        try:
            while True:
                remaining(value)
                pod = api.get(value['pod_id'])
                if not control.resource_matches(pod, value):
                    raise ValueError('assigned resource differs from the approved offer')
                endpoint = pod.get('ssh', {}).get('direct')
                if pod['status'] == 'RUNNING' and endpoint:
                    break
                time.sleep(2)
            if endpoint.get('username') != 'root':
                raise ValueError('exact root direct SSH endpoint required')
            receipt = ssh_bootstrap.deliver(config['ssh_directory'], endpoint['host'], endpoint['port'],
                                            timeout=min(120, remaining(value)))
            private_json(state_directory / 'bootstrap-transfer.json', receipt)
            known = ssh_bootstrap.known_hosts(config['ssh_directory'], endpoint['host'], endpoint['port'])
            prefix = connection(config, endpoint, known)
            # TCP publishing can precede sshd readiness. Retry only a read-only
            # probe on the same pre-authenticated identity, never create/start.
            probe_deadline = min(time.time() + 60, value['requested_at'] + 1200)
            while True:
                try:
                    remote(prefix, ['true'], value, log)
                    break
                except subprocess.CalledProcessError:
                    log.flush()
                    with (state_directory / 'worker.log').open('rb') as errors:
                        errors.seek(max(0, errors.seek(0, 2) - 8192))
                        tail = errors.read().lower()
                    if (time.time() >= probe_deadline or any(message in tail for message in
                            (b'host key verification failed', b'remote host identification', b'permission denied'))):
                        raise
                    time.sleep(2)
            for kind in ('driver', 'wheels', 'task', 'model'):
                manifest = plan_directory / (kind + '-manifest.json')
                command = ssh_command(endpoint['host'], endpoint['port'],
                                      Path(config['ssh_directory']) / 'owner-key', known,
                                      '/root/backtrace/' + kind, digest(manifest))
                push(Path(config[kind]), manifest, command, min(1200, remaining(value)))
            manifests = {kind: digest(plan_directory / (kind + '-manifest.json'))
                         for kind in ('driver', 'wheels', 'task', 'model')}
            source = Path(__file__).with_name('pod_bootstrap.py').read_text()
            program = (source + "\n"
                       + "print(json.dumps(activate(" + repr(manifests) + ","
                       + repr(value['requested_at']) + ")))\n")
            remote(prefix, remote_python(program), value, log)
            permit = {k: value[k] for k in ('policy', 'run', 'attempt', 'pod_id', 'requested_at')}
            permit['driver_sha256'] = frozen.DRIVER_SHA256
            program = ("import os,json,time;from pathlib import Path\n"
                       + "assert abs(time.time()-" + repr(time.time()) + ")<5\n"
                       + "p=Path('/root/backtrace/launch-permit.json')\n"
                       + "f=p.open('x');os.fchmod(f.fileno(),0o600);json.dump(" + repr(permit)
                       + ",f);f.flush();os.fsync(f.fileno());f.close()\n")
            remote(prefix, ['python3', '-I', '-c', program], value, log)
            phase[0] = 'workload'
            try:
                remote(prefix, ['env', 'BACKTRACE_ALLOCATION_REQUESTED_AT=' + str(value['requested_at']),
                                '/opt/backtrace-runtime/venv/bin/python', '-I',
                                '/root/backtrace/driver/one_task.py', '--authorized-run'],
                       value, log, limit=control.USEFUL)
                state = 'finished'
            finally:
                phase[0] = 'retrieval'
                if remaining(value, control.USEFUL) > 15:
                    try:
                        receipt = retrieve(prefix, value, state_directory, log)
                        private_json(state_directory / 'receipt-transfer.json', receipt)
                    except Exception as error:
                        private_json(state_directory / 'receipt-transfer.json', {'error_type': type(error).__name__})
        finally:
            finished.set(); thread.join(timeout=5)
            heartbeat(state_directory, value['attempt'], state, phase[0])


def run(plan_directory, offer_file, key_file, state_directory, *, prior_authorization=None):
    """Paid entry, never used by prepayment preparation or CPU tests on RunPod."""
    check_owner_host()
    plan_directory, state_directory = Path(plan_directory), Path(state_directory)
    plan = json.loads(read_private(plan_directory / 'plan.json'))
    if plan['policy'] != control.POLICY:
        raise ValueError('outdated control plan')
    if (plan['configuration']['files_persist'] is not True
            or state_directory.absolute() != Path(plan['configuration']['state_directory']).absolute()):
        raise ValueError('attempt state directory changed; never create a replacement journal')
    bootstrap = json.loads(read_private(Path(plan['configuration']['ssh_directory']) / 'initializer.json'))
    control.encode_create_request(control.make_request('0' * 32, 0, bootstrap))
    ssh_bootstrap.validate_material(plan['configuration']['ssh_directory'])
    # Rehash every source before the attempt marker/create. No resolver here.
    for kind in ('driver', 'wheels', 'task', 'model'):
        data = (plan_directory / (kind + '-manifest.json')).read_bytes()
        if hashlib.sha256(data).hexdigest() != plan['streams'][kind]['manifest_sha256']:
            raise ValueError('prepared delivery manifest changed')
        verify(Path(plan['configuration'][kind]), data)
    offer = json.loads(read_private(offer_file))
    control.validate_offer(offer, time.time())
    api = control.RunpodAPI(read_private(key_file).strip())
    state_directory.mkdir(mode=0o700, exist_ok=True)
    process = None
    with control.Journal(state_directory) as journal:
        if prior_authorization is not None:
            control.archive_unallocated_attempt(api, journal, prior_authorization)
        try:
            value = control.begin(api, journal, offer, bootstrap=bootstrap)
            heartbeat(state_directory, value['attempt'], 'running')
            # This controller never executes workload code. Killing the worker
            # leaves an independent owner process to observe stale heartbeat.
            process = subprocess.Popen([sys.executable, '-m', 'tools.runpod_job', '_worker',
                                        str(plan_directory), '--api-key-file', str(Path(key_file).absolute()),
                                        '--state-directory', str(state_directory.absolute())],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       start_new_session=True,
                                       env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
                                            'PYTHONPATH': str(Path(__file__).resolve().parents[1])},
                                       cwd=Path(__file__).resolve().parents[1])
            return control.watchdog(api, journal)
        finally:
            if journal.path.exists():
                value = journal.read()
                if value['phase'] != 'deleted':
                    heartbeat(state_directory, value['attempt'], 'failed')
                    control.watchdog(api, journal)
            if process is not None and process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'run', '_worker'))
    parser.add_argument('path', type=Path, help='config JSON for prepare; prepared plan directory otherwise')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--offer', type=Path)
    parser.add_argument('--api-key-file', type=Path)
    parser.add_argument('--state-directory', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        if args.output is None:
            parser.error('--output is required')
        result = prepare(json.loads(read_private(args.path)), args.output)
    else:
        if args.api_key_file is None or args.state_directory is None:
            parser.error('private owner key and state directory required')
        if args.mode == '_worker':
            worker(args.path, args.api_key_file, args.state_directory)
            return
        if args.offer is None:
            parser.error('fresh authenticated --offer is required')
        result = run(args.path, args.offer, args.api_key_file, args.state_directory)
    print(json.dumps({k: v for k, v in result.items() if k in
                      ('policy', 'phase', 'allocation', 'wallet_usd', 'stop_total_usd', 'billing')}))


if __name__ == '__main__':
    main()
