"""Root-side offline activation. Run via authenticated SSH, never as the agent.

Input paths become root-owned and read-only to the dropped UID. This does not
require a privileged container or falsely claim an OS read-only bind mount.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import time

STAGING = Path('/root/backtrace')
INPUT = Path('/kaggle/input')
WORKING = Path('/kaggle/working')
MODEL = 'models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked_tree(root, manifest_sha256):
    root = Path(root)
    data = (root / 'delivery-manifest.json').read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest_sha256 or root.resolve() != root:
        raise ValueError('untrusted received tree')
    value = json.loads(data)
    names = set()
    for row in value['files']:
        name = row['path']
        if (PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts
                or name in names or name == 'delivery-manifest.json'):
            raise ValueError('unsafe input path')
        path = root / name
        if (not stat.S_ISREG(path.lstat().st_mode) or path.resolve() != path
                or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']):
            raise ValueError('received input changed')
        names.add(name)
    actual = list(root.rglob('*'))
    if (any(p.is_symlink() for p in actual)
            or {p.relative_to(root).as_posix() for p in actual if p.is_file()} != names | {'delivery-manifest.json'}):
        raise ValueError('unexpected input file')
    return value


def readonly(root):
    """Permissions enforce the agent boundary; retain execute bits for venvs."""
    root = Path(root)
    for path in sorted(root.rglob('*'), reverse=True):
        if path.is_symlink():
            # venv python links are expected; caller never passes input links.
            continue
        os.chown(path, 0, 0)
        path.chmod(0o555 if path.is_dir() or path.stat().st_mode & 0o111 else 0o444)
    os.chown(root, 0, 0); root.chmod(0o555)


def activate(manifests, requested_at, *, runtime=True):
    """Verify all bytes first, then activate exact logical generation inputs."""
    if os.getuid() != 0 or set(manifests) != {'driver', 'wheels', 'task', 'model'}:
        raise ValueError('root and complete frozen streams required')
    if not 0 <= time.time() - requested_at < 1200:
        raise ValueError('setup deadline exhausted')
    checked = {kind: checked_tree(STAGING / kind, sha) for kind, sha in manifests.items()}
    destinations = {'task': INPUT / 'r0-inputs', 'model': INPUT / MODEL}
    if any(p.exists() or p.is_symlink() for p in destinations.values()):
        raise ValueError('logical inputs already exist; no reuse')
    for kind, target in destinations.items():
        source = STAGING / kind
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if target.parent.resolve() != target.parent:
            raise ValueError('logical input parent is a link')
        (source / 'delivery-manifest.json').unlink()
        source.rename(target)
        readonly(target)
    readonly(STAGING / 'driver')
    WORKING.mkdir(mode=0o700, parents=True, exist_ok=True)
    environment = STAGING / 'runtime'
    if runtime:
        code = STAGING / 'driver/tools/linux_runtime.py'
        remaining = 1200 - (time.time() - requested_at)
        subprocess.run(['/usr/bin/python3.12', '-I', str(code), str(STAGING / 'wheels'),
                        str(STAGING / 'driver/docs/linux-supplemental.lock'), str(environment)],
                       check=True, timeout=max(0.001, remaining),
                       env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/root',
                            'PYTHON_DOTENV_DISABLED': '1', 'HF_HUB_OFFLINE': '1'})
        # The venv is used by UID 65534. Move it to a traversable fixed path;
        # venv interpreters do not need their generated pip launcher shebangs.
        public = Path('/opt/backtrace-runtime')
        if public.exists() or public.is_symlink():
            raise ValueError('runtime path already exists')
        environment.rename(public)
        readonly(public)
    if time.time() - requested_at >= 1200:
        raise ValueError('setup deadline exhausted after activation')
    return {'activation': 'PASS', 'input_access': 'root-owned / agent read-only permissions',
            'manifests': dict(manifests), 'runtime': 'PASS' if runtime else 'NOT RUN'}
