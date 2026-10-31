"""Pinned public bytes enter trusted preparation; private bytes retain SSH delivery.

This is an alternate transport only. Installation and model workers remain offline.
The standalone receive entry has no provider credentials or repository imports.
"""
import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

MAX_MANIFEST=1024**2
MAX_TOTAL=32*1024**3
MAX_LOCAL=64*1024**2
LOCAL_SECONDS=90
MANIFEST_NAME='delivery-manifest.json'
ORIGINS={'files.pythonhosted.org','download.pytorch.org','download-r2.pytorch.org','pypi.nvidia.com','huggingface.co'}


def sha(data):return hashlib.sha256(data).hexdigest()


def public_url(url,*,redirect=False):
    p=urllib.parse.urlsplit(url)
    allowed=p.hostname in ORIGINS or (redirect and p.hostname and
        (p.hostname.endswith('.hf.co') or p.hostname.endswith('.huggingface.co') or p.hostname.endswith('.nvidia.com')))
    if (p.scheme!='https' or not allowed or p.username or p.password or p.port not in (None,443)
            or p.fragment):raise ValueError('only credential-free pinned public HTTPS assets')
    return url


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        public_url(newurl,redirect=True)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def manifest_rows(raw,expected_sha):
    if len(raw)>MAX_MANIFEST or sha(raw)!=expected_sha:raise ValueError('manifest identity')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate manifest key')
            result[key]=value
        return result
    manifest=json.loads(raw,object_pairs_hook=pairs)
    if (set(manifest)!={'schema_version','phase','files'} or manifest['schema_version']!=1
            or manifest['phase'] not in ('bootstrap','model')):raise ValueError('manifest schema')
    rows=manifest['files']
    if not isinstance(rows,list) or not 1<=len(rows)<=1024:raise ValueError('manifest count')
    names=[];total=0
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'path','bytes','sha256'}:raise ValueError('manifest row')
        name=row['path'];p=PurePosixPath(name)
        if (not isinstance(name,str) or str(p)!=name or p.is_absolute() or '..' in p.parts
                or not re.fullmatch(r'[A-Za-z0-9_./+-]+',name) or name in ('','.',MANIFEST_NAME)):
            raise ValueError('plain relative manifest path')
        if type(row['bytes']) is not int or not 0<=row['bytes']<=MAX_TOTAL:raise ValueError('file size')
        if not isinstance(row['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',row['sha256']):raise ValueError('file hash')
        names.append(name);total+=row['bytes']
    if (names!=sorted(set(names)) or total>MAX_TOTAL or
            any(str(p) in names for n in names for p in PurePosixPath(n).parents if str(p)!='.')):
        raise ValueError('manifest order, collision or total')
    return manifest


def public_catalog():
    from tools import small_model_readiness as ready
    lock=ready.lock();catalog={}
    for row in lock['gpu_candidate']['wheels']:
        name=urllib.parse.unquote(urllib.parse.urlsplit(row['url']).path.rsplit('/',1)[-1])
        catalog[('bootstrap','wheels/'+name)]=(row['sha256'],public_url(row['url']))
    for model,spec in lock['models'].items():
        weight=spec['weights_metadata_only'][0]
        catalog[('model','models/'+model+'/model.safetensors')]=(
            weight['lfs']['oid'],public_url(spec['tensor_header']['url']+'?download=true'))
        for name,row in spec['files'].items():
            catalog[('model','tokenizers/'+model+'/'+name)]=(row['sha256'],public_url(row['url']))
    return catalog


def select_public(manifest,catalog):
    selected={};local=0
    for row in manifest['files']:
        pinned=catalog.get((manifest['phase'],row['path']))
        if pinned:
            if row['sha256']!=pinned[0]:raise ValueError('public asset differs from frozen hash')
            selected[row['path']]=public_url(pinned[1])
        else:local+=row['bytes']
    if not selected or local>MAX_LOCAL:raise ValueError('bounded mixed transport required')
    return selected


def plain_stage(stage,destination):
    stage=Path(stage);destination=Path(destination)
    if (stage.parent!=destination.parent or stage==destination or destination.exists() or destination.is_symlink()
            or stage.is_symlink() or not stage.is_dir()):raise ValueError('fresh adjacent staging directory')
    for p in [stage.parent,*stage.parent.parents]:
        if p.is_symlink():raise ValueError('symlink staging ancestor')
    for p in stage.rglob('*'):
        if p.is_symlink() or (not p.is_dir() and not p.is_file()):raise ValueError('plain staging tree')
    return stage,destination


def hydrate(stage,destination,bundle,expected_sha,seconds,*,opener=None,progress=None):
    """Fresh hash-bound files only; a partial response can never become installed."""
    if not 0<seconds<=1200:raise ValueError('bounded public receipt')
    raw=base64.b64decode(bundle['manifest_b64'],validate=True);manifest=manifest_rows(raw,expected_sha)
    urls=bundle['public_urls'];rows={r['path']:r for r in manifest['files']}
    if not isinstance(urls,dict) or not urls or not set(urls)<=set(rows):raise ValueError('public subset')
    for url in urls.values():public_url(url)
    stage,destination=plain_stage(stage,destination)
    present={p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
    local_raw=json.dumps(dict(manifest,files=[r for r in manifest['files'] if r['path'] not in urls]),
        sort_keys=True,separators=(',',':')).encode()+b'\n'
    if (present!=(set(rows)-set(urls))|{MANIFEST_NAME} or
            (stage/MANIFEST_NAME).read_bytes()!=local_raw):raise ValueError('authenticated local subset mismatch')
    if shutil.disk_usage(stage).free<sum(rows[n]['bytes'] for n in urls)+64*1024**2:
        raise ValueError('insufficient public receiver disk')
    opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),PublicRedirect())
    started=time.monotonic();events=[]
    try:
        for name,url in urls.items():
            row=rows[name];target=stage/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            begin=time.monotonic();count=0;digest=hashlib.sha256()
            if progress:progress({'phase':'PUBLIC_DOWNLOAD','path':name,'bytes':0,'total_bytes':row['bytes']})
            last=0
            remaining=seconds-(begin-started)
            if remaining<=0:raise TimeoutError('public delivery deadline')
            request=urllib.request.Request(url,headers={'Accept-Encoding':'identity'})
            with opener.open(request,timeout=min(30,remaining)) as response,target.open('xb') as f:
                if response.status!=200:raise ValueError('complete public asset response required')
                length=response.headers.get('Content-Length')
                if length is not None and int(length)!=row['bytes']:raise ValueError('public content length')
                for block in iter(lambda:response.read(4*1024**2),b''):
                    count+=len(block)
                    if count>row['bytes'] or time.monotonic()-started>seconds:raise ValueError('public size or deadline')
                    f.write(block);digest.update(block)
                    if progress and count-last>=64*1024**2:
                        progress({'phase':'PUBLIC_DOWNLOAD','path':name,'bytes':count,'total_bytes':row['bytes']});last=count
                f.flush();os.fsync(f.fileno())
            if count!=row['bytes'] or digest.hexdigest()!=row['sha256']:raise ValueError('public byte identity')
            events.append({'path':name,'bytes':count,'sha256':digest.hexdigest(),'seconds':time.monotonic()-begin})
            if progress:progress({'phase':'PUBLIC_VERIFIED',**events[-1]})
        if {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}!=set(rows)|{MANIFEST_NAME}:
            raise ValueError('complete asset inventory')
        for name,row in rows.items():
            p=stage/name
            with p.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
            if p.is_symlink() or p.stat().st_size!=row['bytes'] or actual!=row['sha256']:
                raise ValueError('independent installed readback')
        (stage/MANIFEST_NAME).write_bytes(raw)
        stage.rename(destination)
        return {'receipt':{'schema_version':1,'phase':manifest['phase'],'files':len(rows),
            'bytes':sum(r['bytes'] for r in rows.values()),'manifest_sha256':expected_sha,'verified':True},
            'public_files':events,'seconds':time.monotonic()-started}
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True)
        raise


def receiver(prefix,stage,destination,raw,urls,seconds,output):
    from tools import small_model_delivery as delivery
    code=delivery.remote_python(Path(__file__).read_text())+['receive',stage,destination,sha(raw),str(seconds)]
    bundle=json.dumps({'manifest_b64':base64.b64encode(raw).decode(),'public_urls':urls}).encode()
    with Path(output).open('xb') as errors:
        p=subprocess.run(prefix+[shlex.join(code)],input=bundle,stdout=subprocess.PIPE,stderr=errors,
            timeout=seconds+5,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    if p.returncode:raise RuntimeError('pinned public receipt failed; inspect bounded receiver log')
    if len(p.stdout)>MAX_MANIFEST:raise ValueError('bounded receiver receipt')
    return json.loads(p.stdout)


@contextlib.contextmanager
def configured():
    from tools import small_model_delivery as delivery
    previous=delivery.push
    def push(root,manifest_path,command,timeout,*,diagnostics=None):
        root=Path(root);raw=Path(manifest_path).read_bytes()
        manifest=manifest_rows(raw,sha(raw));expected=delivery.verify(root,raw)
        urls=select_public(manifest,public_catalog())
        if root.name not in ('runtime','assets') or diagnostics is None:raise ValueError('explicit prepared public scope')
        destination='/root/backtrace/'+root.name;stage=destination+'-owner-delivered'
        prefix=command[:-1];report={'schema':'pinned_public_delivery_v1','status':'STARTED','expected':expected}
        started=time.monotonic()
        try:
            with tempfile.TemporaryDirectory(prefix='public-local-',dir=root.parent) as td:
                subset=Path(td)/'files';subset.mkdir()
                local_rows=[r for r in manifest['files'] if r['path'] not in urls]
                for row in local_rows:
                    p=subset/row['path'];p.parent.mkdir(parents=True,exist_ok=True);os.link(root/row['path'],p)
                local_raw=json.dumps(dict(manifest,files=local_rows),sort_keys=True,separators=(',',':')).encode()+b'\n'
                local_manifest=Path(td)/'manifest.json';local_manifest.write_bytes(local_raw)
                recv=delivery.remote_python(Path(delivery.__file__).read_text())+['receive',stage,sha(local_raw),'--progress']
                report['owner_delivery']=previous(subset,local_manifest,prefix+[shlex.join(recv)],min(LOCAL_SECONDS,timeout),
                    diagnostics=Path(str(diagnostics)+'.owner.json'))
            remaining=timeout-(time.monotonic()-started)
            report['public_delivery']=receiver(prefix,stage,destination,raw,urls,remaining,Path(str(diagnostics)+'.receiver.log'))
            if report['public_delivery']['receipt']!=expected:raise ValueError('complete mixed readback differs')
            report['status']='PASS';return expected
        except BaseException as error:
            report.update(status='FAIL',error_type=type(error).__name__);raise
        finally:
            report['elapsed_seconds']=time.monotonic()-started
            Path(diagnostics).write_text(json.dumps(report,sort_keys=True)+'\n')
    delivery.push=push
    try:yield
    finally:delivery.push=previous


def qualify_model(prefix,output):
    from tools import small_model_readiness as ready,small_model_minimum_remote as remote
    row=ready.lock()['models']['E2B']['weights_metadata_only'][0]
    raw=json.dumps({'schema_version':1,'phase':'model','files':[{
        'path':'models/E2B/model.safetensors','bytes':row['bytes'],'sha256':row['lfs']['oid']}]},sort_keys=True,separators=(',',':')).encode()+b'\n'
    manifest=manifest_rows(raw,sha(raw));urls=select_public(manifest,public_catalog())
    stage='/root/backtrace/public-e2b-qualification-staging';dest='/root/backtrace/public-e2b-qualification'
    local_raw=json.dumps(dict(manifest,files=[]),sort_keys=True,separators=(',',':')).encode()+b'\n'
    remote.remote(prefix,'import pathlib,json;p=pathlib.Path('+repr(stage)+');p.mkdir(mode=0o700);(p/'+
        repr(MANIFEST_NAME)+').write_bytes('+repr(local_raw)+');print(json.dumps({}))')
    result=receiver(prefix,stage,dest,raw,urls,600,Path(output)/'public-model-qualification.log')
    remote.remote(prefix,'import shutil,json;shutil.rmtree('+repr(dest)+');print(json.dumps({}))')
    return result


if __name__=='__main__':
    if len(sys.argv)!=6 or sys.argv[1]!='receive':raise ValueError('explicit standalone receiver')
    _,_,stage,destination,expected,seconds=sys.argv
    if (not destination.startswith('/root/backtrace/') or '/' in destination[len('/root/backtrace/'):]
            or not stage.startswith('/root/backtrace/')):raise ValueError('dedicated preparation destination')
    seconds=float(seconds)
    if not 0<seconds<=1200:raise ValueError('receiver deadline')
    def expired(signum,frame):raise TimeoutError('public receipt hard deadline')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,seconds)
    raw=sys.stdin.buffer.read(MAX_MANIFEST+1)
    if len(raw)>MAX_MANIFEST:raise ValueError('bounded public receipt input')
    def progress(value):print(json.dumps(value,sort_keys=True),file=sys.stderr,flush=True)
    result=hydrate(stage,destination,json.loads(raw),expected,seconds,progress=progress)
    print(json.dumps(result,sort_keys=True),flush=True)
