"""Read-only native/cgroup-v2 headroom checks; never change resource limits."""
import json
from pathlib import Path, PurePosixPath
import re
import shutil

GIB = 1024**3


def _path(value):
    if (not value.startswith('/') or any(p in ('.', '..') for p in value.split('/'))
            or '\\' in value):
        raise ValueError('unambiguous absolute cgroup path required')
    return PurePosixPath(value)


def locate(cgroup, mountinfo):
    """Resolve the process's unified hierarchy without guessing at namespace roots."""
    lines = [line.split(':', 2) for line in cgroup.splitlines()]
    if len(lines) != 1 or lines[0][:2] != ['0', '']:
        raise ValueError('only a single cgroup-v2 hierarchy is qualified')
    member = _path(lines[0][2]); found = []
    for line in mountinfo.splitlines():
        left, separator, right = line.partition(' - ')
        if not separator or right.split()[0] != 'cgroup2':
            continue
        fields = left.split()
        if len(fields) < 6:
            raise ValueError('invalid cgroup mount record')
        root, mount = _path(fields[3]), _path(fields[4])
        # A subtree/namespace mount hides ancestor limits. Refuse to infer
        # unrestricted memory from its visible root or from physical RAM.
        if root != PurePosixPath('/') or not member.is_relative_to(root):
            raise ValueError('hidden cgroup ancestors require host-side inspection')
        found.append((Path(str(mount/member.relative_to(root))), Path(str(mount))))
    if len(found) != 1:
        raise ValueError('one fully visible cgroup-v2 mount required')
    return found[0]


def assess(meminfo, levels, *, minimum_bytes):
    if type(minimum_bytes) is not int or minimum_bytes <= 0:
        raise ValueError('positive memory requirement required')
    host = {}
    for key in ('MemTotal', 'MemAvailable'):
        values = re.findall(r'^' + key + r':\s+(\d+) kB$', meminfo, re.M)
        if len(values) != 1:
            raise ValueError('host available-memory evidence missing')
        host[key] = int(values[0])*1024
    capacity = [host['MemTotal']]; headroom = [host['MemAvailable']]; rows = []
    for row in levels:
        current = row['memory.current']
        if type(current) is not int or current < 0:
            raise ValueError('invalid cgroup memory use')
        for key in ('memory.max', 'memory.high'):
            value = row[key]
            if value != 'max':
                if type(value) is not int or value < 0:
                    raise ValueError('invalid cgroup memory limit')
                capacity.append(value); headroom.append(max(0, value-current))
        rows.append(dict(row))
    effective = min(capacity); available = min(headroom)
    return {'status': 'PASS' if min(effective, available) >= minimum_bytes else 'INSUFFICIENT',
            'minimum_bytes': minimum_bytes, 'host': host, 'visible_cgroups': rows,
            'effective_capacity_bytes': effective, 'conservative_available_bytes': available,
            'swap_counted_as_ram': False, 'reservation': False,
            'hidden_ancestor_limits': 'MUST_BE_EXCLUDED_BY_NATIVE_HOST_INSPECTION'}


def inspect(*, minimum_bytes=32*GIB, proc=Path('/proc'), read=None):
    read = read or (lambda p: p.read_text())
    member, root = locate(read(proc/'self/cgroup'), read(proc/'self/mountinfo'))
    rows = []
    while member != root:
        row = {'path': str(member)}
        for key in ('memory.current', 'memory.max', 'memory.high'):
            value = read(member/key).strip()
            row[key] = value if value == 'max' else int(value)
        rows.append(row); member = member.parent
    # The true v2 root has no memory.max/current files. Seeing those at the
    # visible root means a cgroup namespace concealed ancestors: fail closed.
    if (root/'memory.max').exists() or (root/'memory.current').exists():
        raise ValueError('namespaced cgroup root hides ancestor memory limits')
    return assess(read(proc/'meminfo'), rows, minimum_bytes=minimum_bytes)


def require(path, *, minimum_bytes=32*GIB, disk_bytes=64*GIB):
    result = inspect(minimum_bytes=minimum_bytes)
    result['disk_free_bytes'] = shutil.disk_usage(path).free
    result['disk_required_bytes'] = disk_bytes
    if result['status'] != 'PASS' or result['disk_free_bytes'] < disk_bytes:
        raise RuntimeError('effective RAM or temporary disk headroom insufficient')
    return result


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True, indent=2))
