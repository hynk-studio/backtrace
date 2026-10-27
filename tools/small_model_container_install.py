"""Standalone offline installation from an authenticated manifest-bound stream."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile

ROOT=Path('/opt/backtrace')


def unpack(archive, destination):
    """Regular entries only; no archive-provided modes, links or extraction hooks."""
    destination.mkdir(mode=0o755)
    seen=set();size=0
    with tarfile.open(archive,'r:gz') as tar:
        for item in tar:
            name=item.name;parts=name.split('/')
            size+=item.size
            if (not item.isfile() or item.pax_headers or name.startswith('/')
                    or any(x in ('','.','..') for x in parts) or '\\' in name
                    or str(PurePosixPath(name))!=name or name in seen
                    or len(seen)>=20000 or not 0<=item.size<=128*1024**2 or size>512*1024**2):
                raise ValueError('unsafe Python runtime archive')
            seen.add(name);target=destination/name
            target.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
            with tar.extractfile(item) as source,target.open('xb') as output:
                shutil.copyfileobj(source,output)
            target.chmod(0o555 if name.startswith('bin/') or '.so' in name else 0o444)
    if 'bin/python3.12' not in seen:raise ValueError('runtime interpreter missing')
    return {'files':len(seen),'bytes':size}


def installed(lock):
    spec=lock['gpu_candidate']
    if platform.python_version()!=spec['python'] or platform.machine()!='x86_64':
        raise ValueError('wrong isolated interpreter')
    norm=lambda n:re.sub(r'[-_.]+','-',n).lower()
    rows=list(importlib.metadata.distributions())
    actual={norm(d.metadata['Name']):d.version for d in rows}
    if actual!={norm(n):v for n,v in spec['packages'].items()} or len(rows)!=len(actual):
        raise ValueError('runtime package inventory differs')
    import torch
    import transformers,accelerate,triton,safetensors
    import cuda.bindings.driver
    if str(torch.__version__)!=spec['packages']['torch'] or torch.version.cuda!=spec['torch_cuda']:
        raise ValueError('wrong CUDA package build')
    torch.set_num_threads(1);x=torch.eye(4,dtype=torch.bfloat16)
    if not torch.equal(x@x,x):raise ValueError('CPU tensor compatibility failed')
    native={}
    for name in ('libtorch_cuda.so','libtorch_cpu.so','libc10_cuda.so'):
        p=Path(torch.__file__).parent/'lib'/name
        ld=subprocess.check_output(['ldd',str(p)],text=True,timeout=30)
        if 'not found' in ld:raise ValueError('native dependency unresolved')
        with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        native[name]={'sha256':digest,'bytes':p.stat().st_size,'ldd':ld}
    return {'status':'PASS_EXACT_CONTAINER_RUNTIME_CPU_ONLY','python':platform.python_version(),
            'packages':actual,'native_libraries':native,'compiled_cuda':torch.version.cuda,
            'gpu_kernels':'NOT_RUN','pretrained_inference':'NOT_RUN'}


def install(payload):
    if os.geteuid()!=0 or ROOT.exists():raise ValueError('fresh dedicated container required')
    payload=Path(payload);ROOT.mkdir(mode=0o755)
    runtime=unpack(payload/'python.tar.gz',ROOT/'python')
    python=ROOT/'python/bin/python3.12'
    env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':'/root','PIP_CONFIG_FILE':'/dev/null',
         'PIP_NO_INDEX':'1','PIP_NO_CACHE_DIR':'1','HF_HUB_OFFLINE':'1'}
    subprocess.run([str(python),'-I','-m','venv','--without-pip',str(ROOT/'venv')],
                   env=env,check=True,timeout=30)
    python=ROOT/'venv/bin/python';wheels=payload/'wheels'
    pip=list(wheels.glob('pip-*.whl'))
    if len(pip)!=1:raise ValueError('one pinned pip wheel required')
    # No-index/no-deps plus audit denial: offline installation cannot resolve
    # unrecorded network content. All bytes were pinned by private_delivery.
    code="""import sys,runpy
def audit(event,args):
 if event in ('socket.connect','socket.getaddrinfo','socket.sendto','socket.sendmsg'):raise RuntimeError('offline install')
sys.addaudithook(audit)
sys.path.insert(0,sys.argv.pop(1));runpy.run_module('pip',run_name='__main__')
"""
    subprocess.run([str(python),'-I','-c',code,str(pip[0]),'install','--no-index','--no-deps',
        '--require-hashes','--only-binary=:all:','--find-links='+str(wheels),'-r',str(payload/'requirements.txt')],
        env=env,check=True,timeout=900,stdout=sys.stderr)
    subprocess.run([str(python),'-I','-m','pip','check'],env=env,check=True,timeout=30,stdout=sys.stderr)
    for name in ('worker.py','launcher.py','installer.py','runtime-lock.json'):
        shutil.copyfile(payload/name,ROOT/name);(ROOT/name).chmod(0o444)
    raw=subprocess.check_output([str(python),'-I',str(ROOT/'installer.py'),'check'],env=env,timeout=120)
    result=json.loads(raw);result['interpreter_archive']=runtime
    (ROOT/'install-receipt.json').write_text(json.dumps(result,sort_keys=True))
    # Installation artifacts are root-owned and traversable, never worker-owned.
    for p in ROOT.rglob('*'):
        if p.is_symlink():continue
        p.chmod(0o755 if p.is_dir() else (p.stat().st_mode & 0o111)|0o444)
    ROOT.chmod(0o755)
    return result


if __name__=='__main__':
    if sys.argv[1]=='install':result=install(sys.argv[2])
    elif sys.argv[1]=='check':result=installed(json.loads((ROOT/'runtime-lock.json').read_bytes()))
    else:raise ValueError('unknown operation')
    print(json.dumps(result,sort_keys=True))
