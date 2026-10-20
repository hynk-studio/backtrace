"""Separate cleanup-only Actions workflow; never allocates or starts a workload."""
import argparse
import json
import os
import time

from tools import cloud_state as state
from tools import runpod_control as control


def starting_lease(store, run_id, source_sha):
    """Hand over only a finished, never-claimed free watcher; never reset a claim."""
    existing = store.read('watcher')
    if existing is None:
        return None
    value, sha = existing
    if value['run_id'] == str(run_id) and value['source_sha'] == source_sha:
        return sha
    if store.read('claim') is not None:
        raise state.StateError('claimed authorization cannot change independent watcher')
    previous = store.run(value['run_id'])
    if (previous['status'] != 'completed' or previous['head_sha'] != value['source_sha']
            or previous['head_branch'] != 'bt-001-a100-watch-20261019'
            or previous['run_attempt'] != 1
            or previous.get('path') != '.github/workflows/a100-watch.yml'):
        raise state.StateError('another independent watcher owns this authorization')
    if store.read('claim') is not None:
        raise state.StateError('claimed authorization cannot change independent watcher')
    # The next write uses this exact blob CAS; Git history retains the prior
    # lease. The ordinary claim/first-attempt/source gates remain unchanged.
    return sha


def watch(store, api, run_id, source_sha, *, wall=time.time, sleep=time.sleep, emit=print):
    started = wall()
    claim, pod_record, previous, reason = None, None, None, None
    lease_sha = starting_lease(store, run_id, source_sha)
    last_wall = started
    while wall() - started < state.TOTAL + 900:
        now = int(wall())
        if now < last_wall - 2:
            reason = 'owner_unobservable'
        last_wall = now
        if claim is None:
            document = store.read('claim')
            if document is not None:
                claim = document[0]
                if claim['watcher_run_id'] != str(run_id) or claim['source_sha'] != source_sha:
                    raise state.StateError('claim binds a different watcher or source')
                recorded = store.read('pod')
                pod_record = recorded[0] if recorded else None
                recorded = store.read('cleanup')
                previous = recorded[0] if recorded else None
            elif now - started >= 600:
                return {'phase': 'no_claim', 'allocation': 'NOT RUN'}
            else:
                lease_sha = store.write('watcher', {'run_id': str(run_id), 'source_sha': source_sha,
                                                   'at': now}, previous_sha=lease_sha)
                sleep(20)
                continue
        if previous and previous['phase'] == 'deleted':
            return previous
        if reason is None:
            try:
                owner = store.run(claim['run_id'])
                recorded = store.read('heartbeat')
                heartbeat = recorded[0] if recorded else None
                reason = state.cleanup_reason(claim, owner, heartbeat, now)
                if pod_record is None:
                    recorded = store.read('pod')
                    pod_record = recorded[0] if recorded else None
            except state.StateError:
                reason = 'owner_unobservable'
        if reason is None and pod_record is not None:
            try:
                pod = api.get(pod_record['pod_id'])
                expected = {'request': {'name': claim['name']}, 'costs': claim['costs'],
                            'region': claim['region']}
                if not control.resource_matches(pod, expected):
                    reason = 'provider_resource_changed'
            except control.ProviderError:
                reason = 'provider_resource_changed'
        if reason is not None:
            try:
                previous = state.reconcile(api, claim, pod_record, previous, reason, now)
                try:
                    recorded = store.read('cleanup')
                    store.write('cleanup', previous, previous_sha=recorded[1] if recorded else None)
                except state.StateError:
                    # Lost GitHub access must not suppress provider cleanup.
                    emit(json.dumps({'durable_cleanup_write': 'FAILED', 'phase': previous['phase']}))
                if previous['phase'] in ('deleted', 'no_resource_observed'):
                    return previous
            except (state.StateError, control.ProviderError) as error:
                emit(json.dumps({'cleanup': 'UNRESOLVED', 'error_type': type(error).__name__}))
        if now - claim['requested_at'] >= state.TOTAL + 180:
            raise state.StateError('cleanup deadline exceeded; reconcile the same attempt')
        sleep(20)
    raise state.StateError('watcher lifetime exhausted; no replacement allocation allowed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--source-sha', required=True)
    args = parser.parse_args()
    try:
        if os.environ.get('GITHUB_REPOSITORY') != state.REPOSITORY:
            raise state.StateError('exact repository required')
        result = watch(state.GitHubState(os.environ['GH_STATE_TOKEN']),
                       control.RunpodAPI(os.environ['RUNPOD_API_KEY'].strip()), args.run_id, args.source_sha)
        print(json.dumps(result, sort_keys=True))
        if result.get('phase') not in ('deleted', 'no_claim', 'no_resource_observed'):
            raise SystemExit(1)
    except Exception as error:
        print(json.dumps({'watcher': 'FAILED', 'error_type': type(error).__name__}))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
