"""Exact 246-wheel offline install for the inference-only payload; stdlib bootstrap."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.private_delivery import verify

INVENTORY_SHA256='72ec973f6e5cf390b891cf8f6354f0c5a95be5e6252c90976afad7ccf27be488'
WHEELS_SHA256='054e0e813a797e1eb4d76bab563b3bfbbefe104010391cec30f24d99a48da569'
OFFLINE="""import runpy,sys
def audit(event,args):
 if event in ('socket.connect','socket.getaddrinfo','socket.sendto','socket.sendmsg'):
  raise RuntimeError('offline serving install forbids networking')
sys.addaudithook(audit)
sys.path.insert(0,sys.argv.pop(1))
runpy.run_module('pip',run_name='__main__')
"""


def expected(path):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=INVENTORY_SHA256:raise ValueError('frozen serving inventory changed')
    rows=json.loads(raw)
    if len(rows)!=246:raise ValueError('complete serving closure required')
    return rows


def install(wheels,inventory,output,seconds=1800):
    if (os.geteuid()!=0 or platform.system()!='Linux' or platform.machine()!='x86_64'
            or sys.version_info[:2]!=(3,12) or not 0<seconds<=4020):
        raise ValueError('root Linux x86_64 Python 3.12 and bounded install required')
    wheels,output=Path(wheels),Path(output)
    rows=expected(inventory);manifest=(wheels/'delivery-manifest.json').read_bytes()
    if hashlib.sha256(manifest).hexdigest()!=WHEELS_SHA256:raise ValueError('wheel stream changed')
    verify(wheels,manifest,exact=True)
    if json.loads(manifest)['files']!=[{k:r[k] for k in ('path','bytes','sha256')} for r in rows]:
        raise ValueError('serving stream and dependency inventory differ')
    output.mkdir(mode=0o700);end=time.monotonic()+seconds
    env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':'/root','PIP_CONFIG_FILE':os.devnull,
         'PIP_NO_INDEX':'1','PIP_NO_CACHE_DIR':'1','PYTHON_DOTENV_DISABLED':'1',
         'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OTEL_SDK_DISABLED':'true'}
    python=output/'venv/bin/python';pip=next(r for r in rows if r['name']=='pip')
    lock=output/'runtime.lock'
    lock.write_text(''.join(r['name']+'=='+r['version']+' --hash=sha256:'+r['sha256']+'\n' for r in rows))
    def run(argv,capture=False):
        left=end-time.monotonic()
        if left<=0:raise TimeoutError('serving install deadline')
        return subprocess.run(argv,check=True,timeout=left,env=env,stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE if capture else None)
    run([sys.executable,'-I','-m','venv','--without-pip',str(output/'venv')])
    run([str(python),'-I','-c',OFFLINE,str(wheels/pip['path']),'install','--no-index','--no-deps',
         '--require-hashes','--only-binary=:all:','--find-links='+str(wheels),'-r',str(lock)])
    run([str(python),'-I','-c',OFFLINE,str(wheels/pip['path']),'check'])
    program="""import importlib.metadata as m,json,sys
def audit(event,args):
 if event in ('socket.connect','socket.getaddrinfo','socket.sendto','socket.sendmsg'):
  raise RuntimeError('offline serving imports forbid networking')
sys.addaudithook(audit)
import torch,vllm,compressed_tensors,transformers,adk_submission
print(json.dumps(sorted([{'name':d.metadata['Name'],'version':d.version} for d in m.distributions()],key=lambda r:r['name'].lower())))
"""
    actual=json.loads(run([str(python),'-I','-c',program],True).stdout.splitlines()[-1])
    normalize=lambda name:re.sub(r'[-_.]+','-',name).lower()
    wanted={normalize(r['name']):r['version'] for r in rows}
    if {normalize(r['name']):r['version'] for r in actual}!=wanted or len(actual)!=len(rows):
        raise ValueError('installed serving inventory differs')
    (output/'inventory.json').write_text(json.dumps(actual,sort_keys=True))
    report={'status':'PASS','packages':len(actual),'offline':True,'model_execution':'NOT_RUN',
            'wheel_manifest_sha256':WHEELS_SHA256,'inventory_source_sha256':INVENTORY_SHA256,
            'inventory_sha256':hashlib.sha256((output/'inventory.json').read_bytes()).hexdigest()}
    (output/'receipt.json').write_text(json.dumps(report,sort_keys=True));return report


if __name__=='__main__':
    print(json.dumps(install(*sys.argv[1:4],seconds=float(sys.argv[4])),sort_keys=True))
