"""One owner-authorized input-free boot/TLS/SSH experiment, not a model run."""
import argparse
import base64
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

from tools import cloud_state as state, cloud_owner, cloud_watch, cloud_bootstrap
from tools import runpod_control as control, ssh_bootstrap as ssh, cloud_transport, cloud_seal
from tools.a100_delivery import ROOT
from tools.runpod_job import check_owner_host, heartbeat, private_json, read_private
from tools.private_delivery import ssh_command
from tools.cloud_qualification import PATHS as BASE_BOUND

AUTHORIZATION = 'owner-bootstrap-probe-20261022'
REVIEW = 'bt-001-bootstrap-probe'
START = 'bt-001-a100-start-bootstrap-probe'
WATCH = 'bt-001-a100-watch-bootstrap-probe'
PROFILE = 'actions-20261019'


class ProbeFailure(RuntimeError):
    def __init__(self, stage, error_type, *, returncode=None, private_output=b''):
        super().__init__('bounded diagnostic stage failed')
        self.diagnostic = {'status':'INCOMPLETE','stage':stage,'error_type':error_type,
                           'returncode':returncode,
                           'private_output_sha256':hashlib.sha256(private_output).hexdigest()}
        self.private_output = private_output[-8192:]
BOUND = tuple(sorted([
    'tools/' + n + '.py' for n in ('bootstrap_probe', 'cloud_state', 'cloud_owner', 'cloud_watch',
      'cloud_bootstrap', 'runpod_control', 'ssh_bootstrap', 'cloud_transport', 'cloud_seal',
      'cloud_offer', 'cloud_inventory', 'cloud_probe', 'runpod_job', 'private_delivery', 'a100_delivery')]
    + ['tests/' + n + '.py' for n in ('test_bootstrap_probe', 'test_cloud_state', 'test_cloud_owner',
       'test_cloud_bootstrap', 'test_runpod_control', 'official_cloud_transport', 'official_cloud_lifecycle')]
    + ['docs/a100-result-recipient.txt', 'docs/cloud-controller-requirements.txt',
       '.github/workflows/a100-cpu.yml', '.github/workflows/bootstrap-probe-qualify.yml',
       '.github/workflows/bootstrap-probe-start.yml', '.github/workflows/bootstrap-probe-watch.yml']))
BOUND = tuple(sorted(set(BOUND) | set(BASE_BOUND) | {'.github/workflows/bootstrap-probe-access.yml'}))


@contextmanager
def scope():
    """Fixed separately authorized namespace, branches and stricter deadlines.

    No runtime-supplied namespace, old claim deletion, branch retargeting or
    modification of old state bytes. Each controller process uses one scope.
    """
    changes = {'AUTHORIZATION': AUTHORIZATION, 'DIRECTORY': 'a100-state/' + AUTHORIZATION,
               'POLICY': 'prepaid10-bootstrap-probe-v1', 'SETUP': 1500, 'USEFUL': 1500,
               'TOTAL': 1800, 'OWNER_BRANCH': START, 'WATCH_BRANCH': WATCH,
               'DOCUMENTS': state.DOCUMENTS | {'observation'}}
    previous = {k: getattr(state, k) for k in changes}; run = control.RUN
    try:
        for k, v in changes.items(): setattr(state, k, v)
        control.RUN = 'bootstrap-only/A10080-TP1'
        yield
    finally:
        for k, v in previous.items(): setattr(state, k, v)
        control.RUN = run


def validate_context(mode, environ):
    branches = {'qualify': REVIEW, 'paid': START, 'watch': WATCH, 'access': REVIEW}
    if (mode not in branches or environ.get('GITHUB_REPOSITORY') != state.REPOSITORY
            or environ.get('GITHUB_REF_NAME') != branches[mode]
            or (environ.get('GITHUB_RUN_ATTEMPT') != '1' and
                not (mode == 'access' and str(environ.get('GITHUB_RUN_ATTEMPT','')).isdigit()
                     and int(environ['GITHUB_RUN_ATTEMPT']) > 0))):
        raise state.StateError('exact first diagnostic workflow context required')


def hashes():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in BOUND}


def require_qualification(store, source):
    receipt = json.loads((ROOT / 'docs/bootstrap-probe-receipt.json').read_text())
    report = (ROOT / 'docs/bootstrap-probe-qualification.json').read_bytes()
    if (receipt['files'] != hashes() or receipt['report_sha256'] != hashlib.sha256(report).hexdigest()):
        raise ValueError('diagnostic qualification does not bind current source')
    run = store.request('GET', '/actions/runs/' + str(receipt['run_id']))
    if (run.get('status') != 'completed' or run.get('conclusion') != 'success'
            or run.get('run_attempt') != 1 or run.get('head_sha') != receipt['source_sha']
            or run.get('head_branch') != REVIEW
            or run.get('path') != '.github/workflows/bootstrap-probe-qualify.yml'):
        raise ValueError('diagnostic qualification run is not successful at its recorded source')
    report_value = json.loads(report)
    if report_value.get('status') != 'PASS' or report_value.get('files') != receipt['files']:
        raise ValueError('diagnostic report is incomplete')
    runs = store.request('GET', '/actions/runs?head_sha=' + source + '&per_page=100')['workflow_runs']
    cpu = [r for r in runs if r.get('path') == '.github/workflows/a100-cpu.yml'
           and r.get('head_branch') == REVIEW and r.get('head_sha') == source]
    if (len(cpu) != 1 or cpu[0].get('run_attempt') != 1 or cpu[0].get('status') != 'completed'
            or cpu[0].get('conclusion') != 'success'):
        raise ValueError('exact-source diagnostic CPU suite is not successful')
    return {'run_id': receipt['run_id'], 'source_sha': receipt['source_sha'],
            'bound_files': len(BOUND), 'cpu_run_id': cpu[0]['id']}


def remote_program(gpu_required):
    return '''import os,json,subprocess,sys
assert os.getuid()==0
assert not any(k.startswith('BT_') or k in ('RUNPOD_API_KEY','GITHUB_TOKEN','KAGGLE_API_TOKEN') for k in os.environ)
r={'root':True,'clean_environment':True,'python':sys.version.split()[0],'model_execution':'NOT RUN'}
''' + ('''p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,timeout=15)
rows=[x.strip().split(', ') for x in p.stdout.strip().splitlines()]
assert len(rows)==1 and len(rows[0])==3
assert 'A100' in rows[0][0] and float(rows[0][1])>=79000
r['gpu']={'name':rows[0][0],'memory_mib':float(rows[0][1]),'driver':rows[0][2]}
''' if gpu_required else "r['gpu']='NOT RUN: free CPU image'\n") + 'print(json.dumps(r,sort_keys=True))\n'


def connect(root, endpoint, *, gpu_required, emit=lambda row: None):
    stage = 'mutual_tls_transfer'; started = time.monotonic()
    emit({'stage': stage, 'status': 'STARTED'})
    try:
        transfer = ssh.deliver(root, endpoint['host'], endpoint['port'], 120, profile=PROFILE)
    except Exception as error:
        raise ProbeFailure(stage,type(error).__name__) from None
    emit({'stage': stage, 'status': 'PASS'})
    stage = 'pinned_ssh'; known = ssh.known_hosts(root, endpoint['host'], endpoint['port'])
    prefix = ssh_command(endpoint['host'], endpoint['port'], Path(root) / 'owner-key', known,
                         '/root/backtrace/unused', '0' * 64)[:-1]
    emit({'stage':stage,'status':'STARTED'})
    try:
        process = ssh.wait_for_command(prefix, ['python3', '-I', '-c', remote_program(gpu_required)], 60)
    except subprocess.CalledProcessError as error:
        raise ProbeFailure('pinned_ssh' if error.returncode == 255 else 'ssh_remote_probe',
            'RemoteCommandError', returncode=error.returncode, private_output=error.stderr or b'') from None
    except (subprocess.TimeoutExpired, TimeoutError) as error:
        raise ProbeFailure(stage, 'TimeoutExpired', private_output=getattr(error, 'stderr', None) or b'') from None
    try: result = json.loads(process.stdout)
    except ValueError:
        raise ProbeFailure('ssh_remote_probe','InvalidJSON',private_output=process.stdout) from None
    emit({'stage': stage, 'status': 'PASS'})
    return {'status': 'PASS', 'mutual_tls': transfer, 'ssh': result,
            'elapsed_seconds': round(time.monotonic() - started, 3)}


def run_worker(directory):
    check_owner_host()
    if any(k in os.environ for k in ('GITHUB_TOKEN','RUNPOD_API_KEY','GH_STATE_TOKEN','KAGGLE_API_TOKEN')):
        raise ValueError('diagnostic child inherited service credentials')
    root = Path(directory); plan = json.loads(read_private(root / 'probe-plan.json'))
    done = threading.Event(); result = {'status': 'INCOMPLETE', 'stage': 'mutual_tls_or_ssh'}
    def beat():
        while not done.is_set():
            heartbeat(root, plan['claim']['attempt'], 'running', 'setup'); done.wait(2)
    thread = threading.Thread(target=beat, daemon=True); thread.start()
    try:
        result = connect(plan['ssh_directory'], plan['endpoint'], gpu_required=True,
            emit=lambda row: private_json(root / 'setup-status.json', row))
        return 0
    except Exception as error:
        if isinstance(error,ProbeFailure):
            result=error.diagnostic
            sys.stderr.buffer.write(error.private_output);sys.stderr.buffer.flush()
        else: result['error_type'] = type(error).__name__
        return 1
    finally:
        done.set(); thread.join(timeout=3)
        private_json(root / 'bootstrap-probe-result.json', result)
        heartbeat(root, plan['claim']['attempt'], 'finished', 'retrieval')


def spawn_worker(directory, configuration, claim, pod_id, endpoint):
    private_json(Path(directory) / 'probe-plan.json',
                 {'claim': claim, 'endpoint': endpoint, 'ssh_directory': configuration['ssh_directory']})
    log = (Path(directory) / 'probe.log').open('xb')
    try:
        return subprocess.Popen([sys.executable, '-I', '-c',
            'import sys;sys.path.insert(0,'+repr(str(ROOT))+');from tools.bootstrap_probe import run_worker;raise SystemExit(run_worker(sys.argv[1]))',
            str(directory)], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}, start_new_session=True)
    finally: log.close()


def transport(root):
    built = cloud_transport.build(root / 'transport')
    if not built['matches_prior_transport']:
        raise ValueError('diagnostic transport differs from fixed hashes')
    return root / 'transport/dropbear-DROPBEAR_2026.94', built


def qualify(root):
    from tests.official_cloud_transport import qualify as host_transport
    from tests.official_cloud_lifecycle import scenario
    binaries, built = transport(root)
    report = {'status': 'RUNNING', 'files': hashes(), 'transport': built, 'paid_operations': 0}
    report['stages']={}; failed=[]
    def check(name,operation):
        print(json.dumps({'qualification_stage':name,'status':'STARTED'}),flush=True)
        try:
            value=operation()
            report['stages'][name]={'status':'PASS','result':value}
        except Exception as error:
            failed.append(name)
            value={'error_type':type(error).__name__}
            if isinstance(error,ProbeFailure):value.update(error.diagnostic)
            report['stages'][name]={'status':'FAIL','failure':value}
        private_json(root/'qualification-progress.json',report)
        print(json.dumps({'qualification_stage':name,'status':report['stages'][name]['status']}),flush=True)
    check('host_transport',lambda:host_transport(binaries/'dropbear',binaries/'dropbearkey',PROFILE))
    check('exact_image_transport',lambda:qualify_image(root,binaries))
    for name in ('success','worker_failure','stale_worker','state_http_failure',
                 'owner_cancelled','bootstrap_delayed','bootstrap_timeout'):
        check('lifecycle_'+name,lambda name=name:scenario(name))
    report.update(status='FAIL' if failed else 'PASS',failed_stages=failed)
    return report


def qualify_image(root,binaries):
    with tempfile.TemporaryDirectory(prefix='backtrace-image-boot-', dir='/root') as td:
        work = Path(td)
        initializer = ssh.prepare(binaries / 'dropbear', binaries / 'dropbearkey', work / 'ssh', profile=PROFILE)
        private_json(work / 'ssh/initializer.json', initializer)
        env_file = work / 'env'; env_file.write_text('\n'.join(k+'='+v for k,v in initializer['env'].items())+'\n'); env_file.chmod(0o600)
        name = 'backtrace-bootstrap-cpu-' + os.environ['GITHUB_RUN_ID']
        with (root / 'image.log').open('w') as log:
            subprocess.run(['docker','pull',control.BASE],stdout=log,stderr=log,check=True,timeout=900)
            inspect = json.loads(subprocess.check_output(['docker','image','inspect',control.BASE],timeout=20))[0]
            assert inspect['Architecture']=='amd64' and any(x.endswith('@'+control.BASE.split('@')[1]) for x in inspect['RepoDigests'])
            try:
                subprocess.run(['docker','run','-d','--rm','--name',name,'--env-file',str(env_file),
                    '-p','127.0.0.1::22','--entrypoint',initializer['entrypoint'][0],control.BASE,
                    *initializer['entrypoint'][1:],*initializer['cmd']],stdout=log,stderr=log,check=True,timeout=30)
                value = json.loads(subprocess.check_output(['docker','inspect',name],timeout=20))[0]
                port = int(value['NetworkSettings']['Ports']['22/tcp'][0]['HostPort'])
                # Docker publishes a proxy before the container's Python TLS
                # receiver binds port 22. Inspect the actual listener, instead
                # of equating published-port metadata with a ready receiver.
                listener_check=("from pathlib import Path;raise SystemExit(0 if any("
                    "x.split()[1].endswith(':0016') and x.split()[3]=='0A' for x in "
                    "Path('/proc/net/tcp').read_text().splitlines()[1:]) else 1)")
                deadline=time.monotonic()+30
                while True:
                    ready=subprocess.run(['docker','exec',name,'/usr/bin/python3.12','-I','-c',listener_check],
                        stdout=log,stderr=log,timeout=5)
                    if ready.returncode==0:break
                    if time.monotonic()>=deadline:raise TimeoutError('image receiver did not listen')
                    time.sleep(.2)
                result=connect(work/'ssh',{'host':'127.0.0.1','port':port},gpu_required=False)
                return dict(result,image=control.BASE,image_id=inspect['Id'],listener_observed=True)
            finally:
                with (root/'image-container.log').open('wb') as container_log:
                    subprocess.run(['docker','logs','--tail','100',name],stdout=container_log,
                                   stderr=container_log,timeout=10)
                subprocess.run(['docker','rm','-f',name],stdout=log,stderr=log,timeout=20)


def paid(root):
    from tools.cloud_offer import inspect_offer
    store = state.GitHubState(os.environ['GITHUB_TOKEN'])
    if store.read('claim') is not None: raise state.StateError('diagnostic authorization already consumed')
    qualified = require_qualification(store, os.environ['GITHUB_SHA'])
    binaries, built = transport(root)
    initializer = ssh.prepare(binaries/'dropbear',binaries/'dropbearkey',root/'ssh',profile=PROFILE)
    private_json(root/'ssh/initializer.json',initializer); ssh.validate_material(root/'ssh',profile=PROFILE)
    offer = inspect_offer(); print(json.dumps({'fresh_offer':offer}),flush=True)
    if offer['status']!='QUALIFIED': return {'status':'NO_QUALIFIED_STOCK','allocation_requests':0,'availability':offer}
    if control.money(offer['costs']['hourly_all_in'])>Decimal('1.804'):
        raise ValueError('diagnostic quote exceeds existing hourly bound')
    api = control.RunpodAPI(os.environ['RUNPOD_API_KEY'].strip())
    samples=[]; last=[0]; observation_sha=[None]
    def emit(row):
        print(json.dumps(row,sort_keys=True),flush=True)
        if 'bootstrap' not in row or time.time()-last[0]<60: return
        last[0]=time.time(); sample=cloud_bootstrap.sample_logs(api,row['pod_id']); samples.append(sample)
        claim=store.read('claim')[0]; observed=row['bootstrap']
        public={'attempt':claim['attempt'],'at':int(time.time()),
            'provider_status':observed['provider_status'],'readiness':observed['readiness'],
            'direct_endpoint_present':observed.get('direct_endpoint_present',False),
            'direct_endpoint_valid':observed.get('direct_endpoint_valid',False),
            'log_status':sample.get('status','SAMPLED'),'log_events':sample.get('events',0)}
        try: observation_sha[0]=store.write('observation',public,previous_sha=observation_sha[0])
        except state.StateError: print(json.dumps({'observation_publish':'UNAVAILABLE'}),flush=True)
    result=cloud_owner.execute(store,api,offer['offer'],initializer,{'ssh_directory':str(root/'ssh')},
        root,os.environ['GITHUB_RUN_ID'],os.environ['GITHUB_SHA'],spawn=spawn_worker,emit=emit,
        before_cleanup=lambda pod_id:cloud_bootstrap.sample_logs(api,pod_id))
    result.update(authorization=AUTHORIZATION,qualification=qualified,log_samples=samples,
                  purpose='BOOTSTRAP ONLY; no model/task',availability=offer)
    probe=root/'bootstrap-probe-result.json'
    result['probe']=json.loads(read_private(probe)) if probe.exists() else {'status':'NOT RUN'}
    result['private_evidence']=cloud_owner.seal_results(root,ROOT/'evidence/bootstrap-probe-private.age')
    return result


def access():
    from tools.cloud_offer import inspect_offer
    api=control.RunpodAPI(os.environ['RUNPOD_API_KEY'].strip()); pods=api.list()
    store=state.GitHubState(os.environ['GITHUB_TOKEN']); recorded=store.read('pod')
    return {'observed_at':control.utc(time.time()),'pod_count':len(pods),
        'owned_pod_status':('ABSENT' if recorded and api.get(recorded[0]['pod_id']) is None else 'NOT_ABSENT_OR_NOT_RECORDED'),
        'availability':inspect_offer(),'provider_mutations':0}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['qualify','paid','watch','access']);args=parser.parse_args()
    os.umask(0o077);validate_context(args.mode,os.environ);check_owner_host()
    root=ROOT/'.local/bootstrap-probe';root.mkdir(mode=0o700,parents=True)
    (ROOT/'evidence').mkdir(exist_ok=True)
    with scope():
        try:
            if args.mode=='qualify': result=qualify(root)
            elif args.mode=='paid': result=paid(root)
            elif args.mode=='access': result=access()
            else: result=cloud_watch.watch(state.GitHubState(os.environ['GITHUB_TOKEN']),
                control.RunpodAPI(os.environ['RUNPOD_API_KEY'].strip()),os.environ['GITHUB_RUN_ID'],os.environ['GITHUB_SHA'])
        except Exception as error:
            result={'status':'BLOCKED','error_type':type(error).__name__,'http_status':getattr(error,'http_status',None)}
            if isinstance(error,ProbeFailure): result['diagnostic']=error.diagnostic
            progress=root/'qualification-progress.json'
            if args.mode=='qualify' and progress.exists():result['partial']=json.loads(read_private(progress))
        if args.mode=='qualify':
            logs={n:root/n for n in ('image.log','image-container.log') if (root/n).is_file()}
            if logs:result['private_evidence']=cloud_seal.seal(logs,ROOT/'evidence/bootstrap-qualification-private.age')
        path=ROOT/'evidence'/('bootstrap-probe-'+args.mode+'.json')
        path.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True),flush=True)
        if result.get('status') in ('BLOCKED','INCOMPLETE','FAIL') or (args.mode=='watch' and result.get('phase') not in ('deleted','no_claim')):
            raise SystemExit(1)


if __name__=='__main__': main()
