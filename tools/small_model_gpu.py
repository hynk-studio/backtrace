"""CUDA installation checks and bounded baseline preparation; no provider client.

Real-device commands operate only on an already provisioned native Linux host.
The free qualification uses CPU tensors in the CUDA build and cannot qualify a GPU.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
import xml.etree.ElementTree as ET

from tools import abductive_benchmark as base
from tools import exact_teacher as exact
from tools import small_model_readiness as ready
from tools import small_model_runner as runner

GIB=1024**3
MIN_DRIVER=(560,35,5)  # Deliberately above CUDA 12.x's limited minor-compatibility floor.
UUID_RE=r'GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
DRIVER_SONAMES=('libcuda.so.1','libnvidia-ptxjitcompiler.so.1','libnvidia-nvvm.so.4')


def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()


def normalize(name):return re.sub(r'[-_.]+','-',name).lower()


def verify_wheels(directory):
    spec=ready.lock()['gpu_candidate'];directory=Path(directory)
    expected={urllib.parse.unquote(Path(urllib.parse.urlparse(r['url']).path).name):r for r in spec['wheels']}
    if {p.name for p in directory.iterdir()}!=set(expected):raise ValueError('CUDA wheel directory must contain exact closure')
    result={}
    for name,row in expected.items():
        p=directory/name;s=p.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or not 0<s.st_size<3*GIB or sha_file(p)!=row['sha256']:
            raise ValueError('CUDA wheel identity/type/hash mismatch: '+name)
        result[name]={'bytes':s.st_size,'sha256':row['sha256']}
    return {'status':'PASS_CUDA_WHEEL_BYTES','wheels':result,'count':len(result),
            'total_bytes':sum(x['bytes'] for x in result.values()),'source_hashes':runner.source_hashes()}


def check_runtime():
    spec=ready.lock()['gpu_candidate']
    if (platform.python_version()!=spec['python'] or platform.system()!='Linux' or platform.machine()!='x86_64'):
        raise ValueError('pinned Linux x86_64 Python required')
    wanted={normalize(k):v for k,v in spec['packages'].items()}
    rows=list(importlib.metadata.distributions())
    actual={normalize(d.metadata['Name']):d.version for d in rows}
    if actual!=wanted or len(rows)!=len(wanted):raise ValueError('installed CUDA closure differs from lock')
    import torch
    import accelerate,transformers,safetensors,triton
    import cuda.bindings.driver
    if str(torch.__version__)!=spec['packages']['torch'] or torch.version.cuda!=spec['torch_cuda']:
        raise ValueError('wrong compiled CUDA build')
    torch.set_num_threads(1)
    x=torch.eye(4,dtype=torch.bfloat16)
    if not torch.equal(x@x,x):raise ValueError('CUDA-build CPU compatibility failed')
    shared={}
    for name in ('libtorch_cuda.so','libtorch_cpu.so','libc10_cuda.so'):
        p=Path(torch.__file__).parent/'lib'/name
        output=subprocess.check_output(['ldd',str(p)],timeout=30,text=True)
        if 'not found' in output:raise ValueError('unresolved native dependency: '+name)
        shared[name]={'bytes':p.stat().st_size,'sha256':sha_file(p),'ldd':output}
    available=torch.cuda.is_available()
    return {'status':'PASS_CUDA_PACKAGE_INSTALL_ONLY','packages':actual,'package_count':len(actual),
            'compiled_cuda':torch.version.cuda,'shared_objects':shared,'cuda_available':available,
            'device_count':torch.cuda.device_count(),'cpu_tensor_check':True,
            'gpu_kernels':'NOT_RUN','pretrained_inference':'NOT_RUN','source_hashes':runner.source_hashes()}


def parse_inventory(raw,uuid):
    if not re.fullmatch(UUID_RE,uuid) or len(raw)>1024*1024:raise ValueError('one full GPU UUID required')
    try:root=ET.fromstring(raw)
    except ET.ParseError as exc:raise ValueError('invalid NVIDIA inventory XML') from exc
    gpus=root.findall('gpu')
    if len(gpus)!=1:raise ValueError('exactly one selected GPU required')
    g=gpus[0]
    if g.findtext('uuid','').lower()!=uuid.lower():raise ValueError('GPU UUID mismatch')
    version=root.findtext('driver_version','')
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?',version):raise ValueError('invalid driver version')
    parts=tuple(int(n) for n in version.split('.'));parts=parts+(0,)*(3-len(parts))
    if parts<MIN_DRIVER:raise ValueError('driver below conservative CUDA 12.6 baseline')
    minor=g.findtext('minor_number','')
    memory=g.findtext('fb_memory_usage/total','')
    mig=g.findtext('mig_mode/current_mig','')
    if not minor.isdigit() or not 0<=int(minor)<255:raise ValueError('invalid GPU device minor')
    if not re.fullmatch(r'\d+ MiB',memory):raise ValueError('unrecognized GPU memory units')
    total=int(memory.split()[0])*1024**2
    if total<24*GIB:raise ValueError('baseline requires at least 24 GiB reported device memory')
    if mig not in ('Disabled','N/A'):raise ValueError('MIG is outside this first qualification')
    if g.findall('processes/process_info'):raise ValueError('selected GPU is already in use')
    return {'uuid':g.findtext('uuid'),'name':g.findtext('product_name'),'driver_version':version,
            'device_basename':'nvidia'+minor,'minimum_total_bytes':24*GIB,'reported_total_bytes':total,
            'mig':mig,'nvidia_smi_xml_sha256':exact.sha(raw)}


def inventory(uuid):
    if not re.fullmatch(UUID_RE,uuid):raise ValueError('one full GPU UUID required')
    binary=shutil.which('nvidia-smi')
    if binary is None:raise RuntimeError('nvidia-smi absent; no device qualification')
    raw=subprocess.check_output([binary,'-q','-x','-i',uuid],timeout=15)
    result=parse_inventory(raw,uuid)
    paths=['/dev/'+result['device_basename'],'/dev/nvidiactl','/dev/nvidia-uvm']
    nodes=[]
    for path in paths:
        s=Path(path).lstat()
        if not stat.S_ISCHR(s.st_mode) or s.st_mode&0o006!=0o006:
            raise ValueError('GPU node must be character device accessible to fixed worker UID: '+path)
        nodes.append({'path':path,'major':os.major(s.st_rdev),'minor':os.minor(s.st_rdev)})
    if nodes[0]['major']!=195 or nodes[0]['minor']!=int(result['device_basename'][6:]) or nodes[1]['major']!=195:
        raise ValueError('unexpected NVIDIA device identity')
    listing=subprocess.check_output(['/sbin/ldconfig','-p'],timeout=10,text=True)
    libs={}
    for soname in DRIVER_SONAMES:
        matches=re.findall(r'^\s*'+re.escape(soname)+r' \(libc6,x86-64[^\n]*\) => (\S+)$',listing,re.M)
        if not matches:
            if soname=='libcuda.so.1':raise ValueError('host libcuda.so.1 is absent from linker inventory')
            continue
        p=Path(matches[0]).resolve(strict=True);s=p.stat()
        if not stat.S_ISREG(s.st_mode) or not 0<s.st_size<256*1024**2:raise ValueError('invalid host driver library')
        libs[soname]={'path':str(p),'bytes':s.st_size,'sha256':sha_file(p)}
    return dict(result,nodes=nodes,driver_libraries=libs)


def attach_devices(command,nodes,libraries,uuid):
    """Low-level explicit mounts; production callers supply freshly inspected inventory.

    Native CPU qualification exercises this with /dev/null only, not fake GPUs.
    """
    mounts=[];driver=command.staging/'driver';driver.mkdir(mode=0o755)
    for soname,info in libraries.items():
        if soname not in DRIVER_SONAMES:raise ValueError('unapproved driver library')
        source=Path(info['path'])
        if source.stat().st_size!=info['bytes'] or sha_file(source)!=info['sha256']:
            raise ValueError('driver library changed')
        shutil.copyfile(source,driver/soname);(driver/soname).chmod(0o444)
    for node in nodes:
        p=Path(node['path']);s=p.lstat()
        if (not stat.S_ISCHR(s.st_mode) or (os.major(s.st_rdev),os.minor(s.st_rdev))!=(node['major'],node['minor'])):
            raise ValueError('device node changed')
        mounts+=['--dev-bind',str(p),str(p)]
    mounts+=['--ro-bind',str(driver),'/driver','--setenv','LD_LIBRARY_PATH','/driver',
             '--setenv','CUDA_VISIBLE_DEVICES',uuid,'--setenv','CUDA_DEVICE_ORDER','PCI_BUS_ID',
             '--setenv','CUDA_CACHE_DISABLE','1']
    at=command.index('--chdir');command[at:at]=mounts
    return command


def gpu_command(python,model,tokenizer,job,gpu,**kwargs):
    command=runner.jail_command(python,model,tokenizer,job,**kwargs)
    try:return attach_devices(command,gpu['nodes'],gpu['driver_libraries'],gpu['uuid'])
    except BaseException:command.close();raise


def device_probe(uuid,output):
    """Must run on the actual host, under the same isolated worker, before weight staging."""
    runtime=check_runtime();gpu=inventory(uuid)
    output=exact._local_path(output);output.mkdir(mode=0o700,exist_ok=False)
    for name in ('model','tokenizer'):(output/name).mkdir(mode=0o700)
    from tools.small_model_runner_probe import boundary_probe
    for name in ('model','tokenizer'):(output/name/'E2B').mkdir(mode=0o700)
    boundaries=boundary_probe(Path(sys.executable),output/'tokenizer',output/'model',output/'boundaries',
        command_factory=lambda *a,**kw:gpu_command(*a,gpu=gpu,**kw))
    job=output/'job.json';base.private_write(job,exact.canonical({'mode':'cuda_probe',
        'packages':ready.lock()['gpu_candidate']['packages'],'gpu':gpu}))
    command=gpu_command(Path(sys.executable),output/'model',output/'tokenizer',job,gpu,metadata_only=True)
    channel=runner.Channel(command,output/'stderr.log')
    try:
        result=channel.read(time.monotonic()+60)
        if result.get('status')!='PASS_ACTUAL_CUDA_KERNELS' or result['gpu']['uuid'].lower()!=uuid.lower():
            raise ValueError('actual isolated GPU probe failed')
    finally:exit_code=channel.close()
    if exit_code!=0:raise RuntimeError('GPU probe did not exit cleanly')
    receipt={'status':'PASS_ACTUAL_GPU_KERNEL_AND_BOUNDARY_PROBE','runtime_status':runtime['status'],
             'gpu':gpu,'worker':result,'source_hashes':runner.source_hashes(),
             'boundaries':boundaries,
             'pretrained_inference':'NOT_RUN','paid_authorization':False}
    base.private_write(output/'receipt.json',exact.canonical(receipt));return receipt


def prepare(scope,packets,tokens,output):
    plan,schedule,scope_hash=runner.load_scope(scope,packets,tokens)
    if plan['scope']!='smoke':raise ValueError('only the original smoke is prepared for first hardware execution')
    weights={n:{'revision':s['revision'],'bytes':s['weights_metadata_only'][0]['bytes'],
                'sha256':s['weights_metadata_only'][0]['lfs']['oid'],
                'url':s['tensor_header']['url']} for n,s in ready.lock()['models'].items()}
    report={'status':'PREPARED_NOT_HARDWARE_QUALIFIED','scope_sha256':scope_hash,
            'source_hashes':runner.source_hashes(),'assignments':[{k:v for k,v in row.items() if k!='messages'} for row in schedule],
            'models':plan['models'],'weights':weights,'generation':plan['generation'],'model_loading':plan['model_loading'],
            'limits':{'allocation_inclusive_seconds':3000,'setup_target_seconds':900,
                      'collector_seconds':1800,'cleanup_reserve_seconds':300,'request_seconds':90,
                      'model_startup_seconds':180,'retries':0,'models_sequential':True},
            'additional_diagnostics':{'random_cuda_requests':36,'random_cuda_max_new_tokens_each':2,
                                      'count_inside_allocation_budget':True,'pretrained_requests':0},
            'resource_candidate':{'minimum_reported_gpu_bytes':24*GIB,'minimum_host_ram_bytes':32*GIB,
                'free_disk_after_runtime_install_bytes':64*GIB,
                'full_checkpoint_bytes':sum(w['bytes'] for w in weights.values()),
                'source_plus_disposable_model_copy_bytes':2*sum(w['bytes'] for w in weights.values()),
                'driver_minimum':'.'.join(map(str,MIN_DRIVER)),'native_bf16':True,'mig_supported':False},
            'cost_proposal':ready.lock()['scope_limits_proposal'],
            'required_hardware_checks':['fresh single-GPU UUID/driver/device inventory','actual isolated BF16 matmul and SDPA',
                'GPU namespace network/filesystem/parent-loss boundaries','full checkpoint hashes and load diagnostics',
                'actual memory, token latency and complete original coverage'],
            'provider_lifecycle':'NOT_CONNECTED; independent allocation-inclusive deadline/export/delete proof required',
            'weights_downloaded':False,'pretrained_inference':'NOT_RUN','training':'NOT_RUN',
            'paid_authorization':False,'current_quote':'NOT_FETCHED','current_balance':'NOT_FETCHED',
            'expected_completion':'UNMEASURED; limits may yield partial coverage, never replace assignments'}
    output=exact._local_path(output);base.private_write(output,exact.canonical(report));return report


def factory(python,sources,models,jobs,gpu,*,mode='pretrained_cuda',maximum=4096):
    if mode not in ('pretrained_cuda','random_cuda_fixture','random_fixture','scripted_control'):
        raise ValueError('unsupported GPU qualification mode')
    check_runtime();sources=ready.validate_sources(sources)
    if mode=='pretrained_cuda':
        ready.inspect_models(sources)
        verified={n:runner.verify_pretrained_directory(n,Path(models)/n) for n in ready.MODELS}
    else:verified={}
    jobs=Path(jobs);jobs.mkdir(mode=0o700,exist_ok=False)
    base.private_write(jobs/'verified-weights.json',exact.canonical(verified))
    commands={}
    try:
        for name in ready.MODELS:
            header=base.strict_json((sources/name/'tensor-header.json').read_bytes())
            job={'mode':mode,'packages':ready.lock()['gpu_candidate']['packages'],
                 'key_mapping':ready.lock()['model_loading']['key_mapping'],'max_input_tokens':12288,
                 'max_new_tokens':maximum,'allowed_unexpected_keys':[k for k in header if k.startswith(ready.NON_TEXT_PREFIXES)]}
            if 'cuda' in mode:job['gpu']=gpu
            p=jobs/(name+'.json');base.private_write(p,exact.canonical(job))
            commands[name]=(gpu_command(python,Path(models)/name,sources/name,p,gpu) if 'cuda' in mode
                            else runner.jail_command(python,Path(models)/name,sources/name,p))
    except BaseException:
        for command in commands.values():command.close()
        raise
    def make(name,output):return runner.Channel(commands[name],output/(name+'-stderr.log'))
    make.close=lambda:[c.close() for c in commands.values()]
    make.staging_paths=[str(c.staging) for c in commands.values()]
    make.gpu_uuid=gpu['uuid'] if gpu else None
    return make


def run_existing(uuid,sources,models,scope,packets,tokens,output):
    """Local host only; caller must supervise allocation timing and resource deletion.

    Does not download weights, obtain a permit, allocate or reuse an old provider controller.
    """
    from transformers import AutoTokenizer
    plan,schedule,_=runner.load_scope(scope,packets,tokens)
    if plan['scope']!='smoke':raise ValueError('first GPU baseline is fixed smoke only')
    total_ram=os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')
    copy_bytes=sum(s['weights_metadata_only'][0]['bytes'] for s in ready.lock()['models'].values())
    if total_ram<32*GIB or shutil.disk_usage(tempfile.gettempdir()).free<copy_bytes+4*GIB:
        raise RuntimeError('baseline RAM or disposable-copy disk capacity insufficient')
    output=exact._local_path(output);output.mkdir(mode=0o700,exist_ok=False)
    probe=device_probe(uuid,output/'device-probe')
    gpu=inventory(uuid)  # Require idle hardware again after probe worker closes.
    if gpu['driver_libraries']!=probe['gpu']['driver_libraries']:raise ValueError('driver changed after probe')
    tokens_by_model={n:AutoTokenizer.from_pretrained(Path(sources)/n,local_files_only=True,trust_remote_code=False) for n in ready.MODELS}
    from tools.small_model_runner_probe import random_models
    random_models(Path(sources),output/'random-models')
    diagnostic=factory(Path(sys.executable),sources,output/'random-models',output/'random-jobs',gpu,
                       mode='random_cuda_fixture',maximum=2)
    measured=runner.collect(schedule,output/'random-collection',diagnostic,tokens_by_model,mode='random_cuda_fixture',
                           max_new_tokens=2,total_seconds=180,startup_seconds=60,request_seconds=30)
    if measured['status']!='COMPLETED' or any(r['status'] not in ('OK','INVALID_OUTPUT') for r in measured['records']):
        raise RuntimeError('actual tiny CUDA model diagnostic failed; pretrained loading stopped')
    gpu=inventory(uuid)
    worker=factory(Path(sys.executable),sources,models,output/'jobs',gpu)
    result=runner.collect(schedule,output/'collection',worker,tokens_by_model,mode='pretrained_cuda',
        max_new_tokens=4096,total_seconds=1800,startup_seconds=180,request_seconds=90)
    evaluation=runner.evaluate(plan,schedule,result)
    base.private_write(output/'evaluation.json',exact.canonical(evaluation))
    return {'status':result['status'],'coverage':result['coverage'],'evaluation_status':evaluation['status'],
            'training':False,'scope':'development_smoke','capability_claim':'NOT_ESTABLISHED'}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('verify-wheels');s.add_argument('directory',type=Path)
    sub.add_parser('check-runtime')
    s=sub.add_parser('prepare')
    for name in ('scope','packets','tokens','output'):s.add_argument(name,type=Path)
    s=sub.add_parser('probe-device');s.add_argument('uuid');s.add_argument('output',type=Path)
    s=sub.add_parser('run-existing');s.add_argument('uuid')
    for name in ('sources','models','scope','packets','tokens','output'):s.add_argument(name,type=Path)
    a=p.parse_args();args=vars(a);command=args.pop('command')
    methods={'verify-wheels':verify_wheels,'check-runtime':check_runtime,'prepare':prepare,'probe-device':device_probe,'run-existing':run_existing}
    print(json.dumps(methods[command](**args),sort_keys=True,indent=2))


if __name__=='__main__':main()
