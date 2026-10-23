"""Bounded absence confirmation for this project's disposable CPU containers.

A Docker CLI timeout is an ambiguous acknowledgement, not a deletion result.
Never treat a failed daemon query or a still-present container as absence.
This helper has no paid-provider operations and is not shipped to the GPU Pod.
"""
import math
import re
import subprocess
import time

OWNED = re.compile(r'backtrace-free-full-setup-[1-9][0-9]{0,19}(?:-[a-z0-9-]{1,32})?')
ID = re.compile(r'[0-9a-f]{64}')


def remove(name, *, container_id=None, timeout=120, run=subprocess.run,
           wall=time.monotonic, sleep=time.sleep):
    if (not isinstance(name, str) or not (OWNED.fullmatch(name) or name == 'backtrace-free-image-qualification')
            or container_id is not None and (not isinstance(container_id, str) or not ID.fullmatch(container_id))
            or type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0):
        raise ValueError('owned free CPU container and finite cleanup deadline required')
    started = wall(); deadline = started + timeout
    report = {'status': 'FAIL', 'name': name, 'container_id': container_id,
              'absence_reads': 0, 'observations': [], 'request': None}
    try:
        result = run(['docker', 'rm', '-f', container_id or name], capture_output=True,
                     text=True, timeout=min(30, max(.001, deadline - wall())))
        report['request'] = {'outcome': 'ACKNOWLEDGED' if result.returncode == 0 else 'ERROR',
                             'returncode': result.returncode}
    except (subprocess.SubprocessError, OSError) as error:
        report['request'] = {'outcome': 'UNCONFIRMED', 'error_type': type(error).__name__}
    while wall() < deadline:
        try:
            result = run(['docker', 'container', 'ls', '--all', '--no-trunc',
                '--filter', 'name=' + name, '--format', '{{.ID}} {{.Names}}'],
                capture_output=True, text=True, timeout=min(10, deadline - wall()))
            if result.returncode != 0:
                raise OSError('daemon observation failed')
            rows = []
            for line in result.stdout.splitlines():
                fields = line.split()
                if len(fields) != 2 or not ID.fullmatch(fields[0]):
                    raise ValueError('malformed container observation')
                if fields[1] == name:
                    rows.append(fields[0])
            if len(rows) > 1 or rows and container_id is not None and rows != [container_id]:
                report['observations'].append({'state': 'IDENTITY_MISMATCH'})
                break
            state = 'PRESENT' if rows else 'ABSENT'
            report['absence_reads'] = 0 if rows else report['absence_reads'] + 1
            report['observations'].append({'state': state})
            if report['absence_reads'] == 2:
                report['status'] = 'PASS'
                break
        except (subprocess.SubprocessError, OSError, ValueError) as error:
            report['absence_reads'] = 0
            report['observations'].append({'state': 'UNKNOWN', 'error_type': type(error).__name__})
        sleep(min(1, max(0, deadline - wall())))
    report['seconds'] = round(wall() - started, 3)
    return report
