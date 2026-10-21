"""Qualified free preparation and the explicitly authorized single paid entry.

The paid mode is restricted to its dedicated branch and run attempt 1. It does
not create a watcher, retry a create, reset a claim or change account settings.
"""
import argparse
import contextlib
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import sys
import time

from tools import a100_delivery as frozen, cloud_resolver as resolver, cloud_task, cloud_transport
from tools import cloud_qualification, cloud_offer, cloud_owner, cloud_worker, cloud_state as state
from tools import ssh_bootstrap as ssh, runpod_control as control
from tools.cloud_probe import secret, failure
from tools.runpod_job import check_owner_host, private_json

SAFE_REASONS = frozenset({
    'real root Linux PID namespace required for the owner run host',
    'real CPU qualification does not bind the current input/transport code',
    'actual free qualification run is not successful at the recorded source',
    'exact source required', 'ambiguous current CPU run', 'current full CPU suite failed',
    'rebuilt transport differs from the actual qualified binaries',
    'earlier owned resource requires reconciliation',
    'authorization is already consumed; never recreate',
    'exact workflow context required; paid reruns are forbidden',
})


def validate_context(mode, environ):
    branch = ('bt-001-a100-start-20261021c' if mode == 'paid'
              else 'bt-001-a100-cpu-qualification')
    attempt = environ.get('GITHUB_RUN_ATTEMPT', '')
    if (mode not in ('preflight', 'paid') or environ.get('GITHUB_REPOSITORY') != state.REPOSITORY
            or environ.get('GITHUB_REF_NAME') != branch
            or not re.fullmatch(r'[1-9][0-9]{0,5}', attempt)
            or (mode == 'paid' and attempt != '1')):
        raise state.StateError('exact workflow context required; paid reruns are forbidden')


def preparation(root, store, source_sha, emit):
    emit({'stage': 'owner_host', 'uid': os.getuid(), 'platform': sys.platform,
          'local_pid_namespace': int(Path('/proc/self/stat').read_bytes().split(b' ', 1)[0]) == os.getpid()})
    check_owner_host()
    root.mkdir(mode=0o700, parents=True)
    receipt = json.loads((frozen.ROOT / 'docs/a100-actions-qualification.json').read_text())
    result = {'qualification': cloud_qualification.require_receipt(store, frozen.ROOT, receipt)}
    result['cpu'] = cloud_qualification.require_current_cpu(store, source_sha)
    emit({'stage': 'qualification', 'status': 'PASS', **result})
    built = cloud_transport.build(root / 'transport')
    emit({'stage': 'transport_build', 'binaries': built['binaries']})
    if built['binaries'] != receipt['transport']:
        raise ValueError('rebuilt transport differs from the actual qualified binaries')
    binary = root / 'transport/dropbear-DROPBEAR_2026.94'
    initializer = ssh.prepare(binary / 'dropbear', binary / 'dropbearkey', root / 'ssh',
                              profile=cloud_worker.PROFILE)
    private_json(root / 'ssh/initializer.json', initializer)
    result['transport'] = ssh.validate_material(root / 'ssh', profile=cloud_worker.PROFILE)
    # Exact wire encoding can be checked without spending or consuming a claim.
    request = control.make_request('0' * 32, 0, initializer, transport_profile=cloud_worker.PROFILE)
    result['create_body_bytes'] = len(control.encode_create_request(request))
    with resolver.kaggle_client() as client:
        source = resolver.get_source(client)
        retained = root / 'retained-driver.py'
        retained.write_bytes(resolver.retained_literal(source)); retained.chmod(0o600)
        cloud_task.prepare(retained, root / 'driver')
        streams = {}
        for kind, resolve in (('wheels', resolver.resolve_wheels), ('task', resolver.resolve_task),
                              ('model', resolver.resolve_model)):
            data = frozen.manifest(kind)
            streams[kind] = {'manifest': data.decode(), 'sha256': hashlib.sha256(data).hexdigest(),
                             'sources': resolve(client)}
            emit({'stage': 'source_resolution', 'stream': kind, 'files': len(streams[kind]['sources'])})
    private_json(root / 'worker-inputs.json', streams)
    manifest = cloud_task.manifest(root / 'driver')
    (root / 'driver-manifest.json').write_bytes(manifest)
    (root / 'driver-manifest.json').chmod(0o600)
    result['driver_sha256'] = cloud_task.CLOUD_DRIVER_SHA256
    result['streams'] = {kind: len(row['sources']) for kind, row in streams.items()}
    api = control.RunpodAPI(secret('RUNPOD_API_KEY'))
    pods = api.list()
    if any(p.get('name', '').startswith('backtrace-a100-') for p in pods):
        raise state.StateError('earlier owned resource requires reconciliation')
    if store.read('claim') is not None:
        raise state.StateError('authorization is already consumed; never recreate')
    result['availability'] = cloud_offer.inspect_offer()
    result['allocation_requests'] = 0
    return result, initializer, api


def wait_for_availability(store, source_sha, availability, emit, *, timeout=360,
                          inspect=cloud_offer.inspect_offer, wall=time.time,
                          monotonic=time.monotonic, sleep=time.sleep):
    """Wait freely for stock after preparation; never claim or create here.

    The independent watcher's existing ten-minute unclaimed window still
    applies. A stale/dead watcher or any concurrent claim stops this wait.
    Allocation-inclusive workload deadlines start only at the immutable claim.
    """
    started = monotonic()
    while availability['status'] == 'NO_QUALIFIED_REGION':
        elapsed = monotonic() - started
        if elapsed >= timeout:
            break
        if store.read('claim') is not None:
            raise state.StateError('authorization is already consumed; never recreate')
        state.require_watcher(store, source_sha, int(wall()))
        emit({'stage': 'stock_wait', 'status': 'WAITING',
              'free_wait_elapsed_seconds': int(elapsed), 'allocation_requests': 0})
        sleep(min(20, timeout - elapsed))
        availability = inspect()
    return availability, int(monotonic() - started)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('preflight', 'paid'), required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL); os.umask(0o077)
    stream = sys.stdout
    emit = lambda value: print(json.dumps(value, sort_keys=True), file=stream, flush=True)
    root = frozen.ROOT / '.local/cloud-owner'
    report = {'mode': args.mode, 'allocation_requests': 0, 'status': 'BLOCKED'}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            source_sha, run_id = os.environ['GITHUB_SHA'], os.environ['GITHUB_RUN_ID']
            validate_context(args.mode, os.environ)
            store = state.GitHubState(os.environ['GITHUB_TOKEN'])
            result, initializer, api = preparation(root, store, source_sha, emit)
            report['preparation'] = result
            if args.mode == 'paid':
                result['availability'], result['free_stock_wait_seconds'] = wait_for_availability(
                    store, source_sha, result['availability'], emit)
            if args.mode == 'preflight':
                report['status'] = 'PREPARATION_PASS'
            elif result['availability']['status'] != 'QUALIFIED':
                report['reason'] = result['availability']['status']
            else:
                # This is the only call site that can consume the new claim.
                # The owner lifecycle independently rechecks the watcher lease,
                # source, first run identity, wallet and cost before a single POST.
                report.update(cloud_owner.execute(store, api, result['availability']['offer'], initializer,
                    {'driver': str(root / 'driver'), 'ssh_directory': str(root / 'ssh')},
                    root, run_id, source_sha, emit=emit))
        except Exception as error:
            report['failure'] = failure(error)
            if str(error) in SAFE_REASONS:
                report['failure']['reason'] = str(error)
            if isinstance(error, resolver.ResolutionError):
                report['failure'].update(input_path=error.input_path, cause_type=error.error_type)
        finally:
            if (root / 'owner-result.json').is_file():
                try:
                    report['private_evidence'] = cloud_owner.seal_results(root,
                        frozen.ROOT / 'evidence/a100-owner-private.age')
                except Exception as error:
                    report['private_retention'] = {'status': 'FAILED', 'error_type': type(error).__name__}
                    report['status'] = 'INCOMPLETE'
    emit(report)
    evidence = frozen.ROOT / 'evidence'; evidence.mkdir(exist_ok=True)
    (evidence / 'a100-owner.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    return 0 if report['status'] in ('PREPARATION_PASS', 'COMPLETE') else 1


if __name__ == '__main__':
    raise SystemExit(main())
