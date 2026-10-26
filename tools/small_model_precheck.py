"""Prepare the hardware-only checkpoint; real device commands remain explicit."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from tools import exact_teacher as exact, small_model_gpu as gpu
from tools import small_model_runner as runner, small_model_resources as resources
from tools import small_model_lifecycle as life

FILES = ('tools/small_model_resources.py', 'tools/small_model_lifecycle.py',
         'tools/small_model_precheck.py', 'tools/small_model_lifecycle_probe.py',
         'tests/test_small_model_precheck.py', '.github/workflows/small-model-precheck-cpu.yml')


def sources():
    return dict(runner.source_hashes(), **{p: life.digest((exact.ROOT/p).read_bytes()) for p in FILES})


def prepare(output):
    baseline = exact.ROOT/'docs/small-model-gpu-baseline-v1.json'
    value = {'schema': 'small-model-precheck-v1', 'status': 'PREPARED_EXECUTION_DISABLED',
             'source_hashes': sources(), 'paid_authorization': False, 'provider_create_enabled': False,
             'previous_permits_reusable': False, 'gpu_minimum_executed': False,
             'minimum_scope': {'pretrained_requests': 0, 'training_steps': 0, 'weight_download_bytes': 0,
                 'checks': ['native namespace and effective memory', 'exact CUDA runtime and exclusive UUID',
                            'isolated native BF16 matmul and SDPA', 'active-context timeout and parent loss',
                            'idle device observation and fresh kernels after each interruption',
                            'bounded export and two independent resource absence observations']},
             'minimum_host': {'python': '3.12.14', 'native_root_linux': True, 'bwrap_required': True,
                 'fully_visible_cgroup_v2': True, 'minimum_available_ram_bytes': 8*resources.GIB,
                 'minimum_free_disk_bytes': 16*resources.GIB, 'minimum_reported_gpu_bytes': 24*resources.GIB},
             'future_baseline': {'plan_sha256': life.digest(baseline.read_bytes()), 'requests': 36,
                 'separate_random_cuda_requests': 36, 'full_checkpoints_required': True,
                 'minimum_available_ram_bytes': 32*resources.GIB, 'minimum_free_disk_bytes': 64*resources.GIB,
                 'status': 'NOT_RUN; separate scope after hardware qualification'},
             'limits': {'allocation_inclusive_seconds': life.TOTAL,
                 'work_stop_elapsed_seconds': life.TOTAL-life.EXPORT-life.CLEANUP,
                 'export_seconds': life.EXPORT, 'cleanup_seconds': life.CLEANUP, 'automatic_retries': 0},
             'cost_proposal': {'compute_cap_usd': '0.90', 'other_cap_usd': '0.10',
                              'total_cap_usd': '1.00', 'credit_reserve_usd': '0.50'},
             'launch_gate': {'status': 'BLOCKED', 'quote': 'NOT_FETCHED', 'balance': 'NOT_FETCHED',
                 'authorization': 'NONE', 'resource': 'NOT_SELECTED',
                 'provider_bootstrap_and_remote_transport': 'NOT_QUALIFIED_FOR_THIS_PAYLOAD',
                 'independent_remote_watcher_deployment': 'NOT_DEPLOYED',
                 'reason': 'CPU supervision rehearsal is not a paid/distributed launch gate'},
             'interpretation': 'A minimum pass would establish hardware plumbing only, never model capability.'}
    life.write(output, value); return value


HOLD = r'''
job=json.loads(Path('/job.json').read_bytes())
if {n:importlib.metadata.version(n) for n in job['packages']}!=job['packages']:
    raise ValueError('package mismatch')
facts=cuda_check(job)
import torch
x=torch.ones((1024,1024),device='cuda:0',dtype=torch.bfloat16)
y=torch.empty_like(x)
torch.mm(x,x,out=y);torch.cuda.synchronize()
send({'status':'CUDA_CONTEXT_ACTIVE','gpu':facts,'allocated_bytes':torch.cuda.memory_allocated()})
while True:
    torch.mm(x,x,out=y);torch.cuda.synchronize()
'''


def _context_worker(directory):
    raw = runner.WORKER.read_text()
    # Preserve the exact qualified CUDA checks; replace only its CLI footer in
    # this diagnostic's disposable standalone script. No checkpoint is mounted.
    head, separator, footer = raw.rpartition('\nif __name__')
    if not separator or re.sub(r'\s+', '', 'if __name__'+footer) not in (
            "if__name__=='__main__':main()", 'if__name__=="__main__":main()'):
        raise ValueError('qualified worker footer changed')
    path = directory/'context-worker.py'; path.write_text(head+'\n'+HOLD); path.chmod(0o600)
    return path


def active_context(uuid):
    raw = subprocess.check_output(['nvidia-smi', '-i', uuid,
        '--query-compute-apps=gpu_uuid,pid,used_gpu_memory', '--format=csv,noheader,nounits'], timeout=10)
    if len(raw) > 16384:
        raise ValueError('unbounded GPU process inventory')
    rows = [line.split(',') for line in raw.decode().strip().splitlines()]
    if (len(rows) != 1 or len(rows[0]) != 3 or rows[0][0].strip().lower() != uuid.lower()
            or not rows[0][1].strip().isdigit() or int(rows[0][1]) <= 0
            or not rows[0][2].strip().isdigit() or int(rows[0][2]) <= 0):
        raise ValueError('one observable active CUDA context required')
    return {'uuid': uuid, 'pid': int(rows[0][1]), 'used_mib': int(rows[0][2]), 'sha256': life.digest(raw)}


def context_child(config):
    config = json.loads(Path(config).read_bytes())
    root = Path(config['root']); device = config['gpu']
    command = gpu.gpu_command(Path(sys.executable), root/'model', root/'tokenizer', root/'job.json',
                              device, script=root/'context-worker.py', metadata_only=True)
    life.write(root/'staging.json', {'path': str(command.staging)})
    channel = runner.Channel(command, root/'stderr.log')
    try:
        hello = channel.read(time.monotonic()+60)
        if (hello.get('status') != 'CUDA_CONTEXT_ACTIVE' or hello['gpu']['uuid'].lower() != device['uuid'].lower()
                or hello['allocated_bytes'] <= 0):
            raise ValueError('CUDA active-context handshake failed')
        life.write(root/'active.json', hello)
        # The outer diagnostic kills this coordinator while the CUDA worker is
        # active. Normal completion is deliberately impossible.
        while True:
            time.sleep(.1)
    finally:
        channel.close()


def interrupt_context(uuid, output, *, parent_loss):
    device = gpu.inventory(uuid); output.mkdir(mode=0o700)
    for name in ('model', 'tokenizer'):
        (output/name).mkdir(mode=0o700)
    _context_worker(output)
    life.write(output/'job.json', {'packages': gpu.ready.lock()['gpu_candidate']['packages'], 'gpu': device})
    life.write(output/'config.json', {'root': str(output), 'gpu': device})
    with (output/'coordinator.log').open('xb') as log:
        process = subprocess.Popen([sys.executable, '-m', 'tools.small_model_precheck',
            'context-child', str(output/'config.json')], stdin=subprocess.DEVNULL, stdout=log,
            stderr=log, start_new_session=True,
            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'HF_HUB_OFFLINE': '1'})
        try:
            end = time.monotonic()+65
            while not (output/'active.json').exists():
                if process.poll() is not None or time.monotonic() >= end:
                    raise RuntimeError('CUDA context did not become active')
                time.sleep(.05)
            before = active_context(uuid)
            if parent_loss:
                os.kill(process.pid, signal.SIGKILL)  # Do not kill the child group directly.
                process.wait(timeout=5)
            else:
                life.stop(process)
            end = time.monotonic()+20
            while True:
                try:
                    after = gpu.inventory(uuid)
                    break
                except ValueError:
                    if time.monotonic() >= end:
                        raise RuntimeError('GPU context did not clear after interruption')
                    time.sleep(.2)
            # Re-execute actual kernels after context teardown, not merely nvidia-smi.
            result = gpu.device_probe(uuid, output/'after-probe')
            return {'status': 'PASS_ACTUAL_CONTEXT_INTERRUPTION', 'parent_loss': parent_loss,
                    'before': before, 'idle_after': after, 'fresh_kernel_status': result['status'],
                    'driver_fault_recovery': 'NOT_TESTED', 'kill_during_specific_kernel': 'NOT_ESTABLISHED'}
        finally:
            life.stop(process)
            staging = output/'staging.json'
            if staging.exists():
                import shutil
                path = Path(json.loads(runner.regular(staging))['path'])
                if path.parent == Path('/tmp') and path.name.startswith('backtrace-model-worker-'):
                    shutil.rmtree(path, ignore_errors=True)


def minimum(uuid, output):
    output = exact._local_path(output); output.mkdir(mode=0o700, exist_ok=False)
    result = {'status': 'INCOMPLETE', 'pretrained_requests': 0, 'training_steps': 0,
              'source_hashes': sources()}
    try:
        memory = resources.require(output, minimum_bytes=8*resources.GIB, disk_bytes=16*resources.GIB)
        life.write(output/'resources.json', memory)
        result['device'] = gpu.device_probe(uuid, output/'device')
        result['interruption'] = [interrupt_context(uuid, output/name, parent_loss=parent) for name, parent in
                                  (('deadline-context', False), ('parent-loss-context', True))]
        result['status'] = 'PASS_HARDWARE_MINIMUM_ONLY'
    except BaseException as error:
        result['failure'] = {'type': type(error).__name__}
        raise
    finally:
        life.write(output/'receipt.json', result)
    return result


def baseline(uuid, sources_path, models, scope, packets, tokens, output):
    """Future explicit full-model stage, with effective headroom before any copies."""
    resources.require(Path(output).parent)
    return gpu.run_existing(uuid, sources_path, models, scope, packets, tokens, output)


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('prepare'); s.add_argument('output', type=Path)
    s = sub.add_parser('minimum'); s.add_argument('uuid'); s.add_argument('output', type=Path)
    s = sub.add_parser('context-child'); s.add_argument('config', type=Path)
    s = sub.add_parser('baseline'); s.add_argument('uuid')
    for name in ('sources_path', 'models', 'scope', 'packets', 'tokens', 'output'):
        s.add_argument(name, type=Path)
    args = vars(p.parse_args()); command = args.pop('command')
    result = {'prepare': prepare, 'minimum': minimum, 'context-child': context_child, 'baseline': baseline}[command](**args)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
