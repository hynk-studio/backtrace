"""Credential-free owner-side worker for the explicit two-hour cloud policy.

Receives only private local paths, scoped file URLs and the exact owned Pod's
pre-authenticated SSH endpoint. It has no provider create/delete capability.
"""
import argparse
import contextlib
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
from tools.task_results import validate as validate_task_results

PROFILE = 'actions-20261019'
CLEAN = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}
WORKLOAD_PYTHON = '/opt/backtrace-runtime/venv/bin/python'
WORKLOAD_DRIVER = '/root/backtrace/driver/one_task.py'


def workload_command(requested_at, *, cpu_prerequisites=False):
    """Set the driver's file-creation mask without changing private SSH setup.

    The retained driver explicitly protects control/output directories with
    0700 and the canary with 0600, but its shared code copies and task venv
    require the usual 022 mask. Exec preserves the PID, environment, permit,
    frozen driver bytes and allocation-inclusive deadlines.
    """
    entry = 'import os,sys;os.umask(0o022);os.execv(sys.argv[1],sys.argv[1:])'
    return ['env', 'BACKTRACE_ALLOCATION_REQUESTED_AT=' + str(requested_at),
            WORKLOAD_PYTHON, '-I', '-c', entry,
            WORKLOAD_PYTHON, '-I', WORKLOAD_DRIVER,
            '--cpu-prerequisites' if cpu_prerequisites else '--authorized-run']


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
assert set(v['streams']) in ({'wheels','task'}, {'model'}, {'wheels','task','model'})
for kind in ('wheels','task','model'):
 if kind not in v['streams']:continue
 row=v['streams'][kind]
 assert set(row)=={'manifest','sha256','sources'}
 manifest=row['manifest'].encode()
 left=v['requested_at']+5400-time.time()
 result=m.pull('/root/backtrace/'+kind,manifest,row['sources'],row['sha256'],left)
 print(json.dumps({'stream':kind,**result}),flush=True)
'''
    return source


def direct_envelope(value):
    return code_envelope(direct_program(), json.dumps(value))


def code_envelope(source, input_text=''):
    # Dropbear limits a command to 9,000 bytes. Carry both reviewed code and
    # scoped URLs over authenticated stdin, with a small hash-checking command.
    sha = hashlib.sha256(source.encode()).hexdigest()
    receiver = ("import io,sys,json,hashlib\n"
                "raw=sys.stdin.buffer.read(8*1024**2+1);assert len(raw)<=8*1024**2\n"
                "v=json.loads(raw);assert set(v)=={'source','input'}\n"
                "assert hashlib.sha256(v['source'].encode()).hexdigest()==" + repr(sha) + "\n"
                "sys.stdin=io.TextIOWrapper(io.BytesIO(v['input'].encode()))\n"
                "exec(v['source'])\n")
    data = json.dumps({'source': source, 'input': input_text}).encode()
    if len(data) > 8 * 1024**2:
        raise ValueError('private direct envelope size limit')
    return remote_python(receiver), data


def setup_remote(remote, streams, manifest, requested_at, *, emit=lambda value: None):
    """Run cheap checks and installation before downloading the model weights."""
    if set(streams) != {'wheels', 'task', 'model'}:
        raise ValueError('complete frozen streams required')
    hashes = {kind: row['sha256'] for kind, row in streams.items()}
    hashes['driver'] = hashlib.sha256(manifest).hexdigest()
    preflight = (frozen.ROOT / 'tools/pod_preflight.py').read_text()
    bootstrap = (frozen.ROOT / 'tools/pod_bootstrap.py').read_text()
    system_source = (frozen.ROOT / 'tools/pod_system.py').read_text()
    system_manifest = json.loads((frozen.ROOT / 'docs/a100-system-packages.json').read_text())
    total = sum(row['bytes'] for stream in streams.values()
                for row in json.loads(stream['manifest'])['files'])
    steps = [
        ('base_environment', code_envelope(preflight + '\nprint(json.dumps(base('
            + repr(total + 16 * 1024**3) + ')))\n')),
        ('system_packages', code_envelope(system_source + '\nprint(json.dumps(install('
            + repr(system_manifest) + ',' + repr(requested_at) + ')))\n')),
        ('runtime_inputs', direct_envelope({'requested_at': requested_at,
            'streams': {kind: streams[kind] for kind in ('wheels', 'task')}})),
        ('runtime_installation', code_envelope(bootstrap + '\nprint(json.dumps(prepare_runtime('
            + repr({kind: hashes[kind] for kind in ('driver', 'wheels')}) + ','
            + repr(requested_at) + ')))\n')),
        ('runtime_hardware', code_envelope(preflight + '\nprint(json.dumps(runtime()))\n')),
        ('model_inputs', direct_envelope({'requested_at': requested_at,
            'streams': {'model': streams['model']}})),
        ('activation', code_envelope(bootstrap + '\nprint(json.dumps(activate('
            + repr(hashes) + ',' + repr(requested_at)
            + ",policy='prepaid10-actions-v1',prepared_runtime=True)))\n")),
    ]
    for stage, (argv, data) in steps:
        emit({'stage': stage, 'status': 'STARTED'})
        try:
            remote(argv, input=data)
        except Exception as error:
            emit({'stage': stage, 'status': 'FAIL', 'error_type': type(error).__name__,
                  'returncode': getattr(error, 'returncode', None)})
            raise
        emit({'stage': stage, 'status': 'PASS'})


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
            ssh.wait_for_command(prefix, ['true'], min(60, remaining(value, state.SETUP)), log=log)
            command = ssh_command(endpoint['host'], endpoint['port'], ssh_root / 'owner-key', known,
                                  '/root/backtrace/driver', hashlib.sha256(manifest).hexdigest())
            push(driver, directory / 'driver-manifest.json', command, min(120, remaining(value, state.SETUP)))
            streams = json.loads(read_private(directory / 'worker-inputs.json'))
            def setup_event(row):
                private_json(directory / 'setup-status.json', row)
                log.write(('BACKTRACE_SETUP ' + json.dumps(row, sort_keys=True) + '\n').encode())
                log.flush()
            setup_remote(remote, streams, manifest, claim['requested_at'], emit=setup_event)
            permit = {key: value[key] for key in ('policy', 'run', 'attempt', 'pod_id', 'requested_at')}
            permit['driver_sha256'] = cloud_task.CLOUD_DRIVER_SHA256
            program = ("import os,json,time;from pathlib import Path\n"
                       + "assert abs(time.time()-" + repr(time.time()) + ")<5\n"
                       + "p=Path('/root/backtrace/launch-permit.json');f=p.open('x');os.fchmod(f.fileno(),0o600)\n"
                       + "json.dump(" + repr(permit) + ",f);f.flush();os.fsync(f.fileno());f.close()\n")
            remote(['python3', '-I', '-c', program])
            phase[0] = 'workload'
            complete_workload(remote, prefix, value, directory, log, phase)
            outcome = 'finished'
        finally:
            finished.set(); thread.join(timeout=5)
            heartbeat(directory, claim['attempt'], outcome, phase[0])
    return outcome


def complete_workload(remote, prefix, value, directory, log, phase):
    """Always recover available evidence; preserve workload errors over cleanup.

    A skipped/failed retrieval can never turn an exit-zero process into success.
    The same real artifact validator runs in the task and after byte transfer.
    """
    directory = Path(directory)
    primary = None
    try:
        remote(workload_command(value['requested_at']), limit=state.USEFUL - 180)
    except BaseException as error:
        primary = error
    phase[0] = 'retrieval'
    try:
        if remaining(value, state.USEFUL) <= 15:
            raise TimeoutError('insufficient time to retrieve actual task receipts')
        receipt = retrieve(prefix, value, directory, log, useful_seconds=state.USEFUL)
        private_json(directory / 'receipt-transfer.json', receipt)
        if primary is None:
            verified = validate_task_results(directory / 'receipts')
            private_json(directory / 'task-validation.json', verified)
    except BaseException as error:
        with contextlib.suppress(OSError):
            private_json(directory / 'retrieval-error.json', {'error_type': type(error).__name__})
        if primary is None:
            raise
        primary.add_note('Evidence retrieval also failed: ' + type(error).__name__)
    if primary is not None:
        raise primary


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
