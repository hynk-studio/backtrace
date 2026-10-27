"""Dedicated OCI worker boundary, without nested namespace privileges.

Standalone trusted launcher, never a model-selected program. The native owner
keeps the evaluator. Only one inference worker is allowed in this container.
Socket creation, process creation, exec, ptrace and namespace changes are denied
in-kernel; ordinary threads remain available. This is not the native bwrap jail.
"""
import ctypes
import errno
import fcntl
import json
import os
from pathlib import Path
import platform
import runpy
import select
import signal
import subprocess
import sys
import time

ROOT = Path('/opt/backtrace')
LIBC = ctypes.CDLL(None, use_errno=True)


def prctl(option, value):
    if LIBC.prctl(option, value, 0, 0, 0):
        raise OSError(ctypes.get_errno(), 'prctl failed')


def restrict_syscalls():
    """x86_64 classic BPF; reject alternate ABIs, require real pthread clone."""
    if platform.machine() != 'x86_64' or platform.system() != 'Linux':
        raise RuntimeError('qualified Linux x86_64 required')
    class Filter(ctypes.Structure):
        _fields_ = [('code',ctypes.c_ushort),('jt',ctypes.c_ubyte),
                    ('jf',ctypes.c_ubyte),('k',ctypes.c_uint32)]
    class Program(ctypes.Structure):
        _fields_ = [('len',ctypes.c_ushort),('filter',ctypes.POINTER(Filter))]
    # LD W ABS, JEQ, RET; seccomp_data.arch, then syscall number.
    rows = [(0x20,0,0,4),(0x15,1,0,0xc000003e),(0x06,0,0,0x80000000),
            (0x20,0,0,0),(0x35,0,1,0x40000000),(0x06,0,0,0x80000000)]
    denied = (41,42,43,44,46,49,50,53,57,58,59,101,155,161,165,166,
              272,288,299,304,307,308,310,311,321,322,323,425,426,427,438)
    for nr in denied:
        rows += [(0x15,0,1,nr),(0x06,0,0,0x00050000|errno.EPERM)]
    # glibc uses clone3 when present, then safely falls back to clone on ENOSYS.
    rows += [(0x15,0,1,435),(0x06,0,0,0x00050000|errno.ENOSYS),
             (0x15,0,7,56),(0x20,0,0,16),(0x54,0,0,0x10900),
             (0x15,0,3,0x10900),(0x20,0,0,16),(0x54,0,0,0x7e0200ff),
             (0x15,1,0,0),(0x06,0,0,0x00050000|errno.EPERM),
             (0x06,0,0,0x7fff0000)]
    array = (Filter*len(rows))(*(Filter(*r) for r in rows))
    program = Program(len(rows), array)
    prctl(38,1)  # PR_SET_NO_NEW_PRIVS
    if LIBC.prctl(22,2,ctypes.byref(program),0,0):
        raise OSError(ctypes.get_errno(), 'seccomp filter unavailable')


def boundary():
    """Observed denial controls run under exactly the production worker filter."""
    import socket
    import threading
    status = dict(r.split(':',1) for r in Path('/proc/self/status').read_text().splitlines() if ':' in r)
    result = {'uid':os.getuid(),'caps':int(status['CapEff'],16),
              'no_new_privs':status['NoNewPrivs'].strip(),
              'seccomp':status['Seccomp'].strip(),
              'pid_namespace':os.readlink('/proc/self/ns/pid'),
              'net_namespace':os.readlink('/proc/self/ns/net')}
    def denied(name, operation):
        try: operation()
        except OSError as e: result[name] = e.errno in (errno.EPERM,errno.EACCES,errno.ENOENT)
        else: result[name] = False
    denied('socket_denied', lambda:socket.socket())
    denied('unix_socket_denied', lambda:socket.socket(socket.AF_UNIX))
    denied('fork_denied', os.fork)
    denied('exec_denied', lambda:os.execve('/usr/bin/true',['true'],{}))
    denied('root_denied', lambda:os.setuid(0))
    denied('private_file_denied', lambda:Path('/root/backtrace/private-canary').read_bytes())
    denied('readonly_job', lambda:Path('/job.json').write_text('overwrite'))
    def ns():
        if LIBC.unshare(0x10000000):raise OSError(ctypes.get_errno(),'unshare')
    denied('namespace_denied', ns)
    threaded=[];t=threading.Thread(target=lambda:threaded.append(True));t.start();t.join(3)
    result['threads_work']=threaded==[True]
    result['credential_environment_absent']=not any(k in ('RUNPOD_API_KEY','GITHUB_TOKEN','BACKTRACE_PRIVATE_CANARY') or k.startswith('BT_') for k in os.environ)
    print(json.dumps(result,sort_keys=True),flush=True)


def child(parent, script):
    # Dropping UID clears parent-death signal: establish it again afterward.
    for cap in range(64):
        if LIBC.prctl(24,cap,0,0,0) and ctypes.get_errno()!=errno.EINVAL:
            raise OSError(ctypes.get_errno(),'capability bound drop failed')
    os.setgroups([]);os.setresgid(65532,65532,65532);os.setresuid(65532,65532,65532)
    prctl(1,signal.SIGKILL)
    if os.getppid()!=parent:raise RuntimeError('supervisor already lost')
    os.closerange(3,1024)
    os.chdir('/tmp')
    os.environ.clear();os.environ.update({'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':'/tmp',
        'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false',
        'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1',
        'CUDA_CACHE_DISABLE':'1'})
    restrict_syscalls()
    if script=='boundary':boundary()
    else:runpy.run_path(str(ROOT/'worker.py'),run_name='__main__')


def supervise(job_name, seconds, script='worker'):
    if (os.geteuid()!=0 or platform.python_version()!='3.12.14'
            or not 0<float(seconds)<=3000 or script not in ('worker','boundary')
            or not job_name.replace('-','').isalnum()):
        raise ValueError('fixed root interpreter, safe job and bounded deadline required')
    parent=os.getppid();prctl(1,signal.SIGKILL)
    if os.getppid()!=parent:raise RuntimeError('SSH parent already lost')
    lock=open('/root/backtrace/worker.lock','a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    job=ROOT/'assets/jobs'/(job_name+'.json')
    value=json.loads(job.read_bytes());model=value.pop('container_model')
    if model not in ('E2B','E4B'):raise ValueError('unknown model')
    # Until real GPU isolation, memory admission and distributed cleanup qualify,
    # this version cannot become a paid/pretrained entry through a CLI flag.
    if value['mode'] not in ('random_fixture','scripted_control'):
        raise ValueError('container v1 is free CPU qualification only')
    for name,target in [('model',ROOT/'assets/models'/model),
                        ('tokenizer',ROOT/'assets/tokenizers'/model)]:
        p=Path('/'+name)
        if p.is_symlink():p.unlink()
        if p.exists():raise ValueError('worker mountpoint already occupied')
        p.symlink_to(target)
    p=Path('/job.json')
    if p.exists():p.unlink()
    with p.open('x') as f:json.dump(value,f)
    p.chmod(0o444)
    started=time.monotonic();end=started+float(seconds)
    log=Path('/root/backtrace')/(job_name+'-state.json')
    child_process=subprocess.Popen([sys.executable,'-I',__file__,'child',str(os.getpid()),script],
        stdin=subprocess.PIPE,bufsize=0,close_fds=True,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    state={'pid':child_process.pid,'start_ticks':Path(f'/proc/{child_process.pid}/stat').read_text().split()[21],
           'supervisor_pid':os.getpid(),'reason':'RUNNING'}
    log.write_text(json.dumps(state));pending=b''
    os.set_blocking(0,False);os.set_blocking(child_process.stdin.fileno(),False)
    try:
        while child_process.poll() is None:
            if time.monotonic()>=end:state['reason']='DEADLINE';break
            readers,writers,_=select.select([0] if len(pending)<131072 else [],
                [child_process.stdin] if pending else [],[],min(.1,max(0,end-time.monotonic())))
            if readers:
                data=os.read(0,65536)
                if not data:state['reason']='TRANSPORT_EOF';break
                pending+=data
            if writers:
                try:pending=pending[os.write(child_process.stdin.fileno(),pending):]
                except BrokenPipeError:break
        if child_process.poll() is None:
            # EOF normally permits graceful exit; deadline never extends.
            child_process.stdin.close()
            try:child_process.wait(timeout=min(1,max(.01,end-time.monotonic())))
            except subprocess.TimeoutExpired:child_process.kill()
        code=child_process.wait(timeout=3)
        state.update(exit_code=code,elapsed_seconds=time.monotonic()-started,
                     reason=state['reason'] if state['reason']!='RUNNING' else 'EXITED')
        log.write_text(json.dumps(state,sort_keys=True))
        return code if code>=0 else 128-code
    finally:
        if child_process.poll() is None:child_process.kill();child_process.wait(timeout=3)
        lock.close()


if __name__=='__main__':
    if sys.argv[1]=='child':child(int(sys.argv[2]),sys.argv[3])
    elif sys.argv[1]=='run':raise SystemExit(supervise(sys.argv[2],float(sys.argv[3]),sys.argv[4] if len(sys.argv)>4 else 'worker'))
    else:raise ValueError('unknown operation')
