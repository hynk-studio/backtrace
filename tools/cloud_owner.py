"""Single-create Actions lifecycle, outside the Pod and its credential-free worker.

Requires qualified local inputs, a fresh explicit offer and the independent
watcher's live lease. The dedicated cloud_launch entry never retries a paid create.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from tools import cloud_state as state, cloud_task, cloud_worker, cloud_seal
from tools import runpod_control as control
from tools.runpod_job import private_json, read_private

SAFE_STATE_REASONS = frozenset({
    'worker heartbeat is stale or finished',
    'create response did not identify this attempt',
    'assigned resource differs from reviewed offer',
    'exact root endpoint required',
    'lifecycle deadline or independent watcher failure',
    'assigned resource changed during execution',
    'invalid durable-state response',
    'durable-state transport or JSON failure',
    'durable write not independently confirmed',
})


def update_heartbeat(store, claim, phase, now, previous_sha=None):
    return store.write('heartbeat', {'attempt': claim['attempt'], 'at': int(now), 'phase': phase},
                       previous_sha=previous_sha)


def stop_worker(process):
    if process is None or process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def spawn_worker(directory, configuration, claim, pod_id, endpoint):
    private_json(Path(directory) / 'worker-plan.json',
        {'claim': claim, 'pod_id': pod_id, 'endpoint': endpoint,
         'driver': configuration['driver'], 'ssh_directory': configuration['ssh_directory']})
    # No inherited GitHub, Kaggle or RunPod key. stdin also carries no key.
    with (Path(directory) / 'worker-process.log').open('xb') as log:
        return subprocess.Popen([sys.executable, '-I', '-c',
            'import sys;sys.path.insert(0,' + repr(str(cloud_task.legacy.ROOT))
            + ');from tools.cloud_worker import run;raise SystemExit(0 if run(sys.argv[1])=="finished" else 1)',
            str(directory)], env={'PATH': '/usr/bin:/bin', 'HOME': str(directory), 'LANG': 'C.UTF-8'},
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)


def local_phase(directory, claim, now, *, first_at, wall=None):
    path = Path(directory) / 'job-status.json'
    if not path.exists() and now - first_at < 15:
        return 'setup'
    value = json.loads(read_private(path))
    # The worker can replace its heartbeat after the caller sampled `now`.
    # Observe time after reading, preserving strict future/staleness checks.
    observed_at = now if wall is None else wall()
    if (value['attempt'] != claim['attempt'] or value['state'] not in ('running', 'finished')
            or value['phase'] not in ('setup', 'workload', 'retrieval')
            or (value['state'] == 'finished' and value['phase'] != 'retrieval')
            or not 0 <= observed_at - control.timestamp(value['at']) <= 15):
        raise state.StateError('worker heartbeat is stale or finished')
    return value['phase']


def execute(store, api, offer, bootstrap, configuration, directory, run_id, source_sha, *,
            wall=time.time, sleep=time.sleep, spawn=spawn_worker, stop=stop_worker,
            emit=lambda value: print(json.dumps(value, sort_keys=True), flush=True)):
    """One immutable claim, at most one POST, cleanup on every exit after claim.

    Tests inject provider and process fixtures. No synthetic result can qualify
    the actual transport, source files, model startup or paid cancellation.
    """
    directory = Path(directory)
    claim = None; pod_record = None; process = None; heartbeat_sha = None
    result = {'allocation_requests': 0, 'worker_exit': None, 'cleanup': None}
    try:
        claim, request = state.claim_before_create(store, api, offer, bootstrap, run_id,
                                                   source_sha, wall=wall)
        heartbeat_sha = update_heartbeat(store, claim, 'setup', wall())
        result['allocation_requests'] = 1  # No retry, including unknown completion.
        created = api.create(request)
        control.RunpodAPI.valid_id(created.get('id'))
        if created.get('name') != claim['name']:
            raise state.StateError('create response did not identify this attempt')
        pod_record = {'attempt': claim['attempt'], 'pod_id': created['id']}
        store.write('pod', pod_record)
        expected = {'request': request, 'region': claim['region'], 'costs': claim['costs']}
        while True:
            now = wall()
            if now - claim['requested_at'] >= 1200:
                raise TimeoutError('bounded bootstrap readiness exceeded')
            pod = api.get(pod_record['pod_id'])
            if not control.resource_matches(pod, expected):
                raise state.StateError('assigned resource differs from reviewed offer')
            heartbeat_sha = update_heartbeat(store, claim, 'setup', now, heartbeat_sha)
            endpoint = pod.get('ssh', {}).get('direct')
            if pod['status'] == 'RUNNING' and endpoint:
                if endpoint.get('username') != 'root':
                    raise state.StateError('exact root endpoint required')
                break
            sleep(20)
        first_at = wall()
        process = spawn(directory, configuration, claim, pod_record['pod_id'], endpoint)
        while process.poll() is None:
            now = wall()
            phase = local_phase(directory, claim, now, first_at=first_at, wall=wall)
            beat = {'attempt': claim['attempt'], 'at': int(now), 'phase': phase}
            owner = store.run(str(run_id))
            reason = state.cleanup_reason(claim, owner, beat, now)
            watcher = store.run(claim['watcher_run_id'])
            if (reason or watcher['status'] != 'in_progress' or watcher['head_sha'] != source_sha
                    or watcher['run_attempt'] != 1):
                raise state.StateError('lifecycle deadline or independent watcher failure')
            if not control.resource_matches(api.get(pod_record['pod_id']), expected):
                raise state.StateError('assigned resource changed during execution')
            heartbeat_sha = update_heartbeat(store, claim, phase, now, heartbeat_sha)
            emit({'phase': phase, 'elapsed_seconds': int(now - claim['requested_at']),
                  'pod_id': pod_record['pod_id']})
            sleep(20)
        result['worker_exit'] = process.returncode
        if process.returncode != 0:
            raise RuntimeError('single worker failed; no paid retry')
    except Exception as error:
        result['failure'] = {'error_type': type(error).__name__,
                             'http_status': getattr(error, 'http_status', None)}
        if isinstance(error, state.StateError):
            message = str(error)
            http = re.fullmatch(r'durable-state HTTP ([0-9]{3})', message)
            if message in SAFE_STATE_REASONS or http:
                result['failure']['reason'] = message
            if http:
                result['failure']['http_status'] = int(http.group(1))
    finally:
        try:
            stop(process)
        except Exception as error:
            result['worker_stop_error'] = type(error).__name__
        if claim is not None:
            # Preserve local cleanup ability even if all GitHub writes fail.
            with contextlib.suppress(Exception):
                update_heartbeat(store, claim, 'finished' if result['worker_exit'] == 0 else 'failed',
                                 wall(), heartbeat_sha)
            previous = None
            while wall() < claim['requested_at'] + state.TOTAL + 180:
                try:
                    previous = state.reconcile(api, claim, pod_record, previous, 'owner_finished', wall())
                    if previous['phase'] in ('deleted', 'no_resource_observed'):
                        result['cleanup'] = previous
                        break
                except (state.StateError, control.ProviderError) as error:
                    emit({'owner_cleanup': 'UNRESOLVED', 'error_type': type(error).__name__})
                sleep(10)
            if result['cleanup'] is None:
                result['cleanup'] = {'phase': 'UNRESOLVED', 'pod_id': pod_record['pod_id'] if pod_record else None}
    result['status'] = ('COMPLETE' if result['worker_exit'] == 0 and result['cleanup']
                         and result['cleanup']['phase'] == 'deleted' else 'INCOMPLETE')
    private_json(directory / 'owner-result.json', result)
    return result


def seal_results(directory, output):
    """Never traverse the owner's bootstrap keys, source maps or credential files."""
    directory = Path(directory)
    files = {name: directory / name for name in (
        'owner-result.json', 'job-status.json', 'worker.log', 'worker-process.log', 'receipt-transfer.json')
        if (directory / name).is_file()}
    receipts = directory / 'receipts'
    if receipts.is_dir():
        for path in sorted(receipts.rglob('*')):
            if path.is_file():
                files['receipts/' + path.relative_to(receipts).as_posix()] = path
    return cloud_seal.seal(files, output)
