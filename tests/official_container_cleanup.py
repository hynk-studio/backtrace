"""Actual Docker absence/presence with authored acknowledgement faults."""
import subprocess
import sys

from tools.free_container_cleanup import ID, remove


def qualify(image, run_id, log):
    results = []
    for case in ('lost-ack', 'false-ack'):
        name = 'backtrace-free-full-setup-' + run_id + '-' + case
        identity = None
        def fault(command, **kwargs):
            if command[1:3] == ['rm', '-f']:
                if case == 'lost-ack':
                    actual = subprocess.run(command, **kwargs)
                    actual.check_returncode()
                    raise subprocess.TimeoutExpired(command, kwargs['timeout'])
                return subprocess.CompletedProcess(command, 0, '', '')
            return subprocess.run(command, **kwargs)
        try:
            result = subprocess.run(['docker', 'run', '-d', '--rm', '--name', name,
                '--network', 'none', '--entrypoint', '/usr/bin/sleep', image, '180'],
                stdout=subprocess.PIPE, stderr=log, text=True, check=True, timeout=30)
            if not ID.fullmatch(result.stdout.strip()):
                raise ValueError('exact created control container identity required')
            identity = result.stdout.strip()
            observed = remove(name, container_id=identity, timeout=60 if case == 'lost-ack' else 3, run=fault)
            if case == 'lost-ack':
                assert observed['status'] == 'PASS' and observed['absence_reads'] == 2
                assert observed['request']['error_type'] == 'TimeoutExpired'
            else:
                assert observed['status'] == 'FAIL' and observed['absence_reads'] == 0
                assert all(x['state'] == 'PRESENT' for x in observed['observations'])
        finally:
            primary = sys.exc_info()[1]
            cleanup = remove(name, container_id=identity)
            if cleanup['status'] != 'PASS':
                if primary is None:
                    raise RuntimeError('free cleanup control itself did not disappear')
                primary.add_note('Separate free cleanup control absence was not confirmed')
        results.append({'case': case, 'status': 'PASS', 'observation': observed,
                        'acknowledgement': 'AUTHORED FAULT', 'container_queries': 'ACTUAL DOCKER',
                        'cleanup_evidence': cleanup})
    return {'status': 'PASS', 'cases': results, 'provider_operations': 0, 'gpu_allocations': 0}
