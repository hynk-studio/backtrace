"""One-seed B1/B2/S candidate through the existing isolated worker and collector."""
import base64
from collections import Counter
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

from tools import small_model_matched_data as data, small_model_pretrained as pretrained
from tools import small_model_readiness as ready, small_model_runner as runner
from tools import small_model_augnes_screen as screening, small_model_container as container
from tools import small_model_minimum_remote as remote, small_model_lifecycle as life
from tools import small_model_delivery as delivery

ROOT=Path(__file__).resolve().parents[1]
ARMS=('B1','B2','S')
JOBS=('E2B-B1-eval','E2B-B2-train','E2B-B2-eval','E2B-S-train','E2B-S-eval')
COLLECT_SECONDS=1200
TRAIN_SECONDS=600
RESTORE_KEYS=('arm','training_steps','training_input_sha256','adapter_bytes','adapter_sha256',
    'adapter_safetensors_base64','target_module','probe_messages','probe_input_ids_sha256','trained_probe_logits_sha256')


def worker_spec_sha(value):
    return life.digest((json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode())


def schedule(tokenizer):
    synthetic=[]
    for row in data.development_inputs():
        encoded=ready.encode(tokenizer,row['messages'],4096)
        if encoded['overflow']:raise ValueError('candidate development input overflow')
        synthetic.append({'model':'E2B','id':row['id'],'messages':row['messages'],
            'input_tokens':encoded['input_tokens'],'input_ids_sha256':encoded['token_ids_sha256']})
    fixed=screening.schedule(tokenizer)
    rows=[dict(r,arm=arm) for arm in ARMS for r in synthetic+fixed]
    if len(rows)!=348:raise AssertionError('96+20 assignments per arm required')
    return rows


def inspect_inputs(prepared,*,cuda_runtime=False):
    from transformers import AutoTokenizer
    if cuda_runtime:pretrained.gpu.check_runtime()
    else:ready.check_packages()
    tokenizer=AutoTokenizer.from_pretrained(Path(prepared)/'sources/E2B',local_files_only=True,trust_remote_code=False)
    paired=data.materialize(tokenizer);rows=schedule(tokenizer)
    target=Path(prepared)/'matched';target.mkdir(mode=0o700,exist_ok=False)
    for arm,spec in paired['specifications'].items():life.write(target/(arm+'-training.json'),spec)
    life.write(target/'schedule.json',{'requests':rows})
    return {'status':'PASS_MATCHED_INPUTS_NOT_INFERENCE','source_hashes':runner.source_hashes(),
        'training':{k:v for k,v in paired.items() if k!='specifications'},
        'specification_sha256':{k:worker_spec_sha(v) for k,v in paired['specifications'].items()},
        'specification_bytes':{k:len(life.encoded(v)) for k,v in paired['specifications'].items()},
        'schedule_sha256':life.digest(rows),'assigned':len(rows),'per_arm':116,
        'synthetic_per_arm':96,'fixed_augnes_per_arm':20,
        'fresh_development_episodes':96,'excluded_historical_episodes':sorted(data.exposed_development_episodes()),
        'assigned_before_allocation':[dict({k:v for k,v in r.items() if k!='messages'},initial_status='NOT_RUN') for r in rows],
        'pretrained_requests':0,'training_steps':0,'planned_updates_per_trained_arm':320}


def prepare_runtime(root):
    root=Path(root);result=remote.prepare(root,ROOT/'.local/cuda-wheels',ROOT/'.local/transport-build')
    prepared=ROOT/'.local/e2b'
    verified=runner.verify_pretrained_directory('E2B',prepared/'models/E2B')
    ready.validate_sources(prepared/'sources')
    assets=root/'assets';assets.mkdir(mode=0o700)
    for kind,origin,names in [('models',prepared/'models/E2B',('config.json','generation_config.json','model.safetensors')),
            ('tokenizers',prepared/'sources/E2B',sorted(ready.FILES))]:
        target=assets/kind/'E2B';target.mkdir(mode=0o700,parents=True)
        for name in names:
            if kind=='models':shutil.move(str(origin/name),target/name)
            else:shutil.copyfile(origin/name,target/name)
    (root/'assets-manifest.json').write_bytes(container.manifest(assets,'model'))
    life.write(Path(root)/'matched-preparation.json',{'assigned':348,'arms':list(ARMS),
        'planned_updates_per_trained_arm':320,'evaluator_delivered':False,'base_model':'E2B','weights':verified})
    return result


def base_job(hardware,header):
    job=pretrained.qualified_job(hardware,header)
    job.pop('adapter_feasibility')
    job.update(max_input_tokens=4096,max_new_tokens=768)
    return job


def check_stopped(prefix,job_name,gpu_uuid):
    if job_name not in JOBS:raise ValueError('fixed candidate job required')
    stopped=remote.remote(prefix,"""import json,pathlib
r=json.loads(pathlib.Path("""+repr('/root/backtrace/'+job_name+'-state.json')+""").read_bytes())
try:r['same_process_alive']=pathlib.Path('/proc',str(r['pid']),'stat').read_text().split()[21]==r['start_ticks']
except (FileNotFoundError,ProcessLookupError):r['same_process_alive']=False
print(json.dumps(r))
""")
    gpu=remote.inventory(prefix,gpu_uuid)
    if stopped['same_process_alive']:raise RuntimeError('candidate worker remains alive')
    return {'worker':stopped,'gpu':gpu}


def command(prefix,job,seconds):
    if job not in JOBS:raise ValueError('fixed candidate job required')
    return prefix+[shlex.join(['/usr/bin/env','-i','PATH=/usr/bin:/bin','LANG=C.UTF-8',
        'LD_LIBRARY_PATH=/opt/backtrace/python/lib','/opt/backtrace/venv/bin/python','-I',
        '/opt/backtrace/launcher.py','run',job,str(seconds),'pretrained'])]


def validate_hello(hello,uuid):
    if (hello.get('ready') is not True or hello.get('mode')!='pretrained_cuda'
            or hello.get('uid')!=65532 or hello.get('caps')!=0 or hello.get('no_new_privs')!='1'
            or hello.get('pid_namespace')==os.readlink('/proc/self/ns/pid')
            or hello.get('net_namespace')==os.readlink('/proc/self/ns/net')
            or hello.get('cuda',{}).get('uuid')!=uuid or hello.get('cuda',{}).get('no_cpu_fallback') is not True):
        raise ValueError('qualified isolated CUDA worker required')


def restore_spec(result,arm,expected_sha):
    if (result.get('status')!='PASS_MATCHED_CANDIDATE_TRAINING' or result.get('arm')!=arm
            or result.get('training_steps')!=320 or result.get('updates_in_worker')!=320
            or result.get('training_input_sha256')!=expected_sha):
        raise ValueError('complete exact-assigned training required')
    raw=base64.b64decode(result['adapter_safetensors_base64'],validate=True)
    if not 0<len(raw)<=524288 or len(raw)!=result['adapter_bytes'] or life.digest(raw)!=result['adapter_sha256']:
        raise ValueError('bounded adapter bytes must match training receipt')
    return dict({k:result[k] for k in RESTORE_KEYS},schema='matched_candidate_restore_v1')


def deliver_restore(spec,arm,restore,output):
    """Only the resulting adapter/probe job crosses existing authenticated SSH."""
    root=Path(spec['root']);stage=root/(arm+'-restore-payload');stage.mkdir(mode=0o700)
    job=dict(spec['base_job'],candidate_restore=restore)
    name='E2B-'+arm+'-eval.json';life.write(stage/name,job)
    if (stage/name).stat().st_size>1024**2:raise ValueError('bounded restore job required')
    manifest=root/(arm+'-restore-manifest.json');manifest.write_bytes(container.manifest(stage,'model'))
    destination='/root/backtrace/'+arm+'-restore'
    ep=spec['endpoint']
    receipt=delivery.push(stage,manifest,spec['prefix']+[delivery.ssh_command(ep['host'],ep['port'],
        root/'keys/owner-key',root/'keys/known-hosts',destination,life.digest(manifest.read_bytes()))[-1]],90,
        diagnostics=output/(arm+'-restore-transfer.json'))
    installed=remote.remote(spec['prefix'],"""import json,pathlib,shutil,hashlib
src=pathlib.Path("""+repr(destination+'/'+name)+""");dst=pathlib.Path("""+repr('/opt/backtrace/assets/jobs/'+name)+""")
if dst.exists():raise ValueError('restore job already consumed')
raw=src.read_bytes()
if hashlib.sha256(raw).hexdigest()!="""+repr(life.digest((stage/name).read_bytes()))+""":raise ValueError('restore job identity changed')
shutil.move(src,dst);dst.chmod(0o444)
print(json.dumps({'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'bytes':dst.stat().st_size}))
""")
    life.write(output/(arm+'-restore-installation.json'),{'transfer':receipt,'installed':installed})


def aggregate(output,schedule):
    """Retain the original denominator even if a later arm never starts."""
    records={(r['arm'],r['id']):dict(model='E2B',arm=r['arm'],id=r['id'],status='NOT_RUN') for r in schedule}
    collections={}
    for arm in ARMS:
        p=ROOT/'.local/matched-collections'/arm
        if not p.exists():continue
        f=p/'collection.json'
        if f.exists():value=json.loads(f.read_bytes())
        elif (p/'recovery.json').exists():
            value=json.loads((p/'recovery.json').read_bytes())
            if value['ledger_sha256']!=life.digest((p/'ledger.jsonl').read_bytes()):
                raise ValueError('interrupted ledger changed after retained recovery')
        else:value=runner.recover(p)
        collections[arm]={k:v for k,v in value.items() if k!='records'}
        for row in value['records']:
            key=(row['arm'],row['id'])
            if key not in records or row['model']!='E2B':raise ValueError('unassigned candidate response')
            records[key]=row
    result={'schema':'matched_candidate_collection_v1','assigned':len(schedule),
        'records':list(records.values()),'coverage':dict(Counter(r['status'] for r in records.values())),
        'collections':collections,'capability_claim':'NOT_ESTABLISHED'}
    # This labeled derived checkpoint can advance; original assignments and raw
    # ledgers remain immutable and are the authority for every retained response.
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    temporary=output/('all-assignment-outcomes-'+str(time.monotonic_ns())+'.tmp')
    life.write(temporary,result);os.replace(temporary,output/'all-assignment-outcomes.json')
    return result


def preserve(output):
    output=Path(output);source=ROOT/'.local/matched-collections';count=0
    plan=ROOT/'.local/e2b/matched/schedule.json'
    if plan.exists():aggregate(output,json.loads(plan.read_bytes())['requests'])
    if source.exists():
        for p in source.rglob('*'):
            if p.is_file() and not p.is_symlink() and p.suffix in ('.json','.jsonl','.log') and p.stat().st_size<=16*1024**2:
                target=output/'collections'/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(p,target);count+=1
    return {'preserved_files':count}


def collect(spec_path,output):
    from transformers import AutoTokenizer
    spec=json.loads(Path(spec_path).read_bytes());output=Path(output)
    tokenizer=AutoTokenizer.from_pretrained(ROOT/'.local/e2b/sources/E2B',local_files_only=True,trust_remote_code=False)
    rows=json.loads((ROOT/'.local/e2b/matched/schedule.json').read_bytes())['requests']
    if rows!=schedule(tokenizer):raise ValueError('qualified candidate schedule changed')
    life.write(output/'input-schedule.json',{'requests':rows})
    (ROOT/'.local/matched-collections').mkdir(mode=0o700,exist_ok=False)
    aggregate(output,rows)
    trained={};training_processes={}
    try:
        for arm in ARMS:
            if arm!='B1':
                job='E2B-'+arm+'-train';channel=container.ContainerChannel(command(spec['prefix'],job,TRAIN_SECONDS),output/(arm+'-training-stderr.log'))
                try:
                    hello=channel.read(time.monotonic()+TRAIN_SECONDS)
                    life.write(output/(arm+'-training-ready.json'),hello)
                    validate_hello(hello,spec['gpu_uuid'])
                    restore=restore_spec(hello['candidate_adapter'],arm,spec['training_spec_sha256'][arm])
                finally:code=channel.close()
                stopped=check_stopped(spec['prefix'],job,spec['gpu_uuid'])
                life.write(output/(arm+'-training-teardown.json'),stopped)
                training_processes[arm]=(stopped['worker']['pid'],stopped['worker']['start_ticks'])
                if code:raise RuntimeError('candidate training worker exited unsuccessfully')
                trained[arm]=hello['candidate_adapter'];deliver_restore(spec,arm,restore,output)
            job='E2B-'+arm+'-eval'
            def factory(name,directory):
                if name!='E2B':raise ValueError('single fixed E2B backbone required')
                return container.ContainerChannel(command(spec['prefix'],job,COLLECT_SECONDS),directory/'E2B-stderr.log')
            factory.gpu_uuid=spec['gpu_uuid'];factory.training_requested=False
            result=runner.collect([r for r in rows if r['arm']==arm],ROOT/'.local/matched-collections'/arm,
                factory,{'E2B':tokenizer},mode='pretrained_cuda',max_new_tokens=768,
                total_seconds=COLLECT_SECONDS,startup_seconds=180,request_seconds=60)
            stopped=check_stopped(spec['prefix'],job,spec['gpu_uuid'])
            life.write(output/(arm+'-evaluation-teardown.json'),stopped)
            if arm!='B1' and (stopped['worker']['pid'],stopped['worker']['start_ticks'])==training_processes[arm]:
                raise ValueError('fresh evaluation process identity was reused')
            preserve(output)
            if result['status']!='COMPLETED' or result['assigned']!=116:raise RuntimeError('candidate arm incomplete; no retries')
            candidate=result['worker_handshakes']['E2B'].get('candidate_adapter')
            if arm=='B1':
                if result['training'] or candidate:raise ValueError('untrained baseline contaminated')
            elif (candidate is None or candidate['status']!='PASS_FRESH_PROCESS_CANDIDATE_RELOAD'
                    or candidate['updates_in_worker']!=0 or candidate['arm']!=arm
                    or candidate['adapter_sha256']!=trained[arm]['adapter_sha256']):
                raise ValueError('independent reloaded worker evidence missing')
        return {'status':'PASS_MATCHED_CANDIDATE_COLLECTION','assigned':348,
            'training_steps':640,'coverage':aggregate(output,rows)['coverage'],
            'capability_claim':'REQUIRES_POST_DELETION_EVALUATION'}
    finally:preserve(output)


def after_hardware(root,endpoint,prefix,output,hardware):
    root=Path(root);output=Path(output)
    header=json.loads((ROOT/'.local/e2b/sources/E2B/tensor-header.json').read_bytes())
    job=base_job(hardware,header);jobs=root/'assets/jobs';jobs.mkdir(mode=0o700)
    life.write(jobs/'E2B-B1-eval.json',job);training={}
    for arm in ('B2','S'):
        training[arm]=json.loads((ROOT/'.local/e2b/matched'/(arm+'-training.json')).read_bytes())
        life.write(jobs/('E2B-'+arm+'-train.json'),dict(job,candidate_training=training[arm]))
    manifest=root/'assets-qualified-manifest.json';manifest.write_bytes(container.manifest(root/'assets','model'))
    transfer=delivery.push(root/'assets',manifest,prefix+[delivery.ssh_command(endpoint['host'],endpoint['port'],
        root/'keys/owner-key',root/'keys/known-hosts','/root/backtrace/assets',life.digest(manifest.read_bytes()))[-1]],600,
        diagnostics=output/'asset-transfer-progress.json')
    installed=remote.remote(prefix,"""import json,pathlib,shutil
src=pathlib.Path('/root/backtrace/assets');dst=pathlib.Path('/opt/backtrace/assets');shutil.move(src,dst)
for p in dst.rglob('*'):
 if p.is_symlink():raise ValueError('asset symlink')
 p.chmod(0o755 if p.is_dir() else 0o444)
dst.chmod(0o755);(dst/'jobs').chmod(0o700)
print(json.dumps({'bytes':sum(p.stat().st_size for p in dst.rglob('*') if p.is_file()),'model':'E2B'}))
""",60)
    life.write(output/'asset-transfer.json',{'transfer':transfer,'installation':installed,'qualified_manifest_sha256':life.digest(manifest.read_bytes())})
    spec=output/'collector-input.json';life.write(spec,{'prefix':prefix,'gpu_uuid':job['gpu']['uuid'],
        'base_job':job,'root':str(root),'endpoint':endpoint,'training_spec_sha256':{a:worker_spec_sha(s) for a,s in training.items()}})
    try:
        with (output/'collector.log').open('xb') as log:
            process=subprocess.run([str(ROOT/'.local/model-runtime/bin/python'),'-m','tools.small_model_matched','collect',str(spec),str(output)],
                stdout=log,stderr=log,timeout=4800,env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8','HOME':str(root),
                    'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'})
    finally:preserve(output)
    if process.returncode:raise RuntimeError('matched collector failed; retain every original assignment')
    result=json.loads((output/'matched-result.json').read_bytes())
    if result['status']!='PASS_MATCHED_CANDIDATE_COLLECTION':raise RuntimeError('matched execution incomplete')
    return result


if __name__=='__main__':
    op,*args=sys.argv[1:]
    if op in ('inspect-inputs','plan-gpu-inputs'):result=inspect_inputs(Path(args[0]),cuda_runtime=op=='plan-gpu-inputs')
    elif op=='collect':
        result=collect(Path(args[0]),Path(args[1]));life.write(Path(args[1])/'matched-result.json',result)
    elif op=='preserve':result=preserve(Path(args[0]))
    else:raise ValueError('explicit candidate operation required')
    print(json.dumps(result,sort_keys=True),flush=True)
