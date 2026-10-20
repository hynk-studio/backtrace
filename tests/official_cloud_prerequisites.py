"""Run the unchanged private driver's complete CPU setup, never its GPU path.

The actual selected task bytes, offline runtime and root Linux UID boundary
must already exist. No provider API, account credential or launch permit is
used. Private stdout/stderr goes to stderr for encrypted retention by caller.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import cloud_task, cloud_worker
from tools.pod_bootstrap import readonly
from tools.runpod_job import check_owner_host


def qualify(source):
    check_owner_host()
    if any(k in os.environ for k in ('KAGGLE_API_TOKEN', 'RUNPOD_API_KEY', 'GITHUB_TOKEN', 'GH_STATE_TOKEN')):
        raise ValueError('CPU driver check must not inherit account credentials')
    cloud_task.manifest(source)  # Exact prepared closure; never alter the driver.
    stage = Path('/root/backtrace')
    if stage.exists() or stage.is_symlink():
        raise ValueError('fresh root staging required')
    stage.mkdir(mode=0o700)
    shutil.copytree(source, stage / 'driver')
    readonly(stage / 'driver')
    working = Path('/kaggle/working')
    working.mkdir(mode=0o700, parents=True, exist_ok=True)
    command = cloud_worker.workload_command(time.time(), cpu_prerequisites=True)
    assert command[-1] == '--cpu-prerequisites' and '--authorized-run' not in command
    result = subprocess.run(command, env=cloud_worker.CLEAN, umask=0o077,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
    sys.stderr.buffer.write(result.stdout); sys.stderr.flush()
    if result.returncode:
        raise RuntimeError('actual retained CPU prerequisites failed; see encrypted log')
    events = [json.loads(line[len('BACKTRACE '):]) for line in result.stdout.decode().splitlines()
              if line.startswith('BACKTRACE ')]
    names = [row['event'] for row in events]
    required = {'run_begin', 'offline_runtime', 'isolation', 'sandbox_dependency_inheritance',
                'setup_ready', 'cpu_prerequisites_passed', 'worker_cleanup', 'run_end'}
    if not required.issubset(names) or any(name.startswith(('server', 'agent', 'model', 'gpu')) for name in names):
        raise ValueError('CPU qualification event sequence is incomplete or entered GPU path')
    begin = next(row for row in events if row['event'] == 'run_begin')
    end = next(row for row in events if row['event'] == 'run_end')
    if (begin['cpu_prerequisites_only'] is not True or end['worker_cleanup_confirmed'] is not True
            or end['scratch_removed'] is not True or Path('/tmp/backtrace-a100-smoke').exists()
            or (stage / 'launch-permit.json').exists() or (stage / 'launch-permit.consumed').exists()):
        raise ValueError('CPU-only entry or cleanup was not independently confirmed')
    return {'status': 'PASS', 'driver_sha256': cloud_task.CLOUD_DRIVER_SHA256,
            'events': names, 'runtime_path': '/opt/backtrace-runtime',
            'inherited_umask': '077', 'workload_umask': '022', 'workload_uid': 65534,
            'actual_sandbox_dependency_check': 'PASS', 'worker_cleanup': 'PASS',
            'private_log_sha256': hashlib.sha256(result.stdout).hexdigest(),
            'host': 'Actions Ubuntu 24.04 CPU', 'gpu_allocations': 0,
            'server_starts': 0, 'task_executions': 0, 'model_execution': 'NOT RUN'}


if __name__ == '__main__':
    os.umask(0o077)
    if len(sys.argv) != 2:
        raise ValueError('exact prepared driver directory required')
    print(json.dumps(qualify(Path(sys.argv[1])), sort_keys=True))
