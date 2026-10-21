"""Require recorded real CPU qualification and the current source's full suite."""
import hashlib
import json
import re
import time

from tools import a100_task, cloud_state as state

PATHS = tuple(sorted(set(
    ['tools/' + name for name in a100_task.POD_TOOLS]
    + ['docs/' + name for name in a100_task.POD_DOCS]
    + ['tools/' + name + '.py' for name in (
        'a100_delivery', 'cloud_prepare', 'cloud_resolver', 'cloud_reference', 'cloud_transport',
        'cloud_task', 'cloud_worker', 'cloud_owner', 'cloud_watch', 'cloud_image', 'cloud_qualification',
        'cloud_probe', 'cloud_inventory', 'cloud_seal', 'cloud_state', 'runpod_control', 'runpod_job',
        'ssh_bootstrap', 'direct_delivery', 'private_delivery', 'pod_bootstrap', 'pod_preflight', 'pod_system',
        'api_probe', 'qualify_api', 'qualify_evaluation', 'probe_results', 'qualification_evidence')]
    + ['tests/official_a100_task.py', 'tests/official_cloud_transport.py', 'tests/official_cloud_prerequisites.py',
       'tests/official_cloud_image.py', 'tests/official_cloud_lifecycle.py',
       'tests/test_cloud_state.py', 'tests/test_cloud_owner.py', 'tests/test_runpod_control.py',
       'docs/a100-task-delivery.json', 'docs/a100-result-recipient.txt', 'docs/a100-system-packages.json',
       'docs/a100-api-runtime-amendment.json', 'docs/api-http-minimal.lock',
       '.github/workflows/a100-cpu.yml', 'tests/test_api_readiness.py', 'tests/official_connected_task.py',
       'tests/test_task_results.py', 'tests/official_private_evidence.py',
       'docs/a100-evaluator-dependencies.json', 'tests/test_evaluation.py',
       'docs/cloud-controller-requirements.txt', '.github/workflows/a100-prepare.yml'])))


def file_hashes(root):
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in PATHS}


def require_receipt(store, root, receipt):
    if (set(receipt) != {'schema_version', 'source_sha', 'run_id', 'report_sha256', 'files', 'transport'}
            or receipt['schema_version'] != 1 or not state.SHA.fullmatch(receipt['source_sha'])
            or not re.fullmatch(r'[0-9a-f]{64}', receipt['report_sha256'])
            or receipt['files'] != file_hashes(root)):
        raise ValueError('real CPU qualification does not bind the current input/transport code')
    run = store.request('GET', '/actions/runs/' + str(receipt['run_id']))
    if (run.get('status') != 'completed' or run.get('conclusion') != 'success'
            or run.get('run_attempt') != 1 or run.get('head_sha') != receipt['source_sha']
            or run.get('head_branch') != 'bt-001-connected-qualification'
            or run.get('path') != '.github/workflows/a100-prepare.yml'):
        raise ValueError('actual free qualification run is not successful at the recorded source')
    return {'run_id': receipt['run_id'], 'source_sha': receipt['source_sha'],
            'bound_files': len(PATHS), 'report_sha256': receipt['report_sha256']}


def require_current_cpu(store, source_sha, *, timeout=600, wall=time.monotonic, sleep=time.sleep):
    if not state.SHA.fullmatch(source_sha):
        raise ValueError('exact source required')
    deadline = wall() + timeout
    while wall() < deadline:
        runs = store.request('GET', '/actions/runs?head_sha=' + source_sha + '&per_page=100')['workflow_runs']
        candidates = [r for r in runs if r.get('path') == '.github/workflows/a100-cpu.yml'
                      and r.get('head_branch') == 'bt-001-connected-qualification'
                      and r.get('head_sha') == source_sha and r.get('run_attempt') == 1]
        if len(candidates) > 1:
            raise ValueError('ambiguous current CPU run')
        if candidates and candidates[0]['status'] == 'completed':
            if candidates[0]['conclusion'] != 'success':
                raise ValueError('current full CPU suite failed')
            return {'run_id': candidates[0]['id'], 'source_sha': source_sha, 'status': 'PASS'}
        sleep(min(10, max(0, deadline - wall())))
    raise TimeoutError('current full CPU qualification deadline')
