"""The same one-create owner/watcher used by the paid entry and CPU replicas.

An immutable claim and independent armed acknowledgement precede POST. Both
controllers retain the exact cleanup identity even when durable state is lost.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
import re

from tools import research_entry_contract as c, runpod_control as control
from tools.cloud_bootstrap import observe
from tools.research_entry_state import StateError


def defaults():
    return dict(total_seconds=10800,setup_seconds=4020,cleanup_seconds=300,
        heartbeat_seconds=60,poll_seconds=10,unclaimed_seconds=600,unknown_create_seconds=90)


def progress(event, **fields):
    print(json.dumps({'research_entry':event,**fields},sort_keys=True),file=sys.__stdout__,flush=True)


def binding(claim):return c.digest(claim)


def check_claim(claim, source, namespace):
    fields={'namespace','source_sha','contract_sha256','authorization_id','owner_run_id',
        'watcher_run_id','requested_at','attempt','name','region','request_sha256','costs',*defaults()}
    if (not isinstance(claim,dict) or set(claim)!=fields
            or claim['source_sha']!=source or claim['namespace']!=namespace
            or claim['contract_sha256']!=c.digest(c.CONTRACT)
            or claim['name']!='backtrace-a100-'+claim['attempt']
            or not re.fullmatch('[0-9a-f]{32}',claim['attempt'])
            or not re.fullmatch('[0-9a-f]{64}',claim['request_sha256'])
            or claim['owner_run_id']==claim['watcher_run_id']):
        raise StateError('claim identity mismatch')
    for key in defaults():
        if not 0<c.number(claim[key])<=defaults()[key]:raise StateError('claim bounds invalid')
    if not (claim['setup_seconds']<claim['total_seconds'] and claim['cleanup_seconds']<claim['total_seconds']
            and c.number(claim['requested_at'])>0):raise StateError('claim deadline invalid')
    if namespace==c.PAID_NAMESPACE and any(claim[k]!=v for k,v in defaults().items()):
        raise StateError('paid lifetime contract changed')
    for value in claim['costs'].values():control.money(value)
    control.validate_region(claim['region'])
    return claim


def require_watcher(store, source, now, limits, *, expected=None):
    row=store.read('watcher')
    if not row:raise StateError('watcher missing')
    value=row[0]
    if (value['source_sha']!=source or value['namespace']!=store.namespace
            or not 0<=now-value['at']<=limits['heartbeat_seconds']
            or (expected and value['run_id']!=expected)):
        raise StateError('watcher lease stale or changed')
    c.require_run(store.run(value['run_id']),value['run_id'],source,c.WATCH,
                  path='.github/workflows/research-entry-watch.yml')
    return value['run_id']


def reconcile(api, claim, pod_id, *, wall=time.time, sleep=time.sleep, possible_create=True):
    """Two complete observations. Failed GET/list/delete never proves absence."""
    begun=wall();total_end=claim['requested_at']+claim['total_seconds']
    end=min(begun+claim['cleanup_seconds'],total_end) if pod_id or not possible_create else total_end
    monotonic_end=time.monotonic()+min(claim['total_seconds'],max(0,end-begun))
    count=0;history=[];identity=pod_id
    while wall()<end and time.monotonic()<monotonic_end:
        try:
            listed=api.list();matches=[p for p in listed if p.get('name')==claim['name']]
            if len(matches)>1:raise StateError('multiple exact-name resources')
            if matches:
                found=matches[0]['id'];control.RunpodAPI.valid_id(found)
                if identity and identity!=found:raise StateError('resource identity changed')
                if not identity:end=min(wall()+claim['cleanup_seconds'],total_end)
                identity=found
            pod=api.get(identity) if identity else None
            if pod:
                if pod.get('name')!=claim['name']:raise StateError('resource name changed')
                count=0
                # A failed stop is secondary; an exact-ID DELETE is still tried.
                with contextlib.suppress(control.ProviderError):api.stop(identity)
                api.delete(identity)
                history.append({'at':wall(),'state':'DELETE_SENT','id':identity})
            else:
                # A second complete list must agree with the ID read.
                listed=api.list()
                present=any(p.get('name')==claim['name'] or p['id']==identity for p in listed)
                # Unknown POST completion can become visible late. Continue
                # cleanup-only observation for the entire useful allocation
                # window; never call an early empty list successful deletion.
                eligible=(bool(identity) or not possible_create or wall()>=max(
                    claim['requested_at']+claim['unknown_create_seconds'],total_end-claim['cleanup_seconds']))
                count=count+1 if not present and eligible else 0
                history.append({'at':wall(),'state':'ABSENT' if count else 'UNCONFIRMED','id':identity})
                if count==2:
                    return {'status':'DELETED' if identity else 'NO_RESOURCE_OBSERVED',
                        'absence_reads':2,'pod_id':identity,'started_at':begun,'completed_at':wall(),
                        'claim_sha256':binding(claim),'history':history[-64:]}
        except Exception as error:
            count=0;history.append({'at':wall(),'state':'UNKNOWN','error_type':type(error).__name__})
        sleep(min(claim['poll_seconds'],max(0,end-wall())))
    return {'status':'UNRESOLVED','absence_reads':count,'pod_id':identity,
        'started_at':begun,'completed_at':wall(),'claim_sha256':binding(claim),'history':history[-64:]}


def watch(store, api, source, run_id, *, limits=None, wall=time.time, sleep=time.sleep):
    limits=limits or defaults();started=wall();claim=None;pod_id=None;lease_sha=None
    reason=None;possible_create=True
    while claim is None:
        c.require_run(store.run(run_id),run_id,source,c.WATCH,
                      path='.github/workflows/research-entry-watch.yml')
        lease_sha=store.write('watcher',{'namespace':store.namespace,'source_sha':source,
            'run_id':str(run_id),'at':wall()},lease_sha)
        row=store.read('claim')
        if row:
            claim=check_claim(row[0],source,store.namespace)
            if claim['watcher_run_id']!=str(run_id):raise StateError('different watcher owns claim')
            c.require_run(store.run(claim['owner_run_id']),claim['owner_run_id'],source,c.OWNER,
                          path='.github/workflows/research-entry-start.yml')
            # From this point any state failure cleans up from the cached claim.
            try:store.write('armed',{'claim_sha256':binding(claim),'run_id':str(run_id),'at':wall()})
            except Exception:reason='ARMED_WRITE_FAILED'
        elif wall()-started>=limits['unclaimed_seconds']:
            return {'status':'NO_CLAIM','provider_create_requests':0}
        else:sleep(limits['poll_seconds'])
    last=wall();monotonic_end=time.monotonic()+max(0,claim['requested_at']+claim['total_seconds']-wall())
    while reason is None:
        try:
            lease_sha=store.write('watcher',{'namespace':store.namespace,'source_sha':source,
                'run_id':str(run_id),'at':wall()},lease_sha)
            current=store.read('claim')
            if not current or binding(current[0])!=binding(claim):raise StateError('claim changed')
            done=store.read('owner-done')
            if done:
                if done[0]['claim_sha256']!=binding(claim):raise StateError('completion binding changed')
                possible_create=done[0]['provider_create_requests']!=0
                reason='OWNER_DONE'
            owner=store.run(claim['owner_run_id'])
            c.require_run(owner,claim['owner_run_id'],source,c.OWNER,
                          path='.github/workflows/research-entry-start.yml')
            row=store.read('pod')
            if row:
                if row[0]['claim_sha256']!=binding(claim):raise StateError('pod binding changed')
                if pod_id and pod_id!=row[0]['pod_id']:raise StateError('pod changed')
                pod_id=row[0]['pod_id']
            beat=store.read('heartbeat');now=wall()
            if now<last:reason='CLOCK_REVERSED'
            elif time.monotonic()>=monotonic_end-claim['cleanup_seconds']:reason='MONOTONIC_DEADLINE'
            elif store.read('owner-done'):reason='OWNER_DONE'
            elif (not beat or beat[0]['claim_sha256']!=binding(claim)
                    or not 0<=now-beat[0]['at']<=claim['heartbeat_seconds']):reason='HEARTBEAT_LOST'
            elif beat[0]['phase'] not in ('setup','workload','export'):reason='INVALID_PHASE'
            else:reason=c.budget_reason(claim,beat[0]['phase'],now)
            if reason is None and pod_id:
                if not c.resource_matches(api.get(pod_id),claim):reason='PROVIDER_CHANGED'
            last=now
        except Exception:reason='OWNER_OR_STATE_UNAVAILABLE'
        if reason is None:sleep(claim['poll_seconds'])
    result=dict(reconcile(api,claim,pod_id,wall=wall,sleep=sleep,possible_create=possible_create),reason=reason,watcher_run_id=str(run_id))
    with contextlib.suppress(Exception):store.write('watcher-cleanup',result)
    return result


def stop(process):
    if process and process.poll() is None:
        with contextlib.suppress(ProcessLookupError):os.killpg(process.pid,signal.SIGTERM)
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):os.killpg(process.pid,signal.SIGKILL)
            process.wait(timeout=5)


def spawn(directory, configuration, claim, endpoint):
    plan=dict(configuration,claim=claim,endpoint=endpoint)
    path=Path(directory)/'worker-plan.json';path.write_bytes(c.encoded(plan));path.chmod(0o600)
    log=(Path(directory)/'worker-process.log').open('xb')
    try:
        return subprocess.Popen([sys.executable,'-I','-B',str(c.ROOT/'tools/research_entry_worker.py'),str(path)],
            stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,
            env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':str(directory),'LANG':'C.UTF-8'})
    finally:log.close()


def execute(store, api, authorization, offer, initializer, configuration, directory, source, run_id,
            *, replica=False, limits=None, wall=time.time, sleep=time.sleep, spawn_worker=spawn):
    limits=limits or defaults();directory=Path(directory);claim=None;process=None;pod_id=None;beat_sha=None
    result={'status':'INCOMPLETE','provider_create_requests':0,'worker_exit':None,'cleanup':None}
    stage='authorization'
    try:
        c.permit(authorization,source,wall(),replica=replica)
        if not replica and limits!=defaults():raise ValueError('production bounds fixed')
        if not replica and configuration.get('authored_cpu') is not False:raise ValueError('paid entry cannot use authored results')
        c.qualification(store,authorization)
        if store.read('claim'):raise StateError('single-use scope already consumed')
        c.require_run(store.run(run_id),run_id,source,c.OWNER,path='.github/workflows/research-entry-start.yml')
        watcher=require_watcher(store,source,wall(),limits)
        if watcher==str(run_id):raise ValueError('separate workflow required')
        if any(p.get('name','').startswith('backtrace-') for p in api.list()):raise StateError('prior resource requires reconciliation')
        price=c.costs(offer,authorization,wall())
        attempt=uuid.uuid4().hex
        request=control.make_request(attempt,wall(),initializer,region=offer['region'],transport_profile='actions-20261019')
        request['ports']=['22/tcp','8443/tcp']
        control.encode_create_request(request)
        claim={'namespace':store.namespace,'source_sha':source,'contract_sha256':c.digest(c.CONTRACT),
            'authorization_id':authorization['id'],'owner_run_id':str(run_id),'watcher_run_id':watcher,
            'requested_at':wall(),'attempt':attempt,'name':request['name'],'region':offer['region'],
            'request_sha256':c.digest(request),'costs':price,**limits}
        stage='claim';store.write('claim',claim)
        progress('claimed',mode='CPU_REPLICA' if replica else 'PAID',source_sha=source)
        beat_sha=store.write('heartbeat',{'claim_sha256':binding(claim),'at':wall(),'phase':'setup'})
        stage='independent_arm';end=wall()+min(30,limits['heartbeat_seconds'])
        while True:
            armed=store.read('armed')
            if armed and armed[0]['claim_sha256']==binding(claim) and armed[0]['run_id']==watcher:break
            if wall()>=end:raise StateError('watcher did not cache claim before create')
            sleep(limits['poll_seconds'])
        require_watcher(store,source,wall(),limits,expected=watcher)
        c.require_run(store.run(run_id),run_id,source,c.OWNER,path='.github/workflows/research-entry-start.yml')
        c.permit(authorization,source,wall(),replica=replica);c.costs(offer,authorization,wall())
        if wall()-claim['requested_at']>=30:raise StateError('claim/create deadline')
        stage='create';result['provider_create_requests']=1
        progress('single_create',mode='CPU_REPLICA' if replica else 'PAID')
        created=api.create(request)  # The only POST /pods; never retry.
        control.RunpodAPI.valid_id(created.get('id'))
        if created.get('name')!=claim['name']:raise StateError('create identity mismatch')
        pod_id=created['id'];store.write('pod',{'claim_sha256':binding(claim),'pod_id':pod_id})
        stage='bootstrap';first_worker=None;endpoint_identity=None
        monotonic_start=time.monotonic();last_wall=wall();last_detail=None
        while True:
            require_watcher(store,source,wall(),limits,expected=watcher)
            c.require_run(store.run(run_id),run_id,source,c.OWNER,path='.github/workflows/research-entry-start.yml')
            phase='setup'
            if process:
                if process.poll() is not None:break
                status=directory/'worker-status.json'
                if status.is_file():
                    state=json.loads(status.read_bytes())
                    if state['claim_sha256']!=binding(claim) or not 0<=wall()-state['at']<=limits['heartbeat_seconds']:
                        raise StateError('worker heartbeat stale')
                    phase=state['phase']
                    if phase not in ('setup','workload','export'):raise StateError('worker phase invalid')
                    detail=state.get('detail',phase)
                    if not isinstance(detail,str) or not re.fullmatch('[A-Za-z0-9_.-]{1,100}',detail):
                        raise StateError('worker detail invalid')
                    if detail!=last_detail:
                        progress(detail,phase=phase,elapsed_seconds=int(wall()-claim['requested_at']));last_detail=detail
                elif wall()-first_worker>=limits['heartbeat_seconds']:raise StateError('worker heartbeat missing')
            reason=c.budget_reason(claim,phase,wall())
            if wall()<last_wall:reason='CLOCK_REVERSED'
            last_wall=wall()
            if time.monotonic()-monotonic_start>=limits['total_seconds']-limits['cleanup_seconds']:
                reason='MONOTONIC_DEADLINE'
            if reason:raise StateError(reason)
            pod=api.get(pod_id)
            if not c.resource_matches(pod,claim):
                raise StateError('assigned resource changed')
            if endpoint_identity and c.digest(c.endpoints(pod))!=endpoint_identity:
                raise StateError('provider endpoint changed during execution')
            if process is None:
                if wall()-claim['requested_at']>=min(1200,limits['setup_seconds']):raise TimeoutError('bootstrap deadline')
                observation=observe(pod,wall()-claim['requested_at'])
                result['bootstrap']=observation
                if observation['readiness']=='READY':
                    try:endpoint=c.endpoints(pod)
                    except (ValueError,KeyError,TypeError):endpoint=None
                    if endpoint:
                        stage='worker';first_worker=wall()
                        endpoint_identity=c.digest(endpoint)
                        process=spawn_worker(directory,configuration,claim,endpoint)
            beat_sha=store.write('heartbeat',{'claim_sha256':binding(claim),'at':wall(),'phase':phase},beat_sha)
            sleep(limits['poll_seconds'])
        result['worker_exit']=process.returncode
        receipt=json.loads((directory/'worker-result.json').read_bytes())
        result['worker']=receipt
        export=receipt.get('export')
        if export:
            cipher=Path(configuration['output'])/'results.age'
            if not cipher.is_file() or c.digest(cipher.read_bytes())!=export['ciphertext_sha256']:raise ValueError('encrypted export bytes mismatch')
            store.write('export',{'claim_sha256':binding(claim),**export})
        if process.returncode!=0 or receipt.get('status')!='PASS' or not export:
            raise RuntimeError('worker incomplete; no retry')
        result['status']='WORK_COMPLETE'
    except Exception as error:
        result['failure']={'stage':stage,'type':type(error).__name__}
        progress('owner_failure',**result['failure'])
    finally:
        stop(process)
        if claim:
            with contextlib.suppress(Exception):store.write('owner-done',{'claim_sha256':binding(claim),'at':wall(),
                'provider_create_requests':result['provider_create_requests']})
            result['cleanup']=reconcile(api,claim,pod_id,wall=wall,sleep=sleep,
                possible_create=result['provider_create_requests']!=0)
            progress('owner_cleanup',status=result['cleanup']['status'])
            with contextlib.suppress(Exception):store.write('owner-cleanup',result['cleanup'])
            if result['status']=='WORK_COMPLETE' and result['cleanup']['status']=='DELETED':result['status']='PASS'
            else:result['status']='INCOMPLETE'
            result['claim']=claim
        (directory/'owner-result.json').write_bytes(c.encoded(result))
    return result
