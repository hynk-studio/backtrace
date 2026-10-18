"""Pinned, offline SSH control transport for the unchanged public base image.

This is separate from the serving wheel closure. No package manager, downloads,
API credentials, password login or account-wide SSH key changes occur in a Pod.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zlib

TRANSPORT = {
    'version': '2026.94',
    'source_url': 'https://codeload.github.com/mkj/dropbear/tar.gz/refs/tags/DROPBEAR_2026.94',
    'source_bytes': 2923600,
    'source_sha256': '827d3f6e510e7554ee18d5c6a00dfee1a6a555559495e65e2e8f8d41c79eed84',
    'binary_sha256': 'aacad0b42337921f2f1be2c952df6d20d50c73ee419b3d6e04760cc753275d8c',
    'keygen_sha256': '50200a9c67332a948176022618e51e3aff68d339d63712d1e0a5d101fa74f8c5',
}

# Literal, reviewed program. The larger compressed binary is split into small
# env entries, keeping every exec argument below Linux's per-string limit.
START = r'''import base64,hashlib,os,zlib
from pathlib import Path
os.umask(0o077)
assert os.getuid()==0
root=Path('/root/backtrace');root.mkdir(mode=0o700)
data=zlib.decompress(base64.b64decode(''.join(os.environ[k] for k in sorted(os.environ) if k.startswith('BT_SSH_PART_'))))
assert hashlib.sha256(data).hexdigest()==os.environ['BT_SSH_SHA']
binary=root/'dropbear';binary.write_bytes(data);binary.chmod(0o700)
host=root/'host-key';host.write_bytes(base64.b64decode(os.environ['BT_SSH_HOST_KEY']));host.chmod(0o600)
ssh=root/'auth';ssh.mkdir(mode=0o700)
keys=ssh/'authorized_keys'
assert not keys.is_symlink()
keys.write_text(os.environ['BT_SSH_PUBLIC_KEY']+'\n');keys.chmod(0o600)
env={'PATH':'/usr/bin:/bin','HOME':'/root','LANG':'C.UTF-8'}
env.update({k:os.environ[k] for k in ('LD_LIBRARY_PATH','CUDA_VISIBLE_DEVICES') if k in os.environ})
os.execve(binary,[str(binary),'-F','-e','-j','-k','-G','root','-W','1048576','-D',str(ssh),'-p','22','-r',str(host),'-P',str(root/'sshd.pid')],env)
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(binary, keygen, directory):
    """Prepare only local keys and reviewed request bytes; no external access."""
    if sha(binary) != TRANSPORT['binary_sha256'] or sha(keygen) != TRANSPORT['keygen_sha256']:
        raise ValueError('unqualified transport executable')
    root = Path(directory).absolute()
    root.mkdir(mode=0o700)
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(root / 'owner-key')],
                   check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    subprocess.run([str(Path(keygen).absolute()), '-t', 'ed25519', '-f', str(root / 'host-key')],
                   check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    public = subprocess.check_output([str(Path(keygen).absolute()), '-y', '-f', str(root / 'host-key')],
                                     stderr=subprocess.DEVNULL, text=True, timeout=15)
    host_public = next(line for line in public.splitlines() if line.startswith('ssh-ed25519 '))
    (root / 'host-public').write_text(host_public + '\n')
    for path in root.iterdir():
        path.chmod(0o600)
    encoded = base64.b64encode(zlib.compress(Path(binary).read_bytes(), 9)).decode()
    env = {'BT_SSH_SHA': TRANSPORT['binary_sha256'],
           'BT_SSH_HOST_KEY': base64.b64encode((root / 'host-key').read_bytes()).decode(),
           'BT_SSH_PUBLIC_KEY': (root / 'owner-key.pub').read_text().strip()}
    env.update({f'BT_SSH_PART_{i // 30000:03}': encoded[i:i+30000] for i in range(0, len(encoded), 30000)})
    result = {'entrypoint': ['/usr/bin/python3.12', '-I', '-c'], 'cmd': [START], 'env': env}
    validate_initializer(result)
    return result


def validate_initializer(value):
    if (set(value) != {'entrypoint', 'cmd', 'env'}
            or value['entrypoint'] != ['/usr/bin/python3.12', '-I', '-c'] or value['cmd'] != [START]):
        raise ValueError('unreviewed container initialization')
    env = value['env']
    fixed = {'BT_SSH_SHA', 'BT_SSH_HOST_KEY', 'BT_SSH_PUBLIC_KEY'}
    parts = sorted(k for k in env if re.fullmatch(r'BT_SSH_PART_\d{3}', k))
    if (set(env) != fixed | set(parts) or not 1 <= len(parts) <= 40
            or parts != [f'BT_SSH_PART_{i:03}' for i in range(len(parts))]
            or any(not isinstance(v, str) or len(v) > 30000 or '\x00' in v for v in env.values())
            or env['BT_SSH_SHA'] != TRANSPORT['binary_sha256']
            or not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\r\n]*)?', env['BT_SSH_PUBLIC_KEY'])
            or len(json.dumps(value).encode()) > 950000):
        raise ValueError('invalid or oversized SSH initializer')
    binary = zlib.decompress(base64.b64decode(''.join(env[k] for k in parts), validate=True))
    if hashlib.sha256(binary).hexdigest() != TRANSPORT['binary_sha256']:
        raise ValueError('SSH executable changed')


def known_hosts(directory, host, port):
    """Identity derives from our pre-generated key; never trust ssh-keyscan."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host) or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('invalid exact SSH endpoint')
    root = Path(directory)
    public = (root / 'host-public').read_text().strip()
    target = root / 'known-hosts'
    with target.open('x') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(f'[{host}]:{port} {public}\n{host} {public}\n')
    return target
