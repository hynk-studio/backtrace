"""Owner-side pinned delivery and hardware-only diagnostics over authenticated SSH."""
import contextlib
import json
import os
from pathlib import Path
import shlex
import signal
import shutil
import subprocess
import time

from tools import small_model_container as container, small_model_gpu as gpu
from tools import small_model_runner as runner, small_model_lifecycle as life
from tools import ssh_bootstrap as ssh, private_delivery as delivery, runpod_control as control

ROOT=Path(__file__).resolve().parents[1]


def prepare(root,wheels,transport):
    root=Path(root).resolve();root.mkdir(mode=0o700)
    transport=Path(transport);binaries=transport/'dropbear-DROPBEAR_2026.94'
    initializer=ssh.prepare(binaries/'dropbear',binaries/'dropbearkey',root/'keys',profile='actions-20261019')
    life.write(root/'keys/initializer.json',initializer)
    raw,receipt=container.runtime_payload(root/'runtime',Path(wheels))
    shutil.copyfile(ROOT/'tools/small_model_minimum_worker.py',root/'runtime/minimum.py')
    subprocess.run(['gcc','-std=c11','-O2','-fPIC','-shared','-Wall','-Wextra','-Werror',
        '-Wl,-z,relro,-z,now','-o',str(root/'runtime/denial-trace.so'),
        str(ROOT/'tools/small_model_minimum_trace.c')],check=True,timeout=30)
    raw=container.manifest(root/'runtime');(root/'runtime-manifest.json').write_bytes(raw)
    life.write(root/'preparation.json',{'runtime':receipt,'manifest':json.loads(raw),
        'transport':ssh.validate_material(root/'keys',profile='actions-20261019'),
        'weight_bytes':0,'pretrained_requests':0,'training_steps':0})
    return initializer


def prefix_for(root,host,port):
    known=ssh.known_hosts(root/'keys',host,port)
    return delivery.ssh_command(host,port,root/'keys/owner-key',known,'/root/backtrace/runtime',
        life.digest((root/'runtime-manifest.json').read_bytes()))[:-1]


def remote(prefix,code,seconds=30):
    p=subprocess.run(prefix+[shlex.join(['/usr/bin/python3.12','-I','-c',code])],
        capture_output=True,timeout=seconds,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    if p.returncode:raise RuntimeError('remote trusted command failed: '+p.stderr[-1000:].decode(errors='replace'))
    if len(p.stdout)>1024**2:raise ValueError('bounded remote diagnostic required')
    return json.loads(p.stdout)


def command(prefix,mode,seconds,actual):
    if mode not in ('boundary','memory','cpu-hold','kernels','active','diagnostic-a','diagnostic-b','diagnostic-c','diagnostic-d') or not 0<seconds<=180:
        raise ValueError('bounded hardware-only diagnostic required')
    if mode.startswith('diagnostic-') and seconds > 30:
        raise ValueError('diagnostic case ceiling is 30 seconds')
    return prefix+[shlex.join(['/usr/bin/env','-i','PATH=/usr/bin:/bin','LANG=C.UTF-8',
        'LD_LIBRARY_PATH=/opt/backtrace/python/lib','/opt/backtrace/venv/bin/python','-I',
        '/opt/backtrace/minimum.py','run',mode,str(seconds),
        '/opt/backtrace/minimum-gpu.json' if actual else '/opt/backtrace/minimum-cpu.json'])]


def state(prefix):
    return remote(prefix,"""import json,pathlib
r=json.loads(pathlib.Path('/root/backtrace/minimum-state.json').read_bytes())
try:
 s=pathlib.Path('/proc',str(r['pid']),'stat').read_text().split();r['same_process_alive']=s[21]==r['start_ticks'];r['process_state']=s[2]
except (FileNotFoundError,ProcessLookupError):r['same_process_alive']=False;r['process_state']='ABSENT'
print(json.dumps(r))
""")


def diagnostic_decision(rows, actual):
    """Classify only comparable, complete observations; never prescribe a relaxation."""
    if set(rows) != {'A', 'B', 'C'}:
        return 'INCONCLUSIVE_STOP_SAME_ROUTE'
    if any(row.get('error') or row.get('exit_code') != 0 for row in rows.values()):
        return 'INCONCLUSIVE_STOP_SAME_ROUTE'
    try:
        identities = [rows[key]['before']['identity'] for key in 'ABC']
        a, b, c = identities
        common = ('limits', 'python', 'executable', 'cuda_visible_devices', 'environment_sha256')
        if any(any(value[name] != a[name] for name in common) for value in identities):
            return 'INCOMPARABLE_STOP_SAME_ROUTE'
        if a['Uid'].split() != ['0']*4:
            return 'INCOMPARABLE_STOP_SAME_ROUTE'
        for value in (b, c):
            if (value['Uid'].split() != ['65532']*4 or value['Gid'].split() != ['65532']*4
                    or value['Groups'] or value['NoNewPrivs'] != '1'
                    or any(int(value[name], 16) for name in ('CapEff', 'CapPrm', 'CapBnd'))):
                return 'INCOMPARABLE_STOP_SAME_ROUTE'
        if int(b['Seccomp_filters']) != int(a['Seccomp_filters']) or int(c['Seccomp_filters']) != int(b['Seccomp_filters'])+1:
            return 'INCOMPARABLE_STOP_SAME_ROUTE'
        # Failure can prevent a library from loading. Missing post-probe mappings
        # are an outcome, not proof that the starting environments differed.
        libraries = [rows[key]['result']['cuda_libraries'] for key in 'ABC']
        seen = {}
        for mapping in libraries:
            for path, value in mapping.items():
                if path in seen and seen[path] != value:
                    return 'INCOMPARABLE_STOP_SAME_ROUTE'
                seen[path] = value
        statuses = [rows[key]['result']['status'] for key in 'ABC']
        if any(status not in ('PASS_ACTUAL_CUDA_KERNELS', 'FAIL') for status in statuses):
            return 'INCONCLUSIVE_STOP_SAME_ROUTE'
        passed = [status == 'PASS_ACTUAL_CUDA_KERNELS' for status in statuses]
    except (KeyError, TypeError, ValueError):
        return 'INCONCLUSIVE_STOP_SAME_ROUTE'
    if not actual:
        return 'CPU_CONTROLS_ONLY'
    # Failure labels may describe different stages (initialization versus
    # identity/memory/kernel checks). They do not identify a common root cause.
    return {(False, False, False): 'ALL_PRIMARY_PROBES_FAILED_CAUSE_UNRESOLVED_STOP',
            (True, False, False): 'WORKER_IDENTITY_LIMIT_LAYER',
            (True, True, False): 'ADDED_FILTER_IMPLICATED_SYSCALL_UNRESOLVED',
            (True, True, True): 'CUDA_PATH_WORKS_FAILURE_NOT_REPRODUCED'}.get(
                tuple(passed), 'NONMONOTONIC_INCONCLUSIVE_STOP_SAME_ROUTE')


def diagnose(prefix, output, *, actual, trace=False):
    """Three bounded fresh processes on an already-installed host; no allocation API."""
    output = Path(output); output.mkdir(mode=0o700, parents=True, exist_ok=False)
    receipt = {'actual_gpu': actual, 'cases': {}, 'decision': 'INCOMPLETE',
               'denied_syscall_trace': 'NOT_COLLECTED', 'automatic_retry': False}
    life.write(output/'started.json', receipt)
    for case in ('ABCD' if trace else 'ABC'):
        row = {}; receipt['cases'][case] = row
        channel = None
        try:
            channel = container.ContainerChannel(command(prefix, 'diagnostic-'+case.lower(), 30, actual), output/(case+'-stderr.log'))
            deadline = time.monotonic()+35
            row['result'] = channel.read(deadline)
            if row['result'].get('case') != case or row['result'].get('phase') != 'RESULT':
                raise ValueError('diagnostic case/phase mismatch')
        except Exception as exc:
            row['error'] = {'type': type(exc).__name__, 'message': str(exc)[:1500]}
        finally:
            if channel is not None:
                try:
                    row['exit_code'] = channel.close()
                except Exception as exc:
                    row['error'] = {'type': type(exc).__name__, 'message': str(exc)[:1500]}
                (output/(case+'-stdout.log')).write_bytes(channel.partial)
            try:
                checkpoints = [json.loads(line.removeprefix('BACKTRACE_CUDA_BEFORE '))
                    for line in (output/(case+'-stderr.log')).read_text().splitlines()
                    if line.startswith('BACKTRACE_CUDA_BEFORE ')]
                if len(checkpoints) != 1 or checkpoints[0].get('case') != case or checkpoints[0].get('phase') != 'BEFORE_CUDA':
                    raise ValueError('one matching pre-CUDA checkpoint required')
                row['before'] = checkpoints[0]
                primary = [json.loads(line.removeprefix('BACKTRACE_CUDA_PRIMARY '))
                    for line in (output/(case+'-stderr.log')).read_text().splitlines()
                    if line.startswith('BACKTRACE_CUDA_PRIMARY ')]
                if len(primary) == 1 and primary[0].get('case') == case:
                    row['primary_checkpoint'] = primary[0]
            except Exception as exc:
                row['checkpoint_error'] = str(exc)[:500]
            life.write(output/(case+'-checkpoint.json'), receipt)
        try:
            row['teardown'] = state(prefix)
            if row['teardown']['same_process_alive']:
                raise RuntimeError('diagnostic process survived; stop before next case')
            if actual:
                row['idle_after'] = inventory(prefix, row['before']['identity']['cuda_visible_devices'])
        except Exception as exc:
            row['error'] = {'type': type(exc).__name__, 'message': str(exc)[:1500]}
            break
        finally:
            life.write(output/(case+'-teardown.json'), receipt)
    receipt['decision'] = diagnostic_decision({k:v for k,v in receipt['cases'].items() if k in 'ABC'}, actual)
    if trace:
        trace_log = output/'D-stderr.log'
        records = [json.loads(line.removeprefix('BACKTRACE_SECCOMP_DENIAL '))
                   for line in trace_log.read_text().splitlines()
                   if line.startswith('BACKTRACE_SECCOMP_DENIAL ')] if trace_log.exists() else []
        receipt['denied_syscall_trace'] = {'case': 'D', 'records': records,
            'complete': not receipt['cases'].get('D', {}).get('error')
                and receipt['cases'].get('D', {}).get('exit_code') == 0,
            'instrumentation_changes_signal_delivery': True,
            'not_a_filter_correction': True}
        total = receipt['cases'].get('D', {}).get('result', {}).get('denial_trace', {}).get('count')
        receipt['denied_syscall_trace'].update(total_denials=total,
            records_truncated=total is None or total > len(records),
            untraced_signal_sensitive_syscalls=[56,57,58,59,322,435])
    life.write(output/'receipt.json', receipt)
    return receipt


def inventory(prefix,uuid=None,idle=True):
    import xml.etree.ElementTree as ET
    query="""import json,subprocess,pathlib,os,stat
ids=subprocess.check_output(['nvidia-smi','--query-gpu=uuid','--format=csv,noheader'],timeout=15).decode().strip().splitlines()
if len(ids)!=1:raise ValueError('exactly one assigned GPU required')
raw=subprocess.check_output(['nvidia-smi','-q','-x','-i',ids[0]],timeout=15).decode()
nodes=[]
for p in sorted(pathlib.Path('/dev').glob('nvidia*')):
 s=p.lstat()
 if stat.S_ISCHR(s.st_mode):nodes.append({'path':str(p),'major':os.major(s.st_rdev),'minor':os.minor(s.st_rdev),'mode':s.st_mode&0o777})
print(json.dumps({'uuid':ids[0],'xml':raw,'nodes':nodes}))
"""
    r=remote(prefix,query,40)
    if uuid and r['uuid'].lower()!=uuid.lower():raise ValueError('assigned GPU UUID changed')
    if idle:
        parsed=gpu.parse_inventory(r['xml'].encode(),r['uuid'])
        expected=['/dev/'+parsed['device_basename'],'/dev/nvidiactl','/dev/nvidia-uvm']
        nodes={n['path']:n for n in r['nodes']}
        if any(p not in nodes or nodes[p]['mode']&6!=6 for p in expected):
            raise ValueError('unprivileged worker GPU device access unavailable')
        if (nodes[expected[0]]['major']!=195 or nodes[expected[0]]['minor']!=int(parsed['device_basename'][6:])
                or nodes['/dev/nvidiactl']['major']!=195):
            raise ValueError('unexpected NVIDIA device major/minor identity')
        numeric=[p for p in nodes if p.startswith('/dev/nvidia') and p[11:].isdigit()]
        if numeric!=[expected[0]]:raise ValueError('additional GPU device exposed')
        return dict(parsed,nodes=r['nodes'])
    g=ET.fromstring(r['xml']).findall('gpu')
    if len(g)!=1 or g[0].findtext('uuid').lower()!=uuid.lower():raise ValueError('active UUID mismatch')
    rows=g[0].findall('processes/process_info')
    if len(rows)!=1 or not rows[0].findtext('pid','').isdigit():raise ValueError('one externally visible CUDA context required')
    return {'uuid':uuid,'context_pid':int(rows[0].findtext('pid')),
        'used_memory':rows[0].findtext('used_memory'),'xml_sha256':life.digest(r['xml'].encode())}


def exercise(prefix,output,*,actual,comparison_only=False):
    output=Path(output);output.mkdir(mode=0o700,parents=True,exist_ok=True)
    result={'status':'INCOMPLETE','actual_gpu':actual,'weight_bytes':0,'pretrained_requests':0,'training_steps':0,'checks':{}}
    def retain(label):life.write(output/(label+'-checkpoint.json'),result)
    def one(mode,seconds=60):
        ch=container.ContainerChannel(command(prefix,mode,seconds,actual),output/(mode+'-'+str(time.monotonic_ns())+'.log'))
        try:r=ch.read(time.monotonic()+seconds+5)
        finally:code=ch.close()
        if code:raise RuntimeError('diagnostic did not exit cleanly: '+mode)
        return r
    memory=remote(prefix,"""import json,pathlib,shutil
p=pathlib.Path('/opt/backtrace');src=pathlib.Path('/root/backtrace/runtime/minimum.py')
shutil.copyfile(src,p/'minimum.py');(p/'minimum.py').chmod(0o444)
shutil.copyfile(src.parent/'denial-trace.so',p/'denial-trace.so');(p/'denial-trace.so').chmod(0o444)
canary=pathlib.Path('/root/backtrace/private-canary');canary.write_text('qualification-only');canary.chmod(0o600)
r={'disk_free_bytes':shutil.disk_usage(p).free,'meminfo':pathlib.Path('/proc/meminfo').read_text(),
 'cgroup':pathlib.Path('/proc/self/cgroup').read_text(),'visible':{},'hidden_ancestor_admission':'NOT_ESTABLISHED'}
for name in ('memory.max','memory.high','memory.current','memory.events'):
 q=pathlib.Path('/sys/fs/cgroup')/name
 if q.exists():r['visible'][name]=q.read_text().strip()
print(json.dumps(r))
""")
    result['memory_observation']=memory
    size=8*1024**3 if actual else 64*1024**2
    if actual:
        import re
        host=int(re.search(r'^MemAvailable:\s+(\d+) kB$',memory['meminfo'],re.M)[1])*1024
        available=[host]
        for key in ('memory.max','memory.high'):
            if memory['visible'].get(key,'max')!='max':
                available.append(int(memory['visible'][key])-int(memory['visible']['memory.current']))
        if min(available)<size+2*1024**3 or memory['disk_free_bytes']<16*1024**3:
            raise RuntimeError('visible memory or disk insufficient for hardware diagnostic')
        device=inventory(prefix);result['initial_gpu']=device
    else:device={'uuid':'GPU-00000000-0000-0000-0000-000000000000','minimum_total_bytes':24*1024**3,'device_basename':'nvidia0'}
    config={'gpu':device,'resident_bytes':size}
    remote(prefix,"import pathlib,json;p=pathlib.Path('/opt/backtrace/"+('minimum-gpu.json' if actual else 'minimum-cpu.json')+"');p.write_text("+repr(json.dumps(config))+");p.chmod(0o444);print('{}')")
    if comparison_only:
        result['cuda_comparison'] = diagnose(prefix, output/'cuda-comparison', actual=actual, trace=True)
        result['status'] = 'DIAGNOSTIC_RECORDED'
        life.write(output/'receipt.json', result)
        return result
    boundary=one('boundary');result['boundary']=boundary
    checks=result['checks']
    for key in ('socket_denied','unix_socket_denied','fork_denied','exec_denied','root_denied',
                'private_file_denied','readonly_job','namespace_denied','threads_work','credential_environment_absent'):
        checks[key]=boundary[key] is True
    checks['worker_identity']=boundary['uid']==65532 and boundary['caps']==0 and boundary['no_new_privs']=='1' and boundary['seccomp']=='2'
    if not all(checks.values()):raise AssertionError('actual worker boundary failed')
    result['resident_memory']=one('memory',120);checks['resident_memory']=result['resident_memory']['resident_bytes']==size
    retain('boundary-memory')
    if actual:
        result['initial_kernels']=one('kernels');checks['initial_kernels']=result['initial_kernels']['status']=='PASS_ACTUAL_CUDA_KERNELS'
        result['initial_idle']=inventory(prefix,device['uuid']);retain('initial-kernels')
    else:
        ch=container.ContainerChannel(command(prefix,'kernels',60,False),output/'missing-gpu.log')
        try:
            try:ch.read(time.monotonic()+65);raise AssertionError('CPU fixture unexpectedly ran CUDA')
            except EOFError:pass
        finally:code=ch.close()
        checks['missing_gpu_rejected']=code!=0 and 'CPU fallback forbidden' in (output/'missing-gpu.log').read_text()
        if not checks['missing_gpu_rejected']:raise AssertionError('missing GPU not rejected at exact kernel gate')
        result['cuda_comparison_cpu'] = diagnose(prefix, output/'cuda-comparison', actual=False, trace=True)
        checks['cuda_comparison_cpu'] = (result['cuda_comparison_cpu']['decision'] == 'CPU_CONTROLS_ONLY'
            and all(row.get('result',{}).get('status') == 'FAIL' and 'CPU fallback forbidden' in row.get('result',{}).get('error', '')
                    for row in result['cuda_comparison_cpu']['cases'].values()))
        if not checks['cuda_comparison_cpu']:raise AssertionError('CPU comparison logging/boundaries failed')
    result['interruptions']={}
    for kind in ('deadline','transport','supervisor'):
        ch=container.ContainerChannel(command(prefix,'active' if actual else 'cpu-hold',15 if kind=='deadline' else 120,actual),output/(kind+'.log'))
        try:
            hello=ch.read(time.monotonic()+30)
            expected='CUDA_CONTEXT_ACTIVE' if actual else 'CPU_CONTEXT_ACTIVE'
            if hello.get('status')!=expected:raise ValueError('active context handshake absent')
            before=state(prefix)
            if not before['same_process_alive']:raise ValueError('worker already gone')
            active=inventory(prefix,device['uuid'],idle=False) if actual else {'kind':'CPU_ONLY'}
            if kind=='deadline':
                try:ch.read(time.monotonic()+20);raise AssertionError('active diagnostic exited without deadline')
                except EOFError:pass
            elif kind=='transport':os.killpg(ch.process.pid,signal.SIGKILL)
            else:remote(prefix,'import os,signal;os.kill('+str(before['supervisor_pid'])+',signal.SIGKILL);print("{}")')
        finally:ch.close()
        end=time.monotonic()+15
        while True:
            after=state(prefix)
            if not after['same_process_alive']:break
            if time.monotonic()>=end:raise TimeoutError('interrupted worker survived')
            time.sleep(.2)
        row={'hello':hello,'before':before,'active':active,'after':after}
        if kind=='deadline' and after['reason']!='DEADLINE':raise ValueError('deadline not observed')
        if actual:
            row['idle_after']=inventory(prefix,device['uuid'])
            row['fresh_kernels']=one('kernels')
            row['idle_after_fresh']=inventory(prefix,device['uuid'])
            if row['fresh_kernels']['status']!='PASS_ACTUAL_CUDA_KERNELS':raise ValueError('fresh kernels failed')
        result['interruptions'][kind]=row;checks[kind]=not after['same_process_alive'];retain(kind)
    if not all(checks.values()):raise AssertionError('minimum diagnostic control failed')
    result['status']='PASS_ACTUAL_HARDWARE_ONLY' if actual else 'PASS_FREE_HARDWARE_PATH_CONTROLS'
    life.write(output/'receipt.json',result);return result


def connected(root,endpoint,output,*,actual,comparison_only=False,after_hardware=None):
    root=Path(root);output=Path(output);output.mkdir(mode=0o700,parents=True,exist_ok=True)
    result={'status':'INCOMPLETE','actual_gpu':actual}
    try:
        host,port=endpoint['host'],endpoint['port'];ssh.validate_endpoint(host,port)
        result['binary_transfer']=ssh.deliver(root/'keys',host,port,60,profile='actions-20261019')
        prefix=prefix_for(root,host,port)
        ssh.wait_for_command(prefix,['true'],30)
        result['runtime_transfer']=delivery.push(root/'runtime',root/'runtime-manifest.json',
            prefix+[delivery.ssh_command(host,port,root/'keys/owner-key',root/'keys/known-hosts',
                '/root/backtrace/runtime',life.digest((root/'runtime-manifest.json').read_bytes()))[-1]],600)
        with (output/'install.log').open('xb') as log:
            p=subprocess.run(prefix+[shlex.join(['/usr/bin/python3.12','-I','/root/backtrace/runtime/installer.py','install','/root/backtrace/runtime'])],
                stdout=subprocess.PIPE,stderr=log,timeout=1100,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        if p.returncode:raise RuntimeError('exact offline install failed')
        result['installation']=json.loads(p.stdout);life.write(output/'installation-checkpoint.json',result)
        result['diagnostics']=exercise(prefix,output/'diagnostics',actual=actual,comparison_only=comparison_only)
        result['status']=result['diagnostics']['status']
        if after_hardware is not None:
            if not actual or comparison_only or result['status']!='PASS_ACTUAL_HARDWARE_ONLY':
                raise ValueError('actual complete hardware qualification required before inference')
            result['inference']=after_hardware(root,endpoint,prefix,output,result['diagnostics'])
            result['status']=result['inference']['status']
    except Exception as e:
        import traceback
        result.update(status='FAIL',error_type=type(e).__name__,error=str(e)[:1500],
            frames=[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(e.__traceback__)][-8:])
    life.write(output/'connected-receipt.json',result);return result


if __name__=='__main__':
    import sys
    root,endpoint,output=sys.argv[1:];result=connected(Path(root),json.loads(Path(endpoint).read_bytes()),Path(output),actual=True)
    print(json.dumps({'status':result['status']}),flush=True)
    raise SystemExit(0 if result['status']=='PASS_ACTUAL_HARDWARE_ONLY' else 1)
