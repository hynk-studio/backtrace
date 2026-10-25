"""Bounded inference-only TLS process; works without nested namespace privileges.

This entrypoint expects an already-running loopback inference server. It neither
starts a GPU nor accepts credentials, tools, task archives, or evaluation labels.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.research_split import inference_proxy


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('material',type=Path); parser.add_argument('output',type=Path)
    parser.add_argument('--upstream-port',type=int,required=True)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--lifetime',type=float,default=10800)
    args=parser.parse_args(); stopped=threading.Event()
    for signum in (signal.SIGTERM,signal.SIGINT): signal.signal(signum,lambda *_:stopped.set())
    begun=time.monotonic()
    with inference_proxy(args.material,args.upstream_port,host='0.0.0.0',port=args.port,
                         lifetime=args.lifetime) as (port,state):
        stopped.wait(args.lifetime)
    report={'status':'PASS','requests':dict(state),'wall_seconds':time.monotonic()-begun,
            'kind':'INFERENCE_ONLY_TLS_FORWARDER','closed':True,'model_started_by_forwarder':False}
    with args.output.open('x') as stream:
        os.fchmod(stream.fileno(),0o600); json.dump(report,stream,sort_keys=True)


if __name__=='__main__': main()
