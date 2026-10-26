"""Bounded CPU collector and evaluator connection for qualified development inputs.

No downloads, provider calls, GPU access, training, retries or implicit fallback.
"""
import base64
from collections import Counter, defaultdict
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import time

from tools import abductive_benchmark as base
from tools import abductive_scoring as score
from tools import exact_teacher as exact
from tools import small_model_readiness as ready
from tools import temporal_benchmark as temporal
from tools import temporal_scoring as temporal_score

MAX_FRAME = 1024 * 1024
WORKER = exact.ROOT / 'tools/small_model_worker.py'


def source_hashes():
    return dict(ready.source_hashes(), **{p: exact.sha((exact.ROOT/p).read_bytes()) for p in (
        'tools/small_model_runner.py', 'tools/small_model_worker.py')})


def load_scope(directory, packets_path, report_path):
    """Reproduce the pinned scope; reject changed prompts, selections or budgets."""
    directory = exact._local_path(directory)
    if {p.name for p in directory.iterdir()} != {'plan.json', 'B0-json.jsonl', 'B1-json.jsonl'}:
        raise ValueError('unexpected scope members')
    plan_raw = regular(directory/'plan.json', MAX_FRAME)
    plan = base.strict_json(plan_raw)
    packets, _ = ready.read_packets(packets_path)
    raw = regular(exact._local_path(report_path), 16*MAX_FRAME)
    report = base.strict_json(raw)
    ready.validate_report(report, packets)
    scope = plan['scope']
    if scope not in ('smoke', 'screening'):
        raise ValueError('invalid scope')
    selection = ready.selected_cases(1 if scope == 'smoke' else 8)
    if (plan['source_hashes'] != ready.source_hashes() or plan['selection'] != selection
            or plan['generation'] != ready.lock()['generation']
            or plan['tokenization_report_sha256'] != exact.sha(raw)
            or plan['gpu_run_authorized'] is not False
            or plan['status'] != 'PREPARED_NOT_GPU_QUALIFIED'):
        raise ValueError('unqualified scope')
    expected_models = {k: {f: v[f] for f in ('repo_id','revision')} for k,v in ready.lock()['models'].items()}
    if plan['models'] != expected_models or plan['model_loading'] != ready.lock()['model_loading']:
        raise ValueError('changed model identity or loading')
    selected = {r['id'] for r in selection}
    inputs = {}
    for arm in ('B0', 'B1'):
        name = arm+'-json.jsonl'
        rows = [r for r in packets[name] if r['id'] in selected]
        expected = b''.join(exact.canonical(r) for r in rows)
        if regular(directory/name, MAX_FRAME) != expected or plan['files'][name] != base.file_info(expected):
            raise ValueError('changed scope input bytes')
        inputs[arm] = rows
    requests = len(selection)*2
    token_index = {(c['model'],c['packet'],c['id']):c for c in report['cases']}
    tokens = {m: sum(token_index[m,arm+'-json.jsonl',r['id']]['input_tokens']
                    for arm,rows in inputs.items() for r in rows) for m in ready.MODELS}
    if (plan['requests_per_model'] != requests or plan['total_requests'] != requests*2
            or plan['input_tokens_per_model'] != tokens
            or plan['max_output_tokens_per_model'] != requests*4096):
        raise ValueError('changed scope accounting')
    schedule = []
    for model in ready.MODELS:
        for index in range(len(selection)):
            for arm in ('B0', 'B1'):
                row = inputs[arm][index]
                token = token_index[model,arm+'-json.jsonl',row['id']]
                schedule.append({'model': model, 'arm': arm, 'id': row['id'], 'messages': row['messages'],
                                 'input_tokens': token['input_tokens'], 'input_ids_sha256': token['token_ids_sha256']})
    return plan, schedule, exact.sha(plan_raw)


def regular(path, limit=MAX_FRAME):
    import stat
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('bounded regular non-hardlinked file required')
        raw = f.read(limit+1)
        if len(raw) > limit:
            raise ValueError('file grew beyond limit')
        return raw


def verify_pretrained_directory(name, directory):
    """Verify full local weight bytes, not merely the previously acquired header."""
    import stat
    directory=exact._local_path(directory)
    if directory.is_symlink() or {p.name for p in directory.iterdir()} != {'config.json','generation_config.json','model.safetensors'}:
        raise ValueError('only the three pinned checkpoint files may be mounted')
    spec=ready.lock()['models'][name]
    for filename in ('config.json','generation_config.json'):
        raw=regular(directory/filename)
        if len(raw)!=spec['files'][filename]['bytes'] or exact.sha(raw)!=spec['files'][filename]['sha256']:
            raise ValueError('checkpoint configuration mismatch')
    weight=spec['weights_metadata_only'][0]
    fd=os.open(directory/'model.safetensors',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=weight['bytes']:
            raise ValueError('full checkpoint size/type mismatch')
        digest=hashlib.sha256()
        while chunk:=stream.read(MAX_FRAME):digest.update(chunk)
        after=os.fstat(stream.fileno())
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or digest.hexdigest()!=weight['lfs']['oid']:
            raise ValueError('full checkpoint hash mismatch')
    return {'model':name,'revision':spec['revision'],'bytes':weight['bytes'],'sha256':digest.hexdigest()}


def pretrained_cpu_factory(python,sources,models,jobs):
    """Explicit local-only CPU entry; never downloads weights or exposes GPU devices.

    This path remains unexecuted with pretrained weights until they are supplied.
    Model assets must remain owner-controlled and unchanged for the run.
    """
    ready.check_packages();sources=ready.validate_sources(sources)
    ready.inspect_models(sources)
    verified={n:verify_pretrained_directory(n,Path(models)/n) for n in ready.MODELS}
    jobs=exact._local_path(jobs);jobs.mkdir(mode=0o700,exist_ok=False)
    for name in ready.MODELS:
        header=base.strict_json((sources/name/'tensor-header.json').read_bytes())
        allowed=[k for k in header if k.startswith(ready.NON_TEXT_PREFIXES)]
        job={'mode':'pretrained_cpu','packages':ready.lock()['cpu_runtime']['packages'],
             'key_mapping':ready.lock()['model_loading']['key_mapping'],
             'max_input_tokens':12288,'max_new_tokens':4096,'allowed_unexpected_keys':allowed}
        base.private_write(jobs/(name+'.json'),exact.canonical(job))
    base.private_write(jobs/'verified-weights.json',exact.canonical(verified))
    commands={name:jail_command(python,Path(models)/name,sources/name,jobs/(name+'.json')) for name in ready.MODELS}
    def make(name,output):
        return Channel(commands[name],output/(name+'-stderr.log'))
    return make


def jail_command(python, model, tokenizer, job, *, script=WORKER, probe=None):
    """Empty mount tree, explicit read-only assets, private PID/network/user namespaces."""
    if sys.platform != 'linux' or os.geteuid() != 0 or not shutil.which('bwrap'):
        raise RuntimeError('native root Linux with bubblewrap required; no fallback')
    python = Path(python).absolute()
    runtime = python.parent.parent
    # This is a trusted, already hash-qualified interpreter, never model input.
    prefix = subprocess.check_output([str(python), '-I', '-c', 'import sys; print(sys.base_prefix)'],
                                     timeout=10, env={'PATH':'/usr/bin:/bin'}).decode().strip()
    command = [shutil.which('bwrap'), '--unshare-user', '--unshare-pid', '--unshare-net',
        '--unshare-ipc', '--unshare-uts', '--disable-userns', '--die-with-parent', '--new-session',
        '--uid','65532','--gid','65532','--cap-drop','ALL','--clearenv',
        '--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib',
        '--symlink','usr/lib64','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp',
        '--ro-bind',str(runtime),str(runtime)]
    if not Path(prefix).is_relative_to('/usr') and Path(prefix) != runtime:
        command += ['--ro-bind',prefix,prefix]
    for host, guest in [(model,'/model'), (tokenizer,'/tokenizer'), (job,'/job.json'), (script,'/worker.py')]:
        command += ['--ro-bind',str(Path(host).absolute()),guest]
    if probe is not None:
        command += ['--bind',str(Path(probe).absolute()),'/probe']
    for key, value in {'PATH':'/usr/bin:/bin', 'HOME':'/tmp', 'HF_HUB_OFFLINE':'1',
        'TOKENIZERS_PARALLELISM':'false', 'OMP_NUM_THREADS':'1', 'OPENBLAS_NUM_THREADS':'1',
        'PYTHONDONTWRITEBYTECODE':'1', 'LANG':'C.UTF-8'}.items():
        command += ['--setenv',key,value]
    return command + ['--chdir','/tmp',str(python),'-I','/worker.py']


class Channel:
    def __init__(self, command, log):
        self.log = open(log, 'xb')
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.log, bufsize=0, start_new_session=True, close_fds=True,
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        os.set_blocking(self.process.stdin.fileno(), False)
        os.set_blocking(self.process.stdout.fileno(), False)
        self.partial = b''

    def wait(self, descriptor, event, deadline):
        with selectors.DefaultSelector() as selector:
            selector.register(descriptor, event)
            remaining = deadline-time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise TimeoutError('worker deadline')

    def read(self, deadline):
        self.partial = b''
        while True:
            self.wait(self.process.stdout, selectors.EVENT_READ, deadline)
            chunk = os.read(self.process.stdout.fileno(), min(65536, MAX_FRAME+1-len(self.partial)))
            if not chunk:
                raise EOFError('worker ended before response')
            self.partial += chunk
            if len(self.partial) > MAX_FRAME:
                raise ValueError('worker frame exceeded limit')
            if b'\n' in self.partial:
                head, tail = self.partial.split(b'\n',1)
                if tail:
                    raise ValueError('unsolicited extra worker output')
                return base.strict_json(head)

    def exchange(self, request, deadline):
        self.partial = b''
        raw = exact.canonical(request)
        if len(raw) > 65536:
            raise ValueError('request exceeded wire limit')
        while raw:
            self.wait(self.process.stdin, selectors.EVENT_WRITE, deadline)
            raw = raw[os.write(self.process.stdin.fileno(), raw):]
        return self.read(deadline)

    def close(self):
        with contextlib.suppress(OSError): self.process.stdin.close()
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError): os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=5)
        self.process.stdout.close()
        self.log.close()
        return self.process.returncode


def response_record(frame, request, tokenizer, max_new_tokens):
    exact._keys(frame, {'id','input_tokens','input_ids_sha256','output_ids','raw_text','elapsed_seconds'})
    if any(frame[k] != request[k] for k in ('id','input_tokens','input_ids_sha256')):
        raise ValueError('response identity/tokenization mismatch')
    ids = frame['output_ids']
    if (not isinstance(ids,list) or not 0 < len(ids) <= max_new_tokens
            or any(type(t) is not int or not 0 <= t < len(tokenizer) for t in ids)):
        raise ValueError('invalid output token IDs')
    seconds = frame['elapsed_seconds']
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError('invalid worker duration')
    decoded = tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
    if decoded != frame['raw_text']:
        raise ValueError('raw text differs from token IDs')
    terminal = ids[-1] if ids[-1] in (1,106,50) else None
    body = ids[:-1] if terminal in (1,106) else ids
    answer = tokenizer.decode(body, skip_special_tokens=False, clean_up_tokenization_spaces=False)
    reason = 'END' if terminal in (1,106) else 'LENGTH_LIMIT' if len(ids)==max_new_tokens else 'NO_TERMINAL'
    invalid = 50 in ids or reason != 'END' or '<|channel>thought' in answer or '<|think|>' in answer
    try:
        base.strict_json(answer)
    except (ValueError,TypeError,RecursionError):
        invalid = True
    return {'status':'INVALID_OUTPUT' if invalid else 'OK', 'finish_reason':reason,
            'raw_output_ids':ids, 'raw_text':decoded, 'answer_text':answer,
            'generated_tokens':len(ids),'worker_seconds':seconds}


def collect(schedule, output, worker_factory, tokenizers, *, mode, max_new_tokens,
            total_seconds, startup_seconds=30, request_seconds=30, fixture_ids=None):
    """One deadline includes startup; original assignments are always retained."""
    if mode not in ('random_fixture','scripted_control','pretrained_cpu'):
        raise ValueError('invalid execution evidence mode')
    if fixture_ids is not None and mode != 'scripted_control':
        raise ValueError('authored responses cannot enter a model worker')
    if not (0 < total_seconds <= 3000 and 0 < startup_seconds <= total_seconds
            and 0 < request_seconds <= total_seconds and type(max_new_tokens) is int and 0 < max_new_tokens <= 4096):
        raise ValueError('bounded execution limits required')
    keys = [(r['model'],r['arm'],r['id']) for r in schedule]
    if not keys or len(keys) != len(set(keys)):
        raise ValueError('nonempty unique assignments required')
    output = exact._local_path(output); output.mkdir(mode=0o700,exist_ok=False)
    records = [dict(model=r['model'],arm=r['arm'],id=r['id'],status='NOT_RUN') for r in schedule]
    assignment = {'mode':mode,'source_hashes':source_hashes(),'requests':[
        {k:v for k,v in r.items() if k!='messages'} for r in schedule],
        'max_new_tokens':max_new_tokens,'total_seconds':total_seconds,
        'startup_seconds':startup_seconds,'request_seconds':request_seconds,'retries':0}
    base.private_write(output/'assignment.json',exact.canonical(assignment))
    started=time.monotonic(); deadline=started+total_seconds
    channel=None; active=None; hellos={}; exits={}; error=None
    ledger=(output/'ledger.jsonl').open('xb')
    try:
        for index,request in enumerate(schedule):
            if time.monotonic() >= deadline:
                error='TOTAL_DEADLINE'; break
            model=request['model']
            if model != active:
                if channel is not None:
                    exits[active]=channel.close(); channel=None
                    if exits[active] != 0:
                        error='WORKER_EXIT'; break
                active=model
                try:
                    channel=worker_factory(model,output)
                    hello=channel.read(min(deadline,time.monotonic()+startup_seconds))
                    if (hello.get('ready') is not True or hello.get('mode') != mode or hello.get('uid') != 65532
                            or hello.get('caps') != 0 or hello.get('no_new_privs') != '1'
                            or hello.get('pid_namespace') == os.readlink('/proc/self/ns/pid')
                            or hello.get('net_namespace') == os.readlink('/proc/self/ns/net')):
                        raise ValueError('worker isolation/mode handshake failed')
                    hellos[model]=hello
                except (OSError,ValueError,TimeoutError,EOFError) as exc:
                    error='STARTUP_'+type(exc).__name__; break
            wire={k:request[k] for k in ('id','messages','input_tokens','input_ids_sha256')}
            if mode == 'scripted_control':
                wire['fixture_ids']=fixture_ids[request['id']]
            ledger.write(exact.canonical({'event':'STARTED','index':index,'model':model,'arm':request['arm'],'id':request['id']}))
            ledger.flush(); os.fsync(ledger.fileno())
            try:
                frame=channel.exchange(wire,min(deadline,time.monotonic()+request_seconds))
                # Preserve the entire received bounded frame before interpreting it.
                base.private_write(output/f'wire-{index:04d}.json',channel.partial)
                records[index].update(response_record(frame,wire,tokenizers[model],max_new_tokens))
            except (OSError,ValueError,TypeError,KeyError,TimeoutError,EOFError,RecursionError) as exc:
                records[index]['status']='TIMEOUT' if isinstance(exc,TimeoutError) else 'WORKER_ERROR'
                records[index]['error_type']=type(exc).__name__
                records[index]['partial_wire_base64']=base64.b64encode(channel.partial).decode()
                error=records[index]['status']
            ledger.write(exact.canonical({'event':'FINISHED','index':index,'record':records[index]}))
            ledger.flush(); os.fsync(ledger.fileno())
            if error: break
    except BaseException as exc:
        error='COORDINATOR_'+type(exc).__name__
        raise
    finally:
        if channel is not None:
            exits[active]=channel.close()
            if error is None and exits[active] != 0: error='WORKER_EXIT'
        ledger.close()
        report={'status':'INCOMPLETE' if error else 'COMPLETED', 'mode':mode,'error':error,
            'assigned':len(records),'coverage':dict(Counter(r['status'] for r in records)),
            'records':records,'worker_handshakes':hellos,'worker_exit_codes':exits,
            'wall_seconds':time.monotonic()-started,'source_hashes':source_hashes(),
            'pretrained_capability_claim':'NOT_ESTABLISHED','gpu_run':False,'training':False}
        base.private_write(output/'collection.json',exact.canonical(report))
    return report


def evaluate(plan,schedule,collection):
    """Trusted evaluator runs after worker cleanup; no references enter real workers."""
    expected=[(r['model'],r['arm'],r['id']) for r in schedule]
    if [(r['model'],r['arm'],r['id']) for r in collection['records']] != expected:
        raise ValueError('collection does not cover original ordered assignments')
    if collection['source_hashes'] != source_hashes() or any(r['status'] not in
        ('OK','INVALID_OUTPUT','TIMEOUT','WORKER_ERROR','INTERRUPTED','NOT_RUN') for r in collection['records']):
        raise ValueError('unknown status or stale collector source')
    metadata={r['id']:r for r in plan['selection']}
    payloads={r['id']:base.strict_json(r['messages'][1]['content']) for r in schedule if r['arm']=='B0'}
    labels={i:{'id':i,'family':metadata[i]['family'],'episode':metadata[i]['episode'],
               'reference':(temporal.reference(p) if p['task']=='temporal_revision' else base.reference(p))}
            for i,p in payloads.items()}
    reports={}
    for model in ready.MODELS:
        reports[model]={}
        for arm in ('B0','B1'):
            records=[r for r in collection['records'] if r['model']==model and r['arm']==arm]
            group={}
            for kind,scorer in [('static',score),('temporal',temporal_score)]:
                chosen=[r for r in records if (payloads[r['id']]['task']=='temporal_revision')==(kind=='temporal')]
                agents=[{'id':r['id'],'input':payloads[r['id']]} for r in chosen]
                refs=[labels[r['id']] for r in chosen]
                predictions=[{'id':r['id'],'response':r['answer_text'] if r['status']=='OK' else None}
                             for r in chosen if r['status'] in ('OK','INVALID_OUTPUT')]
                result=scorer.score_records(agents,refs,predictions)
                received={r['id'] for r in chosen if r['status'] in ('OK','INVALID_OUTPUT')}
                conditional=temporal_score.aggregate([c for c in result['cases'] if c['id'] in received])
                group[kind]={'assigned_protocol_scores':result,'received_only_case_metrics':conditional,
                    'received':len(received),'assigned':len(chosen)}
            reports[model][arm]=group
    return {'status':'DESCRIPTIVE_PIPELINE_ONLY','mode':collection['mode'],'coverage':collection['coverage'],
        'scores':reports,'interpretation':'Assigned-denominator scores include protocol penalties for missing execution. They are not model accuracy when execution is incomplete. Received-only metrics exclude unexecuted cases; paired metrics require complete assigned episodes.',
        'confidence_intervals':'NOT_COMPUTED','capability_claim':'NOT_ESTABLISHED'}


def recover(output):
    """Recover an interrupted coordinator from fsynced records without rerunning requests."""
    output=exact._local_path(output)
    assignment=base.strict_json(regular(output/'assignment.json',16*MAX_FRAME))
    if assignment['source_hashes'] != source_hashes():
        raise ValueError('recovery source changed')
    records=[{k:r[k] for k in ('model','arm','id')}|{'status':'NOT_RUN'} for r in assignment['requests']]
    completed=0;active=None;partial=False
    raw=regular(output/'ledger.jsonl',32*MAX_FRAME)
    lines=raw.splitlines(keepends=True)
    if lines and not lines[-1].endswith(b'\n'):
        partial=True;lines.pop()  # Preserve raw tail on disk; never invent its result.
    for line in lines:
        item=base.strict_json(line);index=item['index']
        if type(index) is not int or index != completed or index >= len(records):
            raise ValueError('ledger assignment order changed')
        if item['event']=='STARTED':
            if active is not None or any(item[k]!=records[index][k] for k in ('model','arm','id')):
                raise ValueError('duplicate or foreign start')
            active=index
        elif item['event']=='FINISHED':
            if active != index or any(item['record'][k]!=records[index][k] for k in ('model','arm','id')):
                raise ValueError('unmatched finished record')
            records[index]=item['record'];active=None;completed+=1
        else:raise ValueError('unexpected ledger event')
    if active is not None:records[active]['status']='INTERRUPTED'
    result={'status':'RECOVERED_INCOMPLETE','mode':assignment['mode'],'source_hashes':source_hashes(),
            'assigned':len(records),'records':records,'coverage':dict(Counter(r['status'] for r in records)),
            'partial_final_ledger_line':partial,'ledger_sha256':exact.sha(raw),
            'retries':0,'capability_claim':'NOT_ESTABLISHED'}
    base.private_write(output/'recovery.json',exact.canonical(result))
    return result
