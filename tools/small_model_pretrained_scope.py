"""Source-bound E2B entry through the existing owner/watcher; no new orchestrator."""
import contextlib
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time
import traceback

from tools import small_model_minimum as minimum, small_model_minimum_remote as remote
from tools import small_model_minimum_probe as probe, small_model_pretrained as pretrained
from tools import small_model_container as container

REVIEW='bt-001-e2b-adapter-20261031'
START='bt-001-e2b-adapter-start-20261031'
STATE_BRANCH='bt-001-e2b-adapter-state-20261031'
NAMESPACE='e2b-adapter-paid-20261031'
WORKFLOW='.github/workflows/small-model-pretrained.yml'
INSTRUCTION='이번에는 목표까지 실제로 이어가도록 하고 혼자 해결할 수 없는 문제가 있을 때만 멈추고 보고해'
CONTRACT=dict(minimum.CONTRACT,scope='E2B_SCREEN20_PLUS_ADAPTER4_GENERATIONS24_V1',
    weight_bytes=10246621918,pretrained_requests=44,training_steps=4,total_seconds=2160,work_seconds=1740,
    excluded_regions=['EU-SE-1'],
    cuda_socket_policy='UNIX_SEQPACKET_PASSIVE_BIND_LISTEN_NO_CONNECTIONS_V1',
    full_model_memory_admission='BOUNDED_ATTEMPT_PROVIDER_AND_VISIBLE_MEMORY_ONLY')
OriginalState=minimum.State
original_sources=minimum.sources
original_choose=minimum.choose


def choose(snapshot,now):
    # EU-SE-1 timed out during the common runtime transfer in run 41210831659.
    # Exclude that route; the fresh cheapest other affordable >=40 GB route wins;
    # this is a prospective route change, not proof of the timeout's cause.
    routed=dict(snapshot,offers=[r for r in snapshot['offers'] if r['region'] not in CONTRACT['excluded_regions']])
    offer=original_choose(routed,now)
    projected=Decimal(offer['costs']['maximum_projection'])
    if (projected>Decimal('0.504')
            or Decimal(snapshot['account']['credit_balance_usd'])-projected<Decimal('1.9060441339')):
        raise ValueError('fresh offer exceeds remaining cumulative continuation budget')
    return offer


class State(OriginalState):
    def __init__(self,token,source,actual,**kw):
        super().__init__(token,source,actual,**kw)
        self.namespace=NAMESPACE if actual else 'e2b-baseline-free-'+source


def sources():
    extra=('tools/small_model_pretrained.py','tools/small_model_pretrained_scope.py',
        'tests/test_small_model_pretrained.py','tools/small_model_training_inputs.py',
        'tests/test_small_model_training_inputs.py','tools/small_model_augnes_screen.py',
        'tests/test_small_model_augnes_screen.py',WORKFLOW,
        'docs/augnes-screening-packets-20261031.json','docs/augnes-screening-rubric-20261031.json',
        'docs/augnes-development-replays-20261031.json','docs/augnes-development-replay-rubric-20261031.json',
        'docs/evidence/e2b-run-41206950960/input-schedule.json')
    return dict(original_sources(),**{p:minimum.life.digest((minimum.ROOT/p).read_bytes()) for p in extra})


def validate_permit(value,source,now):
    expected={'source_sha':source,'contract_sha256':minimum.life.digest(CONTRACT),
        'namespace':NAMESPACE,'instruction':INSTRUCTION,'mode':'OWNER_APPROVED_E2B_ADAPTER_FEASIBILITY',
        'additional_cap_usd':'1.00','allocation_inclusive_seconds':2160,'single_use':True,
        'automatic_retry':False,'top_up_allowed':False,'weight_bytes':10246621918,
        'pretrained_requests':44,'training_steps':4}
    if not isinstance(value,dict) or any(type(value.get(k)) is not type(v) or value[k]!=v for k,v in expected.items()):
        raise ValueError('fresh source-bound E2B permit required')
    if (not re.fullmatch('[1-9][0-9]+',str(value.get('qualification_run_id','')))
            or not 0<=now-minimum.life.finite(value['approved_at'])<86400
            or not now<minimum.life.finite(value['expires_at'])<=value['approved_at']+86400):
        raise ValueError('current complete qualification required')
    # Enforce the cumulative cap from this continuation, including prior trace.
    spent=minimum.provider.money(value['continuation_observed_spend_usd'])
    if spent<0 or spent+minimum.provider.money(value['maximum_projection_usd'])>1:
        raise ValueError('cumulative continuation cap exceeded')
    return value


def require_run(state,rid):
    expected={'head_sha':state.source,'head_branch':START if state.actual else REVIEW,
              'run_attempt':1,'event':'push','path':WORKFLOW}
    # The API can lag the already-running job. Retry only a matching queued run,
    # never a different source, path, attempt or terminal status; retain metadata
    # if admission still fails so the rejection is diagnosable without a rerun.
    for attempt in range(11):
        row=state.run(rid)
        observed={k:row.get(k) for k in (*expected,'status')}
        if all(row.get(k)==v for k,v in expected.items()):
            if row.get('status')=='in_progress':return
            if row.get('status')=='queued' and attempt<10:
                time.sleep(2);continue
        raise ValueError('exact first E2B workflow required: '+json.dumps(observed,sort_keys=True))


def require_qualification(state,permit):
    row=state.run(permit['qualification_run_id'])
    if (row['head_sha']!=state.source or row['head_branch']!=REVIEW or row['run_attempt']!=1
            or row['event']!='push' or row['status']!='completed' or row['conclusion']!='success'
            or row['path']!=WORKFLOW):raise ValueError('successful exact-source free E2B qualification required')


@contextlib.contextmanager
def configured():
    bindings={'REVIEW':REVIEW,'START':START,'STATE_BRANCH':STATE_BRANCH,'State':State,
        'CONTRACT':CONTRACT,'sources':sources,'validate_permit':validate_permit,
        'choose':choose,
        'require_run':require_run,'require_qualification':require_qualification,
        'prepare_runtime':pretrained.prepare_runtime,'REMOTE_MODULE':'tools.small_model_pretrained_scope',
        'SUCCESS_STATUS':'PASS_E2B_ADAPTER_FEASIBILITY'}
    previous={k:getattr(minimum,k) for k in bindings}
    if previous['State'] is not OriginalState:raise RuntimeError('scope contexts cannot nest')
    try:
        for k,v in bindings.items():setattr(minimum,k,v)
        yield
    finally:
        for k,v in previous.items():setattr(minimum,k,v)


def free_entry(prefix,output):
    """The actual pretrained launcher must reject a CPU container, not fall back."""
    job={'container_model':'E2B','mode':'pretrained_cuda','hardware_receipt_sha256':'0'*64,
        'packages':pretrained.ready.lock()['gpu_candidate']['packages'],
        'gpu':{'uuid':'GPU-00000000-0000-0000-0000-000000000000'}}
    remote.remote(prefix,"""import pathlib,json
r=pathlib.Path('/opt/backtrace/assets')
for x in ('models/E2B','tokenizers/E2B','jobs'):(r/x).mkdir(mode=0o755,parents=True,exist_ok=True)
p=r/'jobs/E2B-pretrained.json';p.write_text("""+repr(json.dumps(job))+""");p.chmod(0o444)
(r/'jobs').chmod(0o700)
print('{}')
""")
    log=Path(output)/'pretrained-missing-gpu.log'
    cmd=prefix+[shlex.join(['/usr/bin/env','-i','PATH=/usr/bin:/bin','LANG=C.UTF-8',
        'LD_LIBRARY_PATH=/opt/backtrace/python/lib','/opt/backtrace/venv/bin/python','-I',
        '/opt/backtrace/launcher.py','run','E2B-pretrained','30','pretrained'])]
    channel=container.ContainerChannel(cmd,log)
    try:
        try:channel.read(time.monotonic()+35);raise AssertionError('CPU fixture returned pretrained output')
        except EOFError:pass
    finally:code=channel.close()
    if not code or 'CPU fallback forbidden' not in log.read_text():
        raise AssertionError('pretrained entry did not reject missing GPU at the exact kernel gate')
    from tools.small_model_training_inputs import CPU_CONTROL
    # A numerical implementation control in the same pinned free runtime. It
    # neither loads pretrained weights nor attests a CUDA backward pass.
    control=remote.remote(prefix,"""import subprocess,os,json
p=subprocess.run(['/opt/backtrace/venv/bin/python','-I','-c',"""+repr(CPU_CONTROL)+"""],
 capture_output=True,timeout=90,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8',
 'LD_LIBRARY_PATH':'/opt/backtrace/python/lib','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
if p.returncode:raise RuntimeError(p.stderr[-2000:].decode())
print(json.dumps(json.loads(p.stdout)))
""",100)
    if control['status']!='PASS_RANDOM_CPU_ADAPTER_CONTROL':raise AssertionError('adapter CPU control failed')
    minimum.life.write(Path(output)/'adapter-cpu-control.json',control)
    return {'status':'PASS_CPU_REFUSAL_AND_ADAPTER_CONTROL','explicit_fixture_job':True,
            'exit_code':code,'inference':False,'adapter_control':control}


if __name__=='__main__':
    args=sys.argv[1:]
    if args[0]=='qualify':
        result=probe.qualify(*map(Path,args[1:]),extra=free_entry)
    elif len(args)==3:
        result=remote.connected(Path(args[0]),json.loads(Path(args[1]).read_bytes()),Path(args[2]),
            actual=True,after_hardware=pretrained.after_hardware,compare_before_hardware=True)
    else:
        role,mode=args
        if role not in ('owner','watch') or mode not in ('free','paid'):raise ValueError('explicit role and mode required')
        out=minimum.ROOT/'evidence';out.mkdir(exist_ok=True)
        try:
            with configured():result=minimum.main(role,mode=='paid')
        except Exception as error:
            result={'status':'BLOCKED','error_type':type(error).__name__,'error':str(error)[:500],
                'frames':[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno}
                    for f in traceback.extract_tb(error.__traceback__)][-8:]}
        minimum.life.write(out/('minimum-'+role+'.json'),result)
    print(json.dumps({'status':result['status']}),flush=True)
    raise SystemExit(0 if result['status'] in ('PASS_E2B_ADAPTER_FEASIBILITY','PASS_FREE_MINIMUM_ENTRY','PASS_FREE_REMOTE_CLEANUP','DELETED') else 1)
