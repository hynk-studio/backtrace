"""Create-only CPU rehearsal namespaces and independent cleanup watcher.

This module deliberately has no provider create or paid authorization entry.
The Docker adapter qualifies the controller transition rules, not Runpod/GitHub
availability or a future distributed owner/watcher deployment.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.free_container_cleanup import OWNED,ID

LABEL='backtrace.research.namespace'


def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()


class Journal:
    def __init__(self,root):
        self.root=Path(root).absolute()
        if (self.root.resolve()!=self.root or not self.root.is_dir()
                or self.root.stat().st_uid!=os.geteuid() or self.root.stat().st_mode&0o077):
            raise ValueError('owner-only namespace directory required')

    @classmethod
    def create(cls,parent,source_sha,run_id,*,seconds=2700,stale_seconds=15):
        if (not re.fullmatch('[0-9a-f]{40}',source_sha) or not re.fullmatch('[1-9][0-9]{0,19}',run_id)
                or not all(type(v) in (int,float) and math.isfinite(v) for v in (seconds,stale_seconds))
                or not 0<stale_seconds<seconds<=3000):raise ValueError('finite free rehearsal identity required')
        nonce=uuid.uuid4().hex;namespace='research-split-20261025-'+nonce
        root=Path(parent)/namespace;root.mkdir(mode=0o700)
        journal=cls(root);now=time.time()
        journal.write('claim',{'namespace':namespace,'source_sha':source_sha,'run_id':run_id,
            'mode':'FREE_CPU_REHEARSAL','authorization':'NONE','created_at':now,'deadline':now+seconds,
            'stale_seconds':stale_seconds,'container_name':'backtrace-free-full-setup-'+run_id+'-serve-'+nonce[:12]})
        journal.heartbeat('prepared');return journal

    def read(self,name):
        if not re.fullmatch('[a-z][a-z0-9-]{0,80}',name):raise ValueError('state name')
        path=self.root/(name+'.json')
        if not path.exists():return None
        if path.is_symlink() or not path.is_file() or path.stat().st_size>1024**2:
            raise ValueError('bounded regular state required')
        return json.loads(path.read_bytes())

    def write(self,name,value):
        self.read(name)  # validates the name and any preexisting shape
        with (self.root/(name+'.json')).open('xb') as stream:
            os.fchmod(stream.fileno(),0o600);stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
        fd=os.open(self.root,os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)

    def claim(self):
        value=self.read('claim')
        if (not isinstance(value,dict) or value.get('namespace')!=self.root.name
                or value.get('mode')!='FREE_CPU_REHEARSAL' or value.get('authorization')!='NONE'
                or not OWNED.fullmatch(value.get('container_name',''))
                or not 0<value['stale_seconds']<value['deadline']-value['created_at']<=3000):
            raise ValueError('immutable free claim required')
        return value

    def binding(self):return hashlib.sha256(encoded(self.claim())).hexdigest()

    def heartbeat(self,phase):
        value={'claim_sha256':self.binding(),'at':time.time(),'phase':phase}
        temporary=self.root/('heartbeat-'+uuid.uuid4().hex+'.partial')
        with temporary.open('xb') as stream:
            stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,self.root/'heartbeat.json')

    def require_watcher(self):
        claim=self.claim();watch=self.read('watcher')
        if (not watch or watch['claim_sha256']!=self.binding()
                or not 0<=time.time()-watch['at']<claim['stale_seconds']):
            raise ValueError('fresh independently started watcher required before container create')


class DockerResource:
    def __init__(self,claim):self.claim=claim

    def observe(self):
        name=self.claim['container_name']
        result=subprocess.run(['docker','container','ls','--all','--no-trunc','--filter','name='+name,
            '--format','{{.ID}} {{.Names}}'],capture_output=True,text=True,check=True,timeout=5)
        rows=[]
        for line in result.stdout.splitlines():
            identity,actual=line.split()
            if actual==name:
                if not ID.fullmatch(identity):raise ValueError('invalid resource identity')
                rows.append(identity)
        if not rows:return None
        if len(rows)!=1:raise ValueError('ambiguous resource identity')
        result=subprocess.run(['docker','inspect',rows[0]],capture_output=True,text=True,check=True,timeout=5)
        actual=json.loads(result.stdout)[0]
        if (actual['Id']!=rows[0] or actual['Name']!='/'+name
                or actual['Config']['Labels'].get(LABEL)!=self.claim['namespace']):
            raise ValueError('resource namespace mismatch')
        return rows[0]

    def delete(self,identity):
        # Reobserve before mutation; identity changes and failed reads never authorize deletion.
        observed=self.observe()
        if observed is None:return
        if observed!=identity:raise ValueError('resource changed before deletion')
        subprocess.run(['docker','rm','-f',identity],capture_output=True,check=True,timeout=10)


def cleanup(resource,*,seconds=30):
    end=time.monotonic()+seconds;observations=[];absent=0
    while time.monotonic()<end:
        try:
            identity=resource.observe()
            observations.append({'state':'ABSENT' if identity is None else 'PRESENT','identity':identity})
            absent=absent+1 if identity is None else 0
            if absent==2:return {'status':'PASS','absence_reads':2,'observations':observations}
            if identity is not None:
                try:resource.delete(identity)
                except Exception as error:observations.append({'delete_error':type(error).__name__})
        except Exception as error:
            absent=0;observations.append({'state':'UNKNOWN','error_type':type(error).__name__})
        time.sleep(.1)
    return {'status':'FAIL','absence_reads':absent,'observations':observations}


def watch(journal,resource,*,interval=.2):
    claim=journal.claim();binding=journal.binding()
    journal.write('watcher',{'claim_sha256':binding,'at':time.time(),'pid':os.getpid()})
    reason=None
    while reason is None:
        now=time.time()
        try:
            if journal.binding()!=binding:raise ValueError('claim mutation')
            heartbeat=journal.read('heartbeat')
            if journal.read('owner-done'):reason='OWNER_DONE'
            elif now>=claim['deadline']:reason='TOTAL_DEADLINE'
            elif (not heartbeat or heartbeat.get('claim_sha256')!=binding
                    or not 0<=now-heartbeat['at']<claim['stale_seconds']):reason='OWNER_LOST'
        except Exception:reason='STATE_UNAVAILABLE'
        if reason is None:time.sleep(interval)
    result=dict(cleanup(resource),reason=reason,claim_sha256=binding,independent_pid=os.getpid())
    journal.write('watcher-cleanup',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('namespace',type=Path)
    args=parser.parse_args();journal=Journal(args.namespace)
    result=watch(journal,DockerResource(journal.claim()))
    raise SystemExit(0 if result['status']=='PASS' else 1)
