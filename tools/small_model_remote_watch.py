"""Bounded independent GitHub-runner observation, with no paid target armed.

Separate source/run/boot identities and create-only/CAS records exercise actual
cross-host liveness. The deployed mode can only read Runpod; it cannot allocate,
delete, accept an authorization or adopt an old claim. A future paid cleanup
adapter still needs an explicit resource binding and qualification.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from tools.research_entry_state import State as Wire, StateError
from tools.small_model_provider import ReadOnlyAPI, inventory

BRANCH = 'bt-001-small-model-provider-20261027'
STATE = 'bt-001-small-model-provider-state-20261027'
NAMES = {'owner', 'watch', 'owner-heartbeat', 'watch-heartbeat', 'ready', 'observed', 'done'}
MUTABLE = {'owner-heartbeat', 'watch-heartbeat'}
WAIT, STALE, POLL = 240, 30, 5


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


class State(Wire):
    def __init__(self, token, source, **kw):
        if not re.fullmatch('[0-9a-f]{40}', source):
            raise ValueError('immutable source required')
        super().__init__(token, 'small-free-'+source, **kw)
        self.source = source

    def path(self, name):
        if name not in NAMES:
            raise ValueError('only free observation records are allowed')
        return '/contents/small-provider/'+self.source+'/'+name+'.json'

    def read(self, name):
        row = self.request('GET', self.path(name)+'?ref='+STATE, missing=True)
        if row is None:
            return None
        raw = base64.b64decode(row['content'])
        sha = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if row['type'] != 'file' or row['encoding'] != 'base64' or len(raw)>65536 or row['sha'] != sha:
            raise StateError('state integrity')
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get('source_sha') != self.source:
            raise StateError('state binding')
        return value, sha

    def write(self, name, value, previous=None):
        if previous is not None and (name not in MUTABLE or not re.fullmatch('[0-9a-f]{40}', previous)):
            raise ValueError('immutable or invalid CAS')
        if value.get('source_sha') != self.source:
            raise ValueError('source mismatch')
        raw = encoded(value)
        if len(raw) > 65536:
            raise ValueError('state size')
        body = {'branch': STATE, 'message': 'Record bounded small-model observer '+name,
                'content': base64.b64encode(raw).decode()}
        if previous:
            body['sha'] = previous
        for attempt in range(4):
            try:
                self.request('PUT', self.path(name), body)
                break
            except StateError as error:
                check = self.read(name)
                if check and encoded(check[0]) == raw:
                    return check[1]
                if str(error) == 'state HTTP 409' and (check[1] if check else None) == previous and attempt < 3:
                    time.sleep(.2*(attempt+1))
                    continue
                raise
        check = self.read(name)
        if not check or encoded(check[0]) != raw:
            raise StateError('write not confirmed')
        return check[1]

    def initialize(self):
        if self.request('GET', '/git/ref/heads/'+STATE, missing=True) is None:
            try:
                self.request('POST', '/git/refs', {'ref': 'refs/heads/'+STATE, 'sha': self.source})
            except StateError:
                if self.request('GET', '/git/ref/heads/'+STATE, missing=True) is None:
                    raise


def validate_run(run, row, role, source):
    if (str(run['id']) != row['run_id'] or run['head_sha'] != source or run['run_attempt'] != 1
            or run['head_branch'] != BRANCH or run['event'] != 'push'
            or run['path'] != '.github/workflows/small-model-provider-'+role+'.yml'
            or run['status'] != 'in_progress' or row['source_sha'] != source or row['role'] != role
            or not re.fullmatch('[0-9a-f]{64}', row['boot_sha256'])):
        raise ValueError('independent live source-bound workflow required')


def fresh(beat, source, rid, now):
    if beat is None:
        return False
    row = beat[0]
    return (row.get('source_sha') == source and row.get('run_id') == rid
            and type(row.get('at')) in (int, float) and 0 <= now-row['at'] < STALE)


def run(role):
    if (role not in ('owner', 'watch') or os.environ['GITHUB_REF_NAME'] != BRANCH
            or os.environ['GITHUB_RUN_ATTEMPT'] != '1'):
        raise ValueError('first-run free deployment only')
    source, rid = os.environ['GITHUB_SHA'], os.environ['GITHUB_RUN_ID']
    state = State(os.environ['GITHUB_TOKEN'], source); state.initialize()
    row = {'source_sha': source, 'run_id': rid, 'role': role, 'at': time.time(),
           'boot_sha256': hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()}
    validate_run(state.run(rid), row, role, source)
    state.write(role, row)
    peer_role = 'watch' if role == 'owner' else 'owner'; end = time.monotonic()+WAIT
    while True:
        peer = state.read(peer_role)
        if peer:
            peer = peer[0]; break
        if time.monotonic() >= end:
            raise TimeoutError('counterpart deployment absent')
        time.sleep(POLL)
    validate_run(state.run(peer['run_id']), peer, peer_role, source)
    if peer['run_id'] == rid or peer['boot_sha256'] == row['boot_sha256']:
        raise ValueError('separate workflow and kernel boot identity required')
    result = {'source_sha': source, 'run_id': rid, 'counterpart_run_id': peer['run_id'],
              'role': role, 'independent_boots': True, 'status': 'INCOMPLETE',
              'mode': 'DEPLOYED_READ_ONLY_NO_TARGET', 'authorization_created': False,
              'provider_mutations': 0, 'gpu_minimum': 'NOT_RUN', 'paid_cleanup_armed': False}
    api = ReadOnlyAPI(os.environ['RUNPOD_API_KEY'].strip())
    result['inventory_before'] = inventory(api)
    initial = {'source_sha': source, 'run_id': rid, 'at': time.time()}
    sha = state.write(role+'-heartbeat', initial)
    if role == 'owner':
        while not state.read('ready'):
            if time.monotonic() >= end:
                raise TimeoutError('remote watcher not ready')
            sha = state.write('owner-heartbeat', dict(initial, at=time.time()), sha); time.sleep(POLL)
        # Real heartbeat cessation after a live handshake; no signal or paid
        # resource is involved. The independent workflow must detect staleness.
        for _ in range(3):
            sha = state.write('owner-heartbeat', dict(initial, at=time.time()), sha); time.sleep(POLL)
        ceased = time.time()
        while not state.read('observed'):
            if time.monotonic() >= end:
                raise TimeoutError('remote stale-heartbeat detection absent')
            time.sleep(POLL)
        observed = state.read('observed')[0]
        if (observed['reason'] != 'OWNER_HEARTBEAT_STALE' or observed['owner_run_id'] != rid
                or observed['watch_run_id'] != peer['run_id'] or observed['age_seconds'] < STALE):
            raise ValueError('remote observation mismatch')
        result.update(heartbeat_cessation_at=ceased, remote_observation=observed)
        state.write('done', dict(initial, at=time.time(), watch_run_id=peer['run_id']))
    else:
        while not fresh(state.read('owner-heartbeat'), source, peer['run_id'], time.time()):
            if time.monotonic() >= end:
                raise TimeoutError('fresh owner heartbeat absent')
            time.sleep(POLL)
        state.write('ready', dict(initial, owner_run_id=peer['run_id']))
        samples = 0
        while True:
            sha = state.write('watch-heartbeat', dict(initial, at=time.time()), sha)
            beat = state.read('owner-heartbeat'); now = time.time(); samples += 1
            if not fresh(beat, source, peer['run_id'], now):
                if not beat or beat[0].get('run_id') != peer['run_id'] or beat[0].get('at', now+1)>now:
                    raise StateError('lost/mismatched state is UNKNOWN, not stale evidence')
                observed = dict(initial, at=now, reason='OWNER_HEARTBEAT_STALE',
                    age_seconds=now-beat[0]['at'], owner_run_id=peer['run_id'], watch_run_id=rid,
                    action='NO_TARGET_NO_PROVIDER_MUTATION')
                state.write('observed', observed); break
            if time.monotonic() >= end:
                raise TimeoutError('bounded observation deadline')
            time.sleep(POLL)
        while not state.read('done'):
            if time.monotonic() >= end:
                raise TimeoutError('owner acknowledgement absent')
            time.sleep(POLL)
        result.update(heartbeat_samples=samples, remote_observation=observed)
    result['inventory_after'] = inventory(api)
    result.update(status='PASS', terminated=True, persistent_monitoring=False,
                  cleanup_of_live_resource='NOT_TESTED_NO_RESOURCE')
    return result


if __name__ == '__main__':
    role = sys.argv[1]; root = Path('evidence'); root.mkdir(exist_ok=True)
    try:
        result = run(role)
    except Exception as error:
        result = {'status': 'FAIL', 'error_type': type(error).__name__, 'provider_mutations': 0,
                  'source_sha': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID')}
    (root/('remote-'+role+'.json')).write_bytes(encoded(result)); print(json.dumps(result))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
