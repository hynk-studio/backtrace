"""Frozen retrospective inputs and existing collector; no task execution."""
import json
from pathlib import Path
import shlex
import shutil

from tools import small_model_readiness as ready, small_model_runner as runner
from tools import small_model_container as container, small_model_lifecycle as life

ROOT=Path(__file__).resolve().parents[1]
PACKET=ROOT/'docs/augnes-screening-packets-20261031.json'
SYSTEM=('Return only one JSON object matching the supplied output contract, without markdown. '
        'Use only the supplied historical facts. Separate observation from inference. '
        'Consider competing explanations and missing evidence only when diagnosis is useful. '
        'Choose the smallest justified next action, or proceed/stop when further diagnosis is unnecessary. '
        'Preserve unknown causes, failed evidence and authorization boundaries. Do not execute actions.')


def schedule(tokenizer):
    packet=json.loads(PACKET.read_bytes());rows=[]
    if len(packet['cases'])!=20 or len({c['id'] for c in packet['cases']})!=20:
        raise ValueError('exact twenty distinct issue episodes required')
    for case in packet['cases']:
        payload={k:case[k] for k in ('id','cutoff','goal','facts','prior_claims','constraints','allowed_checks','question')}
        payload['output_contract']=packet['output_contract']
        messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]
        encoded=ready.encode(tokenizer,messages,4096)
        if encoded['overflow']:raise ValueError('screening input overflow')
        rows.append({'model':'E2B','arm':'B1','id':case['id'],'messages':messages,
                     'input_tokens':encoded['input_tokens'],'input_ids_sha256':encoded['token_ids_sha256']})
    return rows


def preserve(output):
    source=ROOT/'.local/augnes-screening-collection';target=Path(output)/'augnes-screening';count=0
    if source.exists():
        target.mkdir(parents=True,exist_ok=True)
        for p in source.iterdir():
            if p.is_file() and not p.is_symlink() and p.suffix in ('.json','.jsonl','.log') and p.stat().st_size<=16*1024**2:
                shutil.copyfile(p,target/p.name);count+=1
    return {'files':count}


def collect(spec_path,output):
    from transformers import AutoTokenizer
    spec=json.loads(Path(spec_path).read_bytes())
    tokenizer=AutoTokenizer.from_pretrained(ROOT/'.local/e2b/sources/E2B',local_files_only=True,trust_remote_code=False)
    rows=schedule(tokenizer)
    life.write(Path(output)/'screening-input-schedule.json',{'requests':rows,'packet_sha256':life.digest(PACKET.read_bytes())})
    def factory(name,directory):
        if name!='E2B':raise ValueError('E2B only')
        command=spec['prefix']+[shlex.join(['/usr/bin/env','-i','PATH=/usr/bin:/bin','LANG=C.UTF-8',
            'LD_LIBRARY_PATH=/opt/backtrace/python/lib','/opt/backtrace/venv/bin/python','-I',
            '/opt/backtrace/launcher.py','run','E2B-screening','900','pretrained'])]
        return container.ContainerChannel(command,directory/'E2B-stderr.log')
    factory.gpu_uuid=spec['gpu_uuid'];factory.training_requested=False
    return runner.collect(rows,ROOT/'.local/augnes-screening-collection',factory,{'E2B':tokenizer},
        mode='pretrained_cuda',max_new_tokens=768,total_seconds=900,startup_seconds=180,request_seconds=60)
