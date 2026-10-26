"""Credential-free serving delivery and fixed native-CPU execution worker."""
import base64
import contextlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import threading
import time
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import research_entry_contract as c, ssh_bootstrap as ssh
from tools import research_comparison as comparison
from tools.research_entry import binding
from tools.research_serving_cpu import CLEAN, REMOTE, PYTHON
from tools.private_delivery import push, ssh_command
from tools.research_split import Endpoint
from tools.research_split_server import MODEL_PATH
from tools.research_reduced import sequence, identity as reduced_identity
from tools.research_isolation import bounded_child, Isolation
from tools.research_split_cpu import wait_namespace_absence, reclaim_slot


def write(path,value):
    path=Path(path);partial=path.with_suffix('.partial')
    with partial.open('w') as stream:
        os.fchmod(stream.fileno(),0o600);json.dump(value,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
    os.replace(partial,path)


def worker(plan):
    root=Path(plan['directory']);work=c.traversable_directory(root/'work')
    output=Path(plan['output']);output.mkdir(mode=0o700,parents=True,exist_ok=True)
    claim=plan['claim'];phase=['setup'];detail=['ssh'];done=threading.Event();serving=None;prefix=None
    report={'status':'FAIL','authored_cpu':plan['authored_cpu'],'pilot_scope':reduced_identity(),'stages':{},'slots':None}
    until=claim['requested_at']+claim['total_seconds']
    setup_until=min(until-660,claim['requested_at']+claim['setup_seconds'])
    monotonic_until=time.monotonic()+max(0,until-time.time())
    monotonic_setup=time.monotonic()+max(0,setup_until-time.time())
    def beat():
        while not done.is_set():
            write(root/'worker-status.json',{'claim_sha256':binding(claim),'phase':phase[0],'detail':detail[0],'at':time.time()})
            done.wait(min(3,claim['heartbeat_seconds']/4))
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    def remaining(cap, *, setup=True):
        left=min((setup_until if setup else until-claim['cleanup_seconds'])-time.time(),
            (monotonic_setup if setup else monotonic_until-claim['cleanup_seconds'])-time.monotonic())
        if left<=0:raise TimeoutError('phase reserve exhausted')
        return min(cap,left)
    previous={}
    def interrupted(*_):raise InterruptedError('controller stopped worker')
    for sig in (signal.SIGTERM,signal.SIGINT):previous[sig]=signal.signal(sig,interrupted)
    with (root/'worker.log').open('xb') as log:
        def remote(argv,*,data=None,seconds=60,setup=True,check=True):
            result=subprocess.run(prefix+[shlex.join(list(map(str,argv)))],input=data,
                stdin=subprocess.DEVNULL if data is None else None,capture_output=True,
                env=CLEAN,timeout=remaining(seconds,setup=setup))
            log.write(result.stdout);log.write(result.stderr);log.flush()
            if check:result.check_returncode()
            return result
        def program(code,**kwargs):return remote(['python3','-I','-c',code],**kwargs)
        try:
            endpoint=plan['endpoint']['ssh'];material=Path(plan['ssh_directory'])
            report['stages']['ssh']=ssh.deliver(material,endpoint['host'],endpoint['port'],
                remaining(120),profile='actions-20261019')
            known=ssh.known_hosts(material,endpoint['host'],endpoint['port'])
            manifest=Path(plan['payload_manifest'])
            command=ssh_command(endpoint['host'],endpoint['port'],material/'owner-key',known,REMOTE,c.digest(manifest.read_bytes()))
            prefix=command[:-1];ssh.wait_for_command(prefix,['true'],remaining(60),log=log)
            detail[0]='source_delivery'
            report['stages']['delivery']=push(plan['payload'],manifest,command,remaining(120))
            needed=sum(row['bytes'] for stream in plan['streams'].values() for row in json.loads(stream['manifest'])['files'])+16*1024**3
            base=("import os,sys,shutil,json;from pathlib import Path;"
                "assert os.geteuid()==0 and sys.version_info[:2]==(3,12);"
                "assert shutil.disk_usage('/root').free>"+str(needed)+";"
                "assert int(Path('/proc/self/stat').read_bytes().split(b' ',1)[0])==os.getpid();"
                "print(json.dumps({'status':'PASS','free_bytes':shutil.disk_usage('/root').free}))")
            report['stages']['base']=json.loads(program(base).stdout)
            for kind in ('wheels','model'):
                if kind=='model':
                    detail[0]='runtime_install'
                    result=remote(['python3','-I',REMOTE+'/tools/research_serving_install.py',
                        '/root/backtrace/wheels',REMOTE+'/docs/linux-wheel-manifest.json',
                        '/root/backtrace/runtime',str(remaining(1200))],seconds=1250)
                    report['stages']['runtime']=json.loads(result.stdout.splitlines()[-1])
                    if plan['authored_cpu']:break
                    # Check actual CUDA before transferring any weights.
                    code=("import torch,json;assert torch.cuda.is_available() and torch.cuda.device_count()==1;"
                        "assert 'A100' in torch.cuda.get_device_name(0);"
                        "assert torch.cuda.get_device_properties(0).total_memory>=79*1024**3;"
                        "x=torch.ones(1,device='cuda');assert x.item()==1;print(json.dumps({'cuda':'PASS'}))")
                    report['stages']['hardware']=json.loads(remote([PYTHON,'-I','-c',code]).stdout)
                row=plan['streams'][kind]
                detail[0]=kind+'_transfer'
                code=("import sys,json;sys.path.insert(0,"+repr(REMOTE)+");from tools.direct_delivery import pull;"
                    "v=json.load(sys.stdin);print(json.dumps(pull('/root/backtrace/"+kind+"',"
                    "v['manifest'].encode(),v['sources'],v['sha256'],v['seconds'])))")
                report['stages'][kind]=json.loads(program(code,data=c.encoded(dict(row,seconds=remaining(1200))),seconds=1250).stdout)
            if not plan['authored_cpu']:
                program("from pathlib import Path;p=Path("+repr(MODEL_PATH)+");p.parent.mkdir(parents=True,exist_ok=True);"
                        "assert not p.exists();Path('/root/backtrace/model').rename(p)")
            base=[PYTHON,'-I','-B',REMOTE+'/tools/research_serving.py',REMOTE+'/transport','/root/backtrace/run',
                '--lifetime',str(remaining(7740,setup=False)), '--ready-seconds',str(remaining(1200))]
            if plan['authored_cpu']:base+=['--authored-cpu',REMOTE+'/tests/research_serving_fixture.py']
            else:base+=['--model-manifest',REMOTE+'/docs/research-entry-model-manifest.json']
            serving=subprocess.Popen(prefix+[shlex.join(base)],env=CLEAN,stdin=subprocess.DEVNULL,
                stdout=log,stderr=log,start_new_session=True)
            detail[0]='readiness'
            while True:
                value=json.loads(program("from pathlib import Path;p=Path('/root/backtrace/run/ready.json');print(p.read_text() if p.is_file() else '{}')").stdout)
                if value:break
                if serving.poll() is not None:raise RuntimeError('server exited before readiness')
                time.sleep(.2)
            expected='AUTHORED_CPU' if plan['authored_cpu'] else 'MODEL_INFERENCE'
            if value.get('kind')!=expected:raise ValueError('authored/real readiness mismatch')
            tls=plan['endpoint']['tls']
            settings=dict(tls,material=plan['tls_directory'],server_sha256=plan['server_sha256'])
            connection=Endpoint(**dict(settings,material=Path(settings['material']))).connection(5)
            connection.connect();connection.close()
            write(root/'endpoint.json',settings)
            report['stages']['ready']={'status':'PASS','result':value,'endpoint_sha256':c.digest(plan['endpoint'])}
            phase[0]='workload'
            def slot(identifier,arm,seconds):
                detail[0]=identifier+'-'+arm
                destination=work/(identifier+'-'+arm)
                row=bounded_child([plan['cpu_python'],'-I','-B',Path(__file__).resolve(),'--slot',
                    plan['inputs'],destination,plan['cpu_wheels'],root/'endpoint.json',identifier,arm],
                    root/(identifier+'-'+arm+'.log'),CLEAN,timeout=seconds)
                checkpoint=destination/'session-checkpoint.json'
                if not checkpoint.is_file():raise RuntimeError('namespace checkpoint missing')
                row['namespace_cleanup']=wait_namespace_absence(json.loads(checkpoint.read_bytes())['namespace_ids'])
                if row['namespace_cleanup']['status']!='PASS':raise RuntimeError('namespace remains')
                row['parent_cleanup']=reclaim_slot(destination)
                receipt=destination/'receipt.json'
                if receipt.is_file():row['result']=json.loads(receipt.read_bytes())
                row['status']=row.get('result',{}).get('status','INFRASTRUCTURE_FAILURE')
                if row['exit_code']!=0:raise RuntimeError('isolated child failed')
                return row
            # Convert the allocation-inclusive wall deadline once to the runner's
            # monotonic clock. Sequence owns all nine denominators and reserves.
            report['slots']=sequence(slot,deadline=time.monotonic()+max(0,until-time.time()))
            report['status']='PASS' if (report['slots']['all_slots_attempted'] and
                all(row['status']!='INFRASTRUCTURE_FAILURE' for row in report['slots']['slots'])) else 'PARTIAL'
        except BaseException as error:
            report['failure']={'type':type(error).__name__,'phase':phase[0]}
            (root/'worker-error.log').write_text(traceback.format_exc())
        finally:
            phase[0]='export'
            detail[0]='stop_export'
            # Preserve partial/no-result slots even after failed readiness.
            if report['slots'] is None:
                report['slots']=sequence(lambda *_:None,deadline=time.monotonic())
            write(work/'slots.json',report['slots'])
            if prefix:
                try:
                    code="import os,signal;from pathlib import Path;\nfor p in Path('/proc').glob('[0-9]*/cmdline'):\n try:\n  raw=p.read_bytes().split(b'\\0')\n  if "+repr((REMOTE+'/tools/research_serving.py').encode())+" in raw and b'/root/backtrace/run' in raw:os.kill(int(p.parent.name),signal.SIGTERM)\n except (FileNotFoundError,ProcessLookupError):pass\n"
                    program(code,setup=False,seconds=20)
                    if serving:serving.wait(timeout=15)
                    names=['run/receipt.json','run/ready.json','run/server.log','runtime/receipt.json','runtime/inventory.json']
                    code=("import base64,json;from pathlib import Path;out={};\nfor n in "+repr(names)+":\n"
                        " p=Path('/root/backtrace')/n\n if p.is_file():\n  assert p.stat().st_size<32*1024**2\n  out[n]=base64.b64encode(p.read_bytes()).decode()\nprint(json.dumps(out))")
                    values=json.loads(program(code,setup=False,seconds=60).stdout)
                    for name,data in values.items():
                        target=work/'remote'/name;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                        target.write_bytes(base64.b64decode(data,validate=True));target.chmod(0o600)
                    receipt=json.loads((work/'remote/run/receipt.json').read_bytes())
                    report['stages']['server_stop']=receipt
                    if receipt['process_cleanup']!='PASS':report['status']='FAIL'
                except BaseException as error:
                    report['retrieval_error']=type(error).__name__;report['status']='FAIL'
            if serving and serving.poll() is None:
                with contextlib.suppress(ProcessLookupError):os.killpg(serving.pid,signal.SIGTERM)
                try:serving.wait(timeout=5)
                except subprocess.TimeoutExpired:serving.kill();serving.wait(timeout=5)
            try:
                from tools.cloud_seal import seal
                write(work/'worker-summary.json',report)
                files={p.relative_to(work).as_posix():p for p in work.rglob('*')
                    if p.is_file() and not p.is_symlink() and 'sandboxes' not in p.parts}
                files.update({'logs/'+p.name:p for p in root.glob('*.log')})
                report['export']=dict(seal(files,output/'results.age'),completed_at=time.time())
            except BaseException as error:report['export_error']=type(error).__name__;report['status']='FAIL'
            done.set();thread.join(timeout=5)
            write(root/'worker-result.json',report)
            for sig,handler in previous.items():signal.signal(sig,handler)
    return report


def slot_main():
    from tools.research_runner import run_slot
    inputs,output,wheels,config=map(Path,sys.argv[2:6]);identifier,arm=sys.argv[6:8]
    settings=json.loads(config.read_bytes());settings['material']=Path(settings['material'])
    isolation=Isolation(output.parent/(output.name+'-private-isolation'),65532)
    result=run_slot(inputs,output,identifier,arm,None,wheels,isolation=isolation,upstream=Endpoint(**settings))
    write(output/'receipt.json',result)
    return result


if __name__=='__main__':
    if sys.argv[1:2]==['--slot']:slot_main()
    else:
        value=worker(json.loads(Path(sys.argv[1]).read_bytes()))
        raise SystemExit(0 if value['status']=='PASS' else 1)
