"""Free native CPU tools -> TLS in frozen OCI image -> authored CPU responses.

The container uses host networking solely to reach the native scripted upstream.
It shares no task/evaluator mounts. This is not a GPU/model readiness claim.
"""
import contextlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import research_comparison as c
from tools.free_container_cleanup import remove
from tools.research_isolation import Isolation, bounded_child
from tools.research_runtime import prepare as prepare_runtime
from tools.research_verifier_cpu import readable_tree
from tools.research_split import Endpoint, credentials
from tools.research_split_sequence import sequence


def unused_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); return sock.getsockname()[1]


def qualify(inputs,output):
    if os.geteuid()!=0: raise ValueError('root native CPU coordinator required')
    report={'status':'INCOMPLETE','source_sha':os.environ.get('GITHUB_SHA'),
        'run_id':os.environ.get('GITHUB_RUN_ID'),'kind':'SPLIT_INFERENCE_AUTHORED_CPU',
        'real_model_runs':0,'provider_operations':0,'stages':{}}
    retained=inputs/'verifier-evidence'; retained.mkdir(mode=0o700)
    deadline=time.monotonic()+1800
    name='backtrace-free-full-setup-'+str(os.getpid())+'-split'
    image=c.load_protocol()['environment']['image']
    with tempfile.TemporaryDirectory(prefix='backtrace-split-',dir='/var/tmp') as temporary:
        public=Path(temporary); public.chmod(0o711)
        private=public/'private'; private.mkdir(mode=0o700)
        work=public/'work'; work.mkdir(mode=0o711)
        env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','HOME':str(private),
             'OTEL_SDK_DISABLED':'true','LITELLM_LOCAL_MODEL_COST_MAP':'True',
             'LITELLM_TELEMETRY':'False','PYTHON_DOTENV_DISABLED':'1',
             'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
        try:
            python,runtime=prepare_runtime(public/'runtime',inputs/'wheels')
            readable_tree(public/'runtime');report['runtime']=runtime
            pins=credentials(private/'tls')
            server_material=private/'server'; server_material.mkdir(mode=0o700)
            for f in ('server.key','server.crt','client.crt'):
                shutil.copyfile(private/'tls'/f,server_material/f);(server_material/f).chmod(0o600)
            fixture_port,tls_port=unused_port(),unused_port()
            if fixture_port==tls_port: raise ValueError('distinct listener ports required')
            endpoint=Endpoint('127.0.0.1',tls_port,private/'tls',pins['server_sha256'])
            configuration={'host':'127.0.0.1','port':tls_port,'material':str(private/'tls'),
                'server_sha256':pins['server_sha256'],'fixture_port':fixture_port}
            c._new_output(private/'endpoint.json',c.encoded(configuration))
            with (private/'image.log').open('wb') as log:
                subprocess.run(['docker','pull',image],stdout=log,stderr=log,check=True,timeout=900)
                details=json.loads(subprocess.check_output(['docker','image','inspect',image],timeout=20))[0]
                if (details['Architecture']!='amd64' or details['Os']!='linux'
                        or not any(d.endswith('@'+image.split('@')[1]) for d in details['RepoDigests'])):
                    raise ValueError('exact image required')
                result_directory=private/'container-result'; result_directory.mkdir(mode=0o700)
                command=['docker','run','-d','--name',name,'--network','host',
                    '--security-opt','no-new-privileges','--read-only','--cap-drop','ALL',
                    '--mount','type=bind,source='+str(c.ROOT/'tools')+',target=/work/tools,readonly',
                    '--mount','type=bind,source='+str(server_material)+',target=/transport,readonly',
                    '--mount','type=bind,source='+str(result_directory)+',target=/results',
                    '--entrypoint','/usr/bin/python3.12',image,'-I','-B','/work/tools/research_split_host.py',
                    '/transport','/results/transport.json','--upstream-port',str(fixture_port),
                    '--port',str(tls_port),'--lifetime','2100']
                subprocess.run(command,stdout=log,stderr=log,check=True,timeout=30)
                ready_deadline=time.monotonic()+20
                while True:
                    connection=endpoint.connection(1)
                    try: connection.connect();break
                    except OSError:
                        if time.monotonic()>=ready_deadline:raise
                        time.sleep(.1)
                    finally: connection.close()
                report['deployment']={'image':image,'image_id':details['Id'],
                    'capabilities':'ALL_DROPPED','network':'HOST_FOR_NATIVE_AUTHORED_UPSTREAM',
                    'task_mounts':0,'evaluator_mounts':0,'client_private_key_in_container':False,
                    'transport':endpoint.identity()}

            def execute(kind,name_,args,*,timeout=330,receipt='receipt.json'):
                destination=work/name_
                remaining=deadline-time.monotonic()
                if remaining<=5:
                    return {'status':'NOT_RUN','reason':'free qualification total deadline'}
                row=bounded_child([python,'-I','-B',Path(__file__).resolve(),'--worker',kind,
                    inputs,destination,public/'runtime/wheels',private/'endpoint.json',*args],
                    private/(name_+'.log'),env,timeout=min(timeout,remaining))
                path=destination/receipt
                if path.is_file():row['result']=c.parse(path.read_bytes())
                row['status']=('PASS' if row['exit_code']==0 and not row['child_timeout']
                    and row.get('result',{}).get('status')=='PASS' else 'FAIL')
                print(json.dumps({'split_stage':kind,'slot':name_,'status':row['status'],
                                  'wall_seconds':row['wall_seconds']}),file=sys.__stdout__,flush=True)
                return row
            report['stages']['isolation']=execute('isolation','isolation',[])
            report['stages']['server_command']=execute('server_command','server-command',[])
            def slot(identifier,arm,seconds):
                return execute('fixture',identifier+'-'+arm,[identifier,arm,'ordinary'],
                               timeout=seconds,receipt='fixture-receipt.json')
            slots=sequence(slot,deadline=deadline)
            slots['status']='PASS' if all(r['status']=='PASS' for r in slots['slots']) else 'FAIL'
            report['stages']['slots']=slots
            selected=slots['slots'][0]['instance_id'];controls=[]
            for control in ('retry','compaction','deadline_before_submit','deadline_after_submit'):
                controls.append(execute('fixture','control-'+control,[selected,'R0',control],
                    receipt='fixture-receipt.json'))
            report['stages']['controls']={'status':'PASS' if all(r['status']=='PASS' for r in controls) else 'FAIL',
                                         'controls':controls}
            outer=execute('fixture','control-outer',[selected,'R0','outer_after_submit'],timeout=25,
                          receipt='fixture-receipt.json')
            checkpoint=work/'control-outer/submitted-checkpoint.json'
            if checkpoint.is_file():
                saved=c.parse(checkpoint.read_bytes()); data=saved['patch'].encode()
                living=[]
                for path in Path('/proc').glob('[0-9]*/ns/pid'):
                    try:
                        if os.readlink(path) in saved['namespace_ids']:living.append(str(path))
                    except OSError:pass
                checks={'outer_deadline':outer['child_timeout'],
                    'original_submission_checkpoint':saved['source']=='ORIGINAL_SUBMIT_PATCH'
                        and len(data)==saved['bytes'] and c.digest(data)==saved['sha256'] and len(data)>0,
                    'agent_namespace_absent':bool(saved['namespace_ids']) and not living,
                    'no_false_completed_receipt':not (work/'control-outer/slot-receipt.json').exists()}
                outer.update(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,
                    artifact_status='SUBMITTED_CHECKPOINT_ONLY; final trace/accounting unavailable',
                    submitted_sha256=saved['sha256'],submitted_bytes=saved['bytes'])
            report['stages']['outer_after_submit']=outer
            subprocess.run(['docker','stop','--time','10',name],capture_output=True,check=True,timeout=20)
            report['transport']=c.parse((private/'container-result/transport.json').read_bytes())
            expected=sum(r['result']['slot']['accounting']['admitted_requests']
                for r in slots['slots']+controls if 'result' in r)
            # Outer kill does not finalize its ledger; only its retained partial
            # checkpoint and server count are available, never token totals.
            report['transport']['completed_children_requests']=expected
            attempts=report['transport']['requests']['attempts']
            metered=[r for slot in slots['slots']+controls if 'result' in slot
                for r in slot['result']['slot']['accounting']['requests']]
            partial=(saved['accounting']['requests'] if checkpoint.is_file() else [])
            checks={'metered_order_and_body_hashes':[a['sha256'] for a in attempts[:len(metered)]]
                    ==[r['forwarded_sha256'] for r in metered],
                'outer_checkpoint_order_and_hashes':[a['sha256'] for a in attempts[len(metered):len(metered)+len(partial)]]
                    ==[r['forwarded_sha256'] for r in partial],
                'outer_inflight_request_observed':len(attempts)==len(metered)+len(partial)+1,
                'all_transport_requests_closed':report['transport']['requests']['active']==0
                    and report['transport']['requests']['finished']==len(attempts),
                'forwarder_stopped':report['transport']['closed']}
            report['stages']['transport_reconciliation']={'status':'PASS' if all(checks.values()) else 'FAIL',
                'checks':checks,'completed_child_requests':len(metered),
                'outer_checkpoint_requests':len(partial),'observed_transport_requests':len(attempts)}
            report['status']='PASS' if all(r['status']=='PASS' for r in report['stages'].values()) else 'FAIL'
        except Exception as error:
            report.update(status='FAIL',error_type=type(error).__name__)
            c._new_output(private/'controller-error.log',traceback.format_exc().encode())
        finally:
            with (private/'container.log').open('wb') as log:
                with contextlib.suppress(Exception):
                    subprocess.run(['docker','logs',name],stdout=log,stderr=log,timeout=10)
            try: report['cleanup']=remove(name)
            except Exception as error:report['cleanup']={'status':'FAIL','error_type':type(error).__name__}
            if report['cleanup']['status']!='PASS':report['status']='FAIL'
            for path in public.rglob('*'):
                if (path.is_file() and not path.is_symlink() and 'sandboxes' not in path.parts
                        and (path.suffix in ('.log','.json') or path.name in ('agent.patch','agent-error.txt'))
                        and ('work' in path.relative_to(public).parts or 'private' in path.relative_to(public).parts
                             or path.name=='install.log') and path.name!='endpoint.json'):
                    target=retained/path.relative_to(public);target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                    shutil.copyfile(path,target);target.chmod(0o600)
    report['temporary_runtime_removed']=not public.exists()
    paths=['tools/research_split.py','tools/research_split_host.py','tools/research_split_cpu.py',
        'tools/research_split_sequence.py','tools/research_runner.py','tools/research_meter.py',
        'tools/research_fixture.py','tools/research_isolation.py','tools/research_runtime.py',
        'tools/research_split_server.py','tools/research_split_cache.py',
        '.github/workflows/research-split-cpu.yml']
    report['implementation']={p:c.digest((c.ROOT/p).read_bytes()) for p in paths}
    c._new_output(output,c.encoded(report));return report


if __name__=='__main__':
    if sys.argv[1:2]==['--worker']:
        kind=sys.argv[2];inputs,output,wheels,configuration=map(Path,sys.argv[3:7])
        if kind=='isolation':
            from tools.research_isolation_probe import qualify as probe
            result=probe(output)
        elif kind=='server_command':
            from adk_submission import VllmServer
            from tools.research_split_server import server_configuration, MIDDLEWARE
            output.mkdir(mode=0o700)
            server=VllmServer(server_configuration())
            try:
                command=server.build_cmd()
                checks={'cache_explicitly_disabled':command.count('--no-enable-prefix-caching')==1
                    and '--enable-prefix-caching' not in command,
                    'loopback_only':command[command.index('--host')+1]=='127.0.0.1',
                    'observed_cache_middleware':command[command.index('--middleware')+1]==MIDDLEWARE,
                    'no_model_process_started':server.process is None}
                result={'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,
                        'command':command,'model_execution':'NOT_RUN'}
                c._new_output(output/'receipt.json',c.encoded(result))
            finally:
                server.stop();Path(server.log_path).unlink(missing_ok=True)
        else:
            from tools.research_fixture import run_fixture
            settings=c.parse(configuration.read_bytes());fixture_port=settings.pop('fixture_port')
            settings['material']=Path(settings['material']);endpoint=Endpoint(**settings)
            isolation=Isolation(output.parent/(output.name+'-private-isolation'),65532)
            control=sys.argv[9]
            result=run_fixture(inputs,output,sys.argv[7],sys.argv[8],wheels,control,
                isolation=isolation,upstream=endpoint,fixture_port=fixture_port,
                qualification_seconds=12 if control.startswith('deadline_') else None)
    else:
        from tools.research_assets import prepare
        result=prepare(Path(sys.argv[1]),qualification=qualify,retain_inputs=False)
    print(json.dumps({'status':result['status']}))
    raise SystemExit(0 if result['status']=='PASS' else 1)
