"""Allocation-clock supervisor, bounded evidence export and cleanup-only watcher.

No allocation or authorization API. An external, separately reviewed entry must
bind an already allocated resource to the original request timestamp. CPU tests
exercise real subprocesses and a Runpod HTTP replica, not a live provider.
"""
import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import subprocess
import sys
import tarfile
import time
import uuid

from tools import exact_teacher as exact, small_model_runner as runner

SCHEMA = 'small-model-lifecycle-v1'
TOTAL, EXPORT, CLEANUP = 3000, 120, 300
LIMIT = 64*1024**2
LEAVES = {'receipt.json', 'failed.json', 'collection.json', 'recovery.json',
          'evaluation.json', 'assignment.json', 'ledger.jsonl', 'resources.json',
          'result.json', 'context-interruption.json', 'worker.log', 'stderr.log',
          'E2B-ready.json', 'E4B-ready.json', 'E2B-stderr.log', 'E4B-stderr.log',
          'facts.json', 'deadline.log', 'parent_loss.log'}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else encoded(value)).hexdigest()


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('finite number required')
    return value


def write(path, value):
    path = Path(path)
    with path.open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())


class Deadline:
    """The remaining monotonic allowance begins at the allocation request, not load."""
    def __init__(self, requested_at, total=TOTAL, *, wall=time.time, mono=time.monotonic, allow_expired=False):
        self.wall, self.mono = wall, mono
        self.requested_at = finite(requested_at); self.total = finite(total)
        now = finite(wall()); elapsed = now-requested_at
        if not 0 < total <= TOTAL or elapsed < 0 or (elapsed >= total and not allow_expired):
            raise ValueError('allocation timestamp is future or already expired')
        self.last_wall = now
        self.end = mono()+total-elapsed

    def remaining(self, reserve=0):
        now = finite(self.wall())
        if now < self.last_wall:
            raise TimeoutError('wall clock reversed')
        self.last_wall = now
        return min(self.end-self.mono(), self.requested_at+self.total-now)-reserve


class Journal:
    """Create-only local rehearsal/host journal; not a distributed state claim."""
    def __init__(self, root):
        self.root = Path(root).absolute()
        info = self.root.stat()
        if (self.root.resolve() != self.root or not self.root.is_dir()
                or info.st_uid != os.geteuid() or info.st_mode & 0o077):
            raise ValueError('owner-only journal directory required')

    @classmethod
    def create(cls, parent, source, resource, requested_at, *, total=TOTAL,
               export_seconds=EXPORT, cleanup_seconds=CLEANUP, stale_seconds=30, replica=False):
        if (not re.fullmatch('[0-9a-f]{40}', source)
                or type(replica) is not bool
                or set(resource) != {'id', 'name'}
                or not re.fullmatch('[A-Za-z0-9_-]{1,128}', resource['id'])
                or not re.fullmatch('backtrace-small-[0-9a-f]{32}', resource['name'])):
            raise ValueError('fresh exact source and resource identity required')
        values = [total, export_seconds, cleanup_seconds, stale_seconds]
        if (any(finite(v) <= 0 for v in values) or not export_seconds+cleanup_seconds < total <= TOTAL
                or stale_seconds >= cleanup_seconds):
            raise ValueError('bounded work/export/cleanup intervals required')
        if not replica and values != [TOTAL, EXPORT, CLEANUP, 30]:
            raise ValueError('production ceilings/reserves fixed')
        Deadline(requested_at, total)
        root = Path(parent)/('small-lifecycle-'+uuid.uuid4().hex); root.mkdir(mode=0o700)
        journal = cls(root)
        journal.put('claim', {'schema': SCHEMA, 'source_sha': source, 'resource': resource,
                    'requested_at': requested_at, 'total_seconds': total,
                    'export_seconds': export_seconds, 'cleanup_seconds': cleanup_seconds,
                    'stale_seconds': stale_seconds, 'replica': replica,
                    'authorization': 'NONE', 'allocation_requests': 0})
        return journal

    def path(self, name):
        if not re.fullmatch('[a-z][a-z0-9-]{0,60}', name):
            raise ValueError('journal name')
        return self.root/(name+'.json')

    def read(self, name):
        path = self.path(name)
        if not path.exists():
            return None
        if name in ('owner-heartbeat', 'watcher-heartbeat'):
            # An atomic replacement can unlink the already opened old inode.
            # Its complete bytes are still valid; nlink==0 is not a hard link.
            # Immutable records keep runner.regular's stricter nlink==1 rule.
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink > 1 or info.st_size > 1024**2
                        or info.st_uid != os.geteuid() or info.st_mode & 0o077):
                    raise ValueError('invalid private atomic heartbeat')
                raw = stream.read(1024**2+1)
                if len(raw) > 1024**2:
                    raise ValueError('heartbeat grew beyond limit')
                return json.loads(raw)
        return json.loads(runner.regular(path, 1024**2))

    def put(self, name, value):
        write(self.path(name), value)

    def binding(self):
        return digest(self.read('claim'))

    def heartbeat(self, name, phase):
        if name not in ('owner-heartbeat', 'watcher-heartbeat'):
            raise ValueError('only heartbeat records are mutable')
        temporary = self.root/(name+'-'+uuid.uuid4().hex+'.partial')
        write(temporary, {'claim_sha256': self.binding(), 'at': time.time(),
                         'phase': phase, 'pid': os.getpid()})
        os.replace(temporary, self.path(name))


class RunpodResource:
    """Cleanup-only adapter: no create, resume, credentials-on-host or old claims."""
    def __init__(self, api, identity):
        self.api, self.identity = api, dict(identity)

    def observe(self):
        rows = self.api.list()
        matches = [p for p in rows if p.get('id') == self.identity['id'] or p.get('name') == self.identity['name']]
        if any({k: p.get(k) for k in ('id', 'name')} != self.identity for p in matches) or len(matches) > 1:
            raise ValueError('resource name/ID collision')
        pod = self.api.get(self.identity['id'])
        if pod is not None and {k: pod.get(k) for k in ('id', 'name')} != self.identity:
            raise ValueError('resource identity changed')
        if bool(matches) != (pod is not None):
            raise ValueError('provider list and exact-ID observations disagree')
        return pod is not None

    def delete(self):
        if self.observe():
            self.api.delete(self.identity['id'])


def cleanup(resource, seconds, *, interval=.2):
    """A DELETE acknowledgement or a failed read is never absence evidence."""
    started = time.time(); end = time.monotonic()+max(0, seconds); history = []; absent = 0
    while time.monotonic() < end:
        try:
            present = resource.observe()
            absent = 0 if present else absent+1
            history.append({'at': time.time(), 'state': 'PRESENT' if present else 'ABSENT'})
            if absent == 2:
                return {'status': 'DELETED', 'absence_reads': 2, 'started_at': started,
                        'completed_at': time.time(), 'history': history[-64:]}
            if present:
                resource.delete()
        except Exception as error:
            absent = 0; history.append({'at': time.time(), 'state': 'UNKNOWN', 'type': type(error).__name__})
        time.sleep(min(interval, max(0, end-time.monotonic())))
    return {'status': 'UNRESOLVED', 'absence_reads': absent, 'started_at': started,
            'completed_at': time.time(), 'history': history[-64:]}


def cleanup_allowance(clock, claim):
    # Never abandon a known owned resource merely because the normal budget
    # has expired. Late cleanup is an explicit overrun, not a new work window.
    remaining = clock.end-time.monotonic()
    return min(claim['cleanup_seconds'], remaining) if remaining > 0 else claim['cleanup_seconds']


def watch(journal, resource, *, interval=.2):
    claim = journal.read('claim'); binding = journal.binding()
    clock = Deadline(claim['requested_at'], claim['total_seconds'], allow_expired=True)
    journal.put('watcher-armed', {'claim_sha256': binding, 'pid': os.getpid(), 'at': time.time()})
    # Cache the exact resource and deadline before publishing liveness. Losing
    # the state path later must not disable cleanup of that cached resource.
    reason = None
    while reason is None:
        try:
            journal.heartbeat('watcher-heartbeat', 'watching')
            if journal.binding() != binding:
                raise ValueError('claim changed')
            beat = journal.read('owner-heartbeat'); now = time.time()
            if journal.read('owner-done'):
                reason = 'OWNER_DONE'
            elif clock.remaining(claim['cleanup_seconds']) <= 0:
                reason = 'CLEANUP_RESERVE'
            elif (not beat or beat['claim_sha256'] != binding
                    or not 0 <= now-beat['at'] < claim['stale_seconds']):
                reason = 'OWNER_LOST'
        except Exception:
            reason = 'STATE_OR_CLOCK_UNAVAILABLE'
        if reason is None:
            time.sleep(interval)
    # The monotonic budget survives clock/state failure.
    late = time.monotonic() >= clock.end
    result = dict(cleanup(resource, cleanup_allowance(clock, claim), interval=interval),
                  reason=reason, claim_sha256=binding, independent_pid=os.getpid(), late_cleanup=late)
    with contextlib.suppress(Exception):
        journal.put('watcher-cleanup', result)
    return result


def namespace_command(command):
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise RuntimeError('native root Linux required')
    # Parent death kills unshare, which kills namespace PID 1 and all detached
    # descendants. This trusted coordinator retains host access; model workers
    # still use the separately qualified input-only bwrap jail.
    return ['/usr/bin/setpriv', '--pdeathsig', 'KILL', '/usr/bin/unshare', '--pid',
            '--fork', '--mount-proc', '--kill-child=KILL', *map(str, command)]


def stop(process):
    if process is None:
        return
    if process.poll() is None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=5)


def export(root, destination):
    """Explicit bounded allowlist; no prompts, weights, jobs, credentials or links."""
    root, destination = Path(root).resolve(), Path(destination)
    if destination.resolve().is_relative_to(root):
        raise ValueError('export must be outside the execution tree')
    rows = []; total = 0
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise ValueError('symlink in evidence tree')
        if (path.name not in LEAVES and not re.fullmatch(r'wire-\d{4}\.json', path.name)):
            continue
        if any(p in ('models', 'random-models', 'sources', 'jobs', 'random-jobs', 'private') for p in relative.parts):
            continue
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 16*1024**2:
            raise ValueError('invalid evidence file type or size')
        total += info.st_size
        if total > LIMIT or len(rows) >= 512:
            raise ValueError('evidence envelope exceeded')
        rows.append((relative.as_posix(), path, info))
    if not rows:
        raise ValueError('no eligible evidence')
    manifest = {'schema': SCHEMA, 'files': []}
    with destination.open('xb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        with tarfile.open(fileobj=stream, mode='w') as archive:
            for name, path, before in rows:
                raw = runner.regular(path, 16*1024**2); after = path.stat()
                if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                    raise ValueError('evidence changed during export')
                import io
                info = tarfile.TarInfo(name); info.size = len(raw); info.mode = 0o600
                archive.addfile(info, io.BytesIO(raw))
                manifest['files'].append({'path': name, 'bytes': len(raw), 'sha256': digest(raw)})
            raw = encoded(manifest); info = tarfile.TarInfo('manifest.json'); info.size = len(raw); info.mode = 0o600
            archive.addfile(info, io.BytesIO(raw))
        stream.flush(); os.fsync(stream.fileno())
    with destination.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'status': 'EXPORTED_LOCAL_PRIVATE', 'sha256': sha, 'bytes': destination.stat().st_size,
            'files': manifest['files'], 'completed_at': time.time(), 'uploaded': False}


def recover(root):
    reports = []
    for assignment in sorted(Path(root).rglob('assignment.json')):
        directory = assignment.parent
        if not (directory/'collection.json').exists() and not (directory/'recovery.json').exists():
            if (directory/'ledger.jsonl').exists():
                value = runner.recover(directory)
                reports.append({'path': str(directory.relative_to(root)), 'coverage': value['coverage']})
                # These owner-written paths identify only disposable worker
                # copies. Work has already stopped in the outer namespace.
                import shutil
                assignment_value = json.loads(runner.regular(assignment, 16*1024**2))
                for item in assignment_value.get('disposable_worker_assets', []):
                    path = Path(item)
                    if (path.parent != Path('/tmp') or not path.name.startswith('backtrace-model-worker-')
                            or path.is_symlink()):
                        raise ValueError('unexpected disposable worker path')
                    if path.exists():
                        if path.stat().st_uid != os.geteuid():
                            raise ValueError('disposable worker owner changed')
                        shutil.rmtree(path)
    return reports


def supervise(journal, resource, command, output, *, interval=.2, recover_results=True):
    """Setup, staging and inference are all children of the same outer deadline.

    The caller supplies an already reviewed command and resource; this cannot
    provision one. The independently started watcher must be armed and fresh.
    """
    claim = journal.read('claim'); binding = journal.binding()
    clock = Deadline(claim['requested_at'], claim['total_seconds'], allow_expired=True)
    output = Path(output); output.mkdir(mode=0o700, exist_ok=False)
    process = None; result = {'status': 'INCOMPLETE', 'allocation_requests': 0,
                             'source_sha': claim['source_sha'], 'claim_sha256': binding}
    try:
        armed = journal.read('watcher-armed'); beat = journal.read('watcher-heartbeat')
        if (not armed or armed['pid'] == os.getpid() or armed['claim_sha256'] != binding
                or not beat or beat['claim_sha256'] != binding
                or not 0 <= time.time()-beat['at'] < claim['stale_seconds']):
            raise ValueError('fresh independently armed watcher required')
        reserve = claim['export_seconds']+claim['cleanup_seconds']
        if clock.remaining(reserve) <= 0:
            raise TimeoutError('work cannot consume export/deletion reserve')
        if not resource.observe():
            raise ValueError('bound resource absent before work')
        with (output/'worker.log').open('xb') as log:
            process = subprocess.Popen(namespace_command(command), stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, start_new_session=True,
                env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8',
                     'HF_HUB_OFFLINE': '1', 'TOKENIZERS_PARALLELISM': 'false'})
            while process.poll() is None:
                if clock.remaining(reserve) <= 0:
                    raise TimeoutError('allocation-inclusive work deadline')
                if journal.binding() != binding:
                    raise ValueError('claim changed during work')
                beat = journal.read('watcher-heartbeat')
                if not beat or beat['claim_sha256'] != binding or not 0 <= time.time()-beat['at'] < claim['stale_seconds']:
                    raise ValueError('independent watcher lost')
                journal.heartbeat('owner-heartbeat', 'work')
                time.sleep(min(interval, max(0, clock.remaining(reserve))))
            result['worker_exit'] = process.returncode
            if clock.remaining(reserve) <= 0:
                raise TimeoutError('work completed after allocation-inclusive deadline')
            if process.returncode != 0:
                raise RuntimeError('worker failed; automatic retry forbidden')
            result['status'] = 'WORK_COMPLETE'
    except Exception as error:
        import traceback
        result['failure'] = {'type': type(error).__name__, 'frames': [
            {'file': Path(f.filename).name, 'function': f.name, 'line': f.lineno}
            for f in traceback.extract_tb(error.__traceback__)[-4:]]}
    finally:
        try:
            stop(process)
        except Exception as error:
            result['stop_error'] = type(error).__name__
            result['status'] = 'INCOMPLETE'
        result['worker_exit'] = process.returncode if process else None
        # Recovery and archive creation are separately killed at the export
        # deadline; slow files or a stuck exporter cannot postpone deletion.
        try:
            seconds = min(claim['export_seconds'], max(0, clock.end-time.monotonic()-claim['cleanup_seconds']))
            if seconds <= 0:
                raise TimeoutError('export reserve exhausted')
            write(output/'result.json', result)
            export_command = [sys.executable, '-m', 'tools.small_model_lifecycle', 'export', str(output),
                              str(output.parent/(output.name+'.tar'))]
            if recover_results:
                export_command.append('--recover')
            with (journal.root/'export.log').open('xb') as log:
                exporting = subprocess.Popen(namespace_command(export_command), stdout=log, stderr=log,
                    start_new_session=True, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'})
                try:
                    export_end = time.monotonic()+seconds
                    while exporting.poll() is None:
                        if time.monotonic() >= export_end:
                            raise TimeoutError('export deadline')
                        with contextlib.suppress(Exception):
                            journal.heartbeat('owner-heartbeat', 'export')
                        time.sleep(min(.1, max(0, export_end-time.monotonic())))
                finally:
                    stop(exporting)
                if exporting.returncode != 0:
                    raise RuntimeError('bounded export failed')
            result['export'] = json.loads(runner.regular(output.parent/(output.name+'.export.json'), LIMIT))
        except Exception as error:
            result['export_error'] = type(error).__name__
        with contextlib.suppress(Exception):
            journal.put('owner-done', {'claim_sha256': binding, 'at': time.time()})
        result['late_cleanup'] = time.monotonic() >= clock.end
        result['cleanup'] = cleanup(resource, cleanup_allowance(clock, claim), interval=interval)
        result['status'] = ('PASS_LOCAL_SUPERVISION' if result['status'] == 'WORK_COMPLETE'
                            and result.get('export') and result['cleanup']['status'] == 'DELETED' else 'INCOMPLETE')
        with contextlib.suppress(Exception):
            journal.put('owner-result', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('export'); a.add_argument('root', type=Path); a.add_argument('output', type=Path)
    a.add_argument('--recover', action='store_true'); args = p.parse_args()
    recovered = recover(args.root) if args.recover else []
    value = dict(export(args.root, args.output), recovered=recovered)
    write(args.output.with_suffix('.export.json'), value)
    print(json.dumps(value, sort_keys=True))


if __name__ == '__main__':
    main()
