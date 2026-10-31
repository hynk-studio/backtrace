"""Hash-pinned private stream delivery. Never installs or executes payload files.

The receiver is stdlib-only and can run under the pinned base's system Python.
Use a pre-reviewed exact file manifest, not a directory crawl of private inputs.
An SSH host key must be authenticated independently before using ``push``.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import zlib

MAX_BYTES = 40 * 1024**3
MAX_MANIFEST_BYTES = 1024**2
MANIFEST_NAME = 'delivery-manifest.json'
PROGRESS_PREFIX = 'BACKTRACE_DELIVERY_PROGRESS '
PROGRESS_PHASES = {'VERIFY_SOURCE', 'STREAM', 'READBACK', 'COMMITTED'}


def reporter(role):
    started=time.monotonic()
    def report(phase,count,total):
        row={'role':role,'phase':phase,'bytes':count,'total_bytes':total,
             'elapsed_seconds':time.monotonic()-started}
        print(PROGRESS_PREFIX+json.dumps(row,separators=(',',':')),file=sys.stderr,flush=True)
    return report


def progress_records(stream):
    """Only bounded typed counters; never expose arbitrary SSH stderr or payloads."""
    stream.seek(0,os.SEEK_END);size=stream.tell();stream.seek(max(0,size-1024**2))
    rows=[]
    for raw in stream.read(1024**2).splitlines():
        if len(raw)>512 or not raw.startswith(PROGRESS_PREFIX.encode()):continue
        try:row=json.loads(raw[len(PROGRESS_PREFIX):])
        except (ValueError,UnicodeError):continue
        if (not isinstance(row,dict) or set(row)!={'role','phase','bytes','total_bytes','elapsed_seconds'}
                or type(row['role']) is not str or row['role'] not in ('sender','receiver')
                or type(row['phase']) is not str or row['phase'] not in PROGRESS_PHASES
                or any(type(row[k]) is not int or not 0<=row[k]<=MAX_BYTES for k in ('bytes','total_bytes'))
                or row['bytes']>row['total_bytes']
                or type(row['elapsed_seconds']) not in (int,float)
                or not 0<=row['elapsed_seconds']<=2400):continue
        rows.append(row)
    return {'stderr_tail_truncated':size>1024**2,'events':rows[-1024:]}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def parse_manifest(data):
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError('manifest too large')
    value = json.loads(data)
    if set(value) != {'schema_version', 'phase', 'files'} or value['schema_version'] != 1:
        raise ValueError('unexpected manifest schema')
    if value['phase'] not in ('bootstrap', 'task', 'model'):
        raise ValueError('only generation-side input phases are accepted')
    records = value['files']
    if not isinstance(records, list) or not 1 <= len(records) <= 1024:
        raise ValueError('invalid manifest file count')
    names = set()
    for row in records:
        if set(row) != {'path', 'bytes', 'sha256'}:
            raise ValueError('unexpected file fields')
        name = row['path']
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_+./-]+', name)
                or name.startswith('/') or PurePosixPath(name).as_posix() != name
                or any(p in ('', '.', '..') for p in name.split('/'))
                or name == MANIFEST_NAME or name in names):
            raise ValueError('invalid or duplicate relative file path')
        if (type(row['bytes']) is not int or not 0 <= row['bytes'] <= MAX_BYTES
                or not isinstance(row['sha256'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', row['sha256'])):
            raise ValueError('invalid file identity')
        names.add(name)
    if any(str(p) in names for n in names for p in PurePosixPath(n).parents if str(p) != '.'):
        raise ValueError('file/directory collision')
    if sum(r['bytes'] for r in records) > MAX_BYTES:
        raise ValueError('delivery exceeds storage envelope')
    return value


def regular_file(root, name):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('source must be a real directory')
    path = root
    for part in PurePosixPath(name).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('symlink in delivery input')
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('delivery input must be a regular file')
    return path


def verify(root, manifest_data, exact=False):
    manifest = parse_manifest(manifest_data)
    for row in manifest['files']:
        path = regular_file(root, row['path'])
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('delivery identity mismatch: ' + row['path'])
    if exact:
        paths = list(Path(root).rglob('*'))
        if any(p.is_symlink() for p in paths):
            raise ValueError('unexpected symlink in received tree')
        actual = {p.relative_to(root).as_posix() for p in paths if p.is_file()}
        if actual != {r['path'] for r in manifest['files']} | {MANIFEST_NAME}:
            raise ValueError('unexpected received file')
        if (Path(root) / MANIFEST_NAME).read_bytes() != manifest_data:
            raise ValueError('received manifest changed')
    return {'schema_version': 1, 'phase': manifest['phase'],
            'manifest_sha256': hashlib.sha256(manifest_data).hexdigest(),
            'files': len(manifest['files']),
            'bytes': sum(r['bytes'] for r in manifest['files']),
            'verified': True}


def emit(root, manifest_data, output, progress=None):
    manifest = parse_manifest(manifest_data)
    total=sum(r['bytes'] for r in manifest['files']);count=0;last=0
    if progress:progress('VERIFY_SOURCE',0,total)
    verify(root, manifest_data)
    if progress:progress('STREAM',0,total)
    class Reader:
        def __init__(self,stream):self.stream=stream
        def read(self,size):
            nonlocal count,last
            block=self.stream.read(size);count+=len(block)
            if progress and (count-last>=16*1024**2 or count==total):
                progress('STREAM',count,total);last=count
            return block
    # Three frozen wheel basenames exceed USTAR's 100-byte name field and
    # cannot be split into its directory prefix. GNU long-name records retain
    # the exact filename; the receiver still enforces the pinned regular entry.
    with tarfile.open(fileobj=output, mode='w|', format=tarfile.GNU_FORMAT) as archive:
        def add(name, size, stream):
            info = tarfile.TarInfo(name)
            info.size, info.mode = size, 0o600
            archive.addfile(info, stream)
        add(MANIFEST_NAME, len(manifest_data), io.BytesIO(manifest_data))
        for row in manifest['files']:
            path = regular_file(root, row['path'])
            with path.open('rb') as stream:
                add(row['path'], row['bytes'], Reader(stream))


def receive(destination, expected_sha256, source, progress=None):
    """Atomic destination; truncated/mutated/extra/link payloads never commit."""
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('expected manifest SHA256 required outside the stream')
    destination = Path(destination).absolute()
    parent = destination.parent
    if not parent.is_dir() or parent.resolve() != parent or destination.exists() or destination.is_symlink():
        raise ValueError('real existing parent and unused destination required')
    if parent.stat().st_uid != os.getuid() or parent.stat().st_mode & 0o077:
        raise ValueError('receiver parent must be owner-only')
    lock = parent / ('.' + destination.name + '.delivery-lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    staging = Path(tempfile.mkdtemp(prefix='.delivery-', dir=parent))
    try:
        with tarfile.open(fileobj=source, mode='r|') as archive:
            first = archive.next()
            if (first is None or first.name != MANIFEST_NAME or not first.isfile()
                    or first.pax_headers or first.size > MAX_MANIFEST_BYTES):
                raise ValueError('manifest must be the first regular entry')
            data = archive.extractfile(first).read()
            if hashlib.sha256(data).hexdigest() != expected_sha256:
                raise ValueError('manifest digest mismatch')
            manifest = parse_manifest(data)
            needed = sum(r['bytes'] for r in manifest['files'])
            count=0;last=0
            if progress:progress('STREAM',0,needed)
            if shutil.disk_usage(parent).free < needed + 64 * 1024**2:
                raise ValueError('insufficient receiver disk')
            (staging / MANIFEST_NAME).write_bytes(data)
            (staging / MANIFEST_NAME).chmod(0o600)
            for row in manifest['files']:
                entry = archive.next()
                if (entry is None or entry.name != row['path'] or not entry.isfile()
                        or entry.size != row['bytes'] or entry.pax_headers):
                    raise ValueError('unexpected, missing or non-regular archive entry')
                target = staging / row['path']
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                hasher = hashlib.sha256()
                with target.open('xb') as output:
                    os.fchmod(output.fileno(), 0o600)
                    stream = archive.extractfile(entry)
                    for block in iter(lambda: stream.read(1024**2), b''):
                        output.write(block)
                        hasher.update(block)
                        count+=len(block)
                        if progress and (count-last>=16*1024**2 or count==needed):
                            progress('STREAM',count,needed);last=count
                    output.flush()
                    os.fsync(output.fileno())
                if hasher.hexdigest() != row['sha256']:
                    raise ValueError('transferred file hash mismatch')
            if archive.next() is not None:
                raise ValueError('extra archive entry')
        # Reopen and rehash installed bytes; tar header/stream hashes alone are insufficient.
        if progress:progress('READBACK',count,needed)
        receipt = verify(staging, data, exact=True)
        if destination.exists() or destination.is_symlink():
            raise ValueError('destination appeared during transfer')
        staging.rename(destination)
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        if progress:progress('COMMITTED',count,needed)
        return receipt
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        lock.unlink()


def remote_python(source):
    """Keep stdlib bootstrap commands below Dropbear's 9,000-byte limit."""
    encoded = base64.b64encode(zlib.compress(source.encode(), 9)).decode('ascii')
    program = 'import base64,zlib;exec(zlib.decompress(base64.b64decode(' + repr(encoded) + ')))'
    argv = ['python3', '-I', '-c', program]
    if len(shlex.join(argv).encode()) >= 9000:
        raise ValueError('remote Python command exceeds SSH command limit')
    return argv


def ssh_command(host, port, key, known_hosts, remote_destination, manifest_sha256):
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host)
            or not 1 <= port <= 65535 or not remote_destination.startswith('/root/')):
        raise ValueError('explicit root SSH destination required')
    for path in (key, known_hosts):
        if not Path(path).is_file() or Path(path).is_symlink():
            raise ValueError('pre-existing key and authenticated known_hosts required')
    source = Path(__file__).read_text()
    argv = remote_python(source) + ['receive', remote_destination, manifest_sha256, '--progress']
    remote = shlex.join(argv)
    if len(remote.encode()) >= 9000:
        raise ValueError('receiver command exceeds SSH command limit')
    return ['ssh', '-F', '/dev/null', '-T', '-p', str(port),
            '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=' + str(Path(known_hosts).absolute()),
            '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'IdentitiesOnly=yes',
            '-o', 'ForwardAgent=no', '-o', 'ClearAllForwardings=yes',
            '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=10',
            '-o', 'ServerAliveCountMax=2', '-i', str(Path(key).absolute()),
            'root@' + host, remote]


def push(root, manifest_path, command, timeout, *, diagnostics=None):
    report={'schema':'private_delivery_progress_v1','status':'STARTED','phase':'SOURCE_VERIFICATION',
            'timeout_seconds':timeout}
    started=time.monotonic();failure=None
    try:return _push(root,manifest_path,command,timeout,report,started)
    except BaseException as error:
        failure=error
        report.update(status='FAIL',error_type=type(error).__name__)
        raise
    finally:
        report['elapsed_seconds']=time.monotonic()-started
        if diagnostics is not None:
            try:
                with Path(diagnostics).open('x') as stream:
                    os.fchmod(stream.fileno(),0o600)
                    json.dump(report,stream,sort_keys=True);stream.write('\n')
            except Exception as storage_error:
                if failure is None:raise
                failure.add_note('delivery diagnostic persistence failed: '+type(storage_error).__name__)


def _push(root, manifest_path, command, timeout, report, started):
    if not 0 < timeout <= 1200:
        raise ValueError('transfer must fit remaining setup time, at most 1200s')
    data = Path(manifest_path).read_bytes()
    expected = verify(root, data)
    report.update(expected=expected,source_verification_seconds=time.monotonic()-started,
                  phase='RECEIVER_COMPLETION')
    clean_env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}
    with tempfile.TemporaryFile() as errors, tempfile.TemporaryFile() as output:
        sender = subprocess.Popen([sys.executable, '-I', str(Path(__file__).resolve()),
                                   'emit', str(root), str(manifest_path), '--progress'],
                                  stdout=subprocess.PIPE, stderr=errors, env=clean_env)
        receiver = None
        try:
            receiver = subprocess.Popen(command, stdin=sender.stdout, stdout=output,
                                        stderr=errors, env=clean_env)
            sender.stdout.close()
            receiver.wait(timeout=max(0.001, timeout - (time.monotonic() - started)))
            report['phase']='SENDER_COMPLETION'
            sender.wait(timeout=max(0.001, timeout - (time.monotonic() - started)))
            if receiver.returncode or sender.returncode:
                raise RuntimeError('private transfer failed; no payload/error bytes disclosed')
            output.seek(0)
            raw = output.read(MAX_MANIFEST_BYTES + 1)
            if len(raw) > MAX_MANIFEST_BYTES or json.loads(raw) != expected:
                raise ValueError('receiver readback does not match sender manifest')
            report.update(status='PASS',phase='EXACT_READBACK')
            return expected
        finally:
            for process in (receiver, sender):
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
            report.update(sender_exit_code=sender.poll(),receiver_exit_code=receiver.poll() if receiver else None,
                          progress=progress_records(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='mode', required=True)
    for name in ('verify', 'emit'):
        sub = commands.add_parser(name)
        sub.add_argument('root', type=Path)
        sub.add_argument('manifest', type=Path)
        sub.add_argument('--progress',action='store_true')
    sub = commands.add_parser('receive')
    sub.add_argument('destination', type=Path)
    sub.add_argument('manifest_sha256')
    sub.add_argument('--progress',action='store_true')
    sub = commands.add_parser('push')
    sub.add_argument('root', type=Path)
    sub.add_argument('manifest', type=Path)
    for name in ('host', 'key', 'known-hosts', 'destination'):
        sub.add_argument('--' + name, required=True)
    sub.add_argument('--port', type=int, required=True)
    sub.add_argument('--remaining-setup-seconds', type=float, required=True)
    args = parser.parse_args()
    if args.mode == 'receive':
        result = receive(args.destination, args.manifest_sha256, sys.stdin.buffer,
                         reporter('receiver') if args.progress else None)
    elif args.mode == 'emit':
        emit(args.root, args.manifest.read_bytes(), sys.stdout.buffer,
             reporter('sender') if args.progress else None)
        return
    elif args.mode == 'verify':
        result = verify(args.root, args.manifest.read_bytes())
    else:
        command = ssh_command(args.host, args.port, args.key, args.known_hosts,
                              args.destination, digest(args.manifest))
        result = push(args.root, args.manifest, command, args.remaining_setup_seconds)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
