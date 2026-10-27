"""Standalone hardware-only OCI diagnostic. No weights, prompts or model calls."""
import ctypes
import errno
import fcntl
import importlib.util
import json
import mmap
import os
from pathlib import Path
import platform
import re
import resource
import select
import signal
import subprocess
import sys
import time

ROOT = Path('/opt/backtrace')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def resident_probe(size):
    if type(size) is not int or not 4096 <= size <= 8*1024**3 or size % 4096:
        raise ValueError('bounded page-aligned RAM diagnostic required')
    with mmap.mmap(-1, size, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS) as pages:
        pages.madvise(mmap.MADV_NOHUGEPAGE)
        for offset in range(0, size, 4096):pages[offset] = 1
        vector=(ctypes.c_ubyte*(size//4096))()
        buffer=(ctypes.c_char*size).from_buffer(pages)
        libc=ctypes.CDLL(None,use_errno=True)
        if libc.mincore(ctypes.c_void_p(ctypes.addressof(buffer)),ctypes.c_size_t(size),vector):
            raise OSError(ctypes.get_errno(),'mincore failed')
        resident=sum(bool(x&1) for x in vector)*4096
        del buffer
        status=Path('/proc/self/status').read_text()
        rss=int(re.search(r'^VmRSS:\s+(\d+) kB$',status,re.M)[1])*1024
        swap=int(re.search(r'^VmSwap:\s+(\d+) kB$',status,re.M)[1])*1024
        if resident!=size or rss<size or swap:raise RuntimeError('requested physical pages not resident')
        time.sleep(.1)
        return {'touched_bytes':size,'resident_bytes':resident,'rss_bytes':rss,'swap_bytes':swap,
                'full_model_memory_admission':'NOT_ESTABLISHED','future_reservation':False}


def child(parent, mode):
    base=module('boundary_launcher',ROOT/'launcher.py')
    for cap in range(64):
        if base.LIBC.prctl(24,cap,0,0,0) and ctypes.get_errno()!=errno.EINVAL:
            raise OSError(ctypes.get_errno(),'capability drop failed')
    os.setgroups([]);os.setresgid(65532,65532,65532);os.setresuid(65532,65532,65532)
    base.prctl(1,signal.SIGKILL)
    if os.getppid()!=parent:raise RuntimeError('supervisor already lost')
    os.closerange(3,1024);os.chdir('/tmp')
    config=json.loads(Path('/job.json').read_bytes())
    os.environ.clear();os.environ.update({'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':'/tmp',
        'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false',
        'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1',
        'CUDA_CACHE_DISABLE':'1','CUDA_VISIBLE_DEVICES':config.get('gpu',{}).get('uuid',''),
        'CUDA_DEVICE_ORDER':'PCI_BUS_ID'})
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576))
    base.restrict_syscalls()
    if mode=='boundary':base.boundary();return
    if mode=='memory':
        print(json.dumps(resident_probe(config['resident_bytes'])),flush=True);return
    if mode=='cpu-hold':
        print(json.dumps({'status':'CPU_CONTEXT_ACTIVE','pid':os.getpid()}),flush=True)
        while True:time.sleep(.1)
    worker=module('fixed_cuda_worker',ROOT/'worker.py')
    facts=worker.cuda_check(config)
    if mode=='kernels':worker.send({'status':'PASS_ACTUAL_CUDA_KERNELS','gpu':facts});return
    if mode!='active':raise ValueError('hardware diagnostic mode required')
    import torch
    x=torch.ones((1024,1024),device='cuda:0',dtype=torch.bfloat16);y=torch.empty_like(x)
    torch.mm(x,x,out=y);torch.cuda.synchronize()
    worker.send({'status':'CUDA_CONTEXT_ACTIVE','gpu':facts,'allocated_bytes':torch.cuda.memory_allocated()})
    while True:torch.mm(x,x,out=y);torch.cuda.synchronize()


def supervise(mode, seconds, config_path):
    if (os.geteuid()!=0 or platform.python_version()!='3.12.14' or
            mode not in ('boundary','memory','cpu-hold','kernels','active') or not 0<float(seconds)<=180):
        raise ValueError('fixed hardware-only modes and bounded root supervisor required')
    base=module('boundary_launcher',ROOT/'launcher.py')
    parent=os.getppid();base.prctl(1,signal.SIGKILL)
    if os.getppid()!=parent:raise RuntimeError('SSH parent lost')
    config_path=Path(config_path)
    if config_path.parent!=ROOT or config_path.name not in ('minimum-cpu.json','minimum-gpu.json'):
        raise ValueError('fixed diagnostic config required')
    config=json.loads(config_path.read_bytes())
    if set(config)-{'gpu','resident_bytes'}:raise ValueError('no model or prompt parameters allowed')
    if mode in ('kernels','active') and not re.fullmatch(r'GPU-[0-9a-fA-F-]{36}',config['gpu']['uuid']):
        raise ValueError('single GPU UUID required')
    lock=open('/root/backtrace/worker.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    job=Path('/job.json')
    if job.exists():job.unlink()
    job.write_text(json.dumps(config));job.chmod(0o444)
    child_process=subprocess.Popen([sys.executable,'-I',__file__,'child',str(os.getpid()),mode],
        stdin=subprocess.DEVNULL,close_fds=True,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8',
        'LD_LIBRARY_PATH':str(ROOT/'python/lib')})
    started=time.monotonic();end=started+float(seconds)
    state={'pid':child_process.pid,'start_ticks':Path(f'/proc/{child_process.pid}/stat').read_text().split()[21],
        'supervisor_pid':os.getpid(),'mode':mode,'reason':'RUNNING'}
    log=Path('/root/backtrace/minimum-state.json');base.state_write(log,state)
    try:
        while child_process.poll() is None:
            if time.monotonic()>=end:state['reason']='DEADLINE';break
            readable,_,_=select.select([0],[],[],min(.1,max(0,end-time.monotonic())))
            if readable and not os.read(0,65536):state['reason']='TRANSPORT_EOF';break
        if child_process.poll() is None:child_process.kill()
        code=child_process.wait(timeout=3)
        state.update(exit_code=code,elapsed_seconds=time.monotonic()-started,
            reason=state['reason'] if state['reason']!='RUNNING' else 'EXITED')
        base.state_write(log,state);return code if code>=0 else 128-code
    finally:
        if child_process.poll() is None:child_process.kill();child_process.wait(timeout=3)
        lock.close()


if __name__=='__main__':
    if sys.argv[1]=='child':child(int(sys.argv[2]),sys.argv[3])
    elif sys.argv[1]=='run':raise SystemExit(supervise(sys.argv[2],float(sys.argv[3]),sys.argv[4]))
    else:raise ValueError('unknown hardware diagnostic operation')
