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
import traceback

from tools import cloud_state as state, cloud_task, cloud_worker, cloud_seal, cloud_bootstrap
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
    'invalid state object', 'invalid durable document', 'wrong workflow run',
    'bootstrap provider resource is absent', 'bootstrap provider reached a terminal state',
    'bootstrap provider returned an unknown state', 'invalid exact bootstrap endpoint',
})


def update_heartbeat(store, claim, phase, now, previous_sha=None, *, sleep=time.sleep):
    value = {'attempt': claim['attempt'], 'at': int(now), 'phase': phase}
    try:
        return store.write('heartbeat', value, previous_sha=previous_sha)
    except state.StateError as error:
        # Only an already-existing mutable heartbeat may recover from a
        # successful PUT whose immediate readback did not confirm the value.
        # No second PUT, claim recovery, initial-heartbeat recovery or create.
        if previous_sha is None or str(error) != 'durable write not independently confirmed':
            raise
        for attempt in range(3):
            try:
                check = store.read('heartbeat')
            except state.StateError:
                check = None
            if check is not None:
                current, sha = check
                if state.encoded(current) == state.encoded(value):
                    return sha
                if current['attempt'] != value['attempt'] or current['at'] >= value['at']:
                    raise error
            if attempt < 2:
                sleep(.25 * (attempt + 1))
        raise


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
            emit=lambda value: print(json.dumps(value, sort_keys=True), flush=True),
            before_cleanup=None):
    """One immutable claim, at most one POST, cleanup on every exit after claim.

    Tests inject provider and process fixtures. No synthetic result can qualify
    the actual transport, source files, model startup or paid cancellation.
    """
    directory = Path(directory)
    claim = None; pod_record = None; process = None; heartbeat_sha = None
    result = {'allocation_requests': 0, 'worker_exit': None, 'cleanup': None}
    stage = 'claim'
    bootstrap_evidence = {'deadline_seconds': cloud_bootstrap.DEADLINE_SECONDS,
                          'polls': 0, 'history': []}
    try:
        claim, request = state.claim_before_create(store, api, offer, bootstrap, run_id,
                                                   source_sha, wall=wall)
        stage = 'initial_heartbeat'
        heartbeat_sha = update_heartbeat(store, claim, 'setup', wall())
        result['allocation_requests'] = 1  # No retry, including unknown completion.
        stage = 'provider_create'
        created = api.create(request)
        control.RunpodAPI.valid_id(created.get('id'))
        if created.get('name') != claim['name']:
            raise state.StateError('create response did not identify this attempt')
        pod_record = {'attempt': claim['attempt'], 'pod_id': created['id']}
        stage = 'record_pod'
        store.write('pod', pod_record)
        expected = {'request': request, 'region': claim['region'], 'costs': claim['costs']}
        while True:
            now = wall()
            stage = 'bootstrap_deadline'
            if now - claim['requested_at'] >= cloud_bootstrap.DEADLINE_SECONDS:
                raise TimeoutError('bounded bootstrap readiness exceeded')
            stage = 'bootstrap_owner_status'
            owner = store.run(str(run_id))
            if (owner['status'] != 'in_progress' or owner['head_sha'] != source_sha
                    or owner['run_attempt'] != 1
                    or owner['head_branch'] != state.OWNER_BRANCH):
                raise state.StateError('lifecycle deadline or independent watcher failure')
            stage = 'bootstrap_watcher_status'
            watcher = store.run(claim['watcher_run_id'])
            if (watcher['status'] != 'in_progress'
                    or watcher['head_sha'] != source_sha or watcher['run_attempt'] != 1
                    or watcher['head_branch'] != state.WATCH_BRANCH):
                raise state.StateError('lifecycle deadline or independent watcher failure')
            stage = 'bootstrap_resource'
            pod = api.get(pod_record['pod_id'])
            observation = cloud_bootstrap.observe(pod, wall() - claim['requested_at'])
            bootstrap_evidence['polls'] += 1
            bootstrap_evidence['last'] = observation
            bootstrap_evidence['history'] = (bootstrap_evidence['history'] + [observation])[-64:]
            private_json(directory / 'bootstrap-readiness.json', bootstrap_evidence)
            result['bootstrap'] = bootstrap_evidence
            emit({'bootstrap': observation, 'pod_id': pod_record['pod_id']})
            reasons = {'POD_ABSENT': 'bootstrap provider resource is absent',
                       'PROVIDER_TERMINAL': 'bootstrap provider reached a terminal state',
                       'UNKNOWN_PROVIDER_STATE': 'bootstrap provider returned an unknown state',
                       'INVALID_DIRECT_ENDPOINT': 'invalid exact bootstrap endpoint'}
            if observation['readiness'] in reasons:
                raise state.StateError(reasons[observation['readiness']])
            if not control.resource_matches(pod, expected):
                raise state.StateError('assigned resource differs from reviewed offer')
            # A slow read must not start a worker past the bootstrap deadline.
            stage = 'bootstrap_deadline'
            if wall() - claim['requested_at'] >= cloud_bootstrap.DEADLINE_SECONDS:
                raise TimeoutError('bounded bootstrap readiness exceeded')
            stage = 'bootstrap_heartbeat'
            heartbeat_sha = update_heartbeat(store, claim, 'setup', wall(), heartbeat_sha)
            if observation['readiness'] == 'READY':
                stage = 'bootstrap_deadline'
                if wall() - claim['requested_at'] >= cloud_bootstrap.DEADLINE_SECONDS:
                    raise TimeoutError('bounded bootstrap readiness exceeded')
                endpoint = pod['ssh']['direct']
                break
            sleep(min(cloud_bootstrap.POLL_SECONDS,
                      max(0, claim['requested_at'] + cloud_bootstrap.DEADLINE_SECONDS - wall())))
        first_at = wall()
        stage = 'spawn_worker'
        process = spawn(directory, configuration, claim, pod_record['pod_id'], endpoint)
        while process.poll() is None:
            now = wall()
            stage = 'local_heartbeat'
            phase = local_phase(directory, claim, now, first_at=first_at, wall=wall)
            beat = {'attempt': claim['attempt'], 'at': int(now), 'phase': phase}
            stage = 'owner_status'
            owner = store.run(str(run_id))
            reason = state.cleanup_reason(claim, owner, beat, now)
            stage = 'watcher_status'
            watcher = store.run(claim['watcher_run_id'])
            if (reason or watcher['status'] != 'in_progress' or watcher['head_sha'] != source_sha
                    or watcher['run_attempt'] != 1):
                raise state.StateError('lifecycle deadline or independent watcher failure')
            stage = 'running_resource'
            if not control.resource_matches(api.get(pod_record['pod_id']), expected):
                raise state.StateError('assigned resource changed during execution')
            stage = 'publish_heartbeat'
            heartbeat_sha = update_heartbeat(store, claim, phase, now, heartbeat_sha)
            emit({'phase': phase, 'elapsed_seconds': int(now - claim['requested_at']),
                  'pod_id': pod_record['pod_id']})
            sleep(20)
        stage = 'worker_exit'
        result['worker_exit'] = process.returncode
        if process.returncode != 0:
            raise RuntimeError('single worker failed; no paid retry')
    except Exception as error:
        result['failure'] = {'error_type': type(error).__name__,
                             'http_status': getattr(error, 'http_status', None), 'stage': stage}
        if isinstance(error, state.StateError):
            message = str(error)
            http = re.fullmatch(r'durable-state HTTP ([0-9]{3})', message)
            if message in SAFE_STATE_REASONS or http:
                result['failure']['reason'] = message
            if http:
                result['failure']['http_status'] = int(http.group(1))
        if stage.startswith('bootstrap_') and pod_record is not None:
            # A failed log sample is secondary evidence; never mask the first
            # failure or prevent exact-ID deletion. Production API is bounded.
            sample = cloud_bootstrap.sample_logs(api, pod_record['pod_id'])
            bootstrap_evidence['log_sample'] = sample
            result['bootstrap'] = bootstrap_evidence
            try:
                private_json(directory / 'bootstrap-readiness.json', bootstrap_evidence)
            except OSError:
                result['bootstrap_diagnostic_write'] = 'FAILED'
        # Preserve source locations, never exception text, command lines or locals.
        try:
            private_json(directory / 'controller-diagnostic.json', {
                'failure': dict(result['failure']), 'observed_at': wall(),
                'frames': [{'file': Path(frame.filename).name, 'function': frame.name,
                            'line': frame.lineno} for frame in traceback.extract_tb(error.__traceback__)]})
        except OSError:
            result['diagnostic_write'] = 'FAILED'
    finally:
        try:
            stop(process)
        except Exception as error:
            result['worker_stop_error'] = type(error).__name__
        if pod_record is not None and before_cleanup is not None:
            try:
                result['pre_cleanup_diagnostic'] = before_cleanup(pod_record['pod_id'])
            except Exception as error:
                result['pre_cleanup_diagnostic'] = {'status': 'UNAVAILABLE',
                                                     'error_type': type(error).__name__}
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
        'owner-result.json', 'job-status.json', 'setup-status.json', 'controller-diagnostic.json',
        'bootstrap-readiness.json',
        'bootstrap-probe-result.json', 'probe.log',
        'worker.log', 'worker-process.log', 'receipt-transfer.json', 'task-validation.json', 'retrieval-error.json')
        if (directory / name).is_file()}
    receipts = directory / 'receipts'
    if receipts.is_dir():
        for path in sorted(receipts.rglob('*')):
            if path.is_file():
                files['receipts/' + path.relative_to(receipts).as_posix()] = path
    return cloud_seal.seal(files, output)
