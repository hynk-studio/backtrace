"""Actual pinned container on free CPU, offline, with no model or service keys."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import a100_delivery as frozen, cloud_task, pod_bootstrap, pod_preflight
from tests.official_cloud_prerequisites import qualify as prerequisites


def qualify():
    if any(k in os.environ for k in ('RUNPOD_API_KEY', 'KAGGLE_API_TOKEN', 'GITHUB_TOKEN', 'GH_STATE_TOKEN')):
        raise ValueError('container qualification must not inherit credentials')
    os.umask(0o077)
    stage = Path('/root/backtrace'); stage.mkdir(mode=0o700, exist_ok=True); stage.chmod(0o700)
    report = {'host': 'exact pinned RunPod image on Actions CPU', 'gpu_allocations': 0,
              'network': 'NONE', 'model_bytes_downloaded': 0, 'stages': {}}
    report['stages']['base'] = pod_preflight.base(8 * 1024**3)
    source = Path('/inputs/driver')
    manifest = cloud_task.manifest(source)
    shutil.copytree(source, stage / 'driver')
    # The source closure uses an external manifest during SSH delivery.
    (stage / 'driver/delivery-manifest.json').write_bytes(manifest)
    hashes = {'driver': hashlib.sha256(manifest).hexdigest(),
              'wheels': hashlib.sha256(frozen.manifest('wheels')).hexdigest()}
    requested = time.time()
    report['stages']['runtime_installation'] = pod_bootstrap.prepare_runtime(hashes, requested)
    report['stages']['runtime'] = pod_preflight.runtime(require_gpu=False)
    pod_bootstrap.require_prepared_runtime(hashes, requested)
    # Remove the transport-only manifest before the driver's exact closure check.
    (stage / 'driver/delivery-manifest.json').unlink()
    task = Path('/inputs/task')
    pod_bootstrap.checked_tree(task, hashlib.sha256(frozen.manifest('task')).hexdigest())
    target = Path('/kaggle/input/r0-inputs')
    pod_bootstrap.input_parent(target)
    shutil.copytree(task, target); (target / 'delivery-manifest.json').unlink()
    pod_bootstrap.readonly(target)
    report['stages']['actual_cpu_prerequisites'] = prerequisites(source, staged=True, host=report['host'])
    report.update(status='PASS', gpu_initialization='NOT RUN', server_starts=0, task_executions=0)
    return report


if __name__ == '__main__':
    result = qualify()
    output = Path('/result/image.json')
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    output.chmod(0o644)  # Explicitly projected report, readable by the CPU runner.
