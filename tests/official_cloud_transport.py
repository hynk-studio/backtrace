"""Free loopback integration of the rebuilt transport; no provider access.

Only this CPU test temporarily binds the observed executable hashes. Paid code
must use separately reviewed fixed hashes. Listener paths/ports are disposable.
"""
import json
import contextlib
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
import queue
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import ssh_bootstrap as ssh
from tools.runpod_job import check_owner_host, private_json
from tools.private_delivery import push, ssh_command


class DelayedRelay:
    """One loopback-only stream; fixed one-way delay, without per-chunk throttling."""
    def __init__(self, target_port, delay=.1):
        self.target_port=target_port;self.delay=delay
        self.stop=threading.Event();self.errors=[];self.sockets=[];self.threads=[]
        self.listener=socket.socket();self.listener.bind(('127.0.0.1',0));self.listener.listen(1)
        self.listener.settimeout(.2);self.port=self.listener.getsockname()[1]

    def __enter__(self):
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start();return self

    def run(self):
        try:
            end=time.monotonic()+70
            while not self.stop.is_set():
                try:client,_=self.listener.accept();break
                except socket.timeout:
                    if time.monotonic()>end:raise TimeoutError('relay accept deadline')
            else:return
            server=socket.create_connection(('127.0.0.1',self.target_port),timeout=5)
            self.sockets=[client,server]
            for sock in self.sockets:sock.settimeout(1)
            def read(src,q):
                try:
                    while not self.stop.is_set():
                        try:data=src.recv(65536)
                        except socket.timeout:continue
                        item=(time.monotonic()+self.delay,data)
                        while not self.stop.is_set():
                            try:q.put(item,timeout=.2);break
                            except queue.Full:pass
                        if not data:return
                except Exception as e:
                    if not self.stop.is_set():self.errors.append(type(e).__name__)
            def write(dst,q):
                try:
                    while not self.stop.is_set():
                        try:due,data=q.get(timeout=.2)
                        except queue.Empty:continue
                        if self.stop.wait(max(0,due-time.monotonic())):return
                        if not data:
                            with contextlib.suppress(OSError):dst.shutdown(socket.SHUT_WR)
                            return
                        dst.sendall(data)
                except Exception as e:
                    if not self.stop.is_set():self.errors.append(type(e).__name__)
            for src,dst in ((client,server),(server,client)):
                q=queue.Queue(maxsize=256)  # At most16MiB queued per direction.
                for fn,args in ((read,(src,q)),(write,(dst,q))):
                    t=threading.Thread(target=fn,args=args,daemon=True);self.threads.append(t);t.start()
            while any(t.is_alive() for t in self.threads) and not self.stop.wait(.1):
                if time.monotonic()>end:raise TimeoutError('relay lifetime deadline')
        except Exception as e:
            if not self.stop.is_set():self.errors.append(type(e).__name__)

    def __exit__(self,*args):
        self.stop.set();self.listener.close()
        for sock in self.sockets:
            with contextlib.suppress(OSError):sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        self.thread.join(3)
        for t in self.threads:t.join(2)
        if self.thread.is_alive() or any(t.is_alive() for t in self.threads):
            raise RuntimeError('free relay cleanup incomplete')


def window_comparison(binary,root,owner,target,original_port):
    """ABBA with identical64MiB and200ms imposed RTT; no provider/model access."""
    import hashlib
    data=hashlib.shake_256(b'backtrace-window-control-v1').digest(64*1024**2)
    payload=root/'window-source';payload.mkdir(mode=0o700)
    (payload/'fixture.bin').write_bytes(data)
    manifest=json.dumps({'schema_version':1,'phase':'bootstrap','files':[
        {'path':'fixture.bin','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}).encode()
    manifest_path=root/'window-manifest.json';manifest_path.write_bytes(manifest)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    command=[str(binary.resolve()),'-F','-e','-j','-k','-G','root','-W','8388608',
        '-D',str(target/'auth'),'-p','127.0.0.1:'+str(port),'-r',str(target/'host-key'),
        '-P',str(target/'window-sshd.pid')]
    rows=[]
    with (root/'window-daemon.log').open('xb') as log:
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
            start_new_session=True,env={'PATH':'/usr/bin:/bin','HOME':'/root','LANG':'C.UTF-8'})
        try:
            end=time.monotonic()+5
            while True:
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.2):break
                except OSError:
                    if process.poll() is not None or time.monotonic()>end:raise
                    time.sleep(.05)
            for i,window in enumerate((1048576,8388608,8388608,1048576)):
                remote_port=original_port if window==1048576 else port
                with DelayedRelay(remote_port) as relay:
                    known=root/('window-known-'+str(i))
                    known.write_text(f'[127.0.0.1]:{relay.port} '+(owner/'host-public').read_text())
                    known.chmod(0o600)
                    destination=target/('window-input-'+str(i))
                    transfer=ssh_command('127.0.0.1',relay.port,owner/'owner-key',known,
                        str(destination),hashlib.sha256(manifest).hexdigest())
                    started=time.monotonic();receipt=push(payload,manifest_path,transfer,60)
                    elapsed=time.monotonic()-started
                    if (destination/'fixture.bin').read_bytes()!=data:raise AssertionError('window control bytes differ')
                if relay.errors:raise RuntimeError('window relay failed: '+str(relay.errors))
                rows.append({'order':i,'window_bytes':window,'imposed_one_way_delay_seconds':.1,
                    'seconds':elapsed,'bytes':len(data),'bytes_per_second':len(data)/elapsed,'receipt':receipt})
                print('BACKTRACE_WINDOW_CONTROL '+json.dumps(rows[-1],sort_keys=True),file=sys.stderr,flush=True)
        finally:
            if process.poll() is None:os.killpg(process.pid,signal.SIGTERM)
            process.wait(timeout=10)
    old=sum(r['seconds'] for r in rows if r['window_bytes']==1048576)/2
    new=sum(r['seconds'] for r in rows if r['window_bytes']==8388608)/2
    return {'status':'MEASURED_FREE_CONTROL_ONLY','rows':rows,'mean_elapsed_ratio_1MiB_to_8MiB':old/new,
        'supports_larger_window_under_imposed_delay':old/new>=2,
        'provider_failure_cause':'NOT_ESTABLISHED','provider_api_calls':0,'model_requests':0,
        'payload_sha256':hashlib.sha256(data).hexdigest(),'network':'LOOPBACK ONLY',
        'test_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def qualify(binary, keygen, profile=None, *, window_control=False):
    check_owner_host()
    observed = {'binary_sha256': ssh.sha(binary), 'keygen_sha256': ssh.sha(keygen)}
    if profile is not None:
        parameters = ssh.transport_parameters(profile)
        if any(parameters[key] != value for key, value in observed.items()):
            raise ValueError('rebuilt binaries differ from fixed Actions transport profile')
    binding = patch.dict(ssh.TRANSPORT, observed) if profile is None else contextlib.nullcontext()
    with tempfile.TemporaryDirectory(prefix='backtrace-transport-cpu-', dir='/root') as td, binding:
        root = Path(td); owner = root / 'owner'; target = root / 'pod'
        init = ssh.prepare(binary, keygen, owner, profile=profile)
        private_json(owner / 'initializer.json', init)
        ssh.validate_material(owner, profile=profile)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        source = ssh.START.replace("'/root/backtrace'", repr(str(target)))
        source = source.replace("('0.0.0.0',22)", repr(('127.0.0.1', port)))
        source = source.replace("'-p','22'", "'-p'," + repr('127.0.0.1:' + str(port)))
        with (root / 'daemon.log').open('w') as log:
            process = subprocess.Popen([sys.executable, '-I', '-c', source],
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
                     'RUNPOD_API_KEY': 'fixture-canary-no-credential', **init['env']},
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            try:
                ssh.deliver(owner, '127.0.0.1', port, 20, profile=profile)
                known = ssh.known_hosts(owner, '127.0.0.1', port)
                command = ssh_command('127.0.0.1', port, owner / 'owner-key', known,
                                      str(target / 'input'), '0' * 64)[:-1]
                program = "import os,json;assert os.getuid()==0;assert not any(k.startswith('BT_') or k=='RUNPOD_API_KEY' for k in os.environ);print('clean-root-ssh')"
                for attempt in range(20):
                    result = subprocess.run(command + [shlex.join(['python3', '-I', '-c', program])],
                        stdin=subprocess.DEVNULL, capture_output=True, timeout=10,
                        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
                    if result.returncode == 0:
                        break
                    if process.poll() is not None:
                        raise RuntimeError('rebuilt daemon exited')
                    time.sleep(.1)
                if result.returncode or result.stdout.strip() != b'clean-root-ssh':
                    raise RuntimeError('rebuilt strict SSH or environment qualification failed')
                wrong = owner / 'wrong-hosts'
                wrong.write_text(f'[127.0.0.1]:{port} ' + (owner / 'owner-key.pub').read_text())
                wrong.chmod(0o600)
                denied = ssh_command('127.0.0.1', port, owner / 'owner-key', wrong,
                                     str(target / 'unused'), '0' * 64)[:-1]
                result = subprocess.run(denied + ["printf should-never-execute"],
                    stdin=subprocess.DEVNULL, capture_output=True, timeout=10,
                    env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
                if result.returncode == 0 or result.stdout:
                    raise RuntimeError('wrong host identity was not rejected')
                import hashlib
                data = b'backtrace private transport fixture\n' * 4096
                source_dir = root / 'source'; source_dir.mkdir(mode=0o700)
                (source_dir / 'fixture.bin').write_bytes(data)
                manifest = json.dumps({'schema_version': 1, 'phase': 'bootstrap', 'files': [
                    {'path': 'fixture.bin', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}]}).encode()
                command = ssh_command('127.0.0.1', port, owner / 'owner-key', known,
                                      str(target / 'input'), hashlib.sha256(manifest).hexdigest())
                manifest_path = root / 'manifest.json'; manifest_path.write_bytes(manifest)
                push(source_dir, manifest_path, command, 20)
                if (target / 'input/fixture.bin').read_bytes() != data:
                    raise RuntimeError('actual SSH byte transfer mismatch')
                extra=window_comparison(binary,root,owner,target,port) if window_control else None
                return dict(observed, profile=profile, mutual_tls='PASS', strict_ssh='PASS', wrong_host='REJECTED',
                            clean_child_environment='PASS', private_transfer_bytes=len(data),
                            network='LOOPBACK ONLY', paid_operations=0,window_control=extra)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)


if __name__ == '__main__':
    os.umask(0o077)
    window='--window-control' in sys.argv
    if window:sys.argv.remove('--window-control')
    if len(sys.argv) not in (3, 4):
        raise ValueError('exact rebuilt binary and keygen required')
    print(json.dumps(qualify(Path(sys.argv[1]), Path(sys.argv[2]),
                             sys.argv[3] if len(sys.argv) == 4 else None,window_control=window), sort_keys=True))
