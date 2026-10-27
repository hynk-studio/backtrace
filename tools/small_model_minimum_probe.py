"""Free exact-image integration of the complete hardware diagnostic entry."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

from tools import small_model_minimum as minimum, small_model_minimum_remote as remote
from tools import runpod_control as control, small_model_lifecycle as life
from tools.free_container_cleanup import remove


def qualify(wheels,transport,output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    result={'status':'INCOMPLETE','source_sha':os.environ.get('GITHUB_SHA'),'source_hashes':minimum.sources(),'actual_gpu':False,'provider_create_requests':0}
    name='backtrace-free-full-setup-'+str(os.getpid())+'-minimum';container_id=None
    try:
        if list(Path('/dev').glob('nvidia[0-9]*')):raise ValueError('CPU-only qualification required')
        with tempfile.TemporaryDirectory(prefix='backtrace-minimum-',dir='/root') as td:
            root=Path(td)/'prepared';init=remote.prepare(root,wheels,transport)
            result['preparation']=json.loads((root/'preparation.json').read_bytes())
            env=Path(td)/'env';env.write_text('\n'.join(k+'='+v for k,v in init['env'].items())+'\n');env.chmod(0o600)
            with (output/'image.log').open('xb') as log:
                subprocess.run(['docker','pull',control.BASE],stdout=log,stderr=log,check=True,timeout=900)
                subprocess.run(['docker','run','-d','--rm','--name',name,'--memory','6g','--memory-swap','6g',
                    '--env-file',str(env),'-p','127.0.0.1::22','--entrypoint',init['entrypoint'][0],control.BASE,
                    *init['entrypoint'][1:],*init['cmd']],stdout=log,stderr=log,check=True,timeout=30)
                info=json.loads(subprocess.check_output(['docker','inspect',name],timeout=20))[0];container_id=info['Id']
                if info['HostConfig']['Privileged'] or info['HostConfig']['CapAdd'] or info['Mounts']:raise ValueError('ordinary container required')
                port=int(info['NetworkSettings']['Ports']['22/tcp'][0]['HostPort'])
                end=time.monotonic()+30
                while True:
                    p=subprocess.run(['docker','exec',name,'/usr/bin/python3.12','-I','-c',
                        "from pathlib import Path;raise SystemExit(0 if any(x.split()[1].endswith(':0016') and x.split()[3]=='0A' for x in Path('/proc/net/tcp').read_text().splitlines()[1:]) else 1)"],stdout=log,stderr=log,timeout=5)
                    if not p.returncode:break
                    if time.monotonic()>=end:raise TimeoutError('bootstrap listener absent')
                    time.sleep(.2)
            result['connected']=remote.connected(root,{'host':'127.0.0.1','port':port},output/'remote',actual=False)
            if result['connected']['status']!='PASS_FREE_HARDWARE_PATH_CONTROLS':raise RuntimeError('free hardware entry failed')
            result['status']='PASS_FREE_MINIMUM_ENTRY'
    except Exception as e:
        result.update(status='FAIL',error_type=type(e).__name__,error=str(e)[:500],
            frames=[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(e.__traceback__)][-8:])
    finally:
        result['cleanup']=remove(name,container_id=container_id)
        if result['cleanup']['status']!='PASS':result['status']='FAIL'
        life.write(output/'receipt.json',result)
    return result


if __name__=='__main__':
    os.umask(0o077);r=qualify(*(Path(x).resolve() for x in sys.argv[1:]));print(json.dumps(r,sort_keys=True))
    raise SystemExit(0 if r['status']=='PASS_FREE_MINIMUM_ENTRY' else 1)
