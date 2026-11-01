"""Source-bound matched E2B candidate through the existing owner/watcher."""
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
from tools import small_model_minimum_probe as probe, small_model_trainability as pretrained
from tools import small_model_container as container
from tools import small_model_public_delivery as public

REVIEW='bt-001-trainability-20261101'
START='bt-001-trainability-start-20261101'
STATE_BRANCH='bt-001-trainability-state-20261101'
NAMESPACE='trainability-paid-20261101'
WORKFLOW='.github/workflows/small-model-trainability.yml'
INSTRUCTION='다음 단계 진행해'
CONTRACT=dict(minimum.CONTRACT,scope='E2B_TRAINABILITY_16X640X2_V1',
    weight_bytes=10246621918,pretrained_requests=48,training_steps=1280,total_seconds=4200,work_seconds=3780,
    maximum_additional_usd='0.75',cumulative_continuation_cap_usd='2.30',
    minimum_post_projection_credit_usd='0.6060441339',
    train_examples_per_arm=16,training_steps_per_arm=640,training_epochs=40,
    maximum_effective_training_tokens_per_arm=1000000,training_maximum_tokens=3072,
    development_episodes=0,fixed_augnes_cases=0,arms=['BASE','Q1','Q4'],seed=17,
    max_input_tokens=4096,max_new_tokens=768,request_seconds=60,
    ssh_receive_window_bytes=8388608,public_asset_delivery='PINNED_HTTPS_PREPARATION_ONLY_V1',
    owner_payload_maximum_bytes=64*1024**2,owner_payload_maximum_seconds=90,
    excluded_regions=[],excluded_routes=[{'gpu':'NVIDIA RTX A6000','region':'US-TX-1'}],
    cuda_socket_policy='UNIX_SEQPACKET_PASSIVE_BIND_LISTEN_NO_CONNECTIONS_V1',
    full_model_memory_admission='BOUNDED_ATTEMPT_PROVIDER_AND_VISIBLE_MEMORY_ONLY')

OriginalState=minimum.State
original_sources=minimum.sources
original_choose=minimum.choose


def choose(snapshot,now):
    # Public bulk delivery materially changes the failed A40 SSH transport path.
    # Keep the unrelated create exclusion; no regional reliability is inferred.
    routed=dict(snapshot,offers=[r for r in snapshot['offers'] if r['region'] not in CONTRACT['excluded_regions']
        and {'gpu':r['gpu'],'region':r['region']} not in CONTRACT['excluded_routes']])
    offer=original_choose(routed,now)
    projected=Decimal(offer['costs']['maximum_projection'])
    if (projected>Decimal('0.75')
            or Decimal(snapshot['account']['credit_balance_usd'])-projected<Decimal('0.6060441339')):
        raise ValueError('fresh offer exceeds remaining cumulative continuation budget')
    return dict(offer,costs=dict(offer['costs'],additional_cap='0.75'))


class State(OriginalState):
    def __init__(self,token,source,actual,**kw):
        super().__init__(token,source,actual,**kw)
        self.namespace=NAMESPACE if actual else 'trainability-free-'+source


def sources():
    extra=('tools/small_model_matched_data.py','tools/small_model_matched.py','tools/small_model_matched_scope.py','tools/small_model_trainability.py','tools/small_model_trainability_data.py','tools/small_model_trainability_scope.py',
        'tests/test_small_model_trainability.py','tools/small_model_sft_inputs.py','docs/small-model-trainability-20261101.md',
        'tools/small_model_pretrained.py','tools/small_model_pretrained_scope.py',
        'tools/small_model_public_delivery.py','tools/small_model_public_scope.py','tests/test_small_model_public_delivery.py',
        'tests/test_small_model_pretrained.py','tools/small_model_training_inputs.py',
        'tests/test_small_model_training_inputs.py','tools/small_model_augnes_screen.py',
        'tests/test_small_model_augnes_screen.py',WORKFLOW,
        'tests/official_cloud_transport.py','tests/small_model_transport_control.py','tools/small_model_delivery.py','tests/test_small_model_delivery.py',
        'tests/test_private_delivery.py','tests/test_ssh_bootstrap.py',
        'docs/augnes-screening-packets-20261031.json','docs/augnes-screening-rubric-20261031.json',
        'docs/evidence/window-paid-run-41225173224/recovered-screening-raw.json',
        'docs/augnes-development-replays-20261031.json','docs/augnes-development-replay-rubric-20261031.json',
        'docs/evidence/e2b-run-41206950960/input-schedule.json')
    return dict(original_sources(),**{p:minimum.life.digest((minimum.ROOT/p).read_bytes()) for p in extra})


def validate_permit(value,source,now):
    expected={'source_sha':source,'contract_sha256':minimum.life.digest(CONTRACT),
        'namespace':NAMESPACE,'instruction':INSTRUCTION,'mode':'OWNER_APPROVED_E2B_TRAINABILITY',
        'additional_cap_usd':'0.75','allocation_inclusive_seconds':4200,'single_use':True,
        'automatic_retry':False,'top_up_allowed':False,'weight_bytes':10246621918,
        'pretrained_requests':48,'training_steps':1280}
    if not isinstance(value,dict) or any(type(value.get(k)) is not type(v) or value[k]!=v for k,v in expected.items()):
        raise ValueError('fresh source-bound E2B permit required')
    if (not re.fullmatch('[1-9][0-9]+',str(value.get('qualification_run_id','')))
            or not 0<=now-minimum.life.finite(value['approved_at'])<86400
            or not now<minimum.life.finite(value['expires_at'])<=value['approved_at']+86400):
        raise ValueError('current complete qualification required')
    # Prospectively bounded completion inside the existing prepaid wallet.
    # The former assistant-selected USD1 continuation envelope remains historical.
    spent=minimum.provider.money(value['continuation_observed_spend_usd'])
    projected=minimum.provider.money(value['maximum_projection_usd'])
    if spent<0 or projected<0 or projected>Decimal('0.75') or spent+projected>Decimal('2.30'):
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
        'prepare_runtime':pretrained.prepare_runtime,'REMOTE_MODULE':'tools.small_model_trainability_scope',
        'SUCCESS_STATUS':'PASS_TRAINABILITY_COLLECTION'}
    previous={k:getattr(minimum,k) for k in bindings}
    if previous['State'] is not OriginalState:raise RuntimeError('scope contexts cannot nest')
    try:
        for k,v in bindings.items():setattr(minimum,k,v)
        with pretrained.delivery.larger_receive_window(),public.configured():yield
    finally:
        for k,v in previous.items():setattr(minimum,k,v)


def free_entry(prefix,output):
    from tools import small_model_public_scope as prior
    result=prior.original_free_entry(prefix,output)
    from tools.small_model_trainability_data import CPU_CONTROL
    control=remote.remote(prefix,"""import subprocess,json
p=subprocess.run(['/opt/backtrace/venv/bin/python','-I','-c',"""+repr(CPU_CONTROL)+"""],
 capture_output=True,timeout=180,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8',
 'LD_LIBRARY_PATH':'/opt/backtrace/python/lib','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
if p.returncode:raise RuntimeError(p.stderr[-4000:].decode())
print(json.dumps(json.loads(p.stdout)))
""",190)
    if control['status']!='PASS_RANDOM_CPU_TRAINABILITY_CONTROL':raise AssertionError('matched numerical control failed')
    minimum.life.write(Path(output)/'trainability-cpu-control.json',control)
    result['matched_control']=control
    result['public_checkpoint']=public.qualify_model(prefix,output)
    return result


if __name__=='__main__':
    args=sys.argv[1:]
    if args[0]=='qualify':
        with configured():
            result=probe.qualify(*map(Path,args[1:]),extra=free_entry)
    elif len(args)==3:
        with configured():
            result=remote.connected(Path(args[0]),json.loads(Path(args[1]).read_bytes()),Path(args[2]),
                actual=True,after_hardware=pretrained.after_hardware,compare_before_hardware=True,
                before_runtime=None)
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
    raise SystemExit(0 if result['status'] in ('PASS_TRAINABILITY_COLLECTION','PASS_FREE_MINIMUM_ENTRY','PASS_FREE_REMOTE_CLEANUP','DELETED') else 1)
