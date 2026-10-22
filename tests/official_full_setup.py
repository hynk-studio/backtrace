"""Actual frozen inputs and runtime through the production SSH setup path.

Free CPU only. Stop before the production GPU check, then use its explicit
CPU runtime mode and the retained driver's CPU-prerequisites entry. No permit,
model stream, model server, task/agent run or service credential enters here.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import cloud_task, cloud_worker as worker, ssh_bootstrap as ssh, runpod_control as control
from tools.private_delivery import push, ssh_command
from tools.direct_delivery import sources_for
from tools.runpod_job import check_owner_host, private_json


def qualify(parent, work, report):
    check_owner_host()
    if any(k in os.environ for k in ('RUNPOD_API_KEY', 'GITHUB_TOKEN', 'KAGGLE_API_TOKEN', 'GH_STATE_TOKEN')):
        raise ValueError('free SSH setup child inherited a service credential')
    stages = report['stages']
    inputs = parent / 'full-ssh-streams.json'
    if inputs.is_symlink() or inputs.stat().st_mode & 0o077 or inputs.stat().st_uid != parent.stat().st_uid:
        raise ValueError('private prepared source map required')
    streams = json.loads(inputs.read_text())
    if set(streams) != {'wheels', 'task', 'model'}: raise ValueError('exact source streams required')
    for kind, row in streams.items():
        raw = worker.frozen.manifest(kind)
        if row['manifest'].encode() != raw or row['sha256'] != hashlib.sha256(raw).hexdigest():
            raise ValueError('scientific input manifest changed')
        sources_for(json.loads(raw), row['sources'])
    driver = parent / 'ssh-driver'; manifest = cloud_task.manifest(driver)
    path = work / 'driver-manifest.json'; path.write_bytes(manifest)
    binaries = parent / 'transport/dropbear-DROPBEAR_2026.94'
    initializer = ssh.prepare(binaries / 'dropbear', binaries / 'dropbearkey', work / 'ssh', profile=worker.PROFILE)
    private_json(work / 'ssh/initializer.json', initializer)
    env_file = work / 'image.env'
    env_file.write_text('\n'.join(k+'='+v for k,v in initializer['env'].items())+'\n'); env_file.chmod(0o600)
    name = 'backtrace-free-full-setup-' + os.environ['GITHUB_RUN_ID']
    def emit(row):
        print(json.dumps({'free_ssh_setup': row}, sort_keys=True), flush=True)
    with (work / 'image.log').open('wb') as image_log, (work / 'ssh.log').open('wb') as log:
        subprocess.run(['docker', 'pull', control.BASE], stdout=image_log, stderr=image_log, check=True, timeout=900)
        image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', control.BASE], timeout=20))[0]
        if (image['Architecture'] != 'amd64' or image['Os'] != 'linux'
                or not any(x.endswith('@'+control.BASE.split('@')[1]) for x in image['RepoDigests'])):
            raise ValueError('exact deployment image required')
        command = ['docker', 'run', '-d', '--rm', '--name', name, '--env-file', str(env_file),
                   '-p', '127.0.0.1::22', '--entrypoint', initializer['entrypoint'][0]]
        for item in ('tools', 'docs', 'tests'):
            command += ['--mount', 'type=bind,source='+str(ROOT/item)+',target=/work/'+item+',readonly']
        command += [control.BASE, *initializer['entrypoint'][1:], *initializer['cmd']]
        try:
            subprocess.run(command, stdout=image_log, stderr=image_log, check=True, timeout=30)
            value = json.loads(subprocess.check_output(['docker', 'inspect', name], timeout=20))[0]
            port = int(value['NetworkSettings']['Ports']['22/tcp'][0]['HostPort'])
            listener = ("from pathlib import Path;raise SystemExit(0 if any("
                "x.split()[1].endswith(':0016') and x.split()[3]=='0A' for x in "
                "Path('/proc/net/tcp').read_text().splitlines()[1:]) else 1)")
            deadline = time.monotonic()+30
            while True:
                ready = subprocess.run(['docker','exec',name,'/usr/bin/python3.12','-I','-c',listener],
                    stdout=image_log, stderr=image_log, timeout=5)
                if ready.returncode == 0: break
                if time.monotonic() >= deadline: raise TimeoutError('CPU container listener deadline')
                time.sleep(.2)
            transfer = ssh.deliver(work/'ssh','127.0.0.1',port,120,profile=worker.PROFILE)
            known = ssh.known_hosts(work/'ssh','127.0.0.1',port)
            prefix = ssh_command('127.0.0.1',port,work/'ssh/owner-key',known,'/root/backtrace/unused','0'*64)[:-1]
            ssh.wait_for_command(prefix,['true'],60,log=log)
            stages['tls_and_pinned_ssh'] = dict(transfer,status='PASS')
            command = ssh_command('127.0.0.1',port,work/'ssh/owner-key',known,
                                  '/root/backtrace/driver',hashlib.sha256(manifest).hexdigest())
            stages['actual_driver_transfer'] = dict(push(driver,path,command,120),status='PASS',
                                                    driver_sha256=cloud_task.CLOUD_DRIVER_SHA256)
            requested = time.time()
            def remote(argv, *, input=None, limit=5400):
                timeout = min(1800, requested+limit-time.time())
                if timeout <= 0: raise TimeoutError('CPU SSH setup deadline')
                try:
                    result = subprocess.run(prefix+[shlex.join(argv)],input=input,
                        stdin=subprocess.DEVNULL if input is None else None,
                        capture_output=True,timeout=timeout,env=worker.CLEAN)
                except subprocess.TimeoutExpired as error:
                    log.write(error.output or b'');log.write(error.stderr or b'');log.flush();raise
                log.write(result.stdout);log.write(result.stderr);log.flush();result.check_returncode()
                return result
            history=[]; active=[None]
            class GPURequired(Exception): pass
            def progress(row):
                if row=={'stage':'runtime_hardware','status':'STARTED'}: raise GPURequired()
                history.append(row);active[0]=row['stage'];emit(row)
            def setup_call(argv, *, input):
                result=remote(argv,input=input)
                values=[json.loads(line) for line in result.stdout.splitlines() if line.startswith(b'{')]
                if active[0]=='runtime_inputs':
                    if [row['stream'] for row in values]!=['wheels','task']:
                        raise ValueError('frozen HTTPS transfer sequence incomplete')
                    stages['actual_input_transfers']={'status':'PASS','streams':values}
                elif values: stages[active[0]]=dict(values[-1],status='PASS')
            try: worker.setup_remote(setup_call,streams,manifest,requested,emit=progress)
            except GPURequired: pass
            else: raise ValueError('CPU check crossed the required GPU boundary')
            completed=[row['stage'] for row in history if row['status']=='PASS']
            if completed!=['base_environment','system_packages','runtime_inputs','runtime_installation']:
                raise ValueError('production runtime setup prefix incomplete')
            stages['production_setup']={'status':'PASS','stages':completed,'stopped':'BEFORE_GPU_CHECK'}
            preflight=(ROOT/'tools/pod_preflight.py').read_text()
            argv,data=worker.code_envelope(preflight+'\nprint(json.dumps(runtime(require_gpu=False)))\n')
            stages['actual_cpu_runtime']=json.loads(remote(argv,input=data).stdout)
            # Match the CPU fixture's logical task activation. Reuse production
            # verification/permissions, with no model directory or launch permit.
            task_sha=streams['task']['sha256']
            bootstrap=(ROOT/'tools/pod_bootstrap.py').read_text()
            program=(bootstrap+'\nsource=STAGING/\'task\'\nchecked_tree(source,'+repr(task_sha)+')\n'
                +"target=INPUT/'r0-inputs'\nassert not target.exists()\ninput_parent(target)\n"
                +"(source/'delivery-manifest.json').unlink()\nsource.rename(target)\nreadonly(target)\n"
                +"assert not (STAGING/'model').exists() and not (STAGING/'launch-permit.json').exists()\n"
                +"print(json.dumps({'status':'PASS','model_activation':'NOT RUN','permit':'ABSENT'}))\n")
            argv,data=worker.code_envelope(program)
            stages['actual_task_layout']=json.loads(remote(argv,input=data).stdout)
            program=("import sys,json\nfrom pathlib import Path\nsys.path.insert(0,'/work')\n"
                +"from tests.official_cloud_prerequisites import qualify\n"
                +"print(json.dumps(qualify(Path('/root/backtrace/driver'),staged=True,host='exact image via pinned SSH')))\n")
            argv,data=worker.code_envelope(program)
            stages['actual_driver_cpu_prerequisites']=json.loads(remote(argv,input=data).stdout.splitlines()[-1])
            report.update(status='PASS',image=control.BASE,image_id=image['Id'],
                          setup_seconds=round(time.time()-requested,3))
        finally:
            with (work/'container.log').open('wb') as container_log:
                with contextlib.suppress(Exception):
                    subprocess.run(['docker','logs','--tail','100',name],stdout=container_log,stderr=container_log,timeout=10)
            # Cleanup evidence must not mask an earlier setup failure or leave
            # a previously assigned PASS when removal itself times out.
            report['container_cleanup']='UNCONFIRMED'
            try:
                removed=subprocess.run(['docker','rm','-f',name],stdout=image_log,stderr=image_log,timeout=30)
                removed.check_returncode()
            except Exception as error:
                report.update(status='FAIL',container_cleanup_error=type(error).__name__)
            else: report['container_cleanup']='REMOVED'


def main():
    os.umask(0o077)
    parent=Path(sys.argv[1]).absolute();work=parent/'full-setup';work.mkdir(mode=0o700)
    report={'status':'FAIL','stages':{},'provider_operations':0,'gpu_allocations':0,
            'model_body_read':False,'gpu_initialization':'NOT RUN','model_execution':'NOT RUN',
            'public_task_execution':'NOT RUN','launch_permit':'NOT CREATED'}
    try: qualify(parent,work,report)
    except Exception as error:
        report['status']='FAIL'
        report['failure']={'error_type':type(error).__name__,'returncode':getattr(error,'returncode',None)}
    path=parent/'full-setup-result.json'
    path.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n');path.chmod(0o644)
    print(json.dumps({'full_ssh_result':report},sort_keys=True),flush=True)
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__': raise SystemExit(main())
