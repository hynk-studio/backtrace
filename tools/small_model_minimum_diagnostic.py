"""Bind the existing lifecycle to one comparison, without claiming CUDA success."""
import contextlib
import json
from pathlib import Path
import re
import sys
import traceback

from tools import small_model_minimum as minimum
from tools import small_model_minimum_remote as remote

REVIEW='bt-001-cuda-trace-20261031'
START='bt-001-cuda-trace-start-20261031'
STATE_BRANCH='bt-001-cuda-trace-state-20261031'
PAID_NAMESPACE='cuda-trace-paid-20261031'
AUTHORIZATION_ID='cuda-trace-20261031-one'
INSTRUCTION='이번에는 목표까지 실제로 이어가도록 하고 혼자 해결할 수 없는 문제가 있을 때만 멈추고 보고해'
WORKFLOW='.github/workflows/small-model-minimum-diagnostic.yml'
CONTRACT=dict(minimum.CONTRACT,scope='CUDA_ABC_AND_DENIED_CALL_TRACE_V1')
OriginalState=minimum.State


class State(OriginalState):
    def __init__(self,token,source,actual,**kw):
        super().__init__(token,source,actual,**kw)
        self.namespace=PAID_NAMESPACE if actual else 'cuda-trace-free-'+source


def validate_permit(value,source,now):
    expected={'source_sha':source,'contract_sha256':minimum.life.digest(CONTRACT),
        'authorization_id':AUTHORIZATION_ID,'namespace':PAID_NAMESPACE,
        'instruction':INSTRUCTION,'mode':'OWNER_APPROVED_CUDA_COMPARISON',
        'additional_cap_usd':'1.00','allocation_inclusive_seconds':3000,
        'single_use':True,'automatic_retry':False,'top_up_allowed':False,
        'weight_download_bytes':0,'pretrained_requests':0,'training_steps':0}
    if not isinstance(value,dict):raise ValueError('diagnostic permit required')
    if any(type(value.get(k)) is not type(v) or value[k]!=v for k,v in expected.items()):
        raise ValueError('fresh bounded diagnostic authorization required')
    if (not re.fullmatch('[1-9][0-9]+',str(value.get('qualification_run_id','')))
            or not 0<=now-minimum.life.finite(value['approved_at'])<86400
            or not now<minimum.life.finite(value['expires_at'])<=value['approved_at']+86400):
        raise ValueError('current qualified diagnostic authorization required')
    return value


def require_run(state,run_id):
    r=state.run(run_id)
    if (r['head_sha']!=state.source or r['head_branch']!=(START if state.actual else REVIEW)
            or r['run_attempt']!=1 or r['status']!='in_progress'
            or r['event']!='push' or r['path']!=WORKFLOW):
        raise ValueError('first exact diagnostic workflow required')


def require_qualification(state,permit):
    r=state.run(permit['qualification_run_id'])
    if (r['head_sha']!=state.source or r['head_branch']!=REVIEW or r['run_attempt']!=1
            or r['event']!='push' or r['status']!='completed'
            or r['conclusion']!='success' or r['path']!=WORKFLOW):
        raise ValueError('complete exact-source free qualification required')


@contextlib.contextmanager
def configured():
    bindings={'REVIEW':REVIEW,'START':START,'STATE_BRANCH':STATE_BRANCH,'State':State,
        'CONTRACT':CONTRACT,'validate_permit':validate_permit,'require_run':require_run,
        'require_qualification':require_qualification,
        'REMOTE_MODULE':'tools.small_model_minimum_diagnostic','SUCCESS_STATUS':'DIAGNOSTIC_RECORDED'}
    previous={k:getattr(minimum,k) for k in bindings}
    if previous['State'] is not OriginalState:raise RuntimeError('scope context cannot nest')
    try:
        for k,v in bindings.items():setattr(minimum,k,v)
        yield
    finally:
        for k,v in previous.items():setattr(minimum,k,v)


def main(role,actual):
    if role not in ('owner','watch') or type(actual) is not bool:
        raise ValueError('explicit diagnostic role and mode required')
    with configured():return minimum.main(role,actual)


def measure(root,endpoint,output):
    """The child entry only measures; it has no provider credentials or API call."""
    result=remote.connected(Path(root),json.loads(Path(endpoint).read_bytes()),
        Path(output),actual=True,comparison_only=True)
    if result['status']=='DIAGNOSTIC_RECORDED':
        comparison=result['diagnostics']['cuda_comparison']
        # connected() has already written its immutable receipt. Keep that
        # original evidence and bind scope metadata in a separate record.
        summary={'status':result['status'],'measurement_decision':comparison['decision'],
            'hardware_qualified':False,'model_baseline_run':False,
            'connected_receipt_sha256':minimum.life.digest(
                (Path(output)/'connected-receipt.json').read_bytes())}
        minimum.life.write(Path(output)/'diagnostic-summary.json',summary)
        result=dict(result,**summary)
    return result


if __name__=='__main__':
    args=sys.argv[1:]
    if len(args)==3:
        result=measure(*args)
    else:
        role,mode=args
        if mode not in ('free','paid'):raise ValueError('explicit mode required')
        out=minimum.ROOT/'evidence';out.mkdir(exist_ok=True)
        try:result=main(role,mode=='paid')
        except Exception as error:
            result={'status':'BLOCKED','error_type':type(error).__name__,'error':str(error)[:500],
                'frames':[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno}
                    for f in traceback.extract_tb(error.__traceback__)][-8:]}
        minimum.life.write(out/('minimum-'+role+'.json'),result)
    print(json.dumps({'status':result['status']}),flush=True)
    raise SystemExit(0 if result['status'] in
        ('DIAGNOSTIC_RECORDED','PASS_FREE_REMOTE_CLEANUP','DELETED') else 1)
