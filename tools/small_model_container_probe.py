"""Free exact-image installation, SSH collection and real worker-loss controls."""
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import traceback

from tools import small_model_container as container
from tools import small_model_runner as runner, small_model_runner_probe as probe
from tools import small_model_readiness as ready, exact_teacher as exact
from tools import abductive_benchmark as base, abductive_scoring as score, temporal_benchmark as temporal
from tools import cloud_transport, ssh_bootstrap as ssh, private_delivery as delivery
from tools import runpod_control as control, small_model_lifecycle as life
from tools.free_container_cleanup import remove


def qualify(sources,packets,tokens,scope,wheels,transport,output):
    ready.check_packages();sources=ready.validate_sources(sources)
    plan,schedule,scope_hash=runner.load_scope(scope,packets,tokens)
    if plan['scope']!='smoke' or list(Path('/dev').glob('nvidia[0-9]*')):
        raise ValueError('original smoke on free CPU required')
    output=Path(output).resolve();output.mkdir(mode=0o700,parents=True)
    if (output/'receipt.json').exists():raise ValueError('fresh evidence directory required')
    result={'status':'INCOMPLETE','scope':'FREE_CONTAINER_EXECUTION_V1','source_hashes':container.sources(),
            'source_sha':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),
            'image':control.BASE,'scope_sha256':scope_hash,'provider_api_calls':0,
            'container_mode':'ORDINARY_OCI_WITH_6_GIB_MEMORY_LIMIT','launch_gates':container.launch_gates()}
    name='backtrace-free-full-setup-'+str(os.getpid())+'-small-container'
    try:
        from transformers import AutoTokenizer
        tokenizers={n:AutoTokenizer.from_pretrained(sources/n,local_files_only=True,trust_remote_code=False) for n in ready.MODELS}
        models=output/'random-models';result['fixture_model_manifests']=probe.random_models(sources,models)
        with tempfile.TemporaryDirectory(prefix='backtrace-small-container-',dir='/root') as td:
            root=Path(td);result['transport_build']=json.loads((transport/'receipt.json').read_bytes())
            binaries=transport/'dropbear-DROPBEAR_2026.94'
            # This rebuild uses a separate pinned controller environment; never
            # contaminate the exact CPU/model closure with owner HTTP libraries.
            for binary,expected in result['transport_build']['binaries'].items():
                path=binaries/binary
                if path.stat().st_size!=expected['bytes'] or delivery.digest(path)!=expected['sha256']:
                    raise ValueError('prebuilt transport bytes changed')
            init=ssh.prepare(binaries/'dropbear',binaries/'dropbearkey',root/'keys',profile='actions-20261019')
            life.write(root/'keys/initializer.json',init)
            result['transport_material']=ssh.validate_material(root/'keys',profile='actions-20261019')
            env=root/'env';env.write_text('\n'.join(k+'='+v for k,v in init['env'].items())+'\n');env.chmod(0o600)
            runtime_manifest,result['runtime_bundle']=container.runtime_payload(root/'runtime',wheels)
            asset_manifest=container.assets(root/'assets',sources,models)
            result['runtime_manifest']=json.loads(runtime_manifest);result['asset_manifest']=json.loads(asset_manifest)
            with (output/'image.log').open('xb') as log:
                subprocess.run(['docker','pull',control.BASE],stdout=log,stderr=log,check=True,timeout=900)
                details=json.loads(subprocess.check_output(['docker','image','inspect',control.BASE],timeout=20))[0]
                if details['Architecture']!='amd64' or not any(d.endswith('@'+control.BASE.split('@')[1]) for d in details['RepoDigests']):
                    raise ValueError('image identity mismatch')
                result['image_id']=details['Id']
                subprocess.run(['docker','run','-d','--rm','--name',name,'--memory','6g','--memory-swap','6g',
                    '--env-file',str(env),'-p','127.0.0.1::22','--entrypoint',init['entrypoint'][0],control.BASE,
                    *init['entrypoint'][1:],*init['cmd']],stdout=log,stderr=log,check=True,timeout=30)
                info=json.loads(subprocess.check_output(['docker','inspect',name],timeout=20))[0]
                result['container_id']=info['Id'];port=int(info['NetworkSettings']['Ports']['22/tcp'][0]['HostPort'])
                result['host_container_controls']={k:info['HostConfig'][k] for k in ('Privileged','CapAdd','SecurityOpt','Memory','MemorySwap','PidMode','NetworkMode')}
                if info['HostConfig']['Privileged'] or info['HostConfig']['CapAdd'] or info['Mounts']:
                    raise ValueError('unexpected container privilege or host mount')
                listener="from pathlib import Path;raise SystemExit(0 if any(x.split()[1].endswith(':0016') and x.split()[3]=='0A' for x in Path('/proc/net/tcp').read_text().splitlines()[1:]) else 1)"
                end=time.monotonic()+30
                while True:
                    p=subprocess.run(['docker','exec',name,'/usr/bin/python3.12','-I','-c',listener],stdout=log,stderr=log,timeout=5)
                    if p.returncode==0:break
                    if time.monotonic()>=end:raise TimeoutError('bootstrap listener absent')
                    time.sleep(.2)
                result['binary_transfer']=ssh.deliver(root/'keys','127.0.0.1',port,60,profile='actions-20261019')
                known=ssh.known_hosts(root/'keys','127.0.0.1',port)
                prefix=delivery.ssh_command('127.0.0.1',port,root/'keys/owner-key',known,
                    '/root/backtrace/runtime',exact.sha(runtime_manifest))[:-1]
                ssh.wait_for_command(prefix,['true'],30,log=log)
                wrong=root/'wrong-hosts';wrong.write_text(f'[127.0.0.1]:{port} '+(root/'keys/owner-key.pub').read_text());wrong.chmod(0o600)
                bad=delivery.ssh_command('127.0.0.1',port,root/'keys/owner-key',wrong,'/root/backtrace/unused','0'*64)[:-1]
                denied=subprocess.run(bad+['true'],capture_output=True,timeout=10,env={'PATH':'/usr/bin:/bin'})
                if denied.returncode==0 or b'Host key verification failed' not in denied.stderr:raise ValueError('wrong SSH host accepted')
                result['wrong_host_key']='REFUSED'
                def remote(code,seconds=30):
                    p=subprocess.run(prefix+[shlex.join(['/usr/bin/python3.12','-I','-c',code])],
                        capture_output=True,timeout=seconds,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
                    if p.returncode:
                        (output/'remote-error.log').write_bytes(p.stderr[-8000:]);raise RuntimeError('remote control failed')
                    return json.loads(p.stdout)
                for kind,raw in [('runtime',runtime_manifest),('assets',asset_manifest)]:
                    mp=root/(kind+'-manifest.json');mp.write_bytes(raw)
                    command=delivery.ssh_command('127.0.0.1',port,root/'keys/owner-key',known,
                        '/root/backtrace/'+kind,exact.sha(raw))
                    result[kind+'_transfer']=delivery.push(root/kind,mp,command,600)
                with (output/'install.log').open('xb') as install_log:
                    installed=subprocess.run(prefix+[shlex.join(['/usr/bin/python3.12','-I',
                        '/root/backtrace/runtime/installer.py','install','/root/backtrace/runtime'])],
                        stdout=subprocess.PIPE,stderr=install_log,timeout=1100,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
                if installed.returncode:raise RuntimeError('exact-image offline installation failed')
                result['installation']=json.loads(installed.stdout)
                setup="""import json,pathlib,shutil
r=pathlib.Path('/root/backtrace/assets');target=pathlib.Path('/opt/backtrace/assets');shutil.move(r,target)
for p in [target,*target.rglob('*')]:p.chmod(0o755 if p.is_dir() else 0o444)
p=pathlib.Path('/root/backtrace/private-canary');p.write_text('not-an-account-secret');p.chmod(0o600)
print(json.dumps({'installed_assets':len(list(target.rglob('*'))),'memory_max':pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip(),'cgroup_ancestry':'HIDDEN_NOT_ADMITTED'}))
"""
                result['container_resource_observation']=remote(setup)
                channel=runner.Channel(container.command(prefix,'E2B','scripted_control',script='boundary'),output/'boundary.log')
                try:boundary=channel.read(time.monotonic()+30)
                finally:boundary_exit=channel.close()
                result['boundary']=boundary
                checks={k:boundary[k] is True for k in ('socket_denied','unix_socket_denied','fork_denied','exec_denied',
                    'root_denied','private_file_denied','readonly_job','namespace_denied','threads_work','credential_environment_absent')}
                checks['worker_identity']=boundary['uid']==65532 and boundary['caps']==0 and boundary['no_new_privs']=='1' and boundary['seccomp']=='2'
                checks['outer_namespaces']=boundary['pid_namespace']!=os.readlink('/proc/self/ns/pid') and boundary['net_namespace']!=os.readlink('/proc/self/ns/net')
                checks['boundary_exit']=boundary_exit==0
                result['checks']=checks
                life.write(output/'boundary-checkpoint.json',result)
                if not all(checks.values()):raise AssertionError('container boundary checks failed')
                raw_ids={}
                for item in schedule:
                    if item['arm']!='B0':continue
                    payload=base.strict_json(item['messages'][1]['content'])
                    ref=temporal.reference(payload) if payload['task']=='temporal_revision' else base.reference(payload)
                    translated=temporal.as_revision(payload) if payload['task']=='temporal_revision' else payload
                    answer=json.dumps(score.optimal_response(translated,ref),sort_keys=True,separators=(',',':'))
                    raw_ids[item['id']]=tokenizers['E2B'].encode(answer,add_special_tokens=False)+[106]
                runs={};result['runs']=runs
                for label,fault in [('oracle',None),('hang','hang'),('crash','crash'),('wrong_id','wrong_id'),('oversize','oversize'),('startup_hang','startup_hang'),('random',None)]:
                    mode='random_fixture' if label=='random' else 'scripted_control'
                    factory=container.factory(prefix,mode,fault=fault)
                    collection=runner.collect(schedule,output/label,factory,tokenizers,mode=mode,
                        max_new_tokens=2 if label=='random' else 4096,total_seconds=1 if label=='startup_hang' else 240,
                        startup_seconds=1 if label=='startup_hang' else 45,request_seconds=1 if label=='hang' else 30,
                        fixture_ids=None if label=='random' else raw_ids)
                    evaluation=runner.evaluate(plan,schedule,collection)
                    life.write(output/label/'evaluation.json',evaluation)
                    runs[label]={k:v for k,v in collection.items() if k not in ('records','worker_handshakes')}
                    if label=='oracle':
                        cases=[c for arms in evaluation['scores'].values() for group in arms.values() for sub in group.values() for c in sub['assigned_protocol_scores']['cases']]
                        checks[label]=collection['coverage']=={'OK':36} and len(cases)==36 and all(c['response_status']=='VALID' and all(v==0 for v in c['losses'].values()) for c in cases)
                    elif label=='random':checks[label]=collection['status']=='COMPLETED' and all(r['status'] in ('OK','INVALID_OUTPUT') and 0<r['generated_tokens']<=2 for r in collection['records'])
                    elif label in ('hang','crash'):checks[label]=collection['coverage']=={'OK':1,('TIMEOUT' if label=='hang' else 'WORKER_ERROR'):1,'NOT_RUN':34}
                    elif label=='startup_hang':checks[label]=collection['coverage']=={'NOT_RUN':36}
                    else:checks[label]=collection['coverage']=={'WORKER_ERROR':1,'NOT_RUN':35}
                    life.write(output/(label+'-checkpoint.json'),result)
                    if not checks[label]:raise AssertionError('collector control failed: '+label)
                def state(job):
                    code="import json,pathlib\np=pathlib.Path('/root/backtrace/"+job+"-state.json')\nr=json.loads(p.read_bytes());q=pathlib.Path('/proc')/str(r['pid'])/'stat'\ntry:s=q.read_text().split();r['same_process_alive']=s[21]==r['start_ticks'];r['process_state']=s[2]\nexcept (FileNotFoundError,ProcessLookupError):r['same_process_alive']=False;r['process_state']='ABSENT'\nprint(json.dumps(r))"
                    return remote(code)
                # Root supervisor deadline, independent of owner Channel deadlines.
                command=container.command(prefix,'E2B','scripted_control',fault='startup_hang',seconds=1)
                channel=runner.Channel(command,output/'deadline.log')
                try:
                    try:channel.read(time.monotonic()+10);raise AssertionError('deadline worker emitted output')
                    except EOFError:pass
                finally:channel.close()
                deadline=state(container.job_name('E2B','scripted_control','startup_hang'))
                result['remote_deadline']=deadline;checks['remote_deadline']=deadline['reason']=='DEADLINE' and not deadline['same_process_alive'] and deadline['elapsed_seconds']<5
                # Real transport death during a worker startup hang; query via a
                # separate authenticated SSH session, never infer from local exit.
                channel=runner.Channel(container.command(prefix,'E2B','scripted_control',fault='startup_hang'),output/'transport-loss.log')
                job=container.job_name('E2B','scripted_control','startup_hang')
                prior=deadline['start_ticks'];end=time.monotonic()+10
                while True:
                    before=state(job)
                    if before['start_ticks']!=prior and before['same_process_alive']:break
                    if time.monotonic()>=end:raise TimeoutError('fresh remote worker did not start')
                    time.sleep(.1)
                os.killpg(channel.process.pid,signal.SIGKILL);channel.close()
                end=time.monotonic()+10
                while True:
                    after=state(job)
                    if not after['same_process_alive']:break
                    if time.monotonic()>=end:raise TimeoutError('remote worker survived transport loss')
                    time.sleep(.1)
                result['transport_loss']={'before':before,'after':after}
                checks['transport_loss']=not after['same_process_alive']
                # Actual privileged supervisor loss also kills its UID-dropped child.
                channel=runner.Channel(container.command(prefix,'E2B','scripted_control',fault='startup_hang'),output/'supervisor-loss.log')
                prior=after['start_ticks'];end=time.monotonic()+10
                while True:
                    before=state(job)
                    if before['start_ticks']!=prior and before['same_process_alive']:break
                    if time.monotonic()>=end:raise TimeoutError('fresh remote supervisor did not start')
                    time.sleep(.1)
                remote('import json,os,signal;os.kill('+str(before['supervisor_pid'])+',signal.SIGKILL);print(json.dumps({"killed":True}))')
                channel.close();end=time.monotonic()+10
                while True:
                    after=state(job)
                    if not after['same_process_alive']:break
                    if time.monotonic()>=end:raise TimeoutError('child survived privileged supervisor loss')
                    time.sleep(.1)
                result['supervisor_loss']={'before':before,'after':after}
                checks['supervisor_loss']=not after['same_process_alive']
                result['status']='PASS_FREE_CONTAINER_EXECUTION' if all(checks.values()) else 'FAIL'
    except Exception as error:
        result.update(status='FAIL',error_type=type(error).__name__,error=str(error)[:250])
        result['frames']=[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)][-8:]
    finally:
        result['cleanup']=remove(name,container_id=result.get('container_id'))
        if result['cleanup']['status']!='PASS':result['status']='FAIL'
        life.write(output/'receipt.json',result)
    return result


if __name__=='__main__':
    os.umask(0o077)
    result=qualify(*(Path(p).resolve() for p in sys.argv[1:]))
    print(json.dumps(result,sort_keys=True))
    raise SystemExit(0 if result['status']=='PASS_FREE_CONTAINER_EXECUTION' else 1)
