"""Free exact-image prerequisite probe; no model bytes or provider credential.

The default OCI capability profile is a replica, not an assertion about the
provider's actual container configuration. Failure stops before runtime transfer.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

from tools import research_comparison as c
from tools.free_container_cleanup import remove

PROBE = r'''
import json,os,pathlib,platform,shutil,subprocess
tools={name:shutil.which(name) for name in ('unshare','nsenter','setpriv','ip')}
status=dict(line.split(':',1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
result={'uid':os.getuid(),'python':platform.python_version(),'tools':tools,
        'effective_capabilities':status.get('CapEff','').strip(),
        'no_new_privileges':status.get('NoNewPrivs','').strip()}
if tools['unshare']:
 p=subprocess.run([tools['unshare'],'--net','--pid','--fork','--mount-proc','true'],capture_output=True,text=True,timeout=5)
 result['namespace_entry']={'exit_code':p.returncode,'stderr':p.stderr[-1000:]}
else: result['namespace_entry']={'exit_code':None,'stderr':'unshare missing'}
print(json.dumps(result))
'''


def run(output):
    output = Path(output); output.mkdir(mode=0o700)
    image = c.load_protocol()['environment']['image']
    report = {'status': 'INCOMPLETE', 'scope': 'FREE_EXACT_IMAGE_DEFAULT_OCI_PREREQUISITES',
        'source_sha': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID'),
        'image': image, 'model_files_transferred': 0, 'gpu_allocations': 0,
        'provider_configuration': 'NOT OBSERVED; default OCI replica only'}
    name = 'backtrace-free-full-setup-' + str(os.getpid()) + '-research-probe'
    try:
        host = subprocess.run(['unshare','--net','--pid','--fork','--mount-proc','true'],
                              capture_output=True,text=True,timeout=10)
        report['host_namespace_entry'] = {'exit_code': host.returncode, 'stderr': host.stderr[-1000:]}
        with (output/'image-pull.log').open('wb') as stream:
            subprocess.run(['docker','pull',image],stdout=stream,stderr=stream,check=True,timeout=900)
        details = json.loads(subprocess.check_output(['docker','image','inspect',image],timeout=30))
        if (len(details)!=1 or details[0]['Architecture']!='amd64' or details[0]['Os']!='linux'
                or not any(d.endswith('@'+image.split('@')[1]) for d in details[0]['RepoDigests'])):
            raise ValueError('exact image identity mismatch')
        report['image_id'] = details[0]['Id']
        child = subprocess.run(['docker','run','--rm','--name',name,'--network','none',
            '--security-opt','no-new-privileges','--entrypoint','/usr/bin/python3.12',image,
            '-I','-c',PROBE],capture_output=True,text=True,timeout=30)
        (output/'image-probe.stderr').write_text(child.stderr)
        if child.returncode: raise ValueError('image prerequisite probe did not execute')
        observed = json.loads(child.stdout); report['observed'] = observed
        report['checks'] = {'host_namespace_reference':host.returncode==0,
            'root_image_entry':observed['uid']==0,
            'required_tools':all(observed['tools'].values()),
            'image_namespace_entry':observed['namespace_entry']['exit_code']==0}
        report['status'] = 'PASS' if all(report['checks'].values()) else 'BLOCKED'
    except Exception as error:
        report.update(status='FAIL',error_type=type(error).__name__)
    finally:
        try:
            report['cleanup'] = remove(name)
        except Exception as error:
            report['cleanup'] = {'status': 'FAIL', 'error_type': type(error).__name__}
        if report['cleanup']['status']!='PASS': report['status']='FAIL'
        report['source_sha256'] = c.digest(Path(__file__).read_bytes())
        c._new_output(output/'deployment.json', c.encoded(report))
    return report


if __name__ == '__main__':
    value=run(sys.argv[1]); print(json.dumps(value,sort_keys=True))
    raise SystemExit(0 if value['status']=='PASS' else 1)
