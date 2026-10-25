"""Free cross-workflow GitHub state handshake; never imports a provider client."""
import json
import os
from pathlib import Path
import sys
import time

from tools import research_entry_contract as c
from tools.research_entry_state import State,StateError


def probe(role):
    source=os.environ['GITHUB_SHA'];rid=os.environ['GITHUB_RUN_ID']
    if os.environ['GITHUB_REF_NAME']!=c.REVIEW or os.environ['GITHUB_RUN_ATTEMPT']!='1':
        raise ValueError('free first-run review source required')
    state=State(os.environ['GITHUB_TOKEN'],'free-github-'+source)
    ref=state.request('GET','/git/ref/heads/'+c.STATE,missing=True)
    if ref is None:
        try:state.request('POST','/git/refs',{'ref':'refs/heads/'+c.STATE,'sha':source})
        except StateError:
            if state.request('GET','/git/ref/heads/'+c.STATE,missing=True) is None:raise
    self_run=state.run(rid)
    c.require_run(self_run,rid,source,c.REVIEW,path='.github/workflows/research-entry-probe-'+role+'.yml')
    row={'mode':'FREE_GITHUB_HANDSHAKE','role':role,'source_sha':source,'run_id':rid,'at':time.time()}
    state.write('probe-'+role,row)
    counterpart='watch' if role=='owner' else 'owner';end=time.monotonic()+180
    while True:
        other=state.read('probe-'+counterpart)
        if other:break
        if time.monotonic()>end:raise TimeoutError('independent workflow not observed')
        time.sleep(2)
    other=other[0];other_run=state.run(other['run_id'])
    if (other['source_sha']!=source or other['run_id']==rid
            or other_run['head_sha']!=source or other_run['run_attempt']!=1
            or other_run['head_branch']!=c.REVIEW or other_run['event']!='push'
            or other_run['path']!='.github/workflows/research-entry-probe-'+counterpart+'.yml'
            or other_run['status']!='in_progress'):raise ValueError('matching independent live workflow required')
    ack='heartbeat' if role=='owner' else 'watcher'
    counterpart_ack='watcher' if role=='owner' else 'heartbeat'
    initial={'mode':'FREE_GITHUB_HANDSHAKE','at':time.time(),'run_id':rid,'other_run_id':other['run_id'],'source_sha':source}
    sha=state.write(ack,initial)
    sha=state.write(ack,dict(initial,at=time.time(),confirmed=True),sha)
    while True:
        observed=state.read(counterpart_ack)
        if observed and observed[0].get('confirmed'):break
        if time.monotonic()>end:raise TimeoutError('cross-workflow CAS handshake not observed')
        time.sleep(2)
    if observed[0]['other_run_id']!=rid:raise ValueError('handshake counterpart changed')
    return {'status':'PASS','kind':'LIVE_GITHUB_TWO_WORKFLOW_HANDSHAKE','source_sha':source,
        'run_id':rid,'counterpart_run_id':other['run_id'],'namespace':state.namespace,
        'create_only_and_mutable_cas':True,'provider_calls':0,'authorization_created':False}


def verify():
    source=os.environ['GITHUB_SHA'];state=State(os.environ['GITHUB_TOKEN'],'free-github-'+source)
    rows={};end=time.monotonic()+180
    for role in ('owner','watch'):
        while True:
            row=state.read('probe-'+role)
            run=state.run(row[0]['run_id']) if row else None
            if run and run['status']=='completed':break
            if time.monotonic()>end:raise TimeoutError('live probe completion missing')
            time.sleep(2)
        if (run['conclusion']!='success' or run['head_sha']!=source or run['run_attempt']!=1
                or run['head_branch']!=c.REVIEW or run['path']!='.github/workflows/research-entry-probe-'+role+'.yml'):
            raise ValueError('live probe source/outcome mismatch')
        rows[role]={'run_id':str(run['id']),'status':run['conclusion']}
    if rows['owner']['run_id']==rows['watch']['run_id']:raise ValueError('separate workflows required')
    return {'status':'PASS','source_sha':source,'runs':rows,'namespace':state.namespace,'provider_calls':0}


if __name__=='__main__':
    role=sys.argv[1];out=Path('evidence');out.mkdir(exist_ok=True)
    try:result=verify() if role=='verify' else probe(role)
    except Exception as error:result={'status':'FAIL','error_type':type(error).__name__}
    (out/('github-probe-'+role+'.json')).write_bytes(c.encoded(result));print(json.dumps(result))
    raise SystemExit(0 if result['status']=='PASS' else 1)
