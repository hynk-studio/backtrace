"""One newly authorized retry; reuse qualified hardware code without editing it."""
import contextlib
import json
from pathlib import Path
import re
import sys
import traceback

from tools import small_model_minimum as minimum

REVIEW='bt-001-small-model-minimum-retry-20261027'
START='bt-001-small-model-minimum-retry-start-20261027'
STATE_BRANCH='bt-001-small-model-minimum-retry-state-20261027'
PAID_NAMESPACE='minimum-retry-paid-20261027'
AUTHORIZATION_ID='hardware-minimum-retry-20261027-one'
INSTRUCTION='1회 다시 진행해'
CPU_WORKFLOW='.github/workflows/small-model-minimum-retry-cpu.yml'
LIVE_WORKFLOW='.github/workflows/small-model-minimum-retry-live.yml'
OriginalState=minimum.State


class State(OriginalState):
    def __init__(self,token,source,actual,**kw):
        super().__init__(token,source,actual,**kw)
        # Construction performs no I/O. Every read/write now targets only this
        # new namespace, on the new branch installed by configured().
        self.namespace=PAID_NAMESPACE if actual else 'minimum-retry-free-'+source


def validate_permit(value,source,now):
    if (not isinstance(value,dict) or value.get('source_sha')!=source
            or value.get('contract_sha256')!=minimum.life.digest(minimum.CONTRACT)
            or value.get('authorization_id')!=AUTHORIZATION_ID or value.get('namespace')!=PAID_NAMESPACE
            or value.get('instruction')!=INSTRUCTION or value.get('single_use') is not True
            or value.get('mode')!='OWNER_APPROVED_HARDWARE_MINIMUM'
            or value.get('additional_cap_usd')!='1.00' or value.get('allocation_inclusive_seconds')!=3000
            or value.get('automatic_retry') is not False or value.get('top_up_allowed') is not False
            or any(type(value.get(k)) is not int or value[k]!=0 for k in ('weight_download_bytes','pretrained_requests','training_steps'))
            or not re.fullmatch('[1-9][0-9]+',str(value.get('qualification_run_id','')))
            or not 0<=now-minimum.life.finite(value['approved_at'])<86400
            or not now<minimum.life.finite(value['expires_at'])<=value['approved_at']+86400):
        raise ValueError('fresh source-bound one-retry authorization required')
    return value


def require_run(state,run_id):
    r=state.run(run_id)
    if (r['head_sha']!=state.source or r['head_branch']!=(START if state.actual else REVIEW)
            or r['run_attempt']!=1 or r['status']!='in_progress' or r['event']!='push'
            or r['path']!=(LIVE_WORKFLOW if state.actual else CPU_WORKFLOW)):
        raise ValueError('first exact retry workflow required')


def require_qualification(state,permit):
    r=state.run(permit['qualification_run_id'])
    if (r['head_sha']!=state.source or r['head_branch']!=REVIEW or r['run_attempt']!=1
            or r['event']!='push' or r['status']!='completed' or r['conclusion']!='success'
            or r['path']!=CPU_WORKFLOW):
        raise ValueError('exact-source complete free retry qualification required')


@contextlib.contextmanager
def configured():
    """Scope the unchanged controller for one synchronous owner/watch process."""
    bindings={'REVIEW':REVIEW,'START':START,'STATE_BRANCH':STATE_BRANCH,'State':State,
        'validate_permit':validate_permit,'require_run':require_run,'require_qualification':require_qualification}
    previous={k:getattr(minimum,k) for k in bindings}
    if previous['State'] is not OriginalState:raise RuntimeError('retry context cannot nest')
    try:
        for key,value in bindings.items():setattr(minimum,key,value)
        yield
    finally:
        for key,value in previous.items():setattr(minimum,key,value)


def main(role,actual):
    if role not in ('owner','watch') or type(actual) is not bool:raise ValueError('explicit retry role and mode required')
    with configured():return minimum.main(role,actual)


if __name__=='__main__':
    role,mode=sys.argv[1:]
    if mode not in ('free','paid'):raise ValueError('explicit retry execution mode required')
    out=minimum.ROOT/'evidence';out.mkdir(exist_ok=True)
    try:result=main(role,mode=='paid')
    except Exception as error:
        result={'status':'BLOCKED','error_type':type(error).__name__,'error':str(error)[:500],
            'frames':[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno}
                for f in traceback.extract_tb(error.__traceback__)][-8:]}
    minimum.life.write(out/('minimum-'+role+'.json'),result)
    print(json.dumps({'role':role,'status':result['status']}))
    raise SystemExit(0 if result['status'] in ('PASS_ACTUAL_HARDWARE_ONLY','PASS_FREE_REMOTE_CLEANUP','DELETED') else 1)
