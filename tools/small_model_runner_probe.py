"""Actual native Linux qualification; scripted outputs and tiny random CPU weights only."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

from tools import abductive_benchmark as base
from tools import abductive_scoring as score
from tools import exact_teacher as exact
from tools import small_model_readiness as ready
from tools import small_model_runner as runner
from tools import temporal_benchmark as temporal


def random_models(sources, output):
    import torch
    from transformers import AutoConfig, Gemma4Config, Gemma4TextConfig, Gemma4ForConditionalGeneration
    torch.set_num_threads(1)
    output.mkdir(mode=0o700)
    manifests={}
    for name in ready.MODELS:
        cfg=AutoConfig.from_pretrained(sources/name,local_files_only=True,trust_remote_code=False)
        text=deepcopy(cfg.text_config.to_dict())
        text.pop('per_layer_config',None)
        # Real tokenizer vocabulary and real input lengths; tiny two-layer random
        # tensors. The preceding readiness stage checked the full layer layouts.
        text.update(hidden_size=16,intermediate_size=32,num_hidden_layers=2,
            layer_types=['sliding_attention','full_attention'],num_kv_shared_layers=0,
            num_attention_heads=2,num_key_value_heads=1,head_dim=8,global_head_dim=8,
            hidden_size_per_layer_input=4,sliding_window=64,dtype='float32')
        config=Gemma4Config(text_config=Gemma4TextConfig.from_dict(text),vision_config=None,audio_config=None)
        config._attn_implementation='sdpa'; torch.manual_seed(71)
        model=Gemma4ForConditionalGeneration(config).eval()
        model.save_pretrained(output/name,safe_serialization=True)
        manifests[name]={p.name:{'bytes':p.stat().st_size,'sha256':exact.sha(p.read_bytes())}
                         for p in (output/name).iterdir()}
        del model
    return manifests


def factory(python,sources,models,jobs,mode,maximum,*,fault=None):
    jobs.mkdir(mode=0o700)
    for name in ready.MODELS:
        job={'mode':mode,'packages':ready.lock()['cpu_runtime']['packages'],
             'key_mapping':ready.lock()['model_loading']['key_mapping'],
             'max_input_tokens':12288,'max_new_tokens':maximum,'fault':fault,'fault_at':1 if fault in ('hang','crash') else 0}
        base.private_write(jobs/(name+'.json'),exact.canonical(job))
    commands={name:runner.jail_command(python,models/name,sources/name,jobs/(name+'.json')) for name in ready.MODELS}
    def make(name,output):
        return runner.Channel(commands[name],output/(name+'-stderr.log'))
    make.close=lambda: [command.close() for command in commands.values()]
    make.staging_paths=[str(command.staging) for command in commands.values()]
    return make


BOUNDARY_SCRIPT = r'''
import json,os,pathlib,socket,subprocess,sys,time
job=json.loads(pathlib.Path('/job.json').read_bytes())
status=dict(x.split(':',1) for x in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in x)
facts={'uid':os.getuid(),'caps':int(status['CapEff'].strip(),16),'nnp':status['NoNewPrivs'].strip(),
       'pid_ns':os.readlink('/proc/self/ns/pid'),'net_ns':os.readlink('/proc/self/ns/net')}
facts['hidden']=[]
for path in job['deny']:
 try: pathlib.Path(path).read_bytes(); facts['hidden'].append(False)
 except (FileNotFoundError,PermissionError): facts['hidden'].append(True)
# PID numbers can coincide across nested PID namespaces. Compare identity.
try: facts['coordinator_hidden']=os.readlink('/proc/'+str(job['coordinator_pid'])+'/ns/pid')!=job['coordinator_pid_namespace']
except OSError: facts['coordinator_hidden']=True
try:
 pathlib.Path('/job.json').write_text('overwrite'); facts['readonly']=False
except OSError: facts['readonly']=True
try:
 os.setuid(0); facts['cannot_become_root']=False
except OSError: facts['cannot_become_root']=True
s=socket.socket();s.settimeout(.2)
try: s.connect(('127.0.0.1',job['port']));facts['host_port_blocked']=False
except OSError: facts['host_port_blocked']=True
s.close()
facts['nested_userns_blocked']=subprocess.run(['/usr/bin/unshare','--user','/usr/bin/true'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
facts['secret_env_absent']='BACKTRACE_PRIVATE_CANARY' not in os.environ
pathlib.Path('/probe/facts.json').write_text(json.dumps(facts))
subprocess.Popen([sys.executable,'-I','-c',"import pathlib,time;time.sleep(2);pathlib.Path('/probe/late').write_text('escaped')"],start_new_session=True)
pathlib.Path('/probe/entered').write_text('yes')
time.sleep(60)
'''


def boundary_probe(python,sources,models,output,*,command_factory=runner.jail_command):
    output.mkdir(mode=0o700)
    script=output/'probe.py';script.write_text(BOUNDARY_SCRIPT)
    canary=output/'private-labels';canary.write_text('evaluator-only');canary.chmod(0o600)
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen()
    job=output/'job.json'
    job.write_bytes(exact.canonical({'deny':[str(canary),str(exact.ROOT/'tools/exact_teacher.py'),
        str(exact.ROOT/'docs/temporal-baseline-cpu-20261026.json')],
        'coordinator_pid':os.getpid(),'coordinator_pid_namespace':os.readlink('/proc/self/ns/pid'),
        'port':sock.getsockname()[1]}))
    observations={}; checks={}
    try:
        for variant in ('deadline','parent_loss'):
            saved=output/variant;saved.mkdir(mode=0o700)
            command=command_factory(python,models/'E2B',sources/'E2B',job,script=script,probe=saved)
            probe=command.probe_path
            log=open(output/(variant+'.log'),'wb')
            started=time.monotonic()
            if variant=='deadline':
                process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,
                    env={'PATH':'/usr/bin:/bin','BACKTRACE_PRIVATE_CANARY':'must-not-enter'})
            else:
                wrapper='import subprocess,sys,time; subprocess.Popen(sys.argv[1:],start_new_session=True);time.sleep(60)'
                process=subprocess.Popen([str(python),'-I','-c',wrapper,*command],stdin=subprocess.DEVNULL,
                    stdout=log,stderr=log,start_new_session=True)
            try:
                until=time.monotonic()+10
                while not (probe/'entered').exists() and process.poll() is None and time.monotonic()<until:
                    time.sleep(.02)
                if not (probe/'entered').exists():
                    detail=(output/(variant+'.log')).read_text(errors='replace')[-2000:]
                    raise RuntimeError('boundary worker did not enter: '+detail)
                os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
                time.sleep(2.2)
                facts=base.strict_json((probe/'facts.json').read_bytes())
                base.private_write(saved/'facts.json',exact.canonical(facts))
                observations[variant]=facts
                checks[variant+'_descendant_stopped']=not (probe/'late').exists()
                checks[variant+'_bounded']=time.monotonic()-started<15
                checks[variant+'_boundaries']=(facts['uid']==65532 and facts['caps']==0 and facts['nnp']=='1'
                    and all(facts['hidden']) and facts['coordinator_hidden'] and all(facts[k] for k in ('readonly','cannot_become_root',
                        'host_port_blocked','nested_userns_blocked','secret_env_absent'))
                    and facts['pid_ns']!=os.readlink('/proc/self/ns/pid')
                    and facts['net_ns']!=os.readlink('/proc/self/ns/net'))
                live=[]
                for proc in Path('/proc').iterdir():
                    if proc.name.isdigit():
                        try:
                            if os.readlink(proc/'ns/pid')==facts['pid_ns']:live.append(proc.name)
                        except OSError:pass
                checks[variant+'_namespace_gone']=not live
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
                log.close()
                command.close()
    finally: sock.close()
    if not all(checks.values()):raise AssertionError(checks)
    return {'checks':checks,'observations':observations,'status':'PASS_NATIVE_BOUNDARIES'}


def interrupted_collection(python,sources,models,packets,tokens,scope,raw_ids,output):
    """Kill the actual coordinator after one completed exchange, then recover its ledger."""
    ids_path=output/'parent-loss-authored-ids.json'
    base.private_write(ids_path,exact.canonical(raw_ids))
    code='''import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from tools import small_model_runner as r,small_model_runner_probe as p
from transformers import AutoTokenizer
sources,models,packets,tokens,scope,output,ids=map(Path,sys.argv[2:])
plan,schedule,_=r.load_scope(scope,packets,tokens)
tokenizers={n:AutoTokenizer.from_pretrained(sources/n,local_files_only=True,trust_remote_code=False) for n in r.ready.MODELS}
worker=p.factory(Path(sys.executable),sources,models,output/'parent-loss-jobs','scripted_control',4096,fault='hang')
r.collect(schedule,output/'parent-loss',worker,tokenizers,mode='scripted_control',max_new_tokens=4096,total_seconds=120,startup_seconds=30,request_seconds=30,fixture_ids=json.loads(ids.read_bytes()))
'''
    log=open(output/'parent-loss-coordinator.log','xb')
    command=[str(python),'-I','-c',code,str(exact.ROOT),*map(str,[sources,models,packets,tokens,scope,output,ids_path])]
    process=subprocess.Popen(command,stdout=log,stderr=log,start_new_session=True,
        env={'PATH':'/usr/bin:/bin','HF_HUB_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'})
    ledger=output/'parent-loss/ledger.jsonl'
    try:
        deadline=time.monotonic()+60;entered=False
        while time.monotonic()<deadline and process.poll() is None:
            if ledger.exists():
                lines=ledger.read_bytes().splitlines()
                if len(lines)>=3:
                    last=base.strict_json(lines[-1]);entered=last['event']=='STARTED' and last['index']==1
                    if entered:break
            time.sleep(.02)
        if not entered:
            detail=(output/'parent-loss-coordinator.log').read_text(errors='replace')[-2000:]
            raise RuntimeError('coordinator never reached second request: '+detail)
        os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
        time.sleep(.3)
        hello=base.strict_json((output/'parent-loss/E2B-ready.json').read_bytes())
        live=[]
        for proc in Path('/proc').iterdir():
            if proc.name.isdigit():
                try:
                    if os.readlink(proc/'ns/pid')==hello['pid_namespace']:live.append(proc.name)
                except OSError:pass
        if live:raise AssertionError('model worker survived coordinator loss')
        recovered=runner.recover(output/'parent-loss')
        plan,schedule,_=runner.load_scope(scope,packets,tokens)
        evaluation=runner.evaluate(plan,schedule,recovered)
        base.private_write(output/'parent-loss/evaluation.json',exact.canonical(evaluation))
        if recovered['coverage']!={'OK':1,'INTERRUPTED':1,'NOT_RUN':34}:
            raise AssertionError(recovered['coverage'])
        assignment=base.strict_json((output/'parent-loss/assignment.json').read_bytes())
        for name in assignment['disposable_worker_assets']:
            path=Path(name)
            if path.parent!=Path(tempfile.gettempdir()) or not path.name.startswith('backtrace-model-worker-') or path.is_symlink():
                raise ValueError('unexpected disposable asset path')
            if path.exists():shutil.rmtree(path)
        return {k:v for k,v in recovered.items() if k!='records'}|{'worker_namespace_gone':True,'disposable_assets_removed':True}
    finally:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
        log.close()


def qualify(sources,packets,tokens,scope,output):
    ready.check_packages();sources=ready.validate_sources(sources)
    plan,schedule,scope_hash=runner.load_scope(scope,packets,tokens)
    if plan['scope']!='smoke':raise ValueError('qualification uses fixed smoke only')
    output=exact._local_path(output);output.mkdir(mode=0o700,exist_ok=False)
    from transformers import AutoTokenizer
    tokenizers={n:AutoTokenizer.from_pretrained(sources/n,local_files_only=True,trust_remote_code=False) for n in ready.MODELS}
    python=Path(sys.executable).absolute()
    models=output/'random-models'
    try:
        manifests=random_models(sources,models)
        boundaries=boundary_probe(python,sources,models,output/'boundaries')
        raw_ids={}
        for item in schedule:
            if item['arm']!='B0':continue
            payload=base.strict_json(item['messages'][1]['content'])
            ref=temporal.reference(payload) if payload['task']=='temporal_revision' else base.reference(payload)
            translated=temporal.as_revision(payload) if payload['task']=='temporal_revision' else payload
            answer=json.dumps(score.optimal_response(translated,ref),sort_keys=True,separators=(',',':'))
            raw_ids[item['id']]=tokenizers['E2B'].encode(answer,add_special_tokens=False)+[106]
        outcomes={};evaluations={};checks={}
        scenarios=[('oracle',None),('tool_boundary',None),('hang','hang'),('crash','crash'),
                   ('wrong_id','wrong_id'),('oversize','oversize'),('startup_hang','startup_hang')]
        for name,fault in scenarios:
            ids={k:v+[50] for k,v in raw_ids.items()} if name=='tool_boundary' else raw_ids
            worker=factory(python,sources,models,output/(name+'-jobs'),'scripted_control',4096,fault=fault)
            result=runner.collect(schedule,output/name,worker,tokenizers,mode='scripted_control',max_new_tokens=4096,
                total_seconds=1 if name=='startup_hang' else 120,
                startup_seconds=1 if name=='startup_hang' else 30,
                request_seconds=1 if name in ('hang','startup_hang') else 15,fixture_ids=ids)
            evaluation=runner.evaluate(plan,schedule,result)
            base.private_write(output/name/'evaluation.json',exact.canonical(evaluation))
            outcomes[name]={k:v for k,v in result.items() if k not in ('records','worker_handshakes')}
            evaluations[name]={m:{a:{kind:{k:v for k,v in sub.items() if k!='assigned_protocol_scores'}
                             for kind,sub in group.items()} for a,group in arms.items()} for m,arms in evaluation['scores'].items()}
            if name=='oracle':
                checks['oracle_all_received']=result['coverage']=={'OK':36} and result['status']=='COMPLETED'
                cases=[c for arms in evaluation['scores'].values() for group in arms.values()
                       for sub in group.values() for c in sub['assigned_protocol_scores']['cases']]
                checks['oracle_all_exact']=len(cases)==36 and all(c['response_status']=='VALID' and all(v==0 for v in c['losses'].values()) for c in cases)
            elif name=='tool_boundary':
                checks[name]=result['coverage']=={'INVALID_OUTPUT':36} and all(50 in r['raw_output_ids'] for r in result['records'])
            elif name in ('hang','crash'):
                expected='TIMEOUT' if name=='hang' else 'WORKER_ERROR'
                checks[name]=result['coverage']=={'OK':1,expected:1,'NOT_RUN':34} and (output/name/'wire-0000.json').is_file()
            elif name=='startup_hang':
                checks[name]=result['coverage']=={'NOT_RUN':36} and result['status']=='INCOMPLETE' and result['wall_seconds']<4
            else:
                checks[name]=result['coverage']=={'WORKER_ERROR':1,'NOT_RUN':35}
        outcomes['parent_loss']=interrupted_collection(python,sources,models,packets,tokens,scope,raw_ids,output)
        checks['parent_loss_recovery']=outcomes['parent_loss']['coverage']=={'OK':1,'INTERRUPTED':1,'NOT_RUN':34}
        worker=factory(python,sources,models,output/'random-jobs','random_fixture',2)
        random_result=runner.collect(schedule,output/'random',worker,tokenizers,mode='random_fixture',max_new_tokens=2,
                                    total_seconds=240,startup_seconds=30,request_seconds=30)
        random_evaluation=runner.evaluate(plan,schedule,random_result)
        base.private_write(output/'random/evaluation.json',exact.canonical(random_evaluation))
        checks['random_both_models_all_assigned']=random_result['status']=='COMPLETED' and all(
            r['status'] in ('OK','INVALID_OUTPUT') and 0<r['generated_tokens']<=2 for r in random_result['records'])
        outcomes['random']={k:v for k,v in random_result.items() if k not in ('records','worker_handshakes')}
        hashes={str(p.relative_to(output)):{'sha256':exact.sha(p.read_bytes()),'bytes':p.stat().st_size}
                for p in output.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.log') and 'random-models' not in p.parts}
        report={'status':'PASS_CPU_PIPELINE_ONLY' if all(checks.values()) else 'FAIL','checks':checks,
                'boundaries':boundaries,'runs':outcomes,'authored_evaluation_summaries':evaluations,
                'fixture_model_manifests':manifests,'artifacts':hashes,'scope_sha256':scope_hash,
                'source_hashes':runner.source_hashes(),
                'qualified_probe_sha256':exact.sha(Path(__file__).read_bytes()),
                'bubblewrap':{'version':subprocess.check_output(['bwrap','--version']).decode().strip(),
                             'sha256':exact.sha(Path(shutil.which('bwrap')).read_bytes())},
                'pretrained_inference':'NOT_RUN','gpu_device_passthrough':'NOT_IMPLEMENTED_OR_QUALIFIED',
                'training':'NOT_RUN','capability_claim':'NOT_ESTABLISHED','paid_execution_authorized':False}
        base.private_write(output/'receipt.json',exact.canonical(report))
        if not all(checks.values()):raise AssertionError(checks)
        return report
    except BaseException as exc:
        base.private_write(output/'failed.json',exact.canonical({'status':'FAIL','error_type':type(exc).__name__}))
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('sources','packets','tokens','scope','output'):p.add_argument(name,type=Path)
    args=p.parse_args()
    result=qualify(args.sources,args.packets,args.tokens,args.scope,args.output)
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=='__main__':main()
