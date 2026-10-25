"""Loopback HTTP replicas for the unchanged GitHub/Runpod wire adapters.

Only the optional Docker backend creates a resource: an owned free CPU container.
There is no provider key, external URL override, real GPU or model here.
"""
import base64
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import research_entry_contract as c, research_entry as entry
from tools.research_entry_state import State
from tools.runpod_control import RunpodAPI, NoRedirect
from tools.research_lifecycle import DockerResource, LABEL


def opener(port):
    actual=urllib.request.build_opener(NoRedirect()).open
    def call(request,timeout):
        u=urllib.parse.urlsplit(request.full_url)
        if u.scheme!='https' or u.netloc not in ('api.github.com','api.runpod.io'):
            raise ValueError('only known production wire targets may be replayed')
        token=request.get_header('Authorization')
        if token not in ('Bearer replica-github','Bearer replica-runpod'):
            raise ValueError('real credential forbidden in replica')
        rewritten=urllib.request.Request('http://127.0.0.1:'+str(port)+u.path+('?' + u.query if u.query else ''),
            data=request.data,headers=dict(request.headers),method=request.method)
        return actual(rewritten,timeout=min(timeout,3))
    return call


def clients(port,namespace):
    return State('replica-github',namespace,opener=opener(port)),RunpodAPI('replica-runpod',opener=opener(port))


def authorization(source):
    now=time.time()
    return {'id':'cpu-replica-'+str(time.time_ns()),'source_sha':source,'contract_sha256':c.digest(c.CONTRACT),
        'qualification_run_id':'99','approved_at':now-1,'expires_at':now+3600,
        'additional_cap':'6','cumulative_cap':'12','account_funded_total':'10','prior_spend_floor':'3',
        'single_use':True,'mode':'CPU_REPLICA'}


def offer():
    from tools import runpod_control as control
    return {'observed_at':control.utc(time.time()),'region':'EU-RO-1','gpu':control.GPU,
        'gpu_count':1,'cloud':'SECURE','image':control.BASE,'container_disk_gb':100,
        'volume_gb':0,'network_volume':None,'interruptible':False,'stock_available':True,
        'auto_pay':False,'authenticated':True,'vcpus':16,'ram_gb':128,
        'compute_per_hour':'.8','storage_per_hour':'.014','tax_rate':'0','other_total':'0','credit_balance':'7'}


def limits():
    return dict(total_seconds=10,setup_seconds=6,cleanup_seconds=3,heartbeat_seconds=1.5,
        poll_seconds=.03,unclaimed_seconds=5,unknown_create_seconds=.2)


class Replica:
    def __init__(self, source, *, faults=(), docker=False, run_id='1'):
        self.source=source;self.faults=set(faults);self.docker=docker;self.run_id=str(run_id)
        self.files={};self.pods={};self.lock=threading.RLock();self.state_lock=threading.RLock()
        self.requests=[];self.used=set()
        self.create_count=0;self.delete_count=0;self.resource=None;self.created_at=None
        self.owner_status='in_progress';self.watcher_status='in_progress'
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_GET(self):self.handle_request()
            def do_PUT(self):self.handle_request()
            def do_POST(self):self.handle_request()
            def do_DELETE(self):self.handle_request()
            def handle_request(self):
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if length>102400:raise ValueError('body too large')
                    body=json.loads(self.rfile.read(length)) if length else None
                    # The actual GitHub and provider services are independent;
                    # a slow Docker DELETE must not block GitHub heartbeats.
                    lock=owner.state_lock if self.path.startswith('/repos/') else owner.lock
                    with lock:code,result=owner.route(self.command,self.path,body)
                    if code==0:
                        self.close_connection=True;return
                    data=c.encoded(result)
                    self.send_response(code);self.send_header('Content-Type','application/json')
                    self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
                except (BrokenPipeError,ConnectionResetError):pass
                except Exception:
                    self.send_response(500);self.end_headers()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.port=self.server.server_port
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def once(self,name):
        if name in self.faults and name not in self.used:self.used.add(name);return True
        return False

    def route(self,method,path,body):
        self.requests.append({'at':time.time(),'method':method,'path':path.split('?')[0]})
        if path.startswith('/repos/'):
            if 'state_unavailable' in self.faults and self.create_count:return 503,{}
            if '/actions/runs/' in path:
                rid=path.rsplit('/',1)[1]
                branch=c.OWNER if rid=='11' else c.WATCH
                status=self.owner_status if rid=='11' else self.watcher_status
                data={'id':int(rid),'head_sha':self.source,'head_branch':branch,'run_attempt':1,
                    'status':status,'event':'push','path':'.github/workflows/research-entry-'+('start' if rid=='11' else 'watch')+'.yml'}
                if rid=='99':data.update(head_branch=c.REVIEW,status='completed',conclusion='success',path='.github/workflows/research-entry-cpu.yml')
                return 200,data
            key=path.split('/contents/',1)[1].split('?')[0]
            if method=='GET':
                if key not in self.files:return 404,{}
                raw,sha=self.files[key]
                if key.endswith('/heartbeat.json') and self.once('stale_heartbeat'):
                    v=json.loads(raw);v['at']-=100;raw=c.encoded(v);sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
                return 200,{'type':'file','encoding':'base64','content':base64.b64encode(raw).decode(),'sha':sha}
            if method=='PUT':
                previous=self.files.get(key)
                if body.get('branch')!=c.STATE:return 422,{}
                if (previous[1] if previous else None)!=body.get('sha'):return 409,{}
                if self.once('state_conflict'):return 409,{}
                raw=base64.b64decode(body['content']);sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
                self.files[key]=(raw,sha)
                if key.endswith('/claim.json') and self.once('claim_ack_lost'):return 0,{}
                if key.endswith('/heartbeat.json') and self.once('heartbeat_ack_lost'):return 0,{}
                return 201,{'content':{'sha':sha}}
        if path.startswith('/v2/pods'):
            if method=='POST' and path=='/v2/pods':
                self.create_count+=1;self.created_at=time.time()
                if self.create_count!=1:return 500,{}
                identity='replica-pod-1'
                pod={'id':identity,'name':body['name'],'image':body['image'],'cloud':body['cloud'],
                    'disk':body['disk'],'mounts':body['mounts'],'ports':body['ports'],
                    'gpu':dict(body['gpu'],vcpuCount=16,memory=128),'status':'RUNNING','locked':False,
                    'dataCenterId':body['dataCenterIds'][0],'cost':'.814','cluster':None,
                    'ssh':{'direct':{'username':'root','host':'127.0.0.1','port':22222}},
                    'runtime':{'ports':[{'private':22,'public':22222,'type':'tcp','ip':'127.0.0.1'},
                                        {'private':8443,'public':22223,'type':'tcp','ip':'127.0.0.1'}]}}
                if self.docker:
                    name='backtrace-free-full-setup-'+self.run_id+'-entry-'+body['name'][-12:]
                    label='entry-'+body['name'][-32:]
                    self.resource=DockerResource({'container_name':name,'namespace':label})
                    argv=['docker','run','-d','--name',name,'--label',LABEL+'='+label,
                        '-p','127.0.0.1::22','-p','127.0.0.1::8443','--security-opt','no-new-privileges']
                    for key,value in body['env'].items():argv+=['-e',key+'='+value]
                    argv+=['--entrypoint',body['entrypoint'][0],body['image'],*body['entrypoint'][1:],*body['cmd']]
                    result=subprocess.run(argv,capture_output=True,check=True,timeout=20)
                    details=json.loads(subprocess.check_output(['docker','inspect',name],timeout=5))[0]
                    if details['Mounts'] or details['HostConfig']['NetworkMode']!='bridge':raise ValueError('replica boundary')
                    for row in pod['runtime']['ports']:
                        row['public']=int(details['NetworkSettings']['Ports'][str(row['private'])+'/tcp'][0]['HostPort'])
                    pod['ssh']['direct']['port']=pod['runtime']['ports'][0]['public']
                self.pods[identity]=pod
                if self.once('create_ack_lost'):return 0,{}
                if self.once('create_500'):return 500,{}
                return 201,pod
            if method=='GET' and path.startswith('/v2/pods?'):
                if self.once('list_error'):return 503,{}
                pods=list(self.pods.values())
                if 'delayed_create_visibility' in self.faults and self.created_at and time.time()-self.created_at<.3:pods=[]
                return 200,{'pods':pods,'pagination':{'hasNextPage':False}}
            identity=path.split('/')[3]
            if method=='GET':
                if self.once('get_error'):return 503,{}
                pod=self.pods.get(identity)
                return (200,pod) if pod else (404,{})
            if method=='DELETE':
                self.delete_count+=1
                if self.once('delete_false_ack'):return 204,{}
                if self.resource:
                    current=self.resource.observe()
                    if current:self.resource.delete(current)
                    if self.resource.observe() is not None:return 503,{}
                self.pods.pop(identity,None)
                if self.once('delete_ack_lost'):return 0,{}
                return 204,{}
            if method=='POST' and path.endswith('/action'):return 200,{}
        return 400,{}

    def close(self):
        if self.resource:
            from tools.research_lifecycle import cleanup
            if cleanup(self.resource)['status']!='PASS':raise RuntimeError('CPU replica container remains')
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

    def __enter__(self):return self
    def __exit__(self,*_):self.close()


def watch_process(port,namespace,source,limits_value,path):
    store,api=clients(port,namespace)
    try:result=entry.watch(store,api,source,'22',limits=limits_value)
    except Exception as error:result={'status':'FAIL','error_type':type(error).__name__}
    Path(path).write_bytes(c.encoded(result))


if __name__=='__main__':
    config=json.loads(Path(sys.argv[1]).read_bytes())
    watch_process(config['port'],config['namespace'],config['source'],config['limits'],config['output'])
