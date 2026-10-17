"""Owner-side one-attempt journal, native-expiry gate and independent watchdog.

No CLI command allocates a Pod. The library create path is exercised with a fake
provider only until authenticated expiry readback and delivery are qualified.
Credentials belong to this external controller, never to the agent Pod.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.error
import urllib.request
import uuid

RUN = 'R0-clean-v2-one-public-task/A10080-TP1'
BASE = ('pytorch/pytorch:2.10.0-cuda12.8-cudnn9-runtime@sha256:'
        'b85566342b86d13a67712e9315d40cdc2dad7f8d86df1aff3831f80835edbcca')
GPU = 'NVIDIA A100 80GB PCIe'
TOTAL, USEFUL, STOP = 3000, 2700, 2880
CAP = Decimal('2.00')
ID = re.compile(r'[A-Za-z0-9_-]{1,128}')


def utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result.timestamp()


def money(value):
    if not isinstance(value, str):
        raise ValueError('money values must be decimal strings')
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError('invalid cost') from error
    if not result.is_finite() or result < 0:
        raise ValueError('invalid cost')
    return result


def validate_offer(offer, now):
    exact = {'gpu': GPU, 'gpu_count': 1, 'cloud': 'SECURE', 'region': 'EU-RO-1',
             'container_disk_gb': 100, 'volume_gb': 0, 'network_volume': None,
             'interruptible': False, 'stock_available': True, 'auto_pay': False,
             'authenticated': True, 'image': BASE}
    if any(type(offer.get(k)) is not type(v) or offer.get(k) != v for k, v in exact.items()):
        raise ValueError('offer does not match the authorized configuration')
    if (type(offer.get('vcpus')) is not int or offer['vcpus'] < 8
            or type(offer.get('ram_gb')) is not int or offer['ram_gb'] < 117):
        raise ValueError('insufficient host offer')
    if not 0 <= now - timestamp(offer['observed_at']) <= 300:
        raise ValueError('authenticated offer is stale or from the future')
    compute = money(offer['compute_per_hour'])
    storage = money(offer['storage_per_hour'])
    tax = money(offer['tax_rate'])
    fixed = money(offer['other_total'])
    hourly = (compute + storage) * (1 + tax)
    maximum = hourly * Decimal(TOTAL) / 3600 + fixed
    if maximum > CAP or money(offer['credit_balance']) < hourly + fixed:
        raise ValueError('insufficient existing credit or all-in cap exceeded')
    return {'hourly_all_in': str(hourly), 'other_total': str(fixed),
            'maximum_all_in': str(maximum), 'compute_per_hour': str(compute),
            'storage_per_hour': str(storage), 'tax_rate': str(tax)}


def make_request(attempt, requested_at):
    if not re.fullmatch(r'[0-9a-f]{32}', attempt):
        raise ValueError('unique UUID hex attempt required')
    return {'cloudType': 'SECURE', 'gpuTypeId': GPU, 'gpuCount': 1,
            'dataCenterId': 'EU-RO-1', 'imageName': BASE,
            'containerDiskInGb': 100, 'volumeInGb': 0,
            'minMemoryInGb': 117, 'minVcpuCount': 8,
            'startSsh': True, 'startJupyter': False, 'ports': '22/tcp',
            'name': 'backtrace-a100-' + attempt,
            'stopAfter': utc(requested_at + STOP),
            'terminateAfter': utc(requested_at + TOTAL)}


class ProviderError(RuntimeError):
    """Deliberately excludes response bodies, URLs with secrets and tokens."""


class RunpodAPI:
    def __init__(self, key, opener=None):
        if not key or '\n' in key or '\r' in key:
            raise ValueError('controller API key required')
        self._key = key
        self._open = opener or urllib.request.build_opener(NoRedirect()).open

    def request(self, method, path, body=None, graphql=False, missing=False):
        if graphql:
            url = 'https://api.runpod.io/graphql'
        else:
            if not re.fullmatch(r'/pods(?:/[A-Za-z0-9_-]{1,128}(?:/stop)?)?', path):
                raise ValueError('unsupported provider path')
            url = 'https://rest.runpod.io/v1' + path
        headers = {'Authorization': 'Bearer ' + self._key, 'Content-Type': 'application/json'}
        request = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                         headers=headers, method=method)
        try:
            with self._open(request, timeout=10) as response:
                status = response.status
                raw = response.read(1024**2 + 1)
        except urllib.error.HTTPError as error:
            if missing and error.code == 404:
                return None
            raise ProviderError('provider HTTP ' + str(error.code)) from None
        except (OSError, TimeoutError):
            raise ProviderError('provider transport failure') from None
        if not 200 <= status < 300 or len(raw) > 1024**2:
            raise ProviderError('invalid provider response')
        if not raw:
            return {}  # A successful DELETE acknowledgement is not deletion evidence.
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise ProviderError('invalid provider JSON') from None

    def graphql(self, query, variables=None):
        response = self.request('POST', '', {'query': query, 'variables': variables or {}}, graphql=True)
        if not isinstance(response, dict) or response.get('errors') or not isinstance(response.get('data'), dict):
            raise ProviderError('GraphQL response failed or incomplete')
        return response['data']

    def check_native_contract(self):
        """Input-schema presence alone cannot qualify persistent expiry readback.

        The published spec lists input fields but not the Pod readback fields.
        This therefore fails closed unless authenticated introspection proves
        both queryable fields exist. Never add guessed fields to a paid request.
        """
        result = self.graphql('query { input: __type(name:"PodFindAndDeployOnDemandInput") '
                              '{ inputFields { name type { kind name ofType { kind name } } } } '
                              'pod: __type(name:"Pod") { fields { name } } }')
        try:
            inputs = {r['name']: r['type'] for r in result['input']['inputFields']}
            fields = {r['name'] for r in result['pod']['fields']}
            for name in ('stopAfter', 'terminateAfter'):
                kind = inputs[name]
                if kind['kind'] == 'NON_NULL':
                    kind = kind['ofType']
                if kind['name'] != 'DateTime' or name not in fields:
                    raise ValueError('expiry not queryable')
        except (KeyError, TypeError, ValueError):
            raise ProviderError('native expiry readback contract is not established') from None

    def create(self, payload):
        return self.graphql('mutation($input:PodFindAndDeployOnDemandInput) '
                            '{ podFindAndDeployOnDemand(input:$input) { id name } }',
                            {'input': payload})['podFindAndDeployOnDemand']

    def native_expiry(self, pod_id):
        self.valid_id(pod_id)
        return self.graphql('query($input:PodFilter) { pod(input:$input) '
                            '{ id stopAfter terminateAfter } }', {'input': {'podId': pod_id}})['pod']

    @staticmethod
    def valid_id(pod_id):
        if not isinstance(pod_id, str) or not ID.fullmatch(pod_id):
            raise ValueError('invalid exact Pod ID')

    def get(self, pod_id):
        self.valid_id(pod_id)
        result = self.request('GET', '/pods/' + pod_id, missing=True)
        if result is not None and (not isinstance(result, dict) or result.get('id') != pod_id):
            raise ProviderError('wrong or incomplete Pod readback')
        return result

    def list(self):
        result = self.request('GET', '/pods')
        if not isinstance(result, list) or any(not isinstance(p, dict) or not p.get('id') for p in result):
            raise ProviderError('invalid Pod list')
        return result

    def stop(self, pod_id):
        self.valid_id(pod_id)
        return self.request('POST', '/pods/' + pod_id + '/stop')

    def delete(self, pod_id):
        self.valid_id(pod_id)
        return self.request('DELETE', '/pods/' + pod_id)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ProviderError('provider redirects are refused')


class Journal:
    """One fixed journal per authorization; caller holds an exclusive lock."""
    def __init__(self, directory):
        self.directory = Path(directory).absolute()
        self.path = self.directory / 'a100-attempt.json'
        self.lock = None

    def __enter__(self):
        p = self.directory
        if (not p.is_dir() or p.resolve() != p or p.stat().st_uid != os.getuid()
                or p.stat().st_mode & 0o077):
            raise ValueError('controller directory must be real, private and owner-controlled')
        fd = os.open(p / 'controller.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        self.lock = os.fdopen(fd, 'r+')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.lock.close()
            raise
        return self

    def __exit__(self, *args):
        self.lock.close()

    def read(self):
        if (self.path.is_symlink() or not self.path.is_file()
                or self.path.stat().st_uid != os.getuid() or self.path.stat().st_mode & 0o077):
            raise ValueError('private regular attempt journal required')
        value = json.loads(self.path.read_text())
        if (value['schema_version'] != 1 or value['run'] != RUN
                or value['request'] != make_request(value['attempt'], value['requested_at'])):
            raise ValueError('journal scope changed')
        if value.get('pod_id') is not None:
            RunpodAPI.valid_id(value['pod_id'])
        return value

    def write(self, value, first=False):
        data = json.dumps(value, sort_keys=True, indent=2).encode() + b'\n'
        if first:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
        else:
            fd, temporary = tempfile.mkstemp(prefix='.attempt-', dir=self.directory)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data); stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def begin(api, journal, offer, wall=time.time):
    """Single non-idempotent request, with durable marker written before sending.

    This is a library integration seam, not a ready-to-rent CLI. External launch
    qualification (delivery/SSH/isolation/credential separation) is still needed.
    """
    if journal.path.exists() or journal.path.is_symlink():
        raise ValueError('attempt already consumed; never recreate after restart')
    costs = validate_offer(offer, wall())
    api.check_native_contract()  # Read-only; a known missing contract must stop before spending.
    t0 = int(wall())
    validate_offer(offer, t0)
    attempt = uuid.uuid4().hex
    value = {'schema_version': 1, 'run': RUN, 'attempt': attempt, 'requested_at': t0,
             'request': make_request(attempt, t0), 'costs': costs,
             'phase': 'requested', 'pod_id': None, 'ownership_confirmed': False,
             'native_expiry_verified': False, 'absence_reads': 0, 'events': []}
    journal.write(value, first=True)
    try:
        result = api.create(value['request'])
        bind(value, result)
        journal.write(value)
        expiry = api.native_expiry(value['pod_id'])  # Independent post-create query.
        if (expiry is None or expiry.get('id') != value['pod_id']
                or any(timestamp(expiry[name]) != timestamp(value['request'][name])
                       for name in ('stopAfter', 'terminateAfter'))):
            raise ValueError('native expiry acknowledgement/readback mismatch')
        value['native_expiry_verified'] = True
        value['phase'] = 'allocated'
        journal.write(value)
    except Exception as error:
        value['phase'] = 'cleanup_required'
        value['events'].append({'event': 'create_or_expiry_failed', 'type': type(error).__name__})
        journal.write(value)
        cleanup_once(api, journal, value)
        raise RuntimeError('attempt consumed; allocation/expiry failed; inspect private journal') from None
    return value


def bind(value, pod):
    if not isinstance(pod, dict) or pod.get('name') != value['request']['name']:
        raise ValueError('attempt ownership is not established')
    RunpodAPI.valid_id(pod.get('id'))
    if value['pod_id'] not in (None, pod['id']):
        raise ValueError('another Pod cannot replace this attempt')
    value['pod_id'] = pod['id']
    value['ownership_confirmed'] = True


def cleanup_once(api, journal, value):
    """Bounded pass; uncertain or stopped resources are never called deleted."""
    if value['phase'] == 'deleted':
        return True
    errors = []
    if value['pod_id'] is None:
        try:
            matches = [p for p in api.list() if p.get('name') == value['request']['name']]
            if len(matches) != 1:
                raise ValueError('ambiguous create remains unresolved')
            bind(value, matches[0])
            journal.write(value)
        except Exception as error:
            value['phase'] = 'cleanup_unresolved'
            value['events'].append({'event': 'reconcile_failed', 'type': type(error).__name__})
            journal.write(value)
            return False
    pod_id = value['pod_id']
    if not value['ownership_confirmed']:
        raise ValueError('refuse mutation without attempt ownership')
    # The immutable returned ID + random exact name establish ownership. If a
    # read succeeds and contradicts that name, do not mutate the resource.
    try:
        current = api.get(pod_id)
        if current is not None and current.get('name') != value['request']['name']:
            raise ValueError('Pod ownership changed')
    except ProviderError:
        current = 'unknown'  # A transient read failure must not suppress exact-ID cleanup.
    except Exception:
        value['phase'] = 'ownership_conflict'
        journal.write(value)
        return False
    if current is not None:
        for action in ('stop', 'delete'):
            try:
                getattr(api, action)(pod_id)
            except Exception as error:
                errors.append({'action': action, 'type': type(error).__name__})
    try:
        absent = api.get(pod_id) is None
        listed = api.list()
        absent = absent and not any(p['id'] == pod_id or p.get('name') == value['request']['name'] for p in listed)
        value['absence_reads'] = value['absence_reads'] + 1 if absent else 0
    except Exception as error:
        value['absence_reads'] = 0
        errors.append({'action': 'readback', 'type': type(error).__name__})
    value['phase'] = 'deleted' if value['absence_reads'] >= 2 else 'cleanup_unresolved'
    value['events'].append({'event': 'cleanup_pass', 'errors': errors,
                            'absence_reads': value['absence_reads']})
    # Keep bounded metadata, never store provider raw bodies or account secrets.
    value['events'] = value['events'][-128:]
    journal.write(value)
    return value['phase'] == 'deleted'


def watchdog(api, journal, wall=time.time, monotonic=time.monotonic, sleep=time.sleep):
    """Separate owner process; survives worker failure and can resume journal.

    An owner-only job-status.json heartbeat is written by the future launcher.
    Missing/stale status triggers immediate cleanup; no workload is started here.
    """
    value = journal.read()
    initial_wall, initial_mono = wall(), monotonic()
    last_wall = initial_wall
    while True:
        now = wall()
        elapsed = max(now - value['requested_at'],
                      initial_wall - value['requested_at'] + monotonic() - initial_mono)
        reason = None
        if now < last_wall - 2:
            reason = 'clock_regression'
        last_wall = now
        if value['phase'] == 'deleted':
            return value
        if value['phase'] != 'allocated' or not value['native_expiry_verified']:
            reason = 'incomplete_launch'
        if elapsed >= USEFUL:
            reason = 'useful_deadline'
        projected = (money(value['costs']['hourly_all_in']) * Decimal(str(max(0, elapsed) + 300))
                     / 3600 + money(value['costs']['other_total']))
        if projected > CAP:
            reason = 'projected_budget'
        if reason is None:
            try:
                path = journal.directory / 'job-status.json'
                if path.is_symlink() or path.stat().st_mode & 0o077 or path.stat().st_uid != os.getuid():
                    raise ValueError('private owner heartbeat required')
                status = json.loads(path.read_text())
                if (status['attempt'] != value['attempt'] or status['state'] != 'running'
                        or not 0 <= now - timestamp(status['at']) <= 30):
                    reason = 'job_finished_failed_or_stale'
            except (OSError, KeyError, TypeError, ValueError):
                reason = 'missing_or_invalid_job_status'
        if reason is None:
            try:
                pod = api.get(value['pod_id'])
                if (pod is None or pod.get('name') != value['request']['name']
                        or pod.get('imageName') != BASE or pod.get('gpuCount') != 1
                        or pod.get('volumeInGb') != 0 or pod.get('networkVolumeId')
                        or money(str(pod['costPerHr'])) > money(value['costs']['compute_per_hour'])):
                    reason = 'provider_resource_changed'
            except Exception:
                reason = 'provider_observation_failed'
        if reason:
            value['events'].append({'event': 'cleanup_trigger', 'reason': reason})
            value['phase'] = 'cleanup_required'
            journal.write(value)
        if value['phase'] != 'allocated':
            if cleanup_once(api, journal, value):
                confirmed = wall()
                value['deletion_confirmed_at'] = utc(confirmed)
                # Cleanup/readback itself consumes time. Do not use the stale
                # timestamp taken before network calls for cap compliance.
                final_elapsed = max(confirmed - value['requested_at'],
                                    initial_wall - value['requested_at'] + monotonic() - initial_mono)
                value['deadline_exceeded'] = final_elapsed > TOTAL
                value['request_to_deletion_seconds'] = final_elapsed
                value['billing'] = 'PENDING separate actual billing evidence'
                journal.write(value)
                return value
        # Continue bounded cleanup after the deadline; do not call it free time
        # or guaranteed cap compliance. Resume uses the same immutable attempt.
        if elapsed >= TOTAL + 180:
            value['deadline_exceeded'] = True
            journal.write(value)
            raise RuntimeError('cleanup unconfirmed; same attempt needs immediate reconciliation')
        sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('status', 'watch'))
    parser.add_argument('directory', type=Path)
    parser.add_argument('--api-key-file', type=Path)
    args = parser.parse_args()
    with Journal(args.directory) as journal:
        if args.mode == 'status':
            value = journal.read()
        else:
            p = args.api_key_file
            if (p is None or p.is_symlink() or not p.is_file() or p.stat().st_uid != os.getuid()
                    or p.stat().st_mode & 0o077):
                parser.error('private owner-side API key file required')
            api = RunpodAPI(p.read_text().strip())
            value = watchdog(api, journal)
        print(json.dumps({k: value.get(k) for k in ('run', 'phase', 'pod_id', 'native_expiry_verified',
                                                   'deletion_confirmed_at', 'deadline_exceeded', 'billing')}))


if __name__ == '__main__':
    main()
