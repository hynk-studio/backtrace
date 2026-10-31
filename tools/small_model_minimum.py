"""One source-bound hardware-only allocation with independent cached-identity cleanup."""
import base64
import contextlib
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

from tools import small_model_container as container, small_model_provider as provider
from tools import small_model_lifecycle as life, runpod_control as control
from tools import research_entry as prior, research_entry_contract as prior_contract
from tools.cloud_bootstrap import observe
from tools.research_entry_state import State as Wire, StateError

ROOT=Path(__file__).resolve().parents[1]
REVIEW='bt-001-small-model-minimum-20261027'
START='bt-001-small-model-minimum-start-20261027'
STATE_BRANCH='bt-001-small-model-minimum-state-20261027'
REMOTE_MODULE='tools.small_model_minimum_remote'
SUCCESS_STATUS='PASS_ACTUAL_HARDWARE_ONLY'
NAMES={'authorization','owner','watch','claim','armed','heartbeat','watch-heartbeat','pod','done','owner-cleanup','watch-cleanup','replica-resource','replica-deleted'}
MUTABLE={'heartbeat','watch-heartbeat'}
CONTRACT={'scope':'HARDWARE_ONLY_OCI_V1','total_seconds':3000,'work_seconds':2580,
    'cleanup_seconds':300,'export_seconds':120,'maximum_additional_usd':'1.00',
    'compute_cap_usd':'0.90','storage_hourly_projection_usd':'0.015','credit_reserve_usd':'0.50',
    'allocations':1,'automatic_retry':False,'weight_bytes':0,'pretrained_requests':0,'training_steps':0,
    'image':control.BASE,'disk_gb':100,'min_gpu_reported_bytes':24*1024**3,'min_provider_ram_gb':32,
    'resident_ram_probe_bytes':8*1024**3,'full_model_memory_admission':'NOT_ESTABLISHED'}


def sources():
    extra=[p for folder,pattern in [('tools','small_model_minimum*.py'),('tests','test_small_model_minimum*.py'),('.github/workflows','small-model-minimum*.yml')] for p in (ROOT/folder).glob(pattern)]
    extra.extend(ROOT/p for p in ('tools/cloud_bootstrap.py','tools/research_entry.py','docs/research-reduced9-amendment-20261026.json','tools/small_model_minimum_trace.c'))
    return dict(container.sources(),**{str(p.relative_to(ROOT)):life.digest(p.read_bytes()) for p in extra})


def prepare_runtime(prepared):
    from tools.small_model_minimum_remote import prepare
    return prepare(prepared,ROOT/'.local/cuda-wheels',ROOT/'.local/transport-build')


class State(Wire):
    def __init__(self,token,source,actual,**kw):
        if not re.fullmatch('[0-9a-f]{40}',source):raise ValueError('immutable source required')
        super().__init__(token,'minimum-paid-20261027' if actual else 'minimum-free-'+source,**kw)
        self.source=source;self.actual=actual

    def path(self,name):
        if name not in NAMES:raise ValueError('minimum state path denied')
        return '/contents/minimum/'+self.namespace+'/'+name+'.json'

    def initialize(self):
        if self.request('GET','/git/ref/heads/'+STATE_BRANCH,missing=True) is None:
            try:self.request('POST','/git/refs',{'ref':'refs/heads/'+STATE_BRANCH,'sha':self.source})
            except StateError:
                if self.request('GET','/git/ref/heads/'+STATE_BRANCH,missing=True) is None:raise

    def read(self,name):
        r=self.request('GET',self.path(name)+'?ref='+STATE_BRANCH,missing=True)
        if r is None:return None
        raw=base64.b64decode(r['content']);sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        value=json.loads(raw)
        if r['type']!='file' or r['encoding']!='base64' or len(raw)>65536 or r['sha']!=sha or value.get('source_sha')!=self.source:
            raise StateError('minimum source or state integrity mismatch')
        return value,sha

    def write(self,name,value,previous=None):
        if name=='authorization':raise ValueError('authorization is written only by the owner-directed review action')
        if previous and name not in MUTABLE:raise ValueError('minimum records are immutable')
        value=dict(value,source_sha=self.source);raw=life.encoded(value)
        if len(raw)>65536:raise ValueError('bounded state required')
        body={'branch':STATE_BRANCH,'message':'Record hardware minimum '+name,'content':base64.b64encode(raw).decode()}
        if previous:body['sha']=previous
        for attempt in range(4):
            try:self.request('PUT',self.path(name),body);break
            except StateError as e:
                check=self.read(name)
                if check and life.encoded(check[0])==raw:return check[1]
                if str(e)=='state HTTP 409' and (check[1] if check else None)==previous and attempt<3:
                    time.sleep(.2*(attempt+1));continue
                raise
        # Contents reads can briefly lag a successful immutable write. Confirm
        # by bounded reads; never repeat an ambiguous non-idempotent write.
        for attempt in range(4):
            check=self.read(name)
            if check and life.encoded(check[0])==raw:return check[1]
            if attempt<3:time.sleep(.2*(attempt+1))
        raise StateError('minimum write not confirmed')


def validate_permit(value,source,now):
    if (not isinstance(value,dict) or value.get('source_sha')!=source or value.get('contract_sha256')!=life.digest(CONTRACT)
            or value.get('mode')!='OWNER_APPROVED_HARDWARE_MINIMUM' or value.get('single_use') is not True
            or value.get('additional_cap_usd')!='1.00' or value.get('allocation_inclusive_seconds')!=3000
            or value.get('instruction')!='최소검증 진행하자' or not re.fullmatch('[1-9][0-9]+',str(value.get('qualification_run_id','')))
            or not 0<=now-value['approved_at']<86400 or not now<value['expires_at']<=value['approved_at']+86400):
        raise ValueError('current single-use source-bound hardware authorization required')
    return value


def require_run(state,run_id):
    r=state.run(run_id)
    if (r['head_sha']!=state.source or r['head_branch']!=(START if state.actual else REVIEW) or r['run_attempt']!=1
            or r['status']!='in_progress' or r['event']!='push'
            or r['path']!='.github/workflows/small-model-minimum-'+('live' if state.actual else 'cpu')+'.yml'):
        raise ValueError('first exact source workflow required')


def require_qualification(state,permit):
    r=state.run(permit['qualification_run_id'])
    if (r['head_sha']!=state.source or r['head_branch']!=REVIEW or r['run_attempt']!=1 or r['event']!='push'
            or r['status']!='completed' or r['conclusion']!='success'
            or r['path']!='.github/workflows/small-model-minimum-cpu.yml'):
        raise ValueError('exact-source complete free qualification required')


def choose(snapshot,now):
    if snapshot['status']!='PASS_READ_ONLY' or not snapshot['account_idle'] or snapshot['inventory']['pod_count']:
        raise ValueError('idle unchanged account required')
    balance=provider.money(snapshot['account']['credit_balance_usd'])
    choices=[]
    for r in snapshot['offers']:
        if not r['stock_eligible'] or r.get('pricing_status')!='OBSERVED' or r['reported_gpu_gb']<40:continue
        # Nominal 24 GB products can report less than the fixed 24 GiB floor.
        compute=provider.money(r['compute_usd_per_hour']);hourly=compute+Decimal('.015')
        maximum=hourly*Decimal(3000)/3600
        if (not 0<=now-control.timestamp(r['observed_at'])<=300 or compute*Decimal(3000)/3600>Decimal('.90')
                or maximum>1 or balance-maximum<Decimal('.50')):continue
        choices.append((hourly,r))
    if not choices:raise ValueError('no fresh affordable >=40GB product meets the reported-24GiB hardware floor')
    hourly,row=min(choices,key=lambda p:(p[0],p[1]['gpu'],p[1]['region']))
    return dict(row,costs={'compute_per_hour':str(provider.money(row['compute_usd_per_hour'])),
        'storage_per_hour':'.015','hourly_all_in_projection':str(hourly),'maximum_projection':str(hourly*Decimal(3000)/3600),
        'initial_balance':str(balance),'additional_cap':'1.00','credit_reserve':'.50'})


def request_for(offer,initializer,attempt):
    from tools.ssh_bootstrap import validate_initializer
    validate_initializer(initializer,profile='actions-20261019')
    if not re.fullmatch('[0-9a-f]{32}',attempt):raise ValueError('fresh attempt identity required')
    request={'cloud':'SECURE','gpu':{'id':offer['gpu'],'count':1,'minRamPerGpu':32,'minVcpuCountPerGpu':8,'minCudaVersion':'12.8'},
        'dataCenterIds':[control.validate_region(offer['region'])],'image':control.BASE,'disk':100,'mounts':{},
        'startSsh':False,'startJupyter':False,'ports':['22/tcp'],'globalNetworking':False,
        'name':'backtrace-small-minimum-'+attempt,**initializer}
    control.encode_create_request(request);return request


def resource_matches(pod,claim):
    if not isinstance(pod,dict):return False
    g=pod.get('gpu',{});pending=pod.get('status') in ('PROVISIONING','STARTING')
    fixed={'name':claim['name'],'image':control.BASE,'cloud':'SECURE','disk':100,'mounts':{},'ports':['22/tcp'],'locked':False}
    if any(pod.get(k)!=v for k,v in fixed.items()) or pod.get('cluster') or g.get('id')!=claim['gpu'] or g.get('count')!=1:return False
    if pod.get('status') not in ('PROVISIONING','STARTING','RUNNING') or pod.get('dataCenterId') not in ((claim['region'],None) if pending else (claim['region'],)):return False
    for key,minimum in [('memory',32),('vcpuCount',8)]:
        if pending and g.get(key) is None:continue
        if type(g.get(key)) not in (int,float) or g[key]<minimum:return False
    return provider.money(pod['cost'])<=provider.money(claim['costs']['compute_per_hour'])+Decimal('.015')


def endpoint(pod):
    """None means provisioning metadata is incomplete, never a trusted endpoint."""
    from tools.ssh_bootstrap import validate_endpoint
    ssh=pod.get('ssh');runtime=pod.get('runtime')
    for value in (ssh,runtime):
        if value is not None and not isinstance(value,dict):raise ValueError('invalid endpoint metadata')
    r=ssh.get('direct') if ssh else None
    if r is not None and not isinstance(r,dict):raise ValueError('invalid direct endpoint')
    if r is not None:
        if r.get('username') not in (None,'root'):raise ValueError('unexpected SSH user')
        host=r.get('host');port=r.get('port')
        if host is not None and not isinstance(host,str):raise ValueError('invalid SSH host')
        if port is not None and (type(port) is not int or not 1<=port<=65535):raise ValueError('invalid SSH port')
        if host is not None:validate_endpoint(host,port if port is not None else 22)
    ports=runtime.get('ports') if runtime else None
    if ports is not None and (not isinstance(ports,list) or any(not isinstance(p,dict) for p in ports)):
        raise ValueError('invalid runtime port metadata')
    rows=[p for p in (ports or []) if p.get('private')==22 and p.get('type')=='tcp']
    if len(rows)>1:raise ValueError('ambiguous runtime SSH mapping')
    if not r or any(r.get(k) is None for k in ('host','port','username')) or not rows:return None
    if any(rows[0].get(k) is None for k in ('ip','public')):return None
    if rows[0]['ip']!=r['host'] or type(rows[0]['public']) is not int or rows[0]['public']!=r['port']:
        raise ValueError('exact authenticated direct SSH mapping required')
    return {'host':r['host'],'port':r['port']}


def check_claim(claim,state,run_id):
    if (claim.get('source_sha')!=state.source or claim.get('contract_sha256')!=life.digest(CONTRACT)
            or claim.get('namespace')!=state.namespace or claim.get('run_id')!=str(run_id)
            or claim.get('actual') is not state.actual or claim.get('owner_boot')==claim.get('watch_boot')
            or not re.fullmatch('backtrace-small-minimum-[0-9a-f]{32}',claim.get('name',''))):
        raise StateError('exact source/role/resource claim required')
    if state.actual and any(claim.get(k)!=v for k,v in {'total_seconds':3000,'cleanup_seconds':300,'poll_seconds':90,'unknown_create_seconds':90}.items()):
        raise StateError('paid deadline contract changed')
    if (life.finite(claim['requested_at'])<=0 or
            any(not re.fullmatch('[0-9a-f]{64}',claim[k]) for k in ('owner_boot','watch_boot'))):
        raise StateError('claim clock and kernel identities required')
    return claim


def work_alarm(seconds):
    """Interrupt blocked owner work at the remaining allocation work deadline."""
    if not 0<life.finite(seconds)<=2580:raise TimeoutError('no hardware work allowance remains')
    if signal.getitimer(signal.ITIMER_REAL)!=(0.0,0.0):raise ValueError('unshared owner deadline timer required')
    def expired(signum,frame):raise TimeoutError('allocation-inclusive work deadline')
    previous=signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,seconds)
    def close():
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)
    return close


class ReplicaAPI:
    """Cross-runner free state replica. Never opens a Runpod connection."""
    def __init__(self,state):self.state=state
    def list(self):
        r=self.state.read('replica-resource');deleted=self.state.read('replica-deleted')
        return [r[0]['pod']] if r and not deleted else []
    def get(self,pod_id):return next((p for p in self.list() if p['id']==pod_id),None)
    def create(self,request):
        pod={'id':'free-'+uuid.uuid4().hex,'name':request['name']}
        self.state.write('replica-resource',{'pod':pod});return pod
    def stop(self,pod_id):return {}
    def delete(self,pod_id):
        r=self.state.read('replica-resource')
        if not r or r[0]['pod']['id']!=pod_id:raise ValueError('replica cannot delete an unrelated identity')
        if not self.state.read('replica-deleted'):self.state.write('replica-deleted',{'pod_id':pod_id,'at':time.time()})
        return {}


def identity(state,role,rid):
    row={'role':role,'run_id':str(rid),'source_sha':state.source,'at':time.time(),
        'boot_sha256':hashlib.sha256(Path('/proc/sys/kernel/random/boot_id').read_bytes()).hexdigest()}
    state.write(role,row);return row


def beat(state,name,claim,previous=None):
    return state.write(name,{'claim_sha256':life.digest(claim),'at':time.time()},previous)


def fresh(row,claim,now,stale):
    return bool(row and row[0]['claim_sha256']==life.digest(claim) and 0<=now-row[0]['at']<stale)


def watch(state,api,rid,me):
    claim=None;pod_id=None;sha=None;reason=None;end=time.monotonic()+(1500 if state.actual else 240)
    while not claim:
        r=state.read('claim')
        if r:
            claim=check_claim(r[0],state,rid)
            if claim['watch_boot']!=me['boot_sha256']:raise ValueError('claim bound another watcher')
        elif time.monotonic()>=end:return {'status':'NO_CLAIM','provider_create_requests':0}
        else:time.sleep(5)
    # Cache the exact name/claim before acknowledging the owner may create.
    try:state.write('armed',{'claim_sha256':life.digest(claim),'watch_boot':me['boot_sha256'],'at':time.time()})
    except Exception:reason='ARM_WRITE_FAILED'
    deadline=time.monotonic()+max(0,claim['requested_at']+claim['total_seconds']-time.time())
    last=time.time();possible=True
    while reason is None:
        try:
            sha=beat(state,'watch-heartbeat',claim,sha)
            r=state.read('pod')
            if r:
                if r[0]['claim_sha256']!=life.digest(claim):raise StateError('pod binding changed')
                pod_id=r[0]['pod_id']
            done=state.read('done')
            if done:
                if done[0]['claim_sha256']!=life.digest(claim):raise StateError('completion binding changed')
                possible=bool(done[0]['provider_create_requests']);reason='OWNER_DONE'
                break  # An owner's completed deletion is not a changed resource.
            now=time.time()
            if now<last:reason='CLOCK_REVERSED'
            elif time.monotonic()>=deadline-claim['cleanup_seconds']:reason='DEADLINE'
            elif not fresh(state.read('heartbeat'),claim,time.time(),240 if state.actual else 15):reason='OWNER_HEARTBEAT_LOST'
            if state.actual:
                require_run(state,rid)
                if pod_id and not resource_matches(api.get(pod_id),claim):reason='RESOURCE_CHANGED'
            last=now
        except Exception:reason='OWNER_OR_STATE_UNAVAILABLE'
        if reason is None:time.sleep(claim['poll_seconds'])
    result=prior.reconcile(api,claim,pod_id,possible_create=possible)
    result.update(reason=reason,watch_boot=me['boot_sha256'],actual=state.actual,provider_create_requests=0)
    with contextlib.suppress(Exception):state.write('watch-cleanup',result)
    return result


def owner(state,api,rid,me,prepared=None):
    result={'status':'INCOMPLETE','actual':state.actual,'provider_create_requests':0,'source_hashes':sources()}
    claim=None;pod_id=None;process=None;sha=None;possible=False;clear_alarm=None
    out=ROOT/'evidence/minimum-owner';out.mkdir(parents=True,exist_ok=True)
    try:
        if state.read('claim'):raise ValueError('single-use hardware scope already consumed')
        peer=None;end=time.monotonic()+180
        while not peer:
            r=state.read('watch')
            if r:peer=r[0];break
            if time.monotonic()>=end:raise TimeoutError('independent watcher unavailable')
            time.sleep(2)
        if peer['run_id']!=str(rid) or peer['role']!='watch' or peer['boot_sha256']==me['boot_sha256']:
            raise ValueError('different runner kernel required')
        require_run(state,rid)
        if state.actual:
            permit=validate_permit(state.read('authorization')[0],state.source,time.time());require_qualification(state,permit)
            snap=provider.inspect(api=provider.ReadOnlyAPI(api._key));result['account_before']=snap
            offer=choose(snap,time.time());result['selected_offer']=offer
            initializer=json.loads((prepared/'keys/initializer.json').read_bytes())
            request=request_for(offer,initializer,uuid.uuid4().hex)
            result['github_budget']=prior_contract.github_budget(state.last_rate,time.time())
        else:
            offer={'region':'EU-RO-1','gpu':'FREE_CPU_REPLICA','costs':{}}
            request={'name':'backtrace-small-minimum-'+uuid.uuid4().hex}
        claim={'source_sha':state.source,'namespace':state.namespace,'run_id':str(rid),'actual':state.actual,
            'owner_boot':me['boot_sha256'],'watch_boot':peer['boot_sha256'],'contract_sha256':life.digest(CONTRACT),
            'name':request['name'],'gpu':offer['gpu'],'region':offer['region'],'costs':offer['costs'],
            'request_sha256':life.digest(request),'requested_at':time.time(),
            'total_seconds':3000 if state.actual else 180,'cleanup_seconds':300 if state.actual else 45,
            'poll_seconds':90 if state.actual else 2,'unknown_create_seconds':90 if state.actual else 10}
        state.write('claim',claim);result['claim']=claim;sha=beat(state,'heartbeat',claim)
        end=time.monotonic()+30
        while True:
            r=state.read('armed');w=state.read('watch-heartbeat')
            if r and r[0]['claim_sha256']==life.digest(claim) and r[0]['watch_boot']==peer['boot_sha256'] and fresh(w,claim,time.time(),240 if state.actual else 15):break
            if time.monotonic()>=end:raise TimeoutError('independent watcher did not arm')
            time.sleep(1)
        if state.actual:
            validate_permit(permit,state.source,time.time());choose(snap,time.time())
            if time.time()-claim['requested_at']>=60 or api.list():raise ValueError('claim expired or account no longer idle')
            clear_alarm=work_alarm(2580-(time.time()-claim['requested_at']))
        possible=True;result['provider_create_requests']=1 if state.actual else 0
        result['create_attempted']=True
        created=api.create(request)  # Exactly one call. No retries on any response.
        pod_id=created.get('id');control.RunpodAPI.valid_id(pod_id)
        if created.get('name')!=claim['name']:raise StateError('create name mismatch')
        state.write('pod',{'claim_sha256':life.digest(claim),'pod_id':pod_id});result['pod_id']=pod_id
        if not state.actual:
            # A real independent runner must detect missing heartbeats and use
            # its cached exact identity to remove this free replica resource.
            end=time.monotonic()+90
            while True:
                observed=state.read('watch-cleanup')
                if observed:break
                if time.monotonic()>=end:raise TimeoutError('independent replica cleanup absent')
                time.sleep(2)
            proof=observed[0]
            if proof['reason']!='OWNER_HEARTBEAT_LOST' or proof['status']!='DELETED' or proof['pod_id']!=pod_id:raise AssertionError('wrong free cleanup outcome')
            result['independent_replica_cleanup']=proof;result['status']='PASS_FREE_REMOTE_CLEANUP';return result
        wall0=time.time();mono0=time.monotonic();last=wall0;endpoint_hash=None
        while True:
            now=time.time();elapsed=now-claim['requested_at']
            if now<last or elapsed>=2580 or time.monotonic()-mono0>=2580-(wall0-claim['requested_at']):raise TimeoutError('allocation-inclusive work stop')
            if not fresh(state.read('watch-heartbeat'),claim,time.time(),240):raise StateError('independent watcher heartbeat lost')
            require_run(state,rid);pod=api.get(pod_id)
            if not resource_matches(pod,claim):raise StateError('assigned hardware or price mismatch')
            observation=observe(pod,elapsed)
            result.setdefault('readiness_observations',[]).append(observation)
            if process is None and elapsed>=900:raise TimeoutError('provider startup exceeded 900 seconds')
            try:ep=endpoint(pod) if pod['status']=='RUNNING' else None
            except ValueError:
                observation['readiness']='INVALID_ENDPOINT_MAPPING';raise
            if ep is None:
                if observation['readiness']=='READY':observation['readiness']='WAIT_RUNTIME_MAPPING'
                if endpoint_hash:raise StateError('provider endpoint disappeared')
            else:
                observation['readiness']='READY';current=life.digest(ep)
                if endpoint_hash and endpoint_hash!=current:raise StateError('provider endpoint changed')
                if process is None:
                    endpoint_hash=current;path=out/'endpoint.json';path.write_bytes(life.encoded(ep));path.chmod(0o600)
                    log=(out/'worker.log').open('xb')
                    try:process=subprocess.Popen([sys.executable,'-m',REMOTE_MODULE,str(prepared),str(path),str(out/'remote')],
                        stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,
                        env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8','HOME':str(prepared)})
                    finally:log.close()
            if process is not None and process.poll() is not None:
                result['remote']=json.loads((out/'remote/connected-receipt.json').read_bytes())
                if process.returncode or result['remote']['status']!=SUCCESS_STATUS:raise RuntimeError('hardware diagnostic failed')
                result['status']=SUCCESS_STATUS;break
            sha=beat(state,'heartbeat',claim,sha);last=now
            time.sleep(30 if process is None else 90)
    except Exception as e:
        import traceback
        result.update(status='FAIL',error_type=type(e).__name__,error=str(e)[:700],
            frames=[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(e.__traceback__)][-8:])
    finally:
        if clear_alarm:clear_alarm()
        prior.stop(process)
        if claim:
            with contextlib.suppress(Exception):state.write('done',{'claim_sha256':life.digest(claim),'provider_create_requests':int(possible),'at':time.time()})
            result['cleanup']=prior.reconcile(api,claim,pod_id,possible_create=possible)
            with contextlib.suppress(Exception):state.write('owner-cleanup',result['cleanup'])
            if result['cleanup']['status'] not in ('DELETED','NO_RESOURCE_OBSERVED'):result['status']='CLEANUP_UNRESOLVED'
        life.write(out/'receipt.json',result)
    return result


def main(role,actual):
    os.umask(0o077);source=os.environ['GITHUB_SHA'];rid=os.environ['GITHUB_RUN_ID']
    if os.environ['GITHUB_RUN_ATTEMPT']!='1' or os.environ['GITHUB_REF_NAME']!=(START if actual else REVIEW):raise ValueError('first dedicated source run required')
    state=State(os.environ['GITHUB_TOKEN'],source,actual);state.initialize();require_run(state,rid)
    if actual:
        p=validate_permit(state.read('authorization')[0],source,time.time());require_qualification(state,p)
    prepared=None
    if role=='owner' and actual:
        prepared=(ROOT/'.local/minimum-prepared').resolve()
        prepare_runtime(prepared)
    me=identity(state,role,rid)
    api=control.RunpodAPI(os.environ['RUNPOD_API_KEY'].strip()) if actual else ReplicaAPI(state)
    return watch(state,api,rid,me) if role=='watch' else owner(state,api,rid,me,prepared)


if __name__=='__main__':
    role,mode=sys.argv[1:];out=ROOT/'evidence';out.mkdir(exist_ok=True)
    try:r=main(role,mode=='paid')
    except Exception as e:
        import traceback
        r={'status':'BLOCKED','error_type':type(e).__name__,'error':str(e)[:500],
            'frames':[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(e.__traceback__)][-8:]}
    life.write(out/('minimum-'+role+'.json'),r);print(json.dumps({'role':role,'status':r['status']}))
    raise SystemExit(0 if r['status'] in ('PASS_ACTUAL_HARDWARE_ONLY','PASS_FREE_REMOTE_CLEANUP','DELETED') else 1)
