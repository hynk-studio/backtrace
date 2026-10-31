"""Existing pinned E4B checkpoint on the unchanged twenty Augnes inputs."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from tools import small_model_pretrained as baseline
from tools import small_model_augnes_screen as screening
from tools import small_model_readiness as ready, small_model_runner as runner
from tools import small_model_lifecycle as life, small_model_minimum_remote as remote
from tools import small_model_container as container, small_model_delivery as delivery
from tools import small_model_gpu as gpu

ROOT=Path(__file__).resolve().parents[1]
PRIOR_INPUTS=ROOT/'docs/evidence/window-paid-run-41225173224/owner/minimum-owner/remote/screening-input-schedule.json'
MODEL_TRANSFER_SECONDS=960


def prepare(output,archive):
    # Historical smoke material is verified but not assigned in this screening.
    return baseline.prepare(output,archive,model_name='E4B')


def checked_schedule(tokenizer):
    rows=screening.schedule(tokenizer,model='E4B')
    prior=json.loads(PRIOR_INPUTS.read_bytes())['requests']
    if len(rows)!=20 or len(prior)!=20 or any(
            a['model']!='E2B' or b['model']!='E4B' or
            any(a[k]!=b[k] for k in ('id','arm','messages')) for a,b in zip(prior,rows)):
        raise ValueError('identical original twenty E2B messages required')
    return rows


def inspect_inputs(prepared,*,cuda_runtime=False):
    from transformers import AutoTokenizer
    if cuda_runtime:gpu.check_runtime()
    else:ready.check_packages()
    tokenizer=AutoTokenizer.from_pretrained(Path(prepared)/'sources/E4B',local_files_only=True,trust_remote_code=False)
    rows=checked_schedule(tokenizer)
    return {'status':'PASS_INPUTS_NOT_INFERENCE','model':'E4B','training_steps':0,
        'identical_e2b_screening_messages':True,'assigned':20,
        'assigned_before_allocation':[{**{k:v for k,v in r.items() if k!='messages'},'initial_status':'NOT_RUN'} for r in rows],
        'packet_sha256':life.digest(screening.PACKET.read_bytes()),
        'comparison_input_sha256':life.digest(PRIOR_INPUTS.read_bytes()),'pretrained_requests':0}


def prepare_runtime(root):
    initializer=remote.prepare(root,ROOT/'.local/cuda-wheels',ROOT/'.local/transport-build')
    prepared=ROOT/'.local/e4b';verified=runner.verify_pretrained_directory('E4B',prepared/'models/E4B')
    ready.validate_sources(prepared/'sources');assets=Path(root)/'assets';assets.mkdir(mode=0o700)
    for kind,origin,names in [('models',prepared/'models/E4B',('config.json','generation_config.json','model.safetensors')),
            ('tokenizers',prepared/'sources/E4B',sorted(ready.FILES))]:
        target=assets/kind/'E4B';target.mkdir(mode=0o700,parents=True)
        for name in names:
            if kind=='models':shutil.move(str(origin/name),target/name)
            else:shutil.copyfile(origin/name,target/name)
    (Path(root)/'assets-manifest.json').write_bytes(container.manifest(assets,'model'))
    life.write(Path(root)/'pretrained-preparation.json',{'weights':verified,'assigned':20,
        'packet_sha256':life.digest(screening.PACKET.read_bytes()),'training_steps':0,'evaluator_delivered':False})
    return initializer


def qualified_job(hardware,header):
    if (hardware.get('status')!='PASS_ACTUAL_HARDWARE_ONLY' or not hardware.get('actual_gpu')
            or not hardware.get('checks') or not all(hardware['checks'].values())):
        raise ValueError('complete actual hardware checks required')
    return {'container_model':'E4B','mode':'pretrained_cuda','gpu':hardware['initial_gpu'],
        'hardware_receipt_sha256':life.digest(hardware),'packages':ready.lock()['gpu_candidate']['packages'],
        'key_mapping':ready.lock()['model_loading']['key_mapping'],'max_input_tokens':4096,'max_new_tokens':768,
        'allowed_unexpected_keys':[k for k in header if k.startswith(ready.NON_TEXT_PREFIXES)]}


def after_hardware(root,endpoint,prefix,output,hardware):
    root=Path(root);output=Path(output)
    header=json.loads((ROOT/'.local/e4b/sources/E4B/tensor-header.json').read_bytes())
    job=qualified_job(hardware,header);jobs=root/'assets/jobs';jobs.mkdir(mode=0o700)
    life.write(jobs/'E4B-screening.json',job)
    manifest=root/'assets-qualified-manifest.json';manifest.write_bytes(container.manifest(root/'assets','model'))
    transfer=delivery.push(root/'assets',manifest,
        prefix+[delivery.ssh_command(endpoint['host'],endpoint['port'],root/'keys/owner-key',
            root/'keys/known-hosts','/root/backtrace/assets',life.digest(manifest.read_bytes()))[-1]],MODEL_TRANSFER_SECONDS,
        diagnostics=output/'asset-transfer-progress.json')
    installed=remote.remote(prefix,"""import json,pathlib,shutil
src=pathlib.Path('/root/backtrace/assets');dst=pathlib.Path('/opt/backtrace/assets')
shutil.move(str(src),dst)
for p in dst.rglob('*'):
 if p.is_symlink():raise ValueError('asset symlink')
 p.chmod(0o755 if p.is_dir() else 0o444)
dst.chmod(0o755);(dst/'jobs').chmod(0o700)
print(json.dumps({'bytes':sum(p.stat().st_size for p in dst.rglob('*') if p.is_file()),'model':'E4B'}))
""",60)
    life.write(output/'asset-transfer.json',{'transfer':transfer,'installation':installed,
        'qualified_manifest_sha256':life.digest(manifest.read_bytes())})
    spec=output/'collector-input.json';life.write(spec,{'prefix':prefix,'gpu_uuid':job['gpu']['uuid']})
    try:
        with (output/'collector.log').open('xb') as log:
            p=subprocess.run([str(ROOT/'.local/model-runtime/bin/python'),'-m','tools.small_model_e4b_screen',
                'collect',str(spec),str(output)],stdout=log,stderr=log,timeout=1530,
                env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8','HOME':str(root),
                     'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'})
    finally:preserve_collection(output)
    stopped=remote.remote(prefix,"""import json,pathlib
r=json.loads(pathlib.Path('/root/backtrace/E4B-screening-state.json').read_bytes())
try:r['same_process_alive']=pathlib.Path('/proc',str(r['pid']),'stat').read_text().split()[21]==r['start_ticks']
except (FileNotFoundError,ProcessLookupError):r['same_process_alive']=False
print(json.dumps(r))
""")
    idle=remote.inventory(prefix,job['gpu']['uuid']);life.write(output/'inference-teardown.json',{'worker':stopped,'gpu':idle})
    if stopped['same_process_alive'] or p.returncode:raise RuntimeError('E4B collector or worker cleanup failed')
    collection=json.loads((output/'collection/collection.json').read_bytes())
    expected=[c['id'] for c in json.loads(screening.PACKET.read_bytes())['cases']]
    if (collection['assigned']!=20 or collection['training'] or [r['id'] for r in collection['records']]!=expected
            or any(r['model']!='E4B' or r['arm']!='B1' for r in collection['records'])):
        raise RuntimeError('original E4B screening denominator changed')
    return {'status':'PASS_E4B_SCREENING' if collection['status']=='COMPLETED' else 'INCOMPLETE_E4B_SCREENING',
        'assigned':20,'coverage':collection['coverage'],'training_steps':0,'capability_claim':'DESCRIPTIVE_ONLY'}


def collect(spec_path,output):
    from transformers import AutoTokenizer
    spec=json.loads(Path(spec_path).read_bytes())
    tokenizer=AutoTokenizer.from_pretrained(ROOT/'.local/e4b/sources/E4B',local_files_only=True,trust_remote_code=False)
    rows=checked_schedule(tokenizer)
    life.write(Path(output)/'input-schedule.json',{'requests':rows,'packet_sha256':life.digest(screening.PACKET.read_bytes())})
    def factory(name,directory):
        if name!='E4B':raise ValueError('E4B only')
        command=spec['prefix']+[shlex.join(['/usr/bin/env','-i','PATH=/usr/bin:/bin','LANG=C.UTF-8',
            'LD_LIBRARY_PATH=/opt/backtrace/python/lib','/opt/backtrace/venv/bin/python','-I',
            '/opt/backtrace/launcher.py','run','E4B-screening','1500','pretrained'])]
        return container.ContainerChannel(command,directory/'E4B-stderr.log')
    factory.gpu_uuid=spec['gpu_uuid'];factory.training_requested=False
    return runner.collect(rows,ROOT/'.local/e4b-screening-collection',factory,{'E4B':tokenizer},mode='pretrained_cuda',
        max_new_tokens=768,total_seconds=1500,startup_seconds=180,request_seconds=60)


def preserve_collection(output):
    source=ROOT/'.local/e4b-screening-collection';target=Path(output)/'collection';count=0
    if source.exists():
        target.mkdir(parents=True,exist_ok=True)
        for p in source.iterdir():
            if p.is_file() and not p.is_symlink() and p.suffix in ('.json','.jsonl','.log') and p.stat().st_size<=16*1024**2:
                shutil.copyfile(p,target/p.name);count+=1
    return {'files':count}


if __name__=='__main__':
    command=sys.argv[1]
    if command=='prepare':result=prepare(sys.argv[2],sys.argv[3])
    elif command=='collect':result=collect(sys.argv[2],sys.argv[3])
    elif command=='inspect-inputs':result=inspect_inputs(sys.argv[2])
    elif command=='plan-gpu-inputs':result=inspect_inputs(sys.argv[2],cuda_runtime=True)
    elif command=='preserve':result=preserve_collection(sys.argv[2])
    else:raise ValueError('explicit preparation or collection required')
    print(json.dumps(result,sort_keys=True))
