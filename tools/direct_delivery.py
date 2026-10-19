"""Pod-side HTTPS delivery of exact, already authorized input bytes.

The owner resolves short-lived download URLs outside the Pod. No account key,
resolver, installation, model execution, or provider operation is present here.
URLs arrive through a private stdin/file channel and are never logged. The
destination becomes visible only after every frozen size and SHA-256 matches.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from tools.private_delivery import MANIFEST_NAME, digest, parse_manifest, verify

# Exact hosts observed in authenticated Kaggle model and saved-output APIs.
# Neither host receives account headers; every body retains frozen size/hash checks.
HOSTS = frozenset({'storage.googleapis.com', 'www.kaggleusercontent.com',
                   'files.pythonhosted.org', 'download-r2.pytorch.org'})
CHUNK = 1024 * 1024


class DownloadError(RuntimeError):
    """Messages deliberately omit signed URLs and provider response bodies."""


def validate_url(url):
    if not isinstance(url, str) or len(url) > 16384 or any(c.isspace() for c in url):
        raise ValueError('invalid private download URL')
    p = urllib.parse.urlsplit(url)
    if (p.scheme != 'https' or p.hostname not in HOSTS or p.port not in (None, 443)
            or p.username is not None or p.password is not None or p.fragment
            or not p.path.startswith('/') or p.path == '/'):
        raise ValueError('HTTPS on the reviewed storage host is required')
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise DownloadError('resolve the final storage URL on the owner host')


def sources_for(manifest, sources):
    names = {r['path'] for r in manifest['files']}
    if not isinstance(sources, dict) or set(sources) != names:
        raise ValueError('one download source per frozen input required')
    for row in manifest['files']:
        source = sources[row['path']]
        if not isinstance(source, dict) or set(source) != {'url', 'encoding', 'wire_bytes'}:
            raise ValueError('unexpected download fields')
        validate_url(source['url'])
        if source['encoding'] not in ('raw', 'single-file-zip'):
            raise ValueError('unsupported transport encoding')
        size = source['wire_bytes']
        if type(size) is not int or not 0 <= size <= row['bytes'] + 16 * 1024**2:
            raise ValueError('bounded exact transport size required')
        if source['encoding'] == 'raw' and size != row['bytes']:
            raise ValueError('raw transport size differs from frozen input')


def time_left(deadline, clock):
    left = deadline - clock()
    if not math.isfinite(left) or left <= 0:
        raise DownloadError('download deadline reached')
    return left


def download_wire(path, source, deadline, *, opener=None, clock=time.monotonic):
    """At most three GETs, with strict Range validation after an interrupted body."""
    open_url = opener or urllib.request.build_opener(NoRedirect()).open
    size = source['wire_bytes']
    for attempt in range(3):
        offset = path.stat().st_size if path.exists() else 0
        if offset == size:
            if not path.exists():
                path.touch(mode=0o600)
            return
        headers = {'Accept-Encoding': 'identity', 'User-Agent': 'Backtrace-input-delivery/1'}
        if offset:
            headers['Range'] = 'bytes=' + str(offset) + '-'
        request = urllib.request.Request(validate_url(source['url']), headers=headers)
        try:
            with open_url(request, timeout=min(15, time_left(deadline, clock))) as response:
                expected_status = 206 if offset else 200
                if response.status != expected_status:
                    raise DownloadError('storage response status or Range support changed')
                if response.headers.get('Content-Encoding', 'identity') != 'identity':
                    raise DownloadError('unexpected HTTP content encoding')
                if response.headers.get('Content-Length') != str(size - offset):
                    raise DownloadError('storage Content-Length differs from resolved size')
                if offset and response.headers.get('Content-Range') != f'bytes {offset}-{size - 1}/{size}':
                    raise DownloadError('storage Content-Range differs from requested offset')
                with path.open('ab') as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    while offset < size:
                        time_left(deadline, clock)
                        data = response.read(min(CHUNK, size - offset))
                        if not data:
                            raise OSError('truncated body')
                        stream.write(data); offset += len(data)
                    time_left(deadline, clock)
                    if response.read(1):
                        raise DownloadError('storage body exceeds resolved size')
                    stream.flush(); os.fsync(stream.fileno())
                return
        except urllib.error.HTTPError as error:
            # An expired URL is re-resolved only by the owner, never by the Pod.
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise DownloadError('storage HTTP failure') from None
        except (OSError, TimeoutError):
            if attempt == 2:
                raise DownloadError('bounded storage retries exhausted') from None
    raise DownloadError('download incomplete')


def download_one(row, source, staging, deadline, *, opener=None, clock=time.monotonic):
    target = staging / row['path']
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Transport files cannot collide with any manifest path.
    fd, name = tempfile.mkstemp(prefix='.wire-', dir=staging.parent)
    os.close(fd); wire = Path(name)
    try:
        download_wire(wire, source, deadline, opener=opener, clock=clock)
        if source['encoding'] == 'raw':
            wire.rename(target)
        else:
            with zipfile.ZipFile(wire) as archive:
                entries = archive.infolist()
                if (len(entries) != 1 or entries[0].is_dir()
                        or entries[0].filename not in (row['path'], Path(row['path']).name)
                        or entries[0].file_size != row['bytes']
                        or (entries[0].external_attr >> 16) & 0o170000 == 0o120000):
                    raise DownloadError('archive must contain only the expected regular file')
                with archive.open(entries[0]) as src, target.open('xb') as dst:
                    os.fchmod(dst.fileno(), 0o600)
                    copied = 0
                    while data := src.read(CHUNK):
                        time_left(deadline, clock)
                        copied += len(data)
                        if copied > row['bytes']:
                            raise DownloadError('unpacked file exceeds frozen size')
                        dst.write(data)
                    dst.flush(); os.fsync(dst.fileno())
        time_left(deadline, clock)
        if target.stat().st_size != row['bytes'] or digest(target) != row['sha256']:
            raise DownloadError('downloaded input identity mismatch')
    except (zipfile.BadZipFile, RuntimeError) as error:
        if isinstance(error, DownloadError):
            raise
        raise DownloadError('invalid encoded input') from None
    finally:
        wire.unlink(missing_ok=True)


def pull(destination, manifest_data, sources, expected_sha256, seconds, *, opener=None):
    if hashlib.sha256(manifest_data).hexdigest() != expected_sha256:
        raise ValueError('externally pinned manifest SHA-256 required')
    manifest = parse_manifest(manifest_data)
    sources_for(manifest, sources)
    if type(seconds) not in (int, float) or not 0 < seconds <= 5400:
        raise ValueError('bounded allocation-inclusive setup time required')
    destination = Path(destination).absolute(); parent = destination.parent
    if (not parent.is_dir() or parent.resolve() != parent or parent.stat().st_uid != os.getuid()
            or parent.stat().st_mode & 0o077 or destination.exists() or destination.is_symlink()):
        raise ValueError('private real parent and unused destination required')
    required = sum(r['bytes'] for r in manifest['files'])
    # At most two concurrent ZIP bodies beside their decoded files.
    required += sum(sorted((s['wire_bytes'] for s in sources.values()
                            if s['encoding'] != 'raw'), reverse=True)[:2])
    if shutil.disk_usage(parent).free < required + 64 * 1024**2:
        raise ValueError('insufficient download storage')
    lock = parent / ('.' + destination.name + '.delivery-lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    staging = Path(tempfile.mkdtemp(prefix='.direct-', dir=parent))
    deadline = time.monotonic() + seconds
    cancelled = threading.Event()
    def clock():
        return float('inf') if cancelled.is_set() else time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(download_one, row, sources[row['path']], staging,
                                       deadline, opener=opener, clock=clock) for row in manifest['files']]
            try:
                for future in as_completed(futures):
                    future.result()
            except BaseException:
                cancelled.set()
                for future in futures:
                    future.cancel()
                raise
        time_left(deadline, time.monotonic)
        (staging / MANIFEST_NAME).write_bytes(manifest_data)
        (staging / MANIFEST_NAME).chmod(0o600)
        receipt = verify(staging, manifest_data, exact=True)
        staging.rename(destination)
        return dict(receipt, transport='direct-https', credentials='short-lived file URLs only')
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        # A failed delivery lock is intentionally retained: no implicit restart.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('expected_sha256')
    parser.add_argument('--seconds', type=float, required=True)
    args = parser.parse_args()
    try:
        source_data = sys.stdin.buffer.read(8 * 1024**2 + 1)
        if len(source_data) > 8 * 1024**2:
            raise ValueError('source map too large')
        result = pull(args.destination, args.manifest.read_bytes(), json.loads(source_data),
                      args.expected_sha256, args.seconds)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        # No chained tracebacks: urllib/zip errors may embed signed URLs.
        print(json.dumps({'delivery': 'FAILED', 'error_type': type(error).__name__}))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
