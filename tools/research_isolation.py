"""Root-owned coordinator; disposable PID/network namespaces for original tools.

Model-selected commands run without capabilities under a dedicated UID. The
coordinator and HTTP ledger never share that UID. This is Linux CPU qualification;
it does not authorize a provider allocation or claim a complete hostile-host jail.
"""
import contextlib
import os
from pathlib import Path, PurePosixPath
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time

UIDS = (65532, 65533)


def file_parts(path):
    raw = str(path)
    if raw.startswith('/workspace/'):
        raw = raw[len('/workspace/'):]
    value = PurePosixPath(raw)
    if value.is_absolute() or not value.parts or any(x in ('.', '..') for x in raw.split('/')):
        raise ValueError('workspace-relative regular file required')
    return value.parts


@contextlib.contextmanager
def parent_fd(root, parts, *, create=False, uid=None):
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=descriptor)
                    os.chown(part, uid, uid, dir_fd=descriptor, follow_symlinks=False)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor); descriptor = child
        yield descriptor, parts[-1]
    finally:
        os.close(descriptor)


def read_workspace(root, path, limit=8 * 1024**2):
    with parent_fd(root, file_parts(path)) as (parent, leaf):
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit or info.st_nlink != 1:
                raise ValueError('bounded unlinked regular workspace file required')
            value = stream.read(limit + 1)
            if len(value) > limit:
                raise ValueError('workspace file exceeded limit')
            return value


def write_workspace(root, path, value, uid, limit=8 * 1024**2):
    if uid not in UIDS or len(value) > limit:
        raise ValueError('bounded workspace write required')
    with parent_fd(root, file_parts(path), create=True, uid=uid) as (parent, leaf):
        # Check link count before truncation; never follow a target symlink.
        fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
        with os.fdopen(fd, 'wb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('regular non-hardlinked workspace target required')
            os.ftruncate(stream.fileno(), 0); os.fchown(stream.fileno(), uid, uid)
            stream.write(value)


KEEPER = r'''
import os, pathlib, signal, subprocess, sys, time
subprocess.run([sys.argv[2], 'link', 'set', 'lo', 'up'], check=True)
def reap(*args):
    try:
        while os.waitpid(-1, os.WNOHANG)[0]: pass
    except ChildProcessError: pass
signal.signal(signal.SIGCHLD, reap)
pathlib.Path(sys.argv[1]).write_text('ready')
while True: time.sleep(1)
'''


class Namespace:
    def __init__(self, root):
        if os.geteuid() != 0 or not all(shutil.which(n) for n in ('unshare', 'nsenter', 'setpriv', 'ip')):
            raise RuntimeError('root Linux namespace tools required')
        self.root = Path(root); self.root.mkdir(mode=0o700)
        ready = self.root / 'ready'
        self.log = (self.root / 'keeper.log').open('wb')
        self.process = subprocess.Popen(['/usr/bin/unshare', '--net', '--pid', '--fork', '--mount-proc',
            '--kill-child=KILL', sys.executable, '-I', '-c', KEEPER, str(ready), shutil.which('ip')],
            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'},
            stdin=subprocess.DEVNULL, stdout=self.log, stderr=self.log, start_new_session=True)
        self.pid = None; self.namespace_id = None
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError('namespace creation failed; see private keeper log')
                children = Path(f'/proc/{self.process.pid}/task/{self.process.pid}/children').read_text().split()
                if ready.exists() and len(children) == 1:
                    self.pid = int(children[0]); self.namespace_id = os.readlink(f'/proc/{self.pid}/ns/pid')
                    break
                time.sleep(.02)
            if self.pid is None:
                raise TimeoutError('namespace readiness deadline')
        except BaseException:
            self.close(); raise

    def prefix(self, uid):
        if uid not in UIDS or not self.alive():
            raise RuntimeError('inactive isolated sandbox')
        return ['/usr/bin/nsenter', '--target', str(self.pid), '--pid', '--net', '--mount',
                '/usr/bin/setpriv', '--no-new-privs', '--bounding-set=-all', '--inh-caps=-all',
                '--ambient-caps=-all', '--reuid='+str(uid), '--regid='+str(uid), '--clear-groups']

    def alive(self):
        try:
            return self.process.poll() is None and os.readlink(f'/proc/{self.pid}/ns/pid') == self.namespace_id
        except (FileNotFoundError, ProcessLookupError):
            return False

    def close(self):
        if self.process.poll() is None:
            with contextlib.suppress(ProcessLookupError): os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=5)
        self.log.close()


class Isolation:
    def __init__(self, root, uid):
        if uid not in UIDS or os.geteuid() != 0:
            raise ValueError('dedicated root-coordinated UID required')
        self.root, self.uid = Path(root), uid
        self.root.mkdir(mode=0o700)
        self.namespaces = {}; self.lock = threading.RLock()
        self.deadline = None; self.timer = None; self.expired = False; self.finished = False
        self.operations = 0; self.closed_namespaces = 0

    def attach(self, manager):
        self.manager = manager
        original_start, original_stop, original_exec = manager.start, manager.stop, manager.exec
        original_copy_to = manager.copy_to
        def start():
            sid = original_start()
            paths = manager.sandboxes[sid]
            # Only this task's known ancestors become traversable. Private input
            # directories are siblings and retain their owner-only permissions.
            paths['root'].chmod(0o711); paths['root'].parent.chmod(0o711)
            paths['root'].parent.parent.chmod(0o711)
            for kind in ('workspace', 'tmp', 'venv'):
                base = paths[kind]
                for p in [base, *base.rglob('*')]:
                    os.chown(p, self.uid, self.uid, follow_symlinks=False)
                base.chmod(0o700)
            with self.lock:
                self.namespaces[sid] = Namespace(self.root / sid)
            return sid
        def execute(sid, command, *, timeout=None):
            with self.lock:
                if self.expired or self.finished:
                    raise TimeoutError('active work has ended')
                namespace = self.namespaces[sid]
                seconds = min(60, timeout if timeout is not None else manager.timeout_seconds)
                if self.deadline is not None:
                    seconds = min(seconds, self.deadline - time.perf_counter())
                if seconds <= 0:
                    raise TimeoutError('active work deadline')
                prefix = namespace.prefix(self.uid)
                self.operations += 1
            wrapped = shlex.join(prefix + ['/bin/bash', '-c', command])
            return original_exec(sid, wrapped, timeout=seconds)
        def stop(sid):
            with self.lock:
                namespace = self.namespaces.pop(sid, None)
            if namespace is not None:
                namespace.close(); self.closed_namespaces += 1
            original_stop(sid)
        def copy_from(sid, source, destination):
            value = read_workspace(manager.sandboxes[sid]['workspace'], source)
            Path(destination).parent.mkdir(parents=True, exist_ok=True)
            Path(destination).write_bytes(value)
        def copy_to(sid, source, destination):
            source, destination = Path(source), str(destination)
            if destination.endswith('/') or destination in ('/workspace', '/tmp'):
                destination = destination.rstrip('/') + '/' + source.name
            if str(destination).startswith('/workspace/'):
                write_workspace(manager.sandboxes[sid]['workspace'], destination, source.read_bytes(), self.uid)
            elif self.deadline is not None:
                raise ValueError('active agent may only write workspace files')
            elif destination == '/tmp' or destination.startswith('/tmp/'):
                relative = source.name if destination in ('/tmp', '/tmp/') else destination[len('/tmp/'):]
                write_workspace(manager.sandboxes[sid]['tmp'], relative, source.read_bytes(), self.uid, 128 * 1024**2)
            else:
                original_copy_to(sid, source, destination)
        manager.start, manager.stop, manager.exec = start, stop, execute
        manager.copy_from, manager.copy_to = copy_from, copy_to
        return manager

    def begin(self, started, seconds=300):
        if self.deadline is not None or self.finished or not 0 < seconds <= 300:
            raise ValueError('one bounded work session required')
        self.deadline = started + seconds
        self.timer = threading.Timer(max(0, self.deadline - time.perf_counter()), self.expire)
        self.timer.daemon = True; self.timer.start()

    def expire(self):
        with self.lock:
            if self.finished: return
            self.expired = True
            for namespace in self.namespaces.values(): namespace.close()

    def finish(self):
        with self.lock:
            self.finished = True
            if self.timer is not None: self.timer.cancel()
            for namespace in self.namespaces.values(): namespace.close()

    def report(self):
        return {'sandbox_uid': self.uid, 'coordinator_uid': os.geteuid(),
                'pid_and_network_namespaces': True, 'no_new_privs': True,
                'capabilities_dropped': True, 'deadline_expired': self.expired,
                'command_operations': self.operations, 'closed_namespaces': self.closed_namespaces,
                'live_namespaces': sum(n.alive() for n in self.namespaces.values()),
                'reference_files_scope': 'owner-only; never copied into an agent sandbox'}


def bounded_child(command, log, env, *, timeout=330):
    """Killing namespace PID 1 also kills detached descendants and inner sandboxes."""
    if os.geteuid() != 0 or not 0 < timeout <= 330:
        raise ValueError('root and bounded child allowance required')
    started = time.perf_counter()
    with Path(log).open('wb') as stream:
        process = subprocess.Popen(['/usr/bin/unshare', '--pid', '--fork', '--mount-proc',
            '--kill-child=KILL', *map(str, command)], env=env, stdin=subprocess.DEVNULL,
            stdout=stream, stderr=stream, start_new_session=True)
        expired = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            expired = True
            with contextlib.suppress(ProcessLookupError): os.killpg(process.pid, signal.SIGKILL)
            code = process.wait(timeout=5)
    return {'exit_code': code, 'child_timeout': expired,
            'wall_seconds': time.perf_counter() - started, 'child_limit_seconds': timeout}
