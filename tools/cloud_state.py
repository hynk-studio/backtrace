"""Small public-safe attempt records, independent of an Actions runner's disk.

Only this fixed authorization's JSON metadata can be written. The initial claim
is create-only, never reset, even when a request times out or no Pod is observed.
This module has no allocation CLI and never stores credentials or payload URLs.
"""
import base64
from decimal import Decimal
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import uuid

from tools import runpod_control as control

AUTHORIZATION = 'owner-calibrated-gpu-20261023'
POLICY = 'prepaid10-actions-v1'
REPOSITORY = 'hynk-studio/backtrace'
BRANCH = 'bt-001-a100-state'
DIRECTORY = 'a100-state/' + AUTHORIZATION
OWNER_BRANCH = 'bt-001-a100-start-calibrated-20261023'
WATCH_BRANCH = 'bt-001-a100-watch-calibrated-20261023'
SETUP, USEFUL, TOTAL = 5400, 6900, 7200
DOCUMENTS = frozenset({'claim', 'pod', 'heartbeat', 'watcher', 'cleanup'})
SHA = re.compile(r'[0-9a-f]{40}')


class StateError(RuntimeError):
    pass


class StateConflictError(StateError):
    """An explicit HTTP 409 rejection, not an ambiguous write acknowledgement."""


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def project_claim(value, run_id, source_sha, watcher_run_id):
    """Explicit allowlist; never serialize the local journal/request/bootstrap."""
    result = {k: value[k] for k in ('attempt', 'requested_at', 'region', 'costs')}
    result.update(schema_version=1, authorization=AUTHORIZATION, policy=POLICY,
                  run=control.RUN, run_id=str(run_id), source_sha=source_sha,
                  watcher_run_id=str(watcher_run_id), name='backtrace-a100-' + value['attempt'],
                  setup_seconds=SETUP, useful_seconds=USEFUL, total_seconds=TOTAL)
    validate_claim(result)
    return result


def validate_claim(value):
    fields = {'schema_version', 'authorization', 'policy', 'run', 'attempt', 'requested_at',
              'region', 'costs', 'run_id', 'source_sha', 'watcher_run_id', 'name',
              'setup_seconds', 'useful_seconds', 'total_seconds'}
    if (set(value) != fields or value['schema_version'] != 1
            or value['authorization'] != AUTHORIZATION or value['policy'] != POLICY
            or value['run'] != control.RUN or value['setup_seconds'] != SETUP
            or value['useful_seconds'] != USEFUL or value['total_seconds'] != TOTAL
            or not re.fullmatch(r'[0-9a-f]{32}', value['attempt'])
            or value['name'] != 'backtrace-a100-' + value['attempt']
            or type(value['requested_at']) is not int or value['requested_at'] <= 0
            or not SHA.fullmatch(value['source_sha'])
            or not re.fullmatch(r'[1-9][0-9]{0,19}', value['run_id'])
            or not re.fullmatch(r'[1-9][0-9]{0,19}', value['watcher_run_id'])
            or value['run_id'] == value['watcher_run_id']):
        raise ValueError('invalid immutable cloud claim')
    control.validate_region(value['region'])
    costs = value['costs']
    if set(costs) != {'hourly_all_in', 'other_total', 'maximum_all_in', 'compute_per_hour',
                      'storage_per_hour', 'tax_rate', 'spent_before', 'initial_balance'}:
        raise ValueError('invalid public cost fields')
    for cost in costs.values():
        control.money(cost)
    return value


def validate_document(name, value):
    if name == 'observation' and AUTHORIZATION == 'owner-bootstrap-probe-20261022':
        fields = {'attempt', 'at', 'provider_status', 'readiness',
                  'direct_endpoint_present', 'direct_endpoint_valid', 'log_status', 'log_events'}
        if (not isinstance(value, dict) or set(value) != fields
                or not re.fullmatch(r'[0-9a-f]{32}', value['attempt'])
                or type(value['at']) is not int or value['at'] <= 0
                or value['provider_status'] not in ('PROVISIONING', 'STARTING', 'RUNNING',
                                                   'EXITED', 'ERROR', 'TERMINATED', 'UNKNOWN', 'ABSENT')
                or value['readiness'] not in ('WAIT_PROVIDER_RUNNING', 'WAIT_DIRECT_ENDPOINT',
                    'READY', 'POD_ABSENT', 'PROVIDER_TERMINAL', 'UNKNOWN_PROVIDER_STATE',
                    'INVALID_DIRECT_ENDPOINT')
                or any(type(value[k]) is not bool for k in ('direct_endpoint_present', 'direct_endpoint_valid'))
                or value['log_status'] not in ('SAMPLED', 'UNAVAILABLE', 'TIME_LIMIT')
                or type(value['log_events']) is not int or not 0 <= value['log_events'] <= 32768):
            raise ValueError('invalid diagnostic observation')
        return
    if name == 'claim':
        validate_claim(value)
        return
    allowed = {
        'pod': {'attempt', 'pod_id'},
        'heartbeat': {'attempt', 'at', 'phase'},
        'watcher': {'run_id', 'source_sha', 'at'},
        'cleanup': {'attempt', 'phase', 'pod_id', 'absence_reads', 'at', 'reason'},
    }
    if name not in allowed or not isinstance(value, dict) or set(value) != allowed[name]:
        raise ValueError('unexpected public state fields')
    if name == 'watcher':
        if not re.fullmatch(r'[1-9][0-9]{0,19}', value['run_id']) or not SHA.fullmatch(value['source_sha']):
            raise ValueError('invalid watcher identity')
    elif not re.fullmatch(r'[0-9a-f]{32}', value['attempt']):
        raise ValueError('invalid attempt identity')
    if 'at' in value and (type(value['at']) is not int or value['at'] <= 0):
        raise ValueError('invalid state time')
    if 'pod_id' in value and value['pod_id'] is not None:
        control.RunpodAPI.valid_id(value['pod_id'])
    if name == 'pod' and value['pod_id'] is None:
        raise ValueError('exact Pod identity required')
    if name == 'heartbeat' and value['phase'] not in ('setup', 'workload', 'retrieval', 'finished', 'failed'):
        raise ValueError('invalid worker phase')
    if name == 'cleanup' and (value['phase'] not in ('watching', 'cleanup_required', 'unresolved',
                                                   'deleted', 'no_resource_observed')
            or type(value['absence_reads']) is not int or not 0 <= value['absence_reads'] <= 2
            or value['reason'] not in (None, 'owner_finished', 'owner_cancelled', 'owner_unobservable',
                                      'heartbeat_lost', 'setup_deadline', 'useful_deadline',
                                      'projected_budget', 'provider_resource_changed')):
        raise ValueError('invalid cleanup result')


class GitHubState:
    def __init__(self, token, *, opener=None):
        if not token or '\n' in token or '\r' in token:
            raise ValueError('owner-side GitHub token required')
        self._token = token
        self._open = opener or urllib.request.build_opener(control.NoRedirect()).open

    def request(self, method, path, body=None, *, missing=False):
        request = urllib.request.Request('https://api.github.com/repos/' + REPOSITORY + path,
            data=None if body is None else encoded(body), method=method,
            headers={'Authorization': 'Bearer ' + self._token,
                     'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
                     'Content-Type': 'application/json', 'User-Agent': 'Backtrace-owner-controller'})
        try:
            with self._open(request, timeout=10) as response:
                raw = response.read(1024**2 + 1)
                if not 200 <= response.status < 300 or len(raw) > 1024**2:
                    raise StateError('invalid durable-state response')
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            if missing and error.code == 404:
                return None
            if error.code == 409:
                raise StateConflictError('durable-state HTTP 409') from None
            raise StateError('durable-state HTTP ' + str(error.code)) from None
        except (OSError, TimeoutError, ValueError):
            raise StateError('durable-state transport or JSON failure') from None

    def read(self, name):
        if name not in DOCUMENTS:
            raise ValueError('unknown state document')
        result = self.request('GET', '/contents/' + DIRECTORY + '/' + name + '.json?ref=' + BRANCH,
                              missing=True)
        if result is None:
            return None
        if (result.get('encoding') != 'base64' or result.get('type') != 'file'
                or not SHA.fullmatch(result.get('sha', ''))):
            raise StateError('invalid state object')
        try:
            raw = base64.b64decode(result['content'], validate=False)
            if len(raw) > 32768:
                raise ValueError('oversized state')
            value = json.loads(raw)
            validate_document(name, value)
        except (KeyError, TypeError, ValueError):
            raise StateError('invalid durable document') from None
        return value, result['sha']

    def write(self, name, value, *, previous_sha=None):
        validate_document(name, value)
        if previous_sha is not None and (name in ('claim', 'pod') or not SHA.fullmatch(previous_sha)):
            raise ValueError('immutable claim/identity cannot be updated')
        data = encoded(value)
        body = {'branch': BRANCH, 'message': 'Record A100 ' + name,
                'content': base64.b64encode(data).decode()}
        if previous_sha is not None:
            body['sha'] = previous_sha
        # Different files still share a Git branch head. An unrelated lease
        # commit can explicitly reject this PUT with 409. Retry only that
        # rejection, with the identical body and unchanged file-level CAS.
        # Timeouts, 5xx and lost acknowledgements are never write-retried.
        for attempt in range(3):
            try:
                self.request('PUT', '/contents/' + DIRECTORY + '/' + name + '.json', body)
                break
            except StateConflictError:
                if attempt == 2:
                    raise
                current = self.read(name)
                current_sha = current[1] if current is not None else None
                if current_sha != previous_sha:
                    raise
                time.sleep(.25 * (attempt + 1))
        check = self.read(name)
        if check is None or encoded(check[0]) != data:
            raise StateError('durable write not independently confirmed')
        return check[1]

    def run(self, run_id):
        if not re.fullmatch(r'[1-9][0-9]{0,19}', str(run_id)):
            raise ValueError('exact workflow run ID required')
        result = self.request('GET', '/actions/runs/' + str(run_id))
        if str(result.get('id')) != str(run_id):
            raise StateError('wrong workflow run')
        return {k: result.get(k) for k in ('id', 'status', 'conclusion', 'head_sha', 'head_branch', 'run_attempt')}


def cloud_costs(offer, now):
    costs = control.validate_offer(offer, now)
    maximum = control.money(costs['hourly_all_in']) * Decimal(TOTAL) / 3600 + control.money(costs['other_total'])
    if maximum + control.money(costs['spent_before']) > control.CAP:
        raise ValueError('two-hour cumulative budget exceeds existing USD 8 stop')
    costs['maximum_all_in'] = str(maximum)
    return costs


def require_watcher(store, source_sha, now):
    document = store.read('watcher')
    if document is None:
        raise StateError('independent cleanup workflow is not ready')
    value = document[0]
    if value['source_sha'] != source_sha or not 0 <= now - value['at'] <= 60:
        raise StateError('independent cleanup lease is stale or differs from source')
    run = store.run(value['run_id'])
    if (run['status'] != 'in_progress' or run['head_sha'] != source_sha
            or run['head_branch'] != WATCH_BRANCH or run['run_attempt'] != 1):
        raise StateError('independent cleanup run is not qualified')
    return value['run_id']


def claim_before_create(store, api, offer, bootstrap, run_id, source_sha, *, wall=time.time):
    """Integration seam; caller must finish input/driver qualification beforehand.

    This function intentionally returns the prepared request without calling
    create. A caller may send it ONCE only after this function returns. Any
    exception, restart, cancellation, or existing claim consumes the authorization.
    """
    now = int(wall())
    costs = cloud_costs(offer, now)
    if store.read('claim') is not None:
        raise StateError('cloud authorization already consumed; do not recreate')
    watcher = require_watcher(store, source_sha, now)
    run = store.run(str(run_id))
    if (run['status'] != 'in_progress' or run['head_sha'] != source_sha
            or run['head_branch'] != OWNER_BRANCH or run['run_attempt'] != 1):
        raise StateError('first, exact owner workflow run required')
    if any(p.get('name', '').startswith('backtrace-a100-') for p in api.list()):
        raise StateError('earlier owned Pod requires reconciliation')
    attempt = uuid.uuid4().hex
    now = int(wall()); costs = cloud_costs(offer, now)
    value = project_claim({'attempt': attempt, 'requested_at': now, 'region': offer['region'],
                           'costs': costs}, run_id, source_sha, watcher)
    request = control.make_request(attempt, now, bootstrap, region=offer['region'],
                                   transport_profile='actions-20261019')
    control.encode_create_request(request)
    store.write('claim', value)  # create-only + readback before any provider POST
    require_watcher(store, source_sha, int(wall()))
    if wall() - now > 30:
        raise StateError('claim/create interval exceeded; authorization remains consumed')
    return value, request


def cleanup_reason(claim, owner_run, heartbeat, now):
    validate_claim(claim)
    elapsed = now - claim['requested_at']
    if owner_run is None or owner_run['head_sha'] != claim['source_sha']:
        return 'owner_unobservable'
    if owner_run['status'] != 'in_progress':
        return 'owner_cancelled' if owner_run.get('conclusion') == 'cancelled' else 'owner_finished'
    if elapsed >= USEFUL:
        return 'useful_deadline'
    projected = (control.money(claim['costs']['hourly_all_in']) * Decimal(str(max(0, elapsed) + 300))
                 / 3600 + control.money(claim['costs']['other_total'])
                 + control.money(claim['costs']['spent_before']))
    if projected > control.CAP:
        return 'projected_budget'
    if heartbeat is None:
        return 'heartbeat_lost' if elapsed > 90 else None
    if (heartbeat['attempt'] != claim['attempt'] or not 0 <= now - heartbeat['at'] <= 90
            or heartbeat['phase'] in ('finished', 'failed')):
        return 'heartbeat_lost'
    if heartbeat['phase'] == 'setup' and elapsed >= SETUP:
        return 'setup_deadline'
    return None


def reconcile(api, claim, pod_record, previous, reason, now):
    """Cleanup-only pass: exact attempt identity, stop/delete, two absence reads.

    An unknown create response is found by its immutable random name. If none
    is found, do not claim deletion; the initial claim still blocks allocation.
    Provider errors propagate for another cleanup-only pass, never a new create.
    """
    validate_claim(claim)
    if pod_record is not None:
        validate_document('pod', pod_record)
        if pod_record['attempt'] != claim['attempt']:
            raise StateError('Pod record belongs to another attempt')
        pod_id = pod_record['pod_id']
    else:
        matches = [p for p in api.list() if p.get('name') == claim['name']]
        if len(matches) > 1:
            raise StateError('multiple exact-name resources; manual reconciliation required')
        pod_id = matches[0]['id'] if matches else None
    if previous is not None:
        validate_document('cleanup', previous)
        if previous['attempt'] != claim['attempt'] or (previous['pod_id'] and pod_id
                                                       and previous['pod_id'] != pod_id):
            raise StateError('cleanup identity changed')
        if pod_id is None:
            pod_id = previous['pod_id']
    absent = False
    if pod_id is not None:
        current = api.get(pod_id)
        if current is not None and current.get('name') != claim['name']:
            raise StateError('exact Pod ID no longer belongs to this attempt')
        if current is not None:
            try:
                api.stop(pod_id)
            except control.ProviderError:
                pass  # Stop failure cannot suppress exact-ID deletion.
            api.delete(pod_id)
        absent = api.get(pod_id) is None
    listed = api.list()
    absent = (absent if pod_id else now - claim['requested_at'] >= 90) and not any(
        p['id'] == pod_id or p.get('name') == claim['name'] for p in listed)
    count = min(2, 1 + (previous['absence_reads'] if previous else 0)) if absent else 0
    phase = ('deleted' if pod_id else 'no_resource_observed') if count == 2 else 'unresolved'
    result = {'attempt': claim['attempt'], 'phase': phase, 'pod_id': pod_id,
              'absence_reads': count, 'at': int(now), 'reason': reason}
    validate_document('cleanup', result)
    return result
