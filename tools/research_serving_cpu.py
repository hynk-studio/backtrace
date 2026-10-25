"""Free exact-image SSH delivery, serving supervision, 18 isolated slots and cleanup.

Only the read-only input resolver sees the Kaggle credential. The server receives
no task/evaluator archives, account keys, client key, host mounts or model weights.
"""
import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import research_comparison as c,cloud_resolver as resolver,ssh_bootstrap as ssh
from tools.a100_delivery import manifest as frozen_manifest
from tools.cloud_transport import build
from tools.private_delivery import push,ssh_command
from tools.research_serving_delivery import bundle,FILES
from tools.research_split import credentials,Endpoint
from tools.research_split_sequence import sequence
from tools.research_split_cpu import reclaim_slot,wait_namespace_absence
from tools.research_lifecycle import Journal,DockerResource,cleanup,LABEL
from tools.research_isolation import bounded_child,Isolation
from tools.research_runtime import prepare as cpu_runtime
from tools.research_verifier_cpu import readable_tree

CLEAN={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','HOME':'/root',
       'OTEL_SDK_DISABLED':'true','LITELLM_LOCAL_MODEL_COST_MAP':'True','LITELLM_TELEMETRY':'False',
       'PYTHON_DOTENV_DISABLED':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
REMOTE='/root/backtrace/serving'
PYTHON='/root/backtrace/runtime/venv/bin/python'


def emit(stage,status):
    print(json.dumps({'serving_cpu':stage,'status':status}),file=sys.__stdout__,flush=True)


def start_watch(journal,log):
    process=subprocess.Popen([sys.executable,'-I','-B',str(c.ROOT/'tools/research_lifecycle.py'),str(journal.root)],
        env=CLEAN,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    end=time.monotonic()+10
    while not journal.read('watcher'):
        if process.poll() is not None or time.monotonic()>=end:raise RuntimeError('independent watcher did not start')
        time.sleep(.05)
    journal.require_watcher();return process


def fault_cases(parent,image,source,run_id):
    reports={}
    for mode in ('parent_death','network_loss','insufficient_time'):
        journal=Journal.create(parent,source,run_id,seconds=30,stale_seconds=5)
        resource=DockerResource(journal.claim());watcher=None;owner=None
        with (journal.root/'private.log').open('wb') as log:
            try:
                program=("import sys,time,http.client;from pathlib import Path;sys.path.insert(0,sys.argv[1]);"
                         "from tools.research_lifecycle import Journal;j=Journal(sys.argv[2]);\n"
                         "while True:\n"
                         " endpoint=j.read('endpoint')\n"
                         " if endpoint:\n"
                         "  conn=http.client.HTTPConnection('127.0.0.1',endpoint['port'],timeout=.5)\n"
                         "  try:conn.request('GET','/');assert conn.getresponse().status==200\n"
                         "  except (OSError,http.client.HTTPException) as error:\n"
                         "   j.write('owner-network-failure',{'error_type':type(error).__name__});sys.exit(2)\n"
                         "  finally:conn.close()\n"
                         " j.heartbeat('fixture-owner');time.sleep(.1)\n")
                owner=subprocess.Popen([sys.executable,'-I','-c',program,str(c.ROOT),str(journal.root)],
                    env=CLEAN,stdout=log,stderr=log,start_new_session=True)
                watcher=start_watch(journal,log);name=journal.claim()['container_name']
                if mode=='insufficient_time':
                    called=[]
                    result=sequence(lambda *a:called.append(a),deadline=time.monotonic()+999)
                    assert not called and len(result['slots'])==18 and all(r['status']=='NOT_RUN' for r in result['slots'])
                    journal.write('owner-done',{'reason':'insufficient_time'})
                    report={'status':'PASS','slots':result,'containers_created':0}
                else:
                    journal.require_watcher()
                    subprocess.run(['docker','run','-d','--name',name,'--label',LABEL+'='+journal.root.name,
                        '-p','127.0.0.1::8000','--entrypoint','/usr/bin/python3.12',image,
                        '-I','-m','http.server','8000'],stdout=log,stderr=log,check=True,timeout=20)
                    identity=resource.observe();assert identity
                    report={'containers_created':1,'identity':identity}
                    if mode=='network_loss':
                        details=json.loads(subprocess.check_output(['docker','inspect',identity],timeout=5))[0]
                        port=int(details['NetworkSettings']['Ports']['8000/tcp'][0]['HostPort'])
                        import http.client
                        end=time.monotonic()+5
                        while True:
                            conn=http.client.HTTPConnection('127.0.0.1',port,timeout=.5)
                            try:conn.request('GET','/');assert conn.getresponse().status==200;break
                            except OSError:
                                if time.monotonic()>end:raise
                                time.sleep(.1)
                            finally:conn.close()
                        journal.write('endpoint',{'port':port})
                        subprocess.run(['docker','network','disconnect','bridge',identity],stdout=log,stderr=log,
                                       check=True,timeout=5)
                        conn=http.client.HTTPConnection('127.0.0.1',port,timeout=.5)
                        try:
                            conn.request('GET','/');conn.getresponse();raise AssertionError('network remained available')
                        except OSError:report['network_loss_observed']=True
                        finally:conn.close()
                        owner.wait(timeout=5)
                        assert owner.returncode==2 and journal.read('owner-network-failure')
                        report['owner_observation']=journal.read('owner-network-failure')
                    else:
                        owner.kill();owner.wait(timeout=5)
                    report['owner_exit_code']=owner.returncode
                watcher.wait(timeout=20)
                result=journal.read('watcher-cleanup')
                assert watcher.returncode==0 and result['status']=='PASS' and result['absence_reads']==2
                assert result['reason']==('OWNER_DONE' if mode=='insufficient_time' else 'OWNER_LOST')
                assert resource.observe() is None
                report.update(status='PASS',watcher=result,namespace=journal.root.name,
                              claim_sha256=journal.binding(),independent_watcher=True)
                reports[mode]=report;emit(mode,'PASS')
            finally:
                if owner and owner.poll() is None:owner.kill();owner.wait(timeout=5)
                if not journal.read('owner-done'):journal.write('owner-done',{'reason':'fixture-finalizer'})
                final=cleanup(resource)
                if watcher and watcher.poll() is None:
                    try:watcher.wait(timeout=10)
                    except subprocess.TimeoutExpired:watcher.kill();watcher.wait(timeout=5)
                if final['status']!='PASS':raise RuntimeError('fault container cleanup unconfirmed')
    return reports


def qualify(inputs,output):
    if os.geteuid()!=0:raise ValueError('native root CPU coordinator required')
    source=os.environ['GITHUB_SHA'];run_id=os.environ['GITHUB_RUN_ID']
    report={'status':'FAIL','source_sha':source,'run_id':run_id,'kind':'FREE_SERVING_LIFECYCLE',
            'provider_operations':0,'real_model_runs':0,'model_files_transferred':0,'stages':{}}
    retained=inputs/'verifier-evidence';retained.mkdir(mode=0o700)
    image=c.load_protocol()['environment']['image'];watcher=None;serving=None;journal=None
    stop_heartbeat=threading.Event();heartbeat_thread=None;heartbeat_errors=[]
    with tempfile.TemporaryDirectory(prefix='backtrace-serving-',dir='/var/tmp') as temporary:
        root=Path(temporary);root.chmod(0o711)
        private=root/'private';private.mkdir(mode=0o700)
        work=root/'work';work.mkdir(mode=0o711)
        with (private/'controller.log').open('wb') as log:
            try:
                emit('source_resolution','STARTED')
                with resolver.kaggle_client() as client:sources=resolver.resolve_wheels(client)
                report['transport_build']=build(private/'transport')
                if not report['transport_build']['matches_prior_transport']:raise ValueError('SSH binary differs')
                pins=credentials(private/'tls')
                payload=private/'payload';manifest=bundle(payload,private/'tls',authored_cpu=True)
                manifest_path=private/'payload-manifest.json';manifest_path.write_bytes(manifest)
                report['payload']={'manifest_sha256':c.digest(manifest),'files':json.loads(manifest)['files'],
                                   'task_archives':0,'evaluator_inputs':0,'client_private_key':False}
                binaries=private/'transport/dropbear-DROPBEAR_2026.94'
                initializer=ssh.prepare(binaries/'dropbear',binaries/'dropbearkey',private/'ssh',profile='actions-20261019')
                env_file=private/'image.env';env_file.write_text('\n'.join(k+'='+v for k,v in initializer['env'].items())+'\n');env_file.chmod(0o600)
                subprocess.run(['docker','pull',image],stdout=log,stderr=log,check=True,timeout=900)
                details=json.loads(subprocess.check_output(['docker','image','inspect',image],timeout=10))[0]
                assert details['Architecture']=='amd64' and details['Os']=='linux'
                assert any(d.endswith('@'+image.split('@')[1]) for d in details['RepoDigests'])
                report['image']={'reference':image,'image_id':details['Id']}
                journal=Journal.create(private,source,run_id)
                phase=['bootstrap']
                def beat():
                    while not stop_heartbeat.wait(.5):
                        try:journal.heartbeat(phase[0])
                        except Exception as error:heartbeat_errors.append(type(error).__name__);return
                heartbeat_thread=threading.Thread(target=beat,daemon=True);heartbeat_thread.start()
                watcher=start_watch(journal,log);resource=DockerResource(journal.claim())
                name=journal.claim()['container_name'];journal.require_watcher()
                begun=time.monotonic()
                subprocess.run(['docker','run','-d','--name',name,'--label',LABEL+'='+journal.root.name,
                    '--env-file',str(env_file),'-p','127.0.0.1::22','-p','127.0.0.1::8443',
                    '--security-opt','no-new-privileges','--entrypoint',initializer['entrypoint'][0],image,
                    *initializer['entrypoint'][1:],*initializer['cmd']],stdout=log,stderr=log,check=True,timeout=30)
                details=json.loads(subprocess.check_output(['docker','inspect',name],timeout=10))[0]
                assert not details['Mounts'] and details['HostConfig']['NetworkMode']=='bridge'
                port=int(details['NetworkSettings']['Ports']['22/tcp'][0]['HostPort'])
                tls_port=int(details['NetworkSettings']['Ports']['8443/tcp'][0]['HostPort'])
                # Wait for the bootstrap listener without issuing a TLS request.
                probe="from pathlib import Path;raise SystemExit(0 if any(x.split()[1].endswith(':0016') and x.split()[3]=='0A' for x in Path('/proc/net/tcp').read_text().splitlines()[1:]) else 1)"
                end=time.monotonic()+20
                while subprocess.run(['docker','exec',name,'/usr/bin/python3.12','-I','-c',probe],stdout=log,stderr=log,timeout=5).returncode:
                    if time.monotonic()>=end:raise TimeoutError('bootstrap listener')
                    time.sleep(.1)
                report['stages']['tls_ssh']=dict(ssh.deliver(private/'ssh','127.0.0.1',port,120,profile='actions-20261019'),status='PASS')
                known=ssh.known_hosts(private/'ssh','127.0.0.1',port)
                command=ssh_command('127.0.0.1',port,private/'ssh/owner-key',known,REMOTE,c.digest(manifest))
                prefix=command[:-1];ssh.wait_for_command(prefix,['true'],60,log=log)
                report['stages']['source_delivery']=dict(push(payload,manifest_path,command,120),status='PASS')
                def remote(argv,*,data=None,seconds=60,check=True):
                    if heartbeat_errors or watcher.poll() is not None:raise RuntimeError('watcher or heartbeat unavailable')
                    result=subprocess.run(prefix+[shlex.join(argv)],input=data,stdin=subprocess.DEVNULL if data is None else None,
                        capture_output=True,env=CLEAN,timeout=seconds)
                    log.write(result.stdout);log.write(result.stderr);log.flush()
                    if check:result.check_returncode()
                    return result
                def program(code,**kwargs):return remote(['python3','-I','-c',code],**kwargs)
                phase[0]='runtime_transfer';emit(phase[0],'STARTED')
                wheel_manifest=frozen_manifest('wheels')
                code=("import sys,json;sys.path.insert(0,"+repr(REMOTE)+");from tools.direct_delivery import pull;"
                    "v=json.load(sys.stdin);print(json.dumps(pull('/root/backtrace/wheels',v['manifest'].encode(),v['sources'],v['sha256'],1200)))")
                result=program(code,data=c.encoded({'manifest':wheel_manifest.decode(),'sources':sources,'sha256':c.digest(wheel_manifest)}),seconds=1250)
                report['stages']['wheels']=dict(json.loads(result.stdout),status='PASS')
                phase[0]='runtime_install';emit(phase[0],'STARTED')
                result=remote(['python3','-I',REMOTE+'/tools/research_serving_install.py','/root/backtrace/wheels',
                    REMOTE+'/docs/linux-wheel-manifest.json','/root/backtrace/runtime','1200'],seconds=1250)
                report['stages']['runtime']=json.loads(result.stdout.splitlines()[-1])
                report['setup_seconds']=time.monotonic()-begun
                code="import sys,json;sys.path.insert(0,"+repr(REMOTE)+");from tools.research_serving import official_command,official_environment;print(json.dumps({'command':official_command(8000),'environment':official_environment(8000)}))"
                prepared=json.loads(remote([PYTHON,'-I','-c',code]).stdout.splitlines()[-1]);command_value=prepared['command']
                assert '--no-enable-prefix-caching' in command_value and '--enable-prefix-caching' not in command_value
                assert prepared['environment']['PYTHONPATH']==REMOTE and 'LD_LIBRARY_PATH' in prepared['environment']
                report['stages']['official_command']={'status':'PASS',**prepared,'gpu_initialization':'NOT_RUN'}
                phase[0]='failed_readiness';emit(phase[0],'STARTED')
                base=[PYTHON,'-I','-B',REMOTE+'/tools/research_serving.py',REMOTE+'/transport']
                fixture=['--authored-cpu',REMOTE+'/tests/research_serving_fixture.py']
                failed=remote(base+['/root/backtrace/failed','--lifetime','15','--ready-seconds','2',*fixture,'--failed-readiness'],seconds=20,check=False)
                value=json.loads(program("from pathlib import Path;print(Path('/root/backtrace/failed/receipt.json').read_text())").stdout)
                assert failed.returncode==1 and not value['ready'] and value['error_type']=='TimeoutError' and value['process_cleanup']=='PASS'
                report['stages']['failed_readiness']={'status':'PASS','result':value}
                phase[0]='serving';emit(phase[0],'STARTED')
                serving=subprocess.Popen(prefix+[shlex.join(base+['/root/backtrace/run','--lifetime','1800',
                    '--ready-seconds','20',*fixture])],env=CLEAN,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
                end=time.monotonic()+30
                while True:
                    result=program("from pathlib import Path;p=Path('/root/backtrace/run/ready.json');print(p.read_text() if p.is_file() else '{}')")
                    ready=json.loads(result.stdout)
                    if ready:break
                    if serving.poll() is not None or time.monotonic()>end:raise RuntimeError('serving readiness failed')
                    time.sleep(.1)
                endpoint=Endpoint('127.0.0.1',tls_port,private/'tls',pins['server_sha256'])
                connection=endpoint.connection(2);connection.connect();connection.close()
                report['stages']['serving_ready']={'status':'PASS','result':ready,'network':'DOCKER_BRIDGE_PUBLISHED_PORT',
                    'mounts':0,'transport':endpoint.identity(),'provider_network':'NOT_RUN'}
                python,runtime=cpu_runtime(root/'cpu-runtime',inputs/'wheels');readable_tree(root/'cpu-runtime');report['cpu_runtime']=runtime
                settings={'host':'127.0.0.1','port':tls_port,'material':str(private/'tls'),'server_sha256':pins['server_sha256']}
                c._new_output(private/'endpoint.json',c.encoded(settings))
                phase[0]='eighteen_slots';rows=[]
                def execute(identifier,arm,seconds):
                    destination=work/(identifier+'-'+arm)
                    row=bounded_child([python,'-I','-B',Path(__file__).resolve(),'--worker',inputs,destination,
                        root/'cpu-runtime/wheels',private/'endpoint.json',identifier,arm],private/(identifier+'-'+arm+'.log'),CLEAN,timeout=seconds)
                    checkpoint=destination/'session-checkpoint.json'
                    if not checkpoint.is_file():raise RuntimeError('namespace checkpoint unavailable')
                    row['namespace_cleanup']=wait_namespace_absence(c.parse(checkpoint.read_bytes())['namespace_ids'])
                    if row['namespace_cleanup']['status']!='PASS':raise RuntimeError('unsafe namespace reuse')
                    row['parent_cleanup']=reclaim_slot(destination)
                    if (destination/'receipt.json').is_file():row['result']=c.parse((destination/'receipt.json').read_bytes())
                    row['status']='PASS' if row['exit_code']==0 and row.get('result',{}).get('status')=='PASS' else 'FAIL'
                    rows.append(row);emit(identifier+'-'+arm,row['status'])
                    if row['status']!='PASS':raise RuntimeError('authored runner fixture failed')
                    return row
                slots=sequence(execute,deadline=time.monotonic()+1800)
                report['stages']['slots']=dict(slots,status='PASS' if all(r['status']=='PASS' for r in slots['slots']) else 'FAIL')
                phase[0]='stop_export'
                # Signal the supervisor itself, not its child process group.
                result=program("import os,signal;from pathlib import Path;\nfor p in Path('/proc').glob('[0-9]*/cmdline'):\n try:\n  raw=p.read_bytes().split(b'\\0')\n  if "+repr((REMOTE+'/tools/research_serving.py').encode())+" in raw and b'/root/backtrace/run' in raw:os.kill(int(p.parent.name),signal.SIGTERM)\n except (FileNotFoundError,ProcessLookupError):pass\n")
                serving.wait(timeout=15)
                assert serving.returncode==0
                receipt=json.loads(program("from pathlib import Path;print(Path('/root/backtrace/run/receipt.json').read_text())").stdout)
                metered=[r for row in rows for r in row.get('result',{}).get('slot',{}).get('accounting',{}).get('requests',[])]
                checks={'all_closed':receipt['transport']['active']==0,'exact_request_order':
                    [r['sha256'] for r in receipt['transport']['attempts']]==[r['forwarded_sha256'] for r in metered],
                    'all_18_slots':len(rows)==18,'exact_108_requests':len(metered)==108,
                    'process_group_absent':receipt['process_cleanup']=='PASS'}
                report['stages']['server_stop']={'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'receipt':receipt}
                names=['run/receipt.json','run/ready.json','run/server.log','failed/receipt.json','failed/server.log',
                       'runtime/inventory.json','runtime/receipt.json']
                code=("import base64,json;from pathlib import Path;names="+repr(names)+
                      ";data={n:base64.b64encode((Path('/root/backtrace')/n).read_bytes()).decode() for n in names};"
                      "assert sum(len(v) for v in data.values())<32*1024**2;print(json.dumps(data))")
                downloaded=json.loads(program(code).stdout)
                for name,data in downloaded.items():
                    target=private/'remote'/name;target.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
                    c._new_output(target,base64.b64decode(data,validate=True))
                from tools.cloud_seal import seal
                files={str(p.relative_to(work)):p for p in work.rglob('*') if p.is_file() and not p.is_symlink() and 'sandboxes' not in p.parts}
                files.update({'remote/'+str(p.relative_to(private/'remote')):p for p in (private/'remote').rglob('*') if p.is_file()})
                report['stages']['encrypted_export']=dict(seal(files,Path(output).parent/'serving-results.age'),status='PASS')
                journal.write('export',report['stages']['encrypted_export'])
                journal.write('owner-done',{'reason':'export_complete'})
                report['stages']['owner_cleanup']=cleanup(resource)
                journal.write('owner-cleanup',report['stages']['owner_cleanup'])
                watcher.wait(timeout=40);report['stages']['watcher_cleanup']=journal.read('watcher-cleanup')
                assert watcher.returncode==0
                report['namespace']={'name':journal.root.name,'claim_sha256':journal.binding(),'mode':'FREE_CPU_REHEARSAL'}
                report['stages']['faults']={'status':'PASS','cases':fault_cases(private,image,source,run_id)}
                report['status']='PASS' if all(v['status']=='PASS' for v in report['stages'].values()) else 'FAIL'
            except BaseException as error:
                report.update(status='FAIL',error_type=type(error).__name__)
                (private/'failure.log').write_text(traceback.format_exc())
            finally:
                if journal:
                    with contextlib.suppress(Exception):
                        subprocess.run(['docker','logs','--tail','100',journal.claim()['container_name']],stdout=log,stderr=log,timeout=10)
                    if not journal.read('owner-done'):journal.write('owner-done',{'reason':'finalizer'})
                    final=cleanup(DockerResource(journal.claim()))
                    report['final_cleanup']=final
                    if final['status']!='PASS':report['status']='FAIL'
                stop_heartbeat.set()
                if heartbeat_thread:heartbeat_thread.join(timeout=2)
                if watcher and watcher.poll() is None:
                    try:watcher.wait(timeout=40)
                    except subprocess.TimeoutExpired:watcher.kill();watcher.wait(timeout=5);report['status']='FAIL'
                if serving and serving.poll() is None:serving.kill();serving.wait(timeout=5)
                for area in (work,private):
                    for path in area.rglob('*'):
                        relative=path.relative_to(root)
                        if (path.is_file() and not path.is_symlink() and path.suffix in ('.json','.log','.patch','.txt')
                                and 'payload' not in relative.parts and 'ssh' not in relative.parts
                                and 'tls' not in relative.parts and 'transport' not in relative.parts
                                and path.name not in ('endpoint.json','payload-manifest.json') and 'sandboxes' not in relative.parts):
                            target=retained/relative;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                            shutil.copyfile(path,target);target.chmod(0o600)
    report['temporary_runtime_removed']=not root.exists()
    paths=list(FILES)+['tools/research_serving_cpu.py','tools/research_serving_delivery.py','tools/research_lifecycle.py',
        'tools/research_split_sequence.py','tools/research_split_cpu.py','tools/research_runner.py','tools/research_meter.py',
        'tools/research_isolation.py','tests/research_serving_fixture.py','.github/workflows/research-serving-cpu.yml']
    report['implementation']={p:c.digest((c.ROOT/p).read_bytes()) for p in paths}
    c._new_output(output,c.encoded(report));return report


def worker():
    from tools.research_runner import run_slot
    inputs,output,wheels,configuration=map(Path,sys.argv[2:6]);identifier,arm=sys.argv[6:8]
    settings=c.parse(configuration.read_bytes());settings['material']=Path(settings['material'])
    isolation=Isolation(output.parent/(output.name+'-private-isolation'),65532)
    result=run_slot(inputs,output,identifier,arm,None,wheels,isolation=isolation,upstream=Endpoint(**settings))
    checks={'completed':result['status']=='COMPLETED','original_tools':result['charged_tool_calls']==2,
        'six_requests':result['accounting']['admitted_requests']==6,'tokens':result['accounting']['totals']['total_tokens']==108,
        'authored_patch':b'backtrace-authored-cpu-fixture.txt' in (output/'agent.patch').read_bytes(),
        'cleanup':result['sandbox_cleanup'] and result['isolation']['live_namespaces']==0}
    receipt={'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'slot':result}
    c._new_output(output/'receipt.json',c.encoded(receipt));return receipt


if __name__=='__main__':
    if sys.argv[1:2]==['--worker']:result=worker()
    else:
        from tools.research_assets import prepare
        result=prepare(Path(sys.argv[1]),qualification=qualify,retain_inputs=False)
    print(json.dumps({'status':result['status']}))
    raise SystemExit(0 if result['status']=='PASS' else 1)
