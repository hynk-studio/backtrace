"""Credential-free owner-side worker for the explicit two-hour cloud policy.

Receives only private local paths, scoped file URLs and the exact owned Pod's
pre-authenticated SSH endpoint. It has no provider create/delete capability.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import threading
import time

from tools import cloud_state as state, cloud_task, ssh_bootstrap as ssh
from tools import a100_delivery as frozen
from tools.private_delivery import digest, push, remote_python, ssh_command, verify
from tools.runpod_job import check_owner_host, heartbeat, private_json, read_private, remaining, retrieve

PROFILE = 'actions-20261019'
CLEAN = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}


def direct_program():
    """Reviewed stdlib-only modules, with URLs supplied through private stdin."""
    source = "import types,sys,json,time,hashlib\n"
    source += "pkg=types.ModuleType('tools');pkg.__path__=[];sys.modules['tools']=pkg\n"
    for name in ('private_delivery', 'direct_delivery'):
        code = (frozen.ROOT / 'tools' / (name + '.py')).read_text()
        source += "m=types.ModuleType('tools." + name + "');sys.modules[m.__name__]=m\n"
        source += 'exec(' + repr(code) + ',m.__dict__)\n'
    source += '''v=json.loads(sys.stdin.buffer.read(8*1024**2+1))
assert set(v)=={'requested_at','streams'}
assert set(v['streams'])=={'wheels','task','model'}
for kind in ('wheels','task','model'):
 row=v['streams'][kind]
 assert set(row)=={'manifest','sha256','sources'}
 manifest=row['manifest'].encode()
 left=v['requested_at']+5400-time.time()
 result=m.pull('/root/backtrace/'+kind,manifest,row['sources'],row['sha256'],left)
 print(json.dumps({'stream':kind,**result}),flush=True)
'''
    return source


def direct_envelope(value):
    # Dropbear limits a command to 9,000 bytes. Carry both reviewed code and
    # scoped URLs over authenticated stdin, with a small hash-checking command.
    source = direct_program()
    sha = hashlib.sha256(source.encode()).hexdigest()
    receiver = ("import io,sys,json,hashlib\n"
                "raw=sys.stdin.buffer.read(8*1024**2+1);assert len(raw)<=8*1024**2\n"
                "v=json.loads(raw);assert set(v)=={'source','input'}\n"
                "assert hashlib.sha256(v['source'].encode()).hexdigest()==" + repr(sha) + "\n"
                "sys.stdin=io.TextIOWrapper(io.BytesIO(v['input'].encode()))\n"
                "exec(v['source'])\n")
    data = json.dumps({'source': source, 'input': json.dumps(value)}).encode()
    if len(data) > 8 * 1024**2:
        raise ValueError('private direct envelope size limit')
    return remote_python(receiver), data


def run(directory):
    check_owner_host()
    if any(k in os.environ for k in ('RUNPOD_API_KEY', 'KAGGLE_API_TOKEN', 'GH_STATE_TOKEN', 'GITHUB_TOKEN')):
        raise ValueError('worker must not inherit service credentials')
    directory = Path(directory).absolute()
    plan = json.loads(read_private(directory / 'worker-plan.json'))
    claim = state.validate_claim(plan['claim'])
    endpoint = plan['endpoint']; ssh_root = Path(plan['ssh_directory'])
    if endpoint['username'] != 'root':
        raise ValueError('exact root direct endpoint required')
    ssh.validate_endpoint(endpoint['host'], endpoint['port'])
    value = dict(claim, pod_id=plan['pod_id'])
    driver = Path(plan['driver'])
    manifest = cloud_task.manifest(driver)
    if manifest != read_private(directory / 'driver-manifest.json').encode():
        raise ValueError('prepared cloud manifest changed')
    verify(driver, manifest)
    phase, finished = ['setup'], threading.Event()
    def beat():
        while not finished.is_set():
            heartbeat(directory, claim['attempt'], 'running', phase[0])
            finished.wait(2)
    heartbeat(directory, claim['attempt'], 'running', 'setup')
    thread = threading.Thread(target=beat, daemon=True); thread.start()
    outcome, prefix = 'failed', None
    with (directory / 'worker.log').open('xb') as log:
        def remote(argv, *, limit=state.SETUP, input=None):
            return subprocess.run(prefix + [shlex.join(argv)], input=input,
                stdin=subprocess.DEVNULL if input is None else None, stdout=log, stderr=log,
                check=True, timeout=remaining(value, limit), env=CLEAN)
        try:
            ssh.deliver(ssh_root, endpoint['host'], endpoint['port'],
                        min(120, remaining(value, state.SETUP)), profile=PROFILE)
            known = ssh.known_hosts(ssh_root, endpoint['host'], endpoint['port'])
            prefix = ssh_command(endpoint['host'], endpoint['port'], ssh_root / 'owner-key', known,
                                 '/root/backtrace/unused', '0' * 64)[:-1]
            probe_deadline = min(time.time() + 60, claim['requested_at'] + state.SETUP)
            while True:
                try:
                    remote(['true'])
                    break
                except subprocess.CalledProcessError:
                    log.flush()
                    with (directory / 'worker.log').open('rb') as errors:
                        errors.seek(max(0, errors.seek(0, 2) - 8192)); tail = errors.read().lower()
                    if time.time() >= probe_deadline or any(message in tail for message in (
                            b'host key verification failed', b'remote host identification', b'permission denied')):
                        raise
                    time.sleep(2)
            command = ssh_command(endpoint['host'], endpoint['port'], ssh_root / 'owner-key', known,
                                  '/root/backtrace/driver', hashlib.sha256(manifest).hexdigest())
            push(driver, directory / 'driver-manifest.json', command, min(120, remaining(value, state.SETUP)))
            streams = json.loads(read_private(directory / 'worker-inputs.json'))
            argv, data = direct_envelope({'requested_at': claim['requested_at'], 'streams': streams})
            remote(argv, input=data)
            hashes = {kind: row['sha256'] for kind, row in streams.items()}
            hashes['driver'] = hashlib.sha256(manifest).hexdigest()
            source = (frozen.ROOT / 'tools/pod_bootstrap.py').read_text()
            program = source + "\nprint(json.dumps(activate(" + repr(hashes) + ',' + repr(claim['requested_at'])
            program += ",policy='prepaid10-actions-v1')))\n"
            remote(remote_python(program))
            permit = {key: value[key] for key in ('policy', 'run', 'attempt', 'pod_id', 'requested_at')}
            permit['driver_sha256'] = cloud_task.CLOUD_DRIVER_SHA256
            program = ("import os,json,time;from pathlib import Path\n"
                       + "assert abs(time.time()-" + repr(time.time()) + ")<5\n"
                       + "p=Path('/root/backtrace/launch-permit.json');f=p.open('x');os.fchmod(f.fileno(),0o600)\n"
                       + "json.dump(" + repr(permit) + ",f);f.flush();os.fsync(f.fileno());f.close()\n")
            remote(['python3', '-I', '-c', program])
            phase[0] = 'workload'
            try:
                remote(['env', 'BACKTRACE_ALLOCATION_REQUESTED_AT=' + str(claim['requested_at']),
                        '/opt/backtrace-runtime/venv/bin/python', '-I',
                        '/root/backtrace/driver/one_task.py', '--authorized-run'], limit=state.USEFUL - 180)
                outcome = 'finished'
            finally:
                phase[0] = 'retrieval'
                if remaining(value, state.USEFUL) > 15:
                    try:
                        receipt = retrieve(prefix, value, directory, log, useful_seconds=state.USEFUL)
                        private_json(directory / 'receipt-transfer.json', receipt)
                    except Exception as error:
                        private_json(directory / 'receipt-transfer.json', {'error_type': type(error).__name__})
                        outcome = 'failed'
        finally:
            finished.set(); thread.join(timeout=5)
            heartbeat(directory, claim['attempt'], outcome, phase[0])
    return outcome


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args(); os.umask(0o077)
    try:
        result = run(args.directory)
        print(json.dumps({'worker': result}))
        raise SystemExit(0 if result == 'finished' else 1)
    except Exception as error:
        print(json.dumps({'worker': 'failed', 'error_type': type(error).__name__}))
        raise SystemExit(1) from None
