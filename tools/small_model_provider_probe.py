"""Free exact-image TLS/SSH delivery and non-GPU prerequisites for this payload.

Uses ordinary Docker isolation, never privileged mode, host cgroup mounts or
GPU passthrough. BLOCKED prerequisites are retained independently of transport.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

from tools import cloud_transport, ssh_bootstrap as ssh, private_delivery as delivery
from tools import runpod_control as control, small_model_precheck as pre
from tools import small_model_lifecycle as life
from tools.free_container_cleanup import remove

ROOT = Path(__file__).resolve().parents[1]
PROFILE = 'actions-20261019'
EXTRA = ('tools/small_model_provider.py', 'tools/small_model_remote_watch.py',
         'tools/small_model_provider_probe.py', 'tools/cloud_transport.py',
         'tools/ssh_bootstrap.py', 'tools/private_delivery.py', 'tools/free_container_cleanup.py',
         'tools/cloud_offer.py', 'tools/cloud_inventory.py', 'tools/cloud_probe.py',
         'tools/research_entry_state.py', 'tools/research_entry_contract.py',
         'tests/test_small_model_provider.py', 'docs/cloud-controller-requirements.txt',
         '.github/workflows/small-model-provider-cpu.yml',
         '.github/workflows/small-model-provider-owner.yml',
         '.github/workflows/small-model-provider-watch.yml')


def sources():
    return dict(pre.sources(), **{p: life.digest((ROOT/p).read_bytes()) for p in EXTRA})


def payload(directory):
    directory.mkdir(mode=0o700)
    names = sorted(set(pre.sources()) | {'docs/small-model-gpu-baseline-v1.json'})
    rows = []
    for name in names:
        raw = (ROOT/name).read_bytes(); target = directory/name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.write_bytes(raw); target.chmod(0o600)
        rows.append({'path': name, 'bytes': len(raw), 'sha256': life.digest(raw)})
    return life.encoded({'schema_version': 1, 'phase': 'bootstrap', 'files': rows})


REMOTE = r'''
import hashlib,json,os,pathlib,platform,shutil,subprocess,sys
root=pathlib.Path('/root/backtrace/payload');sys.path.insert(0,str(root))
from tools import small_model_precheck as pre, small_model_resources as resources
manifest=json.loads((root/'delivery-manifest.json').read_bytes())
for r in manifest['files']:
 p=root/r['path'];assert not p.is_symlink() and len(p.read_bytes())==r['bytes']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
assert not any(k in ('RUNPOD_API_KEY','GITHUB_TOKEN') or k.startswith('BT_') for k in os.environ)
pre.prepare(root/'remote-plan.json')
r={'python':platform.python_version(),'uid':os.getuid(),'payload_files':len(manifest['files']),
 'payload_sha256':hashlib.sha256((root/'delivery-manifest.json').read_bytes()).hexdigest(),
 'prepared_plan_sha256':hashlib.sha256((root/'remote-plan.json').read_bytes()).hexdigest(),
 'credential_environment':'ABSENT','gpu_calls':0,'pretrained_requests':0,'training_steps':0,
 'tools':{n:shutil.which(n) for n in ('unshare','setpriv','bwrap')}}
if r['tools']['unshare']:
 p=subprocess.run(['unshare','--net','--pid','--fork','--mount-proc','true'],capture_output=True,text=True,timeout=5)
 r['namespace_entry']={'exit_code':p.returncode,'stderr':p.stderr[-400:]}
else:r['namespace_entry']={'exit_code':None,'stderr':'unshare missing'}
try:r['memory']=resources.inspect(minimum_bytes=8*resources.GIB)
except Exception as e:r['memory']={'status':'BLOCKED','error_type':type(e).__name__,'reason':str(e)[:200]}
r['checks']={'python_exact':r['python']=='3.12.14','root':r['uid']==0,'tools':all(r['tools'].values()),
 'namespaces':r['namespace_entry']['exit_code']==0,'memory':r['memory']['status']=='PASS'}
r['status']='PASS_NON_GPU_PREREQUISITES' if all(r['checks'].values()) else 'BLOCKED_NON_GPU_PREREQUISITES'
print(json.dumps(r,sort_keys=True))
'''


def qualify(output):
    output = Path(output).resolve(); output.mkdir(mode=0o700, parents=True, exist_ok=False)
    if list(Path('/dev').glob('nvidia[0-9]*')):
        raise ValueError('free CPU environment required')
    result = {'status': 'INCOMPLETE', 'scope': 'FREE_EXACT_IMAGE_NEW_PAYLOAD',
              'source_sha': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID'),
              'source_hashes': sources(), 'provider_api_calls': 0, 'gpu_calls': 0,
              'provider_network_nat': 'NOT_OBSERVED', 'provider_capabilities': 'NOT_OBSERVED',
              'image': control.BASE, 'container_mode': 'DEFAULT_UNPRIVILEGED_OCI',
              'full_runtime_installation': 'NOT_RUN', 'paid_launch_enabled': False}
    name = 'backtrace-free-full-setup-'+str(os.getpid())+'-small-provider'
    try:
        with tempfile.TemporaryDirectory(prefix='backtrace-small-provider-', dir='/root') as td:
            root = Path(td); result['transport_build'] = cloud_transport.build(root/'build')
            binaries = root/'build/dropbear-DROPBEAR_2026.94'
            init = ssh.prepare(binaries/'dropbear', binaries/'dropbearkey', root/'keys', profile=PROFILE)
            life.write(root/'keys/initializer.json', init)
            result['transport_material'] = ssh.validate_material(root/'keys', profile=PROFILE)
            env = root/'env'; env.write_text('\n'.join(k+'='+v for k,v in init['env'].items())+'\n'); env.chmod(0o600)
            manifest = payload(root/'payload'); (root/'manifest.json').write_bytes(manifest)
            result['payload_manifest'] = json.loads(manifest)
            with (output/'image.log').open('xb') as log:
                subprocess.run(['docker','pull',control.BASE],stdout=log,stderr=log,check=True,timeout=900)
                details = json.loads(subprocess.check_output(['docker','image','inspect',control.BASE],timeout=20))[0]
                if details['Architecture'] != 'amd64' or not any(d.endswith('@'+control.BASE.split('@')[1]) for d in details['RepoDigests']):
                    raise ValueError('image digest mismatch')
                result['image_id'] = details['Id']
                subprocess.run(['docker','run','-d','--rm','--name',name,'--env-file',str(env),
                    '-p','127.0.0.1::22','--entrypoint',init['entrypoint'][0],control.BASE,
                    *init['entrypoint'][1:],*init['cmd']],stdout=log,stderr=log,check=True,timeout=30)
                container = json.loads(subprocess.check_output(['docker','inspect',name],timeout=20))[0]
                result['container_id'] = container['Id']
                port = int(container['NetworkSettings']['Ports']['22/tcp'][0]['HostPort'])
                listener = "from pathlib import Path;raise SystemExit(0 if any(x.split()[1].endswith(':0016') and x.split()[3]=='0A' for x in Path('/proc/net/tcp').read_text().splitlines()[1:]) else 1)"
                end = time.monotonic()+30
                while True:
                    p = subprocess.run(['docker','exec',name,'/usr/bin/python3.12','-I','-c',listener],stdout=log,stderr=log,timeout=5)
                    if p.returncode == 0:break
                    if time.monotonic() >= end:raise TimeoutError('TLS listener absent')
                    time.sleep(.2)
                result['binary_transfer'] = ssh.deliver(root/'keys','127.0.0.1',port,60,profile=PROFILE)
                known = ssh.known_hosts(root/'keys','127.0.0.1',port)
                command = delivery.ssh_command('127.0.0.1',port,root/'keys/owner-key',known,
                    '/root/backtrace/payload',life.digest(manifest))
                ssh.wait_for_command(command[:-1], ['true'], 30, log=log)
                wrong = root/'wrong-hosts'
                wrong.write_text(f'[127.0.0.1]:{port} '+(root/'keys/owner-key.pub').read_text());wrong.chmod(0o600)
                bad = delivery.ssh_command('127.0.0.1',port,root/'keys/owner-key',wrong,
                    '/root/backtrace/unused','0'*64)[:-1]
                denied = subprocess.run(bad+['true'],capture_output=True,timeout=10,env={'PATH':'/usr/bin:/bin'})
                if denied.returncode == 0 or b'Host key verification failed' not in denied.stderr:
                    raise ValueError('wrong host was not refused')
                result['wrong_host_key'] = 'REFUSED'
                result['payload_transfer'] = delivery.push(root/'payload',root/'manifest.json',command,60)
                remote = subprocess.run(command[:-1]+[shlex.join(['/usr/bin/python3.12','-I','-c',REMOTE])],
                    capture_output=True,timeout=30,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
                if remote.returncode:
                    (output/'remote-error.log').write_bytes(remote.stderr[-8000:])
                    raise RuntimeError('remote payload preparation failed')
                observed = json.loads(remote.stdout)
                if (observed['payload_sha256'] != life.digest(manifest)
                        or observed['prepared_plan_sha256'] != life.digest((ROOT/'docs/small-model-precheck-plan-v1.json').read_bytes())):
                    raise ValueError('remote payload/plan bytes mismatch')
                result['remote'] = observed
                result.update(status='PASS_TRANSPORT', execution_environment=observed['status'])
    except Exception as error:
        result.update(status='FAIL',error_type=type(error).__name__)
        import traceback
        result['frames'] = [{'file':Path(f.filename).name,'function':f.name,'line':f.lineno}
                            for f in traceback.extract_tb(error.__traceback__)][-8:]
    finally:
        result['cleanup'] = remove(name, container_id=result.get('container_id'))
        if result['cleanup']['status'] != 'PASS':result['status'] = 'FAIL'
        life.write(output/'receipt.json',result)
    return result


if __name__ == '__main__':
    os.umask(0o077)
    result = qualify(sys.argv[1]); print(json.dumps(result,sort_keys=True))
    raise SystemExit(0 if result['status']=='PASS_TRANSPORT' else 1)
