"""Standalone hardware-only OCI diagnostic. No weights, prompts or model calls."""
import ctypes
import errno
import fcntl
import hashlib
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
DIAGNOSTIC_MODES = ('diagnostic-a', 'diagnostic-b', 'diagnostic-c')


def diagnostic_identity():
    fields = dict(row.split(':', 1) for row in Path('/proc/self/status').read_text().splitlines() if ':' in row)
    names = ('Uid', 'Gid', 'Groups', 'CapEff', 'CapPrm', 'CapBnd', 'NoNewPrivs', 'Seccomp', 'Seccomp_filters')
    return {**{name: fields.get(name, 'UNAVAILABLE').strip() for name in names},
            'limits': {name: list(resource.getrlimit(getattr(resource, name)))
                       for name in ('RLIMIT_CORE', 'RLIMIT_FSIZE', 'RLIMIT_NOFILE', 'RLIMIT_AS', 'RLIMIT_NPROC')},
            'python': platform.python_version(), 'executable': sys.executable,
            'cuda_visible_devices': os.environ.get('CUDA_VISIBLE_DEVICES'),
            'environment_sha256': hashlib.sha256(json.dumps(dict(os.environ), sort_keys=True).encode()).hexdigest()}


def diagnostic_cuda(config, mode):
    """Same original kernel probe first; supplemental observations never repair it."""
    case = mode[-1].upper()
    checkpoint = {'case': case, 'phase': 'BEFORE_CUDA', 'identity': diagnostic_identity()}
    # The existing channel permits one stdout response. Put the durable pre-CUDA
    # checkpoint in stderr so it also survives timeout/EOF without a new protocol.
    print('BACKTRACE_CUDA_BEFORE '+json.dumps(checkpoint), file=sys.stderr, flush=True)
    result = {'case': case, 'phase': 'RESULT', 'status': 'FAIL'}
    try:
        worker = module('fixed_cuda_worker', ROOT/'worker.py')
        result['gpu'] = worker.cuda_check(config)
        result['status'] = 'PASS_ACTUAL_CUDA_KERNELS'
    except Exception as exc:
        import traceback
        traceback.print_exc()  # Preserve original warning/exception, including CUDA code.
        result.update(error_type=type(exc).__name__, error=str(exc)[:1500])
    print('BACKTRACE_CUDA_PRIMARY '+json.dumps(result), file=sys.stderr, flush=True)
    # These calls follow the unchanged torch probe. They are not independent
    # controls and must not be used to replace a failed primary observation.
    result['supplemental_after_probe'] = {}
    try:
        driver = ctypes.CDLL('libcuda.so.1')
        driver.cuInit.argtypes = [ctypes.c_uint]; driver.cuInit.restype = ctypes.c_int
        result['supplemental_after_probe']['cuInit_return'] = driver.cuInit(0)
    except Exception as exc:
        result['supplemental_after_probe']['driver_error'] = str(exc)[:500]
    result['device_open'] = {}
    for name in (config['gpu']['device_basename'], 'nvidiactl', 'nvidia-uvm'):
        try:
            fd = os.open('/dev/'+name, os.O_RDWR | os.O_CLOEXEC)
            os.close(fd); result['device_open'][name] = 0
        except OSError as exc:
            result['device_open'][name] = exc.errno
    paths = set()
    for row in Path('/proc/self/maps').read_text().splitlines():
        parts = row.split(None, 5)
        if len(parts) == 6 and Path(parts[5]).name.startswith(('libcuda.', 'libcudart.')):
            paths.add(parts[5])
    result['cuda_libraries'] = {}
    for path in sorted(paths):
        try:
            with open(path, 'rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            result['cuda_libraries'][path] = {'sha256': digest}
            if Path(path).name.startswith('libcudart.'):
                runtime = ctypes.CDLL(path)
                runtime.cudaGetDeviceCount.argtypes = [ctypes.POINTER(ctypes.c_int)]
                runtime.cudaGetDeviceCount.restype = ctypes.c_int
                count = ctypes.c_int()
                code = runtime.cudaGetDeviceCount(ctypes.byref(count))
                result['supplemental_after_probe']['cudaGetDeviceCount_return'] = code
                result['supplemental_after_probe']['device_count'] = count.value if code == 0 else None
        except Exception as exc:
            result['cuda_libraries'][path] = {'error_type': type(exc).__name__, 'error': str(exc)[:500]}
    print(json.dumps(result), flush=True)


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
    if mode != 'diagnostic-a':
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
    if mode == 'diagnostic-b':
        base.prctl(38, 1)  # B and C share no-new-privileges; only C adds our filter.
    elif mode != 'diagnostic-a':
        base.restrict_syscalls()
    if mode in DIAGNOSTIC_MODES:
        diagnostic_cuda(config, mode);return
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
            mode not in ('boundary','memory','cpu-hold','kernels','active',*DIAGNOSTIC_MODES) or not 0<float(seconds)<=180):
        raise ValueError('fixed hardware-only modes and bounded root supervisor required')
    base=module('boundary_launcher',ROOT/'launcher.py')
    parent=os.getppid();base.prctl(1,signal.SIGKILL)
    if os.getppid()!=parent:raise RuntimeError('SSH parent lost')
    config_path=Path(config_path)
    if config_path.parent!=ROOT or config_path.name not in ('minimum-cpu.json','minimum-gpu.json'):
        raise ValueError('fixed diagnostic config required')
    config=json.loads(config_path.read_bytes())
    if set(config)-{'gpu','resident_bytes'}:raise ValueError('no model or prompt parameters allowed')
    if mode in ('kernels','active',*DIAGNOSTIC_MODES) and not re.fullmatch(r'GPU-[0-9a-fA-F-]{36}',config['gpu']['uuid']):
        raise ValueError('single GPU UUID required')
    if mode in DIAGNOSTIC_MODES and (seconds > 30 or
            not re.fullmatch(r'nvidia[0-9]+',config['gpu']['device_basename'])):
        raise ValueError('30-second fixed-device diagnostic required')
    lock=open('/root/backtrace/worker.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    job=Path('/job.json')
    if job.exists():job.unlink()
    job.write_text(json.dumps(config));job.chmod(0o444)
    child_process=subprocess.Popen([sys.executable,'-I',__file__,'child',str(os.getpid()),mode],
        stdin=subprocess.DEVNULL,close_fds=True,start_new_session=mode in DIAGNOSTIC_MODES,
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8',
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
        if child_process.poll() is None and state['reason']=='TRANSPORT_EOF':
            # A completed JSON response can reach the owner before Python/CUDA
            # finishes finalization. Preserve the same bounded graceful EOF
            # allowance as the already qualified container supervisor.
            try:child_process.wait(timeout=min(1,max(.001,end-time.monotonic())))
            except subprocess.TimeoutExpired:pass
        if child_process.poll() is None:child_process.kill()
        code=child_process.wait(timeout=3)
        state.update(exit_code=code,elapsed_seconds=time.monotonic()-started,
            reason=state['reason'] if state['reason']!='RUNNING' else 'EXITED')
        base.state_write(log,state);return code if code>=0 else 128-code
    finally:
        # A/B permit trusted-library process creation. Clean their process group,
        # including children that outlive the main probe, under the same deadline.
        if mode in DIAGNOSTIC_MODES:
            try:os.killpg(child_process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        if child_process.poll() is None:child_process.kill();child_process.wait(timeout=3)
        lock.close()


if __name__=='__main__':
    if sys.argv[1]=='child':child(int(sys.argv[2]),sys.argv[3])
    elif sys.argv[1]=='run':raise SystemExit(supervise(sys.argv[2],float(sys.argv[3]),sys.argv[4]))
    else:raise ValueError('unknown hardware diagnostic operation')
