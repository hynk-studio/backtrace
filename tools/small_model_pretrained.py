"""Reuse the pinned E2B sources and original development assignments.

Preparation downloads the actual checkpoint without allocating a GPU. No labels
or evaluator files are sent to a model. Execution is a later explicit entry.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

from tools import small_model_readiness as ready, small_model_runner as runner
from tools import small_model_lifecycle as life
from tools import small_model_minimum_remote as remote, small_model_container as container
from tools import private_delivery as delivery, small_model_gpu as gpu
from tools import small_model_training_inputs as training
from tools import small_model_augnes_screen as screening

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT/'docs/augnes-development-replays-20261031.json'


def replay_schedule(tokenizer):
    packet=json.loads(REPLAY.read_bytes());rows=[]
    neutral='Return only a JSON object matching the supplied output contract. Use only the supplied historical facts. Recommend a next action; do not execute it.'
    strong=neutral+' Separate observation from inference. Consider competing explanations and missing evidence. Choose the smallest action that would distinguish them; stop when further action is unjustified. Preserve unknown causes, failed evidence and authorization boundaries.'
    for case in packet['cases']:
        payload={k:case[k] for k in ('id','cutoff','facts','question','goal','constraints','prior_claims','allowed_checks')}
        payload['facts']=[{'id':'F'+str(i+1),'observation':fact} for i,fact in enumerate(payload['facts'])]
        payload['output_contract']=packet['output_contract']
        for arm,prompt in [('B0',neutral),('B1',strong)]:
            messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]
            encoded=ready.encode(tokenizer,messages,12288)
            if encoded['overflow']:raise ValueError('replay token overflow')
            rows.append({'model':'E2B','arm':arm,'id':case['id'],'messages':messages,
                'input_tokens':encoded['input_tokens'],'input_ids_sha256':encoded['token_ids_sha256']})
    return rows


def prepare_runtime(root):
    initializer=remote.prepare(root,ROOT/'.local/cuda-wheels',ROOT/'.local/transport-build')
    prepared=ROOT/'.local/e2b'
    verified=runner.verify_pretrained_directory('E2B',prepared/'models/E2B')
    ready.validate_sources(prepared/'sources')
    assets=Path(root)/'assets';assets.mkdir(mode=0o700)
    for kind,origin,names in [('models',prepared/'models/E2B',('config.json','generation_config.json','model.safetensors')),
                              ('tokenizers',prepared/'sources/E2B',sorted(ready.FILES))]:
        target=assets/kind/'E2B';target.mkdir(mode=0o700,parents=True)
        for name in names:
            # Relocate the verified large checkpoint; no duplicate 16 GB file.
            if kind=='models':shutil.move(str(origin/name),target/name)
            else:shutil.copyfile(origin/name,target/name)
    (Path(root)/'assets-manifest.json').write_bytes(container.manifest(assets,'model'))
    life.write(Path(root)/'pretrained-preparation.json',{'weights':verified,
        'replay_packet_sha256':life.digest(REPLAY.read_bytes()),'assigned_original':1,'assigned_replay':0,
        'training_steps':0,'planned_training_steps':4,
        'untrained_screening_assigned':20,'evaluator_delivered':False})
    return initializer


def qualified_job(hardware,header):
    if (hardware.get('status')!='PASS_ACTUAL_HARDWARE_ONLY' or not hardware.get('actual_gpu')
            or not hardware.get('checks') or not all(hardware['checks'].values())):
        raise ValueError('complete actual hardware checks required')
    return {'container_model':'E2B','mode':'pretrained_cuda','gpu':hardware['initial_gpu'],
        'adapter_feasibility':training.specification(),
        'hardware_receipt_sha256':life.digest(hardware),'packages':ready.lock()['gpu_candidate']['packages'],
        'key_mapping':ready.lock()['model_loading']['key_mapping'],'max_input_tokens':12288,'max_new_tokens':4096,
        'allowed_unexpected_keys':[k for k in header if k.startswith(ready.NON_TEXT_PREFIXES)]}


def after_hardware(root,endpoint,prefix,output,hardware):
    header=json.loads((ROOT/'.local/e2b/sources/E2B/tensor-header.json').read_bytes())
    job=qualified_job(hardware,header)
    jobs=root/'assets/jobs';jobs.mkdir(mode=0o700)
    life.write(jobs/'E2B-pretrained.json',job)
    screen_job={k:v for k,v in job.items() if k!='adapter_feasibility'}
    screen_job.update(max_input_tokens=4096,max_new_tokens=768)
    life.write(jobs/'E2B-screening.json',screen_job)
    # The complete multimodal-key allowlist can exceed SSH command-size bounds.
    # Send the trusted job through the existing authenticated manifest stream.
    manifest=root/'assets-qualified-manifest.json'
    manifest.write_bytes(container.manifest(root/'assets','model'))
    # Installed model bytes are immutable and contain no prompts or labels.
    transfer=delivery.push(root/'assets',manifest,
        prefix+[delivery.ssh_command(endpoint['host'],endpoint['port'],root/'keys/owner-key',
            root/'keys/known-hosts','/root/backtrace/assets',life.digest(manifest.read_bytes()))[-1]],600)
    installed=remote.remote(prefix,"""import json,pathlib,shutil
src=pathlib.Path('/root/backtrace/assets');dst=pathlib.Path('/opt/backtrace/assets')
shutil.move(str(src),dst)
for p in dst.rglob('*'):
 if p.is_symlink():raise ValueError('asset symlink')
 p.chmod(0o755 if p.is_dir() else 0o444)
dst.chmod(0o755)
# The root supervisor copies only the selected job to /job.json. Other jobs,
# including the later training targets, are not readable by either worker.
(dst/'jobs').chmod(0o700)
print(json.dumps({'bytes':sum(p.stat().st_size for p in dst.rglob('*') if p.is_file()),'model':'E2B'}))
""",60)
    life.write(output/'asset-transfer.json',{'transfer':transfer,'installation':installed,
        'qualified_manifest_sha256':life.digest(manifest.read_bytes())})
    spec=output/'collector-input.json';life.write(spec,{'prefix':prefix,'gpu_uuid':job['gpu']['uuid']})
    python=ROOT/'.local/model-runtime/bin/python'
    # Preserve an untrained practical baseline before the separate training probe.
    try:
        with (output/'screening-collector.log').open('xb') as log:
            p=subprocess.run([str(python),'-m','tools.small_model_pretrained','collect-screening',str(spec),str(output)],
                stdout=log,stderr=log,timeout=930,env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8','HOME':str(root),
                    'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'})
    finally:screening.preserve(output)
    stopped=check_stopped(prefix,'E2B-screening',job['gpu']['uuid'])
    life.write(output/'screening-teardown.json',stopped)
    if stopped['worker']['same_process_alive'] or p.returncode:
        raise RuntimeError('untrained screening collector or cleanup failed')
    screen=json.loads((output/'augnes-screening/collection.json').read_bytes())
    if screen['status']!='COMPLETED' or screen['training']:
        raise RuntimeError('untrained twenty-case screening incomplete; preserve all assignments')
    try:
        with (output/'collector.log').open('xb') as log:
            p=subprocess.run([str(python),'-m','tools.small_model_pretrained','collect-probe',str(spec),str(output)],
                stdout=log,stderr=log,timeout=300,env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8','HOME':str(root),
                    'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'})
    finally:
        preserve_collection(output)
    # An observed idle GPU and absent worker are required before evaluation.
    stopped=check_stopped(prefix,'E2B-pretrained',job['gpu']['uuid'])
    life.write(output/'inference-teardown.json',stopped)
    if stopped['worker']['same_process_alive'] or p.returncode:raise RuntimeError('inference collector or cleanup failed')
    collection=json.loads((output/'collection/collection.json').read_bytes())
    # One original development input only verifies generation after the update.
    # The original 24-response baseline remains separate and unchanged; this is
    # not a tiny selected subset from which a learning score can be estimated.
    _,schedule,_=runner.load_scope(ROOT/'.local/e2b/scope',ROOT/'.local/e2b/packets',ROOT/'.local/e2b/tokenization.json')
    selected=[r for r in schedule if r['model']=='E2B']
    if (collection['assigned']!=1 or len(collection['records'])!=1 or any(
            collection['records'][0][k]!=selected[0][k] for k in ('id','model','arm'))):
        raise RuntimeError('single fixed post-update generation required')
    adaptation=collection.get('worker_handshakes',{}).get('E2B',{}).get('adapter_feasibility',{})
    if adaptation.get('status')!='PASS_TINY_UPDATE_SAVE_RELOAD_ONLY' or adaptation.get('training_steps')!=4:
        raise RuntimeError('actual four-update save/reload evidence absent')
    life.write(output/'adapter-feasibility.json',adaptation)
    return {'status':'PASS_E2B_ADAPTER_FEASIBILITY' if collection['status']=='COMPLETED' else 'INCOMPLETE_E2B_COLLECTION',
        'assigned':21,'adapter_assigned':1,'untrained_screening_assigned':20,
        'untrained_screening_coverage':screen['coverage'],
        'coverage':collection['coverage'],'collection_status':collection['status'],
        'training_steps':adaptation['training_steps'],'capability_claim':'IMPLEMENTATION_ONLY',
        'memory_limit':'Provider allocation and visible memory observed; hidden ancestor limit not attested'}


def check_stopped(prefix,job_name,gpu_uuid):
    if job_name not in ('E2B-pretrained','E2B-screening'):raise ValueError('known job required')
    stopped=remote.remote(prefix,"""import json,pathlib
r=json.loads(pathlib.Path("""+repr('/root/backtrace/'+job_name+'-state.json')+""").read_bytes())
try:r['same_process_alive']=pathlib.Path('/proc',str(r['pid']),'stat').read_text().split()[21]==r['start_ticks']
except (FileNotFoundError,ProcessLookupError):r['same_process_alive']=False
print(json.dumps(r))
""")
    return {'worker':stopped,'gpu':remote.inventory(prefix,gpu_uuid)}


def collect(spec_path,output,*,probe_only=False):
    from transformers import AutoTokenizer
    spec=json.loads(Path(spec_path).read_bytes());output=Path(output)
    prepared=ROOT/'.local/e2b'
    tokenizer=AutoTokenizer.from_pretrained(prepared/'sources/E2B',local_files_only=True,trust_remote_code=False)
    _,schedule,_=runner.load_scope(prepared/'scope',prepared/'packets',prepared/'tokenization.json')
    selected=[r for r in schedule if r['model']=='E2B']
    selected=selected[:1] if probe_only else selected+replay_schedule(tokenizer)
    life.write(output/'input-schedule.json',{'requests':selected,'packet_sha256':life.digest(REPLAY.read_bytes())})
    def factory(name,directory):
        if name!='E2B':raise ValueError('E2B only')
        command=spec['prefix']+[shlex.join(['/usr/bin/env','-i','PATH=/usr/bin:/bin','LANG=C.UTF-8',
            'LD_LIBRARY_PATH=/opt/backtrace/python/lib','/opt/backtrace/venv/bin/python','-I',
            '/opt/backtrace/launcher.py','run','E2B-pretrained','240' if probe_only else '1500','pretrained'])]
        return container.ContainerChannel(command,directory/'E2B-stderr.log')
    factory.gpu_uuid=spec['gpu_uuid'];factory.training_requested=True
    return runner.collect(selected,ROOT/'.local/e2b-collection',factory,{'E2B':tokenizer},mode='pretrained_cuda',
        max_new_tokens=4096,total_seconds=240 if probe_only else 1500,startup_seconds=180,request_seconds=90)


def preserve_collection(output):
    screening.preserve(output)
    source=ROOT/'.local/e2b-collection';target=Path(output)/'collection';count=0
    if source.exists():
        target.mkdir(parents=True,exist_ok=True)
        for p in source.iterdir():
            if p.is_file() and not p.is_symlink() and p.suffix in ('.json','.jsonl','.log') and p.stat().st_size<=16*1024**2:
                shutil.copyfile(p,target/p.name);count+=1
    return {'files':count}


def inspect_inputs(prepared,*,cuda_runtime=False):
    from transformers import AutoTokenizer
    prepared=Path(prepared)
    if cuda_runtime:gpu.check_runtime()
    else:ready.check_packages()
    tokenizer=AutoTokenizer.from_pretrained(prepared/'sources/E2B',local_files_only=True,trust_remote_code=False)
    plan,schedule,_=runner.load_scope(prepared/'scope',prepared/'packets',prepared/'tokenization.json')
    original=[r for r in schedule if r['model']=='E2B'];replays=replay_schedule(tokenizer)
    previous=json.loads((ROOT/'docs/evidence/e2b-run-41206950960/input-schedule.json').read_bytes())['requests']
    current=original+replays
    if len(previous)!=24 or len(current)!=24 or any(
            a['model']!='E2B' or b['model']!='E2B' or
            any(a[k]!=b[k] for k in ('id','arm','messages')) for a,b in zip(previous,current)):
        raise ValueError('E2B comparison must preserve all 24 E2B messages and assignments')
    for row in original:
        actual=ready.encode(tokenizer,row['messages'],12288)
        if actual['input_tokens']!=row['input_tokens'] or actual['token_ids_sha256']!=row['input_ids_sha256']:
            raise ValueError('original tokenizer evidence did not reproduce')
    # Exercise scoring with missing execution before spending; absence is not accuracy.
    missing={'mode':'pretrained_cuda','source_hashes':runner.source_hashes(),
        'coverage':{'NOT_RUN':18},'records':[dict(model=r['model'],arm=r['arm'],id=r['id'],status='NOT_RUN') for r in original]}
    runner.evaluate(plan,original,missing)
    return {'status':'PASS_INPUTS_NOT_INFERENCE','identical_e2b_comparison_messages':True,
        'training_inputs':training.verify_tokens(tokenizer),
        'untrained_screening_assignments':[{k:v for k,v in r.items() if k!='messages'} for r in screening.schedule(tokenizer)],
        'original_assigned':1,'replay_assigned':0,
        'historical_original_count':len(original),'historical_replay_count':len(replays),
        'assigned_before_allocation':[{**{k:v for k,v in r.items() if k!='messages'},'initial_status':'NOT_RUN'}
            for r in screening.schedule(tokenizer)+original[:1]],
        'historical_comparison_not_assigned':[{k:v for k,v in r.items() if k!='messages'} for r in original[1:]+replays],
        'replays':[{k:v for k,v in r.items() if k!='messages'} for r in replays],
        'packet_sha256':life.digest(REPLAY.read_bytes()),'pretrained_requests':0}


def prepare(output, readiness_archive):
    output = Path(output).resolve(); output.mkdir(mode=0o700, parents=True, exist_ok=False)
    record = json.loads((ROOT/'docs/small-model-readiness-cpu-20261026.json').read_bytes())['artifact']
    raw = Path(readiness_archive).read_bytes()
    if hashlib.sha256(raw).hexdigest() != record['verified_sha256']:
        raise ValueError('historical tokenizer archive hash mismatch')
    with zipfile.ZipFile(readiness_archive) as archive:
        tokens = archive.read('tokenization-cases.json')
    expected = record['verified_members']['tokenization-cases.json']
    if len(tokens) != expected['bytes'] or life.digest(tokens) != expected['sha256']:
        raise ValueError('historical tokenizer report hash mismatch')
    (output/'tokenization.json').write_bytes(tokens)
    ready.rebuild_packets(output/'packets')
    ready.prepare_scope(output/'packets',output/'tokenization.json',output/'scope',scope='smoke')
    plan,schedule,_ = runner.load_scope(output/'scope',output/'packets',output/'tokenization.json')
    selected = [row for row in schedule if row['model']=='E2B']
    if len(selected)!=18 or {row['arm'] for row in selected}!={'B0','B1'}:
        raise ValueError('original 18 E2B assignments required')
    ready.acquire_sources(output/'sources')
    spec = ready.lock()['models']['E2B']; weight = spec['weights_metadata_only'][0]
    if shutil.disk_usage(output).free < weight['bytes'] + 4*1024**3:
        raise RuntimeError('insufficient free disk before checkpoint acquisition')
    model = output/'models/E2B'; model.mkdir(mode=0o700,parents=True)
    for name in ('config.json','generation_config.json'):
        shutil.copyfile(output/'sources/E2B'/name,model/name)
    destination = model/'model.safetensors'; started=time.monotonic(); size=0
    # The complete response is hash-checked against the previously pinned LFS OID.
    request=urllib.request.Request(spec['tensor_header']['url']+'?download=true')
    with urllib.request.urlopen(request,timeout=60) as response, destination.open('xb') as stream:
        if response.status!=200:raise ValueError('complete checkpoint response required')
        while chunk:=response.read(8*1024**2):
            size+=len(chunk)
            if size>weight['bytes'] or time.monotonic()-started>900:
                raise RuntimeError('checkpoint acquisition bound exceeded')
            stream.write(chunk)
    verified=runner.verify_pretrained_directory('E2B',model)
    result={'status':'PASS_PRETRAINED_BYTES_NOT_INFERENCE','weights':verified,
        'assigned':len(selected),'independent_development_episodes':1,
        'scope':'E2B_ONLY_FROM_ORIGINAL_SMOKE','excluded_model':'E4B_MEASURED_SEPARATELY',
        'checkpoint_download_seconds':time.monotonic()-started,'pretrained_requests':0,
        'source_sha':__import__('os').environ.get('GITHUB_SHA')}
    life.write(output/'preparation.json',result); return result


if __name__=='__main__':
    if sys.argv[1]=='prepare':result=prepare(sys.argv[2],sys.argv[3])
    elif sys.argv[1]=='collect':result=collect(sys.argv[2],sys.argv[3])
    elif sys.argv[1]=='collect-probe':result=collect(sys.argv[2],sys.argv[3],probe_only=True)
    elif sys.argv[1]=='collect-screening':result=screening.collect(sys.argv[2],sys.argv[3])
    elif sys.argv[1]=='inspect-inputs':result=inspect_inputs(sys.argv[2])
    elif sys.argv[1]=='plan-gpu-inputs':result=inspect_inputs(sys.argv[2],cuda_runtime=True)
    elif sys.argv[1]=='preserve':result=preserve_collection(sys.argv[2])
    else:raise ValueError('explicit preparation or collection required')
    print(json.dumps(result,sort_keys=True))
