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
import shutil
import sys
import sysconfig
import time

STAGING = Path('/root/backtrace')
INPUT = Path('/kaggle/input')
WORKING = Path('/kaggle/working')
MODEL = 'models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
PIP_WHEEL = 'pip-25.0.1-py3-none-any.whl'
PIP_SHA256 = 'c46efd13b6aa8279f33f2864459c8ce587ea6a1a59ee20de055868d8f7688f7f'

# The pinned Ubuntu Python omits ensurepip. Support only the standard venv
# seeding invocation, using the already frozen wheel, without patching harnesses.
VENV_SEED = r'''import argparse,hashlib,os,subprocess,sys
from pathlib import Path
root=Path(SEED_ROOT_TOKEN)
wheel=root/'pip-25.0.1-py3-none-any.whl'
sha='c46efd13b6aa8279f33f2864459c8ce587ea6a1a59ee20de055868d8f7688f7f'
lock='pip==25.0.1 --hash=sha256:'+sha+'\n'
parser=argparse.ArgumentParser(description='Offline pinned pip seed for venv')
parser.add_argument('--upgrade',action='store_true')
parser.add_argument('--default-pip',action='store_true')
parser.parse_args()
if sys.prefix==sys.base_prefix:
 raise SystemExit('pinned seed is restricted to virtual environments')
for p in (root,wheel,root/'bootstrap.lock'):
 if p.is_symlink() or p.resolve()!=p or p.stat().st_uid!=0 or p.stat().st_mode&0o022:
  raise SystemExit('untrusted pip bootstrap path')
with wheel.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=sha:raise SystemExit('pip wheel changed')
if (root/'bootstrap.lock').read_text()!=lock:raise SystemExit('pip lock changed')
program="""import runpy,sys
def audit(event,args):
 if event in ('socket.connect','socket.getaddrinfo','socket.sendto','socket.sendmsg'):
  raise RuntimeError('offline venv seed blocked network access')
sys.addaudithook(audit)
sys.path.insert(0,sys.argv.pop(1))
runpy.run_module('pip',run_name='__main__')
"""
args=[sys.executable,'-I','-c',program,str(wheel),'install','--upgrade',
 '--disable-pip-version-check','--no-index','--no-deps','--require-hashes',
 '--only-binary=:all:','--find-links='+str(root),'-r',str(root/'bootstrap.lock')]
env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':os.environ.get('HOME','/tmp'),
 'PIP_CONFIG_FILE':os.devnull,'PIP_NO_CACHE_DIR':'1','PYTHON_DOTENV_DISABLED':'1'}
subprocess.run(args,env=env,stdin=subprocess.DEVNULL,check=True,timeout=60)
'''


def ensure_venv_seed(wheels, *, stdlib=None, seed_root=Path('/opt/backtrace-bootstrap')):
    """Restore missing venv seeding from frozen pip; never overwrite ensurepip."""
    stdlib = Path(sysconfig.get_path('stdlib') if stdlib is None else stdlib)
    seed_root = Path(seed_root)
    if (os.getuid() != 0 or sys.version_info[:2] != (3, 12)
            or stdlib.resolve() != stdlib or not stdlib.is_dir()
            or stdlib.stat().st_uid != 0 or stdlib.stat().st_mode & 0o022
            or (stdlib / 'ensurepip').exists() or (stdlib / 'ensurepip').is_symlink()
            or not seed_root.is_absolute() or seed_root.parent.resolve() != seed_root.parent):
        raise ValueError('expected root-controlled CPython 3.12 without ensurepip')
    source = Path(wheels) / PIP_WHEEL
    if source.is_symlink() or not source.is_file() or digest(source) != PIP_SHA256:
        raise ValueError('frozen pip bootstrap wheel required')
    code = VENV_SEED.replace('SEED_ROOT_TOKEN', repr(str(seed_root)))
    target = stdlib / 'ensurepip.py'
    if target.exists() or target.is_symlink():
        if (target.is_symlink() or target.read_text() != code
                or target.stat().st_uid != 0 or target.stat().st_mode & 0o022):
            raise ValueError('existing ensurepip is not this reviewed seed')
    if seed_root.exists() or seed_root.is_symlink():
        if (seed_root.is_symlink() or seed_root.resolve() != seed_root
                or {p.name for p in seed_root.iterdir()} != {PIP_WHEEL, 'bootstrap.lock'}
                or any(p.is_symlink() or not p.is_file() for p in seed_root.iterdir())
                or digest(seed_root / PIP_WHEEL) != PIP_SHA256):
            raise ValueError('existing pip seed differs')
    else:
        seed_root.mkdir(mode=0o755)
        shutil.copyfile(source, seed_root / PIP_WHEEL)
    lock = 'pip==25.0.1 --hash=sha256:' + PIP_SHA256 + '\n'
    lock_path = seed_root / 'bootstrap.lock'
    if lock_path.exists():
        if lock_path.is_symlink() or lock_path.read_text() != lock:
            raise ValueError('existing bootstrap lock differs')
    else:
        lock_path.write_text(lock)
    readonly(seed_root)
    if not target.exists():
        with target.open('x') as stream:
            stream.write(code); stream.flush(); os.fsync(stream.fileno())
        os.chown(target, 0, 0); target.chmod(0o444)
    return {'venv_seed': 'pinned offline pip 25.0.1', 'shim_sha256': digest(target)}


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
        ensure_venv_seed(STAGING / 'wheels')
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
