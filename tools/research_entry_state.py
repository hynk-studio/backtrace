"""New durable namespace; no access to historical claims or paid branch heads."""
import base64
import hashlib
import json
import re
import time
import urllib.error
import urllib.request

from tools.research_entry_contract import REPOSITORY, STATE, encoded
from tools.runpod_control import NoRedirect

MUTABLE = frozenset({'heartbeat','watcher'})
NAMES = MUTABLE | {'authorization','claim','armed','pod','export','owner-done',
    'owner-cleanup','watcher-cleanup','probe-owner','probe-watch'}


class StateError(RuntimeError): pass


class State:
    def __init__(self, token, namespace, *, opener=None):
        if not token or '\n' in token or not re.fullmatch('[a-z0-9-]{5,100}', namespace):
            raise ValueError('token and new scoped namespace required')
        self.token, self.namespace = token, namespace
        self.last_rate=None
        self.open = opener or urllib.request.build_opener(NoRedirect()).open

    def request(self, method, path, body=None, *, missing=False):
        req=urllib.request.Request('https://api.github.com/repos/'+REPOSITORY+path,
            data=None if body is None else encoded(body), method=method,
            headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json',
                'X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
        try:
            with self.open(req, timeout=10) as response:
                headers=getattr(response,'headers',{})
                try:
                    self.last_rate={k:int(headers['x-ratelimit-'+k]) for k in ('limit','remaining','reset')}
                    self.last_rate.update(resource=headers['x-ratelimit-resource'],observed_at=time.time())
                except (KeyError,TypeError,ValueError):self.last_rate=None
                data=response.read(1024**2+1)
                if not 200 <= response.status < 300 or len(data)>1024**2: raise StateError('state response')
                return json.loads(data)
        except urllib.error.HTTPError as error:
            if missing and error.code==404:return None
            raise StateError('state HTTP '+str(error.code)) from None
        except (OSError, ValueError):raise StateError('state transport or JSON') from None

    def path(self,name):
        if name not in NAMES:raise ValueError('state name')
        return '/contents/research-state/'+self.namespace+'/'+name+'.json'

    def read(self,name):
        obj=self.request('GET',self.path(name)+'?ref='+STATE,missing=True)
        if obj is None:return None
        try:
            if obj['type']!='file' or obj['encoding']!='base64':raise ValueError()
            raw=base64.b64decode(obj['content']);value=json.loads(raw)
            actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            if len(raw)>65536 or obj['sha']!=actual or not isinstance(value,dict):raise ValueError()
            return value,actual
        except (KeyError,ValueError,TypeError):raise StateError('invalid state blob') from None

    def write(self,name,value,previous=None):
        if name=='authorization':raise ValueError('only explicit owner action writes authorization')
        if previous is not None and (name not in MUTABLE or not re.fullmatch('[0-9a-f]{40}',previous)):
            raise ValueError('immutable state cannot be overwritten')
        raw=encoded(value)
        if len(raw)>65536:raise ValueError('state size')
        body={'branch':STATE,'message':'Record research '+name,'content':base64.b64encode(raw).decode()}
        if previous:body['sha']=previous
        # Recover only explicit same-file CAS-preserving 409 conflicts. An
        # ambiguous write is read-confirmed, never blindly sent a second time.
        for attempt in range(4):
            try:
                self.request('PUT',self.path(name),body);break
            except StateError as error:
                if str(error)=='state HTTP 409' and attempt<3:
                    current=self.read(name)
                    if (current[1] if current else None)==previous:
                        time.sleep(.1*(attempt+1));continue
                if name not in MUTABLE:raise
                break
        for attempt in range(4):
            check=self.read(name)
            if check and encoded(check[0])==raw:return check[1]
            if check and name in MUTABLE and check[0].get('at',0)>=value.get('at',0):break
            time.sleep(.1*(attempt+1))
        raise StateError('durable write not confirmed')

    def run(self,run_id):
        if not re.fullmatch('[1-9][0-9]{0,19}',str(run_id)):raise ValueError('run id')
        return self.request('GET','/actions/runs/'+str(run_id))
