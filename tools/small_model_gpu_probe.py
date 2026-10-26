"""Free native Linux evidence for the CUDA build; deliberately no physical GPU claim."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
import time

from tools import abductive_benchmark as base
from tools import abductive_scoring as score
from tools import exact_teacher as exact
from tools import small_model_gpu as gpu
from tools import small_model_readiness as ready
from tools import small_model_runner as runner
from tools import small_model_runner_probe as probe
from tools import temporal_benchmark as temporal


def char_command(*args,**kwargs):
    command=runner.jail_command(*args,**kwargs)
    node=command.staging/'character-control'
    os.mknod(node,stat.S_IFCHR|0o666,os.makedev(1,3));node.chmod(0o666)
    try:
        gpu.attach_devices(command,[{'path':str(node),'major':1,'minor':3}],{},'none')
        at=command.index('--chdir');command[at:at]=['--setenv','BACKTRACE_CHAR_CONTROL',str(node)]
        return command
    except BaseException:command.close();raise


def qualify(sources,packets,tokens,scope,output):
    output=exact._local_path(output);output.mkdir(mode=0o700,exist_ok=False)
    runtime=gpu.check_runtime()
    if runtime['cuda_available'] or runtime['device_count']!=0:
        raise ValueError('free qualification must not consume an exposed GPU')
    sources=ready.validate_sources(sources);plan,schedule,_=runner.load_scope(scope,packets,tokens)
    python=Path(sys.executable)
    models=output/'random-models';manifests=probe.random_models(sources,models)
    boundaries=probe.boundary_probe(python,sources,models,output/'boundaries',command_factory=char_command)
    script=output/'character-probe.py'
    script.write_text('''import json,os,stat
p=os.environ['BACKTRACE_CHAR_CONTROL'];s=os.stat(p)
assert stat.S_ISCHR(s.st_mode)
with open(p,'wb',buffering=0) as f:n=f.write(b'character-control')
print(json.dumps({'status':'PASS_REAL_CHARACTER_BIND_ONLY','major':os.major(s.st_rdev),'minor':os.minor(s.st_rdev),'written':n}),flush=True)
''')
    job=output/'char-job.json';base.private_write(job,b'{}\n')
    channel=runner.Channel(char_command(python,models/'E2B',sources/'E2B',job,script=script),output/'char-stderr.log')
    try:char=channel.read(time.monotonic()+10)
    finally:exit_code=channel.close()
    if exit_code!=0 or char!={'status':'PASS_REAL_CHARACTER_BIND_ONLY','major':1,'minor':3,'written':17}:
        raise AssertionError('character bind control failed')
    base.private_write(output/'character-bind.json',exact.canonical(char))
    no_gpu_job=output/'no-gpu-job.json'
    base.private_write(no_gpu_job,exact.canonical({'mode':'cuda_probe','packages':ready.lock()['gpu_candidate']['packages'],
        'gpu':{'uuid':'GPU-12345678-1234-1234-1234-123456789abc'}}))
    channel=runner.Channel(runner.jail_command(python,models/'E2B',sources/'E2B',no_gpu_job),output/'no-gpu-stderr.log')
    failed=False
    try:channel.read(time.monotonic()+30)
    except EOFError:failed=True
    finally:exit_code=channel.close()
    log=(output/'no-gpu-stderr.log').read_text()
    if not failed or exit_code==0 or 'CUDA 12.6 device unavailable; CPU fallback forbidden' not in log:
        raise AssertionError('missing-GPU rejection was not the expected actual worker failure')
    from transformers import AutoTokenizer
    tokenizers={n:AutoTokenizer.from_pretrained(sources/n,local_files_only=True,trust_remote_code=False) for n in ready.MODELS}
    raw_ids={}
    for item in schedule:
        if item['arm']!='B0':continue
        payload=base.strict_json(item['messages'][1]['content'])
        ref=temporal.reference(payload) if payload['task']=='temporal_revision' else base.reference(payload)
        translated=temporal.as_revision(payload) if payload['task']=='temporal_revision' else payload
        answer=json.dumps(score.optimal_response(translated,ref),sort_keys=True,separators=(',',':'))
        raw_ids[item['id']]=tokenizers['E2B'].encode(answer,add_special_tokens=False)+[106]
    runs={};checks={}
    for name,mode,maximum in [('oracle','scripted_control',4096),('random','random_fixture',2)]:
        factory=gpu.factory(python,sources,models,output/(name+'-jobs'),None,mode=mode,maximum=maximum)
        result=runner.collect(schedule,output/name,factory,tokenizers,mode=mode,max_new_tokens=maximum,
            total_seconds=240,startup_seconds=30,request_seconds=30,
            fixture_ids=raw_ids if mode=='scripted_control' else None)
        evaluation=runner.evaluate(plan,schedule,result)
        base.private_write(output/name/'evaluation.json',exact.canonical(evaluation))
        runs[name]={k:v for k,v in result.items() if k!='records'}
        checks[name+'_complete']=result['status']=='COMPLETED' and result['assigned']==36 and not result['gpu_run']
        if name=='oracle':
            cases=[c for arms in evaluation['scores'].values() for group in arms.values()
                   for sub in group.values() for c in sub['assigned_protocol_scores']['cases']]
            checks['oracle_exact']=len(cases)==36 and all(c['response_status']=='VALID' and all(v==0 for v in c['losses'].values()) for c in cases)
        else:checks['random_tokens_retained']=all(0<len(r['raw_output_ids'])<=2 for r in result['records'])
    prepared=gpu.prepare(scope,packets,tokens,output/'baseline-plan.json')
    hashes={str(p.relative_to(output)):{'bytes':p.stat().st_size,'sha256':gpu.sha_file(p)}
            for p in output.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.log') and 'random-models' not in p.parts}
    report={'status':'PASS_FREE_CUDA_PREPARATION_ONLY' if all(checks.values()) else 'FAIL',
        'runtime':runtime,'boundaries_with_character_control':boundaries,'character_bind':char,
        'actual_no_gpu_worker_rejected':True,'checks':checks,'runs':runs,
        'random_fixture_manifests':manifests,'artifacts':hashes,
        'baseline_plan_sha256':exact.sha(exact.canonical(prepared)),'source_hashes':runner.source_hashes(),
        'qualified_probe_sha256':gpu.sha_file(Path(__file__)),
        'actual_gpu_kernels':'NOT_RUN','actual_nvidia_device_binding':'NOT_RUN','pretrained_inference':'NOT_RUN',
        'training':'NOT_RUN','paid_allocation':False,'capability_claim':'NOT_ESTABLISHED'}
    base.private_write(output/'receipt.json',exact.canonical(report))
    if not all(checks.values()):raise AssertionError(checks)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('sources','packets','tokens','scope','output'):p.add_argument(name,type=Path)
    print(json.dumps(qualify(**vars(p.parse_args())),sort_keys=True,indent=2))


if __name__=='__main__':main()
