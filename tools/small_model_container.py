"""Native owner adapter for the unchanged collector and a dedicated OCI worker.

This version only permits free CPU fixtures. Hidden memory ancestry, live GPU
boundaries and distributed provider cleanup still block a paid launch.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import stat
import sys
import tarfile

from tools import small_model_provider_probe as provider
from tools import small_model_readiness as ready, small_model_gpu as gpu
from tools import small_model_runner as runner, exact_teacher as exact
from tools import private_delivery as delivery

ROOT=Path(__file__).resolve().parents[1]
EXTRA=('tools/small_model_container.py','tools/small_model_container_worker.py',
       'tools/small_model_container_install.py','tools/small_model_container_probe.py',
       'tests/test_small_model_container.py','.github/workflows/small-model-container-cpu.yml')


def sources():return dict(provider.sources(),**{p:exact.sha((ROOT/p).read_bytes()) for p in EXTRA})


def python_archive(output):
    if platform.python_version()!='3.12.14':raise ValueError('pinned owner Python required')
    prefix=Path(sys.base_prefix);count=0;size=0
    with tarfile.open(output,'w:gz',format=tarfile.USTAR_FORMAT) as tar:
        candidates=[prefix/'bin/python3.12',*sorted((prefix/'lib').rglob('*'))]
        for source in candidates:
            name=source.relative_to(prefix).as_posix()
            if any(p in ('site-packages','__pycache__','test','tests') for p in source.relative_to(prefix).parts):continue
            if not source.is_file() or source.suffix in ('.a','.pyc'):continue
            if source.is_symlink() and not source.resolve().is_relative_to(prefix.resolve()):
                raise ValueError('runtime link escapes interpreter prefix')
            s=source.stat()
            if not stat.S_ISREG(s.st_mode):raise ValueError('runtime regular files required')
            info=tarfile.TarInfo(name);info.size=s.st_size;info.mode=0o444
            with source.open('rb') as f:tar.addfile(info,f)
            count+=1;size+=s.st_size
    return {'files':count,'bytes':size,'archive_bytes':output.stat().st_size,'sha256':gpu.sha_file(output)}


def manifest(directory, phase='bootstrap'):
    rows=[{'path':p.relative_to(directory).as_posix(),'bytes':p.stat().st_size,'sha256':gpu.sha_file(p)}
          for p in sorted(directory.rglob('*')) if p.is_file()]
    raw=exact.canonical({'schema_version':1,'phase':phase,'files':rows})
    delivery.verify(directory,raw);return raw


def runtime_payload(directory,wheels):
    directory.mkdir(mode=0o700);wheel_result=gpu.verify_wheels(wheels)
    archive=python_archive(directory/'python.tar.gz')
    for source,name in [('tools/small_model_worker.py','worker.py'),
            ('tools/small_model_container_worker.py','launcher.py'),
            ('tools/small_model_container_install.py','installer.py'),
            ('docs/small-model-runtime-lock-v1.json','runtime-lock.json'),
            ('docs/small-model-gpu-requirements.txt','requirements.txt')]:
        shutil.copyfile(ROOT/source,directory/name)
    (directory/'wheels').mkdir()
    for p in Path(wheels).iterdir():
        # Hard links are only owner-side staging of already verified public wheels.
        os.link(p,directory/'wheels'/p.name)
    return manifest(directory),{'wheels':wheel_result,'python':archive}


def assets(directory,sources,models):
    directory.mkdir(mode=0o700)
    ready.validate_sources(sources)
    for name in ready.MODELS:
        for kind,names,origin in [('tokenizers',ready.FILES,Path(sources)/name),
                                  ('models',{'config.json','generation_config.json','model.safetensors'},Path(models)/name)]:
            target=directory/kind/name;target.mkdir(mode=0o700,parents=True)
            for leaf in sorted(names):
                p=origin/leaf
                if p.is_symlink() or not p.is_file():raise ValueError('plain approved asset required')
                shutil.copyfile(p,target/leaf)
    jobs=directory/'jobs';jobs.mkdir()
    for mode in ('scripted_control','random_fixture'):
        for fault in (None,'hang','crash','wrong_id','oversize','startup_hang') if mode=='scripted_control' else (None,):
            for name in ready.MODELS:
                key=job_name(name,mode,fault)
                job={'container_model':name,'mode':mode,'packages':ready.lock()['gpu_candidate']['packages'],
                     'key_mapping':ready.lock()['model_loading']['key_mapping'],'max_input_tokens':12288,
                     'max_new_tokens':4096 if mode=='scripted_control' else 2,'fault':fault,
                     'fault_at':1 if fault in ('hang','crash') else 0}
                (jobs/(key+'.json')).write_bytes(exact.canonical(job))
    return manifest(directory,'model')


def job_name(name,mode,fault):return name+'-'+mode.replace('_','-')+'-'+(fault or 'normal').replace('_','-')


def command(ssh_prefix,name,mode,*,fault=None,seconds=240,script='worker'):
    if name not in ready.MODELS or mode not in ('scripted_control','random_fixture'):
        raise ValueError('container path permits CPU controls only')
    if not 0<seconds<=3000 or script not in ('worker','boundary'):raise ValueError('invalid boundary')
    return [*ssh_prefix,shlex.join(['/opt/backtrace/venv/bin/python','-I','/opt/backtrace/launcher.py',
            'run',job_name(name,mode,fault),str(seconds),script])]


def factory(ssh_prefix,mode,*,fault=None,seconds=240):
    def make(name,output):
        return runner.Channel(command(ssh_prefix,name,mode,fault=fault,seconds=seconds),output/(name+'-stderr.log'))
    return make


def launch_gates():
    return {'paid_launch_enabled':False,'actual_provider_container':'NOT_OBSERVED',
            'hidden_cgroup_ancestor_admission':'BLOCKED_REQUIRES_HOST_EVIDENCE',
            'source_resource_bound_remote_deletion':'NOT_QUALIFIED',
            'gpu_context_teardown':'NOT_RUN','pretrained_inference':'NOT_RUN','training':'NOT_RUN'}
