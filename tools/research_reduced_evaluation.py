"""Credential-free independent CPU evaluation gated by both deletion receipts."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import research_entry_contract as c, research_reduced as reduced
from tools import research_comparison as comparison, cloud_resolver as resolver
from tools.direct_delivery import pull
from tools.linux_runtime import BOOTSTRAP, offline_child
from tools.research_entry import binding
from tools.research_isolation import bounded_child
from tools.research_runner import checked_slot
from tools.research_split_cpu import reclaim_slot
from tools.research_verifier_cpu import readable_tree


def deletion_proof(owner,watch):
    claim=owner['claim'];expected=binding(claim)
    for row in (owner['cleanup'],watch):
        if (row.get('status')!='DELETED' or row.get('absence_reads')!=2
                or row.get('claim_sha256')!=expected or not row.get('pod_id')):
            raise ValueError('both matching two-read deletion receipts required before evaluation')
    if owner['cleanup']['pod_id']!=watch['pod_id']:
        raise ValueError('cleanup identities disagree')
    return {'status':'PASS','claim_sha256':expected,'pod_id':watch['pod_id'],
        'owner_completed_at':owner['cleanup']['completed_at'],'watcher_completed_at':watch['completed_at']}


def patches(inputs,work,slots):
    expected=[(t['instance_id'],a) for t in reduced.load()['primary'] for a in t['arm_order']]
    if [(r['instance_id'],r['arm']) for r in slots]!=expected:
        raise ValueError('exact nine-slot denominator and order required')
    candidates=comparison.parse((c.ROOT/'docs/research-preparation-cpu-20261024.json').read_bytes())['research_inputs']['assembly']['arms']
    rows=[]
    for slot in slots:
        identifier,arm=slot['instance_id'],slot['arm']
        row={'instance_id':identifier,'arm':arm,'status':'NOT_EVALUATED','agent_status':slot['status']}
        result=slot.get('result',{});path=work/(identifier+'-'+arm)/'agent.patch'
        if result.get('patch_submitted') is not True or not path.is_file():
            row['reason']='no retained originally submitted patch';rows.append(row);continue
        _,task=checked_slot(inputs,identifier,arm)
        # Parent-owned output is checked against both input and runner receipts.
        raw=comparison.read_file(path,8*1024**2)
        if (result.get('instance_id')!=identifier or result.get('arm')!=arm
                or result.get('candidate_sha256')!=candidates[arm]['archive_sha256']
                or result.get('agent_task_sha256')!=task['agent_task_sha256']
                or result.get('patch_sha256')!=c.digest(raw) or result.get('patch_bytes')!=len(raw)):
            raise ValueError('patch, candidate or task binding changed')
        rows.append(dict(row,status='READY',patch_sha256=c.digest(raw),patch=raw.decode()))
    return rows


def dependencies(root,config,env):
    lock=comparison.parse((c.ROOT/'docs/research-evaluator-dependencies.json').read_bytes())
    root.mkdir(mode=0o700)
    def fetch(row):
        manifest=c.encoded({'schema_version':1,'phase':'bootstrap','files':[
            {k:row[k] for k in ('path','bytes','sha256')}]})
        target=root/row['name'];source=resolver.retry_read(lambda:resolver.pypi_source(row))
        pull(target,manifest,{row['path']:source},c.digest(manifest),180)
        return target/row['path']
    with ThreadPoolExecutor(max_workers=8) as pool:wheels=list(pool.map(fetch,lock['files']))
    site=root/'site-packages';runtime=Path(config['cpu_wheels']).parent
    with (root/'install.log').open('wb') as stream:
        subprocess.run(offline_child(config['cpu_python'],'bootstrap-pip',
            str(runtime/'bootstrap'/BOOTSTRAP['path']),'install','--no-index','--no-deps',
            '--target',str(site),*map(str,wheels)),env=env,stdout=stream,stderr=stream,check=True,timeout=60)
    readable_tree(root)
    return site,{'packages':len(wheels),'lock_sha256':c.digest((c.ROOT/'docs/research-evaluator-dependencies.json').read_bytes()),
                 'agent_runtime_modified':False}


def retain(config,destination):
    import shutil
    root=Path(config['directory']).parent/'evaluation'
    for path in root.rglob('*'):
        if (path.is_file() and not path.is_symlink() and path.suffix in ('.json','.log','.txt','.xml')
                and not any(n in path.relative_to(root).parts for n in ('dependencies','sandboxes'))):
            target=Path(destination)/'evaluation'/path.relative_to(root)
            target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            shutil.copyfile(path,target);target.chmod(0o600)


def evaluate(inputs,config,owner,watch,*,authored_cpu):
    proof=deletion_proof(owner,watch)
    root=c.traversable_directory(Path(config['directory']).parent/'evaluation')
    private=root/'private';private.mkdir(mode=0o700)
    report={'status':'INCOMPLETE','kind':'AUTHORED_CPU' if authored_cpu else 'REAL_MODEL_PATCHES',
        'pilot_scope':reduced.identity(),'deletion_proof':proof,'began_at':time.time(),
        'effect_estimate':'NOT_COMPUTED','controls':[],'slots':[]}
    env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','HOME':str(private),
        'OTEL_SDK_DISABLED':'true','LITELLM_LOCAL_MODEL_COST_MAP':'True',
        'LITELLM_TELEMETRY':'False','PYTHON_DOTENV_DISABLED':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
    try:
        slots=owner.get('worker',{}).get('slots',{}).get('slots')
        if slots is None:slots=reduced.sequence(lambda *_:None,deadline=0)['slots']
        rows=patches(Path(inputs),Path(config['directory'])/'work',slots)
        report['slots']=[{k:v for k,v in row.items() if k!='patch'} for row in rows]
        if not any(r['status']=='READY' for r in rows):
            report['status']='NOT_RUN';return report
        site,report['dependencies']=dependencies(root/'dependencies',config,env)
        deadline=time.monotonic()+1200
        def execute(identifier,name,jobs):
            destination=root/name;plan=private/(name+'.json');plan.write_bytes(c.encoded(jobs))
            remaining=deadline-time.monotonic()
            if remaining<=0:return {'status':'NOT_RUN','reason':'independent CPU total deadline'}
            row=bounded_child([config['cpu_python'],'-I','-B',Path(__file__).resolve(),'--worker',
                inputs,destination,identifier,config['cpu_wheels'],site,plan],private/(name+'.log'),env,
                timeout=min(330,remaining))
            # Namespace PID 1 termination reaps nested processes; remove retained
            # sandbox paths before reusing the evaluator UID on the next job.
            if destination.exists():
                for child in destination.iterdir():
                    if child.is_dir() and child.name!='private':reclaim_slot(child)
            receipt=destination/'receipt.json'
            if receipt.is_file():row['result']=json.loads(receipt.read_bytes())
            row['status']='PASS' if row['exit_code']==0 and not row['child_timeout'] and row.get('result',{}).get('status')=='PASS' else 'FAIL'
            print(json.dumps({'cpu_evaluation':name,'status':row['status'],'wall_seconds':row['wall_seconds']}),file=sys.__stdout__,flush=True)
            return row
        for task in reduced.load()['primary']:
            report['controls'].append(execute(task['instance_id'],task['instance_id']+'-controls','controls'))
        controls_pass=all(r['status']=='PASS' for r in report['controls'])
        for row,public in zip(rows,report['slots']):
            if row['status']!='READY':continue
            if not controls_pass:
                public.update(status='NOT_EVALUATED',reason='paired verifier controls failed');continue
            measured=execute(row['instance_id'],row['instance_id']+'-'+row['arm'],[
                {'name':row['arm'],'patch':row['patch'],'expected':False if authored_cpu else None}])
            public.update(evaluation=measured,status='EVALUATED' if measured['status']=='PASS' else 'EVALUATION_FAILED')
        report['all_nine_evaluated']=all(r['status']=='EVALUATED' for r in report['slots'])
        report['status']='PASS' if controls_pass and report['all_nine_evaluated'] else 'INCOMPLETE'
    except Exception as error:
        import traceback
        report.update(status='FAIL',error_type=type(error).__name__)
        (private/'failure.log').write_text(traceback.format_exc())
    finally:
        report['completed_at']=time.time();(root/'receipt.json').write_bytes(c.encoded(report))
    return report


if __name__=='__main__':
    if sys.argv[1:2]!=['--worker']:raise ValueError('private evaluator child only')
    from tools.research_reduced_evaluator import worker
    inputs,output=map(Path,sys.argv[2:4]);identifier=sys.argv[4]
    wheels,site,plan=map(Path,sys.argv[5:8])
    result=worker(inputs,output,identifier,wheels,site,json.loads(plan.read_bytes()))
    raise SystemExit(0 if result['status']=='PASS' else 1)
