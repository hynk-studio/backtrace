"""Inference-only process owner. No provider, task archive, evaluator or credential API.

The same supervisor is rehearsed with an explicitly labelled authored CPU child.
Real model startup additionally requires the exact local weights and a CUDA GPU.
"""
import argparse
import contextlib
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.research_split import inference_proxy
from tools.research_split_server import MODEL_PATH, PATH, server_configuration
from tools.startup_guard import child_subreaper, group_members, stop_group

CLEAN={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':'/root',
       'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','PYTHON_DOTENV_DISABLED':'1',
       'OTEL_SDK_DISABLED':'true','LITELLM_LOCAL_MODEL_COST_MAP':'True','LITELLM_TELEMETRY':'False'}


def write_new(path,value):
    with Path(path).open('x') as stream:
        os.fchmod(stream.fileno(),0o600)
        json.dump(value,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())


def official_command(port):
    from adk_submission import VllmServer
    server=VllmServer(server_configuration(port))
    try:
        command=server.build_cmd()
        # The installed official builder uses the current Python interpreter.
        if command[0]!=sys.executable:raise ValueError('official interpreter changed')
        return command
    finally:
        server.stop();Path(server.log_path).unlink(missing_ok=True)


def model_ready(manifest):
    from tools.private_delivery import verify
    expected=Path(manifest).read_bytes()
    if hashlib.sha256(expected).hexdigest()!=MODEL_MANIFEST_SHA256:
        raise ValueError('model manifest identity changed')
    verified=verify(Path(MODEL_PATH),expected)
    import torch
    if (not torch.cuda.is_available() or torch.cuda.device_count()!=1
            or 'A100' not in torch.cuda.get_device_name(0)
            or torch.cuda.get_device_properties(0).total_memory < 79*1024**3):
        raise ValueError('one A100 80GB required before model launch')
    return verified


def readiness(port,*,authored=False,timeout=1):
    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=timeout)
    try:
        connection.request('GET',PATH,headers={'Connection':'close'})
        response=connection.getresponse();raw=response.read(65537)
        if response.status!=200 or len(raw)>65536:return None
        value=json.loads(raw)
        if authored:
            if value!={'status':'AUTHORED_CPU','model_execution':False}:return None
        else:
            expected={'model':MODEL_PATH,'max_model_len':32768,'tensor_parallel_size':1,
                      'disable_custom_all_reduce':True,'enable_prefix_caching':False}
            observed=value.get('observed',{})
            if (value.get('status')!='PASS' or any(observed.get(k)!=v for k,v in expected.items())
                    or observed.get('dtype') not in ('bfloat16','torch.bfloat16')):return None
        return value
    finally:connection.close()


def supervise(command,material,output,*,upstream_port,tls_port,lifetime,ready_seconds,authored=False):
    if (not all(type(v) in (int,float) and math.isfinite(v) and 0<v<=10800
                for v in (lifetime,ready_seconds)) or ready_seconds>=lifetime
            or upstream_port==tls_port):raise ValueError('distinct ports and bounded deadlines required')
    output=Path(output);output.mkdir(mode=0o700)
    report={'status':'INCOMPLETE','kind':'AUTHORED_CPU' if authored else 'MODEL_INFERENCE',
            'ready':False,'process_cleanup':'UNCONFIRMED','command_sha256':
            hashlib.sha256(json.dumps(command).encode()).hexdigest()}
    stopped=threading.Event();previous={};process=None;group=None;old_reaper=child_subreaper()
    started=time.monotonic();deadline=started+lifetime
    for sig in (signal.SIGTERM,signal.SIGINT):
        previous[sig]=signal.signal(sig,lambda *_:stopped.set())
    try:
        child_subreaper(1)
        with (output/'server.log').open('xb') as log:
            process=subprocess.Popen(command,env=dict(CLEAN,PYTHONPATH=str(Path(__file__).resolve().parents[1])),stdin=subprocess.DEVNULL,stdout=log,
                stderr=log,start_new_session=True)
            group=process.pid
            report['process_group']=group
            until=min(deadline,started+ready_seconds)
            last_error=None
            while not stopped.is_set() and time.monotonic()<until:
                if process.poll() is not None:raise RuntimeError('inference child exited before readiness')
                try:observed=readiness(upstream_port,authored=authored,timeout=min(1,until-time.monotonic()))
                except (OSError,ValueError,http.client.HTTPException) as error:
                    last_error=type(error).__name__;observed=None
                if observed:break
                stopped.wait(.1)
            else:raise TimeoutError('initialized serving readiness deadline')
            report.update(ready=True,metadata=observed,ready_seconds=time.monotonic()-started,
                          last_readiness_error=last_error)
            with inference_proxy(material,upstream_port,host='0.0.0.0',port=tls_port,
                                 lifetime=max(.001,deadline-time.monotonic())) as (port,state):
                write_new(output/'ready.json',{'kind':report['kind'],'port':port,'metadata':observed,
                    'process_group':group,'ready_seconds':report['ready_seconds']})
                while not stopped.wait(.1) and time.monotonic()<deadline:
                    if process.poll() is not None:raise RuntimeError('inference child exited while serving')
            report['transport']=state
            report['status']='PASS'
            report['stop_reason']='SIGNAL' if stopped.is_set() else 'LIFETIME'
    except BaseException as error:
        report.update(status='FAIL',error_type=type(error).__name__)
    finally:
        if process is not None:
            try:
                stop_group(process,group)
                observations=[group_members(group)];time.sleep(.05);observations.append(group_members(group))
                report['process_absence_reads']=observations
                if any(observations):raise RuntimeError('server process group remains')
                report['process_cleanup']='PASS'
            except Exception as error:
                report.update(status='FAIL',cleanup_error=type(error).__name__)
        if old_reaper is not None:child_subreaper(old_reaper)
        for sig,handler in previous.items():signal.signal(sig,handler)
        report['wall_seconds']=time.monotonic()-started
        write_new(output/'receipt.json',report)
    return report


# Bound at source preparation to the unchanged eight-file model manifest.
MODEL_MANIFEST_SHA256='5da90d200d82ff2f2b3a5563b7adce4390d82418f178a3d97037ff076cc2f5a7'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('material',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--upstream-port',type=int,default=8000)
    parser.add_argument('--tls-port',type=int,default=8443)
    parser.add_argument('--lifetime',type=float,required=True)
    parser.add_argument('--ready-seconds',type=float,required=True)
    parser.add_argument('--authored-cpu',type=Path)
    parser.add_argument('--failed-readiness',action='store_true')
    parser.add_argument('--model-manifest',type=Path)
    args=parser.parse_args();os.umask(0o077)
    if args.authored_cpu:
        if args.model_manifest:parser.error('authored fixture cannot accept model inputs')
        command=[sys.executable,'-I','-B',str(args.authored_cpu),str(args.upstream_port)]
        if args.failed_readiness:command.append('--failed-readiness')
    else:
        if not args.model_manifest or args.failed_readiness:parser.error('exact model manifest required')
        model_ready(args.model_manifest);command=official_command(args.upstream_port)
    result=supervise(command,args.material,args.output,upstream_port=args.upstream_port,
        tls_port=args.tls_port,lifetime=args.lifetime,ready_seconds=args.ready_seconds,
        authored=bool(args.authored_cpu))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
