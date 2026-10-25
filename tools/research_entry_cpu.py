"""Free full entry: wire adapters, independent watcher, exact serving image."""
import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

from tools import research_entry_contract as c, research_entry as entry
from tools.research_entry_prepare import prepare
from tests.research_entry_replica import Replica,clients,authorization
from tests.research_entry_replica import offer as replica_offer


def qualify(inputs,output):
    from tools.runpod_job import check_owner_host
    check_owner_host();os.umask(0o077)
    source=os.environ['GITHUB_SHA'];run_id=os.environ['GITHUB_RUN_ID']
    report={'status':'FAIL','source_sha':source,'run_id':run_id,'kind':'FULL_ENTRY_CPU_REPLICA',
        'provider_create_requests':0,'real_model_runs':0,'model_files_transferred':0}
    retained=Path(inputs)/'verifier-evidence';retained.mkdir(mode=0o700)
    with tempfile.TemporaryDirectory(prefix='backtrace-entry-',dir='/var/tmp') as temporary:
        outer=Path(temporary);outer.chmod(0o711)
        try:
            configuration,initializer,prepared=prepare(outer/'prepared',inputs,Path(output).parent,authored_cpu=True)
            report['preparation']=prepared
            with (outer/'docker-pull.log').open('wb') as log:
                subprocess.run(['docker','pull',c.CONTRACT['image']],check=True,stdout=log,stderr=log,timeout=900)
            with Replica(source,docker=True,run_id=run_id) as replica:
                namespace='free-entry-'+run_id+'-'+str(time.time_ns())
                store,api=clients(replica.port,namespace)
                limits=dict(total_seconds=2700,setup_seconds=1800,cleanup_seconds=60,
                    heartbeat_seconds=60,poll_seconds=1,unclaimed_seconds=60,unknown_create_seconds=5)
                watch_config={'port':replica.port,'namespace':namespace,'source':source,'limits':limits,'output':str(outer/'watch-result.json')}
                (outer/'watch-config.json').write_bytes(c.encoded(watch_config))
                with (outer/'watch-process.log').open('wb') as log:
                    watcher=subprocess.Popen([sys.executable,'-I','-B',str(c.ROOT/'tests/research_entry_replica.py'),str(outer/'watch-config.json')],
                        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(outer)},
                        stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
                    try:
                        end=time.monotonic()+15
                        while not store.read('watcher'):
                            if watcher.poll() is not None or time.monotonic()>end:raise RuntimeError('watcher did not start')
                            time.sleep(.1)
                        report['owner']=entry.execute(store,api,authorization(source),replica_offer(),initializer,
                            configuration,configuration['directory'],source,'11',replica=True,limits=limits)
                        watcher.wait(timeout=90)
                        report['watcher']=json.loads((outer/'watch-result.json').read_bytes())
                        report['replica']={'create_requests':replica.create_count,'delete_requests':replica.delete_count,
                            'remaining_resources':len(replica.pods),'requests':replica.requests,
                            'namespace':namespace,'watcher_pid':watcher.pid,'owner_pid':os.getpid(),
                            'state_records':{name:json.loads(raw) for name,(raw,sha) in replica.files.items()}}
                        owner=report['owner'];watch=report['watcher'];worker=owner.get('worker',{})
                        slots=worker.get('slots',{}).get('slots',[])
                        stop=worker.get('stages',{}).get('server_stop',{})
                        attempted=[request for row in slots for request in row.get('result',{}).get('accounting',{}).get('requests',[])]
                        report['checks']={'owner':owner['status']=='PASS','watcher':watch['status']=='DELETED',
                            'single_create':replica.create_count==1,'no_remaining_resource':not replica.pods,
                            'nine_slots':len(slots)==9 and all(r['status']=='COMPLETED' for r in slots),
                            'exact_54_attempts':len(attempted)==54,
                            'exact_request_order':[r['forwarded_sha256'] for r in attempted]==[r['sha256'] for r in stop.get('transport',{}).get('attempts',[])],
                            'server_cleanup':stop.get('process_cleanup')=='PASS',
                            'export_before_owner_cleanup':worker.get('export',{}).get('completed_at',float('inf'))<=owner.get('cleanup',{}).get('started_at',0),
                            'export_before_watcher_cleanup':worker.get('export',{}).get('completed_at',float('inf'))<=watch.get('started_at',0)}
                        if all(report['checks'].values()):
                            from tools.research_reduced_evaluation import evaluate,retain
                            report['independent_evaluation']=evaluate(Path(inputs),configuration,owner,watch,authored_cpu=True)
                            retain(configuration,retained)
                            report['checks']['independent_evaluation']=report['independent_evaluation']['status']=='PASS'
                        report['status']='PASS' if all(report['checks'].values()) else 'FAIL'
                    finally:
                        if watcher.poll() is None:watcher.kill();watcher.wait(timeout=5)
        except BaseException as error:
            report.update(status='FAIL',error_type=type(error).__name__)
            (outer/'failure.log').write_text(traceback.format_exc())
        finally:
            # Keep logs and receipts, never owner keys, signed URL plans, payloads
            # or raw runtime wheels. research_assets encrypts this directory.
            for p in outer.rglob('*'):
                if (p.is_file() and not p.is_symlink() and p.suffix in ('.log','.json')
                        and not any(part in ('private','cpu-runtime','sandboxes') for part in p.relative_to(outer).parts)
                        and p.name not in ('worker-plan.json','endpoint.json','watch-config.json')):
                    dest=retained/p.relative_to(outer);dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                    shutil.copyfile(p,dest);dest.chmod(0o600)
    report['implementation']=c.source_files();report['temporary_runtime_removed']=not outer.exists()
    Path(output).write_bytes(c.encoded(report));return report


if __name__=='__main__':
    from tools.research_assets import prepare as acquire
    result=acquire(Path(sys.argv[1]),qualification=qualify,retain_inputs=False)
    print(json.dumps({'entry_cpu':result['status']}),flush=True)
    raise SystemExit(0 if result['status']=='PASS' else 1)
