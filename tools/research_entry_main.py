"""Paid workflows remain inert until an explicit source-bound owner permit exists."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time
import shutil

from tools import research_entry_contract as c, research_entry as entry
from tools.research_entry_state import State
from tools.runpod_control import RunpodAPI


def context(role):
    if (os.environ.get('GITHUB_REPOSITORY')!=c.REPOSITORY
            or os.environ.get('GITHUB_REF_NAME')!=(c.OWNER if role=='owner' else c.WATCH)
            or os.environ.get('GITHUB_RUN_ATTEMPT')!='1'):
        raise ValueError('dedicated first-run workflow required')
    return os.environ['GITHUB_SHA'],os.environ['GITHUB_RUN_ID']


def main(role):
    os.umask(0o077);source,run_id=context(role)
    state=State(os.environ['GITHUB_TOKEN'],c.PAID_NAMESPACE)
    record=state.read('authorization')
    permit=c.permit(record[0] if record else None,source,time.time())
    c.qualification(state,permit)
    if state.read('claim'):raise ValueError('pilot scope already consumed; no paid rerun')
    api=RunpodAPI(os.environ['RUNPOD_API_KEY'].strip())
    if role=='watch':return entry.watch(state,api,source,run_id)
    from tools.research_assets import prepare as acquire
    from tools.research_entry_prepare import prepare
    from tools.research_entry_offer import inspect
    from tools.runpod_job import check_owner_host
    check_owner_host()
    result={}
    def run(inputs,output):
        with tempfile.TemporaryDirectory(prefix='research-paid-entry-',dir='/var/tmp') as temporary:
            outer=Path(temporary);outer.chmod(0o711)
            config,initializer,prepared=prepare(outer/'prepared',inputs,Path(output).parent,authored_cpu=False)
            fresh=inspect()
            if not fresh['account_idle'] or api.list():raise ValueError('idle unchanged prepaid account required')
            reviewed=None
            for row in fresh['offers']:
                try:c.costs(row['offer'],permit,time.time())
                except ValueError:continue
                reviewed=row['offer'];break
            if reviewed is None:raise ValueError('no fresh affordable exact offer; zero create')
            result.update(entry.execute(state,api,permit,reviewed,initializer,config,config['directory'],source,run_id))
            result['preparation']=prepared
            from tools.research_reduced_evaluation import evaluate,retain
            # Allocation cleanup has finished. Allow the independent watcher to
            # publish its matching deletion proof before free CPU evaluation.
            end=time.monotonic()+60;watch=None
            while time.monotonic()<end:
                try:record=state.read('watcher-cleanup')
                except Exception:record=None
                if record:watch=record[0];break
                time.sleep(2)
            result['watcher_cleanup']=watch
            try:
                result['independent_evaluation']=evaluate(Path(inputs),config,result,watch or {},authored_cpu=False)
            except Exception as error:
                result['independent_evaluation']={'status':'BLOCKED','error_type':type(error).__name__}
            if result['independent_evaluation']['status']!='PASS' and result['status']=='PASS':
                result['status']='INCOMPLETE'
            # This is an independent complete provider list and balance read,
            # after deletion, never another allocation or account-setting write.
            try:
                result['account_after']=inspect()
                result['pods_after']=[{k:p.get(k) for k in ('id','name','status')} for p in api.list()]
            except Exception as error:result['account_after_error']=type(error).__name__
            retained=Path(inputs)/'verifier-evidence';retained.mkdir(mode=0o700,exist_ok=True)
            retain(config,retained)
            for path in Path(config['directory']).rglob('*'):
                if (path.is_file() and not path.is_symlink() and path.suffix in ('.log','.json','.patch','.txt')
                        and 'sandboxes' not in path.parts and path.name not in ('worker-plan.json','endpoint.json')):
                    target=retained/path.relative_to(config['directory'])
                    target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                    shutil.copyfile(path,target);target.chmod(0o600)
            # The public acquisition envelope remains an input-acquisition
            # receipt; this separate owner report records actual paid execution.
            Path(output).write_bytes(c.encoded(result))
            return result
    envelope=acquire(c.ROOT/'evidence/research-owner',qualification=run,retain_inputs=False)
    envelope['callback_kind']='AUTHORIZED_PILOT_ENTRY'
    envelope['provider_operations']=result.get('provider_create_requests',0)
    envelope['model_execution']='SEE_SEPARATE_OWNER_AND_WORKER_RECEIPTS'
    (c.ROOT/'evidence/research-owner/assets.json').write_bytes(c.encoded(envelope))
    result['input_acquisition_status']=envelope['status']
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('role',choices=('owner','watch'))
    args=parser.parse_args();out=c.ROOT/'evidence';out.mkdir(exist_ok=True)
    try:result=main(args.role)
    except Exception as error:result={'status':'BLOCKED','error_type':type(error).__name__,'provider_create_requests':0}
    (out/('research-'+args.role+'.json')).write_bytes(c.encoded(result))
    print(json.dumps({'role':args.role,'status':result.get('status')}))
    raise SystemExit(0 if result.get('status') in ('PASS','DELETED','NO_CLAIM') else 1)
