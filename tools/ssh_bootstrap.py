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
import socket
import ssl
import subprocess
import time

TRANSPORT = {
    'version': '2026.94',
    'source_url': 'https://codeload.github.com/mkj/dropbear/tar.gz/refs/tags/DROPBEAR_2026.94',
    'source_bytes': 2923600,
    'source_sha256': '827d3f6e510e7554ee18d5c6a00dfee1a6a555559495e65e2e8f8d41c79eed84',
    'build_host': 'Kaggle CPU; GCC 13.3.0-6ubuntu2~24.04.1; GLIBC 2.39-0ubuntu8.9',
    'binary_sha256': '18b9bda72eddc5622f030c3d08b52078ac519912867a2facef40edac852d363a',
    'keygen_sha256': '5d33b842b70f674859459713ce3f28e62e32bdaca04950d6a599e1b8d84f3690',
}

# Only this small receiver and ephemeral server identity enter the create body.
# The pinned executable travels later over TLS 1.3 with mutual authentication.
# The same TCP port is handed to the existing, pinned SSH transport after SHA256
# verification. No HTTP service, package download or arbitrary upload is added.
START = r'''import base64,hashlib,os,socket,ssl,time
from pathlib import Path
os.umask(0o077)
assert os.getuid()==0
root=Path('/root/backtrace');root.mkdir(mode=0o700)
for name,key in (('tls-key','BT_TLS_KEY'),('tls-cert','BT_TLS_CERT'),('tls-client','BT_TLS_CLIENT')):
 p=root/name;p.write_bytes(base64.b64decode(os.environ[key],validate=True));p.chmod(0o600)
ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.minimum_version=ssl.TLSVersion.TLSv1_3
ctx.load_cert_chain(root/'tls-cert',root/'tls-key')
ctx.load_verify_locations(cafile=root/'tls-client');ctx.verify_mode=ssl.CERT_REQUIRED
deadline=time.monotonic()+1200
def bounded(sock):
 left=deadline-time.monotonic()
 if left<=0:raise TimeoutError('bootstrap deadline')
 sock.settimeout(min(10,left))
def take(sock,n):
 data=bytearray()
 while len(data)<n:
  bounded(sock);part=sock.recv(min(65536,n-len(data)))
  if not part:raise EOFError('short bootstrap stream')
  data.extend(part)
 return bytes(data)
size=int(os.environ['BT_SSH_BYTES']);assert 0<size<=2*1024*1024
binary=root/'dropbear';partial=root/'dropbear.partial'
with socket.socket() as listener:
 listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
 listener.bind(('0.0.0.0',22));listener.listen(4)
 for attempt in range(128):
  bounded(listener)
  try:raw,_=listener.accept()
  except TimeoutError:continue
  try:
   bounded(raw);conn=ctx.wrap_socket(raw,server_side=True)
  except (ssl.SSLError,TimeoutError,ConnectionError):
   raw.close();continue
  with conn:
   try:
    assert int.from_bytes(take(conn,8),'big')==size
    digest=hashlib.sha256();left=size
    with partial.open('xb') as output:
     while left:
      data=take(conn,min(65536,left));digest.update(data);output.write(data);left-=len(data)
     output.flush();os.fsync(output.fileno())
    assert digest.hexdigest()==os.environ['BT_SSH_SHA']
    partial.rename(binary);binary.chmod(0o700)
    bounded(conn);conn.sendall((digest.hexdigest()+'\n').encode())
   finally:
    partial.unlink(missing_ok=True)
  break
 else:raise TimeoutError('bootstrap authentication limit')
for name in ('tls-key','tls-cert','tls-client'):(root/name).unlink()
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
    for name, purpose in (('server', 'serverAuth'), ('client', 'clientAuth')):
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'ed25519', '-nodes', '-days', '7',
                        '-subj', '/CN=backtrace-bootstrap-' + name,
                        '-addext', 'subjectAltName=DNS:backtrace-bootstrap',
                        '-addext', 'basicConstraints=critical,CA:FALSE',
                        '-addext', 'keyUsage=critical,digitalSignature',
                        '-addext', 'extendedKeyUsage=' + purpose,
                        '-keyout', str(root / (name + '.key')), '-out', str(root / (name + '.crt'))],
                       check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=15,
                       env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
    (root / 'transport').write_bytes(Path(binary).read_bytes())
    for path in root.iterdir():
        path.chmod(0o600)
    env = {'BT_SSH_SHA': TRANSPORT['binary_sha256'],
           'BT_SSH_BYTES': str((root / 'transport').stat().st_size),
           'BT_SSH_HOST_KEY': base64.b64encode((root / 'host-key').read_bytes()).decode(),
           'BT_SSH_PUBLIC_KEY': (root / 'owner-key.pub').read_text().strip()}
    env.update({key: base64.b64encode((root / name).read_bytes()).decode() for key, name in
                (('BT_TLS_KEY', 'server.key'), ('BT_TLS_CERT', 'server.crt'), ('BT_TLS_CLIENT', 'client.crt'))})
    result = {'entrypoint': ['/usr/bin/python3.12', '-I', '-c'], 'cmd': [START], 'env': env}
    validate_initializer(result)
    return result


def validate_initializer(value):
    if (set(value) != {'entrypoint', 'cmd', 'env'}
            or value['entrypoint'] != ['/usr/bin/python3.12', '-I', '-c'] or value['cmd'] != [START]):
        raise ValueError('unreviewed container initialization')
    env = value['env']
    fixed = {'BT_SSH_SHA', 'BT_SSH_BYTES', 'BT_SSH_HOST_KEY', 'BT_SSH_PUBLIC_KEY',
             'BT_TLS_KEY', 'BT_TLS_CERT', 'BT_TLS_CLIENT'}
    if (set(env) != fixed
            or any(not isinstance(v, str) or len(v) > 4096 or '\x00' in v for v in env.values())
            or env['BT_SSH_SHA'] != TRANSPORT['binary_sha256']
            or not re.fullmatch(r'[1-9][0-9]{0,6}', env['BT_SSH_BYTES'])
            or not 0 < int(env['BT_SSH_BYTES']) <= 2 * 1024 * 1024
            or not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\r\n]*)?', env['BT_SSH_PUBLIC_KEY'])
            or len(json.dumps(value).encode()) > 16384):
        raise ValueError('invalid or oversized SSH initializer')
    for key in ('BT_SSH_HOST_KEY', 'BT_TLS_KEY', 'BT_TLS_CERT', 'BT_TLS_CLIENT'):
        if not base64.b64decode(env[key], validate=True):
            raise ValueError('empty transport identity')


def private_bytes(path):
    path = Path(path)
    if (path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid()
            or path.stat().st_mode & 0o077):
        raise ValueError('private transport file required')
    return path.read_bytes()


def validate_material(directory):
    """Prepaid gate: executable, identity pairing, expiry and permissions."""
    root = Path(directory)
    if root.is_symlink() or root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise ValueError('private transport directory required')
    value = json.loads(private_bytes(root / 'initializer.json'))
    validate_initializer(value)
    data = private_bytes(root / 'transport')
    if (hashlib.sha256(data).hexdigest() != TRANSPORT['binary_sha256']
            or len(data) != int(value['env']['BT_SSH_BYTES'])):
        raise ValueError('SSH executable changed')
    for name, key in (('server.key', 'BT_TLS_KEY'), ('server.crt', 'BT_TLS_CERT'),
                      ('client.crt', 'BT_TLS_CLIENT'), ('host-key', 'BT_SSH_HOST_KEY')):
        if base64.b64decode(value['env'][key], validate=True) != private_bytes(root / name):
            raise ValueError('transport identity changed')
    private_bytes(root / 'client.key'); private_bytes(root / 'owner-key')
    for name in ('server', 'client'):
        subprocess.run(['openssl', 'x509', '-in', str(root / (name + '.crt')), '-checkend', '3600', '-noout'],
                       check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=10,
                       env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
    context(directory)  # Also verifies that the client private key matches.
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(root / 'server.crt', root / 'server.key')
    return {'method': 'mutual-tls13-then-pinned-ssh', 'binary_bytes': len(data),
            'binary_sha256': TRANSPORT['binary_sha256'], 'minimum_validity_seconds': 3600}


def context(directory):
    root = Path(directory)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_verify_locations(cafile=root / 'server.crt')
    ctx.load_cert_chain(root / 'client.crt', root / 'client.key')
    return ctx


def deliver(directory, host, port, timeout):
    """One authenticated executable transfer; retry only TCP-not-ready."""
    validate_endpoint(host, port)
    if not 0 < timeout <= 1200:
        raise ValueError('bounded bootstrap timeout required')
    root = Path(directory)
    data = private_bytes(root / 'transport')
    if hashlib.sha256(data).hexdigest() != TRANSPORT['binary_sha256']:
        raise ValueError('SSH executable changed')
    ctx = context(root)
    deadline = time.monotonic() + timeout
    def budget():
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError('bootstrap transfer deadline')
        return min(10, left)
    while True:
        try:
            raw = socket.create_connection((host, port), timeout=budget())
            break
        except (ConnectionRefusedError, TimeoutError):
            time.sleep(min(1, budget()))
    with raw:
        raw.settimeout(budget())
        with ctx.wrap_socket(raw, server_hostname='backtrace-bootstrap') as conn:
            conn.settimeout(budget()); conn.sendall(len(data).to_bytes(8, 'big') + data)
            receipt = bytearray()
            while len(receipt) < 65:
                conn.settimeout(budget()); part = conn.recv(65 - len(receipt))
                if not part:
                    raise EOFError('missing bootstrap acknowledgement')
                receipt.extend(part)
            if receipt != (TRANSPORT['binary_sha256'] + '\n').encode():
                raise ValueError('incorrect bootstrap acknowledgement')
    return {'bytes': len(data), 'sha256': TRANSPORT['binary_sha256']}


def validate_endpoint(host, port):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host) or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('invalid exact SSH endpoint')


def known_hosts(directory, host, port):
    """Identity derives from our pre-generated key; never trust ssh-keyscan."""
    validate_endpoint(host, port)
    root = Path(directory)
    public = (root / 'host-public').read_text().strip()
    target = root / 'known-hosts'
    with target.open('x') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(f'[{host}]:{port} {public}\n{host} {public}\n')
    return target
