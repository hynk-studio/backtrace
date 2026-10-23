"""Free post-deletion verification of the current byte-bound R1 patch only."""
import base64
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import traceback
import zipfile

from tools import a100_delivery as frozen, cloud_resolver as resolver, cloud_state as state
from tools import cloud_seal, task_followup, cloud_task
from tools.direct_delivery import pull
from tools.pod_bootstrap import readonly
from tools.runpod_job import check_owner_host

BRANCH = 'bt-001-calibrated-evaluation-20261023'
BINDING = {'authorization': 'owner-calibrated-gpu-20261023', 'run_id': '39947273089',
    'source_sha': '6973f96255cdecf2d02f7e1ad976522f7982699d',
    'pod_id': 'i3kf5oiwlg1z3r', 'attempt': 'a90828af9e28484380c4a3fee8a2e85a'}
NAMES = ('agent.patch', 'task-result.json', 'wire.jsonl', 'results/traces/trace_fastapi_11194.json')
CLEAN = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHON_DOTENV_DISABLED': '1',
    'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'OTEL_SDK_DISABLED': 'true',
    'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'PIP_NO_INDEX': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}


def checked_claim(store):
    claim, pod = store.read('claim')[0], store.read('pod')[0]
    actual = {k: claim[k] for k in BINDING if k != 'pod_id'}
    actual['pod_id'] = pod['pod_id']
    if actual != BINDING or pod['attempt'] != claim['attempt'] or claim['run'] != cloud_task.RUN_NAME:
        raise ValueError('exact consumed R1 claim and Pod required')
    return claim


def deleted(store, claim):
    cleanup = store.read('cleanup')
    run = store.run(claim['run_id'])
    if run['head_sha'] != BINDING['source_sha'] or run['head_branch'] != state.OWNER_BRANCH or run['run_attempt'] != 1:
        raise ValueError('original paid workflow identity differs')
    if cleanup is None or run['status'] != 'completed':
        return None
    row = cleanup[0]
    if (row['attempt'] != BINDING['attempt'] or row['pod_id'] != BINDING['pod_id']
            or row['phase'] != 'deleted' or row['absence_reads'] != 2):
        return None
    return row


def receive(store, identity, prefix, root):
    import pyrage
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        row = store.request('GET', '/contents/' + prefix + '/receipts.age.b64?ref=' + state.BRANCH, missing=True)
        if row is None:
            time.sleep(5); continue
        if row.get('type') != 'file' or row.get('encoding') != 'base64':
            raise ValueError('encrypted receipt object required')
        ciphertext = base64.b64decode(base64.b64decode(row['content']), validate=True)
        if len(ciphertext) > 512 * 1024:
            raise ValueError('compressed receipt bound exceeded')
        data = pyrage.decrypt(ciphertext, [identity])
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            rows = archive.infolist()
            if (len(rows) != 5 or {x.filename for x in rows} != set(NAMES) | {'manifest.json'}
                    or sum(x.file_size for x in rows) > 16 * 1024**2
                    or any(x.is_dir() or stat.S_ISLNK(x.external_attr >> 16) for x in rows)):
                raise ValueError('exact bounded receipt members required')
            manifest = json.loads(archive.read('manifest.json'))
            if manifest.get('binding') != BINDING or set(manifest.get('files', {})) != set(NAMES):
                raise ValueError('receipt binding differs')
            bodies = {name: archive.read(name) for name in NAMES}
        for name, body in bodies.items():
            if manifest['files'][name] != {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}:
                raise ValueError('receipt bytes differ')
        root.mkdir(mode=0o700)
        for name, body in bodies.items():
            path = root / name; path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with path.open('xb') as stream: stream.write(body)
        (root.parent / 'receipt-manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2))
        return {'files': len(bodies), 'ciphertext_bytes': len(ciphertext),
                'ciphertext_sha256': hashlib.sha256(ciphertext).hexdigest(),
                'archive_sha256': hashlib.sha256(data).hexdigest()}
    raise TimeoutError('post-deletion R1 receipt deadline')


def run(root, report, emit):
    check_owner_host()
    if (os.environ.get('GITHUB_REPOSITORY') != state.REPOSITORY
            or os.environ.get('GITHUB_REF_NAME') != BRANCH
            or os.environ.get('GITHUB_RUN_ATTEMPT') != '1' or 'RUNPOD_API_KEY' in os.environ):
        raise ValueError('first-attempt free CPU context without provider key required')
    root.mkdir(mode=0o700, parents=True)
    store = state.GitHubState(os.environ['GITHUB_TOKEN']); claim = checked_claim(store)
    report['stage'] = 'resolve_frozen_inputs'
    with resolver.kaggle_client() as client:
        wheels = resolver.resolve_wheels(client, progress=lambda stage, count: emit({'stage': stage, 'files': count}))
        task = resolver.resolve_task(client)
        evaluator_manifest, evaluator = resolver.resolve_evaluator(client)
    report['stage'] = 'download_frozen_inputs'
    for kind, sources, limit in [('wheels', wheels, 1800), ('task', task, 600)]:
        data = frozen.manifest(kind)
        report[kind] = pull(root / kind, data, sources, hashlib.sha256(data).hexdigest(), limit)
    report['evaluator'] = pull(root / 'evaluator', evaluator_manifest, evaluator, hashlib.sha256(evaluator_manifest).hexdigest(), 120)
    rows = json.loads((frozen.ROOT / 'docs/a100-evaluator-dependencies.json').read_text())['files']
    data = json.dumps({'schema_version': 1, 'phase': 'bootstrap', 'files': [{k: r[k] for k in ('path', 'bytes', 'sha256')} for r in rows]}).encode()
    pull(root / 'evaluator/wheels', data, {r['path']: resolver.pypi_source(r) for r in rows}, hashlib.sha256(data).hexdigest(), 120)
    report['stage'] = 'offline_runtime'
    runtime = Path('/opt/backtrace-runtime')
    with (root / 'runtime.log').open('wb') as log:
        subprocess.run([sys.executable, '-I', str(frozen.ROOT / 'tools/linux_runtime.py'), str(root / 'wheels'),
            str(frozen.ROOT / 'docs/linux-supplemental.lock'), str(runtime)], env=CLEAN, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, check=True, timeout=1800)
    readonly(runtime)
    inputs = Path('/opt/backtrace-calibrated-eval-inputs'); shutil.copytree(root / 'task', inputs); readonly(inputs)
    identity, prefix = task_followup.receiver(store, os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_SHA'])
    emit({'stage': 'receiver', 'path': prefix, 'status': 'READY'})
    report['stage'] = 'wait_original_receipts'
    report['handoff'] = receive(store, identity, prefix, root / 'receipts')
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        report['cleanup'] = deleted(store, checked_claim(store))
        if report['cleanup']: break
        time.sleep(5)
    if not report['cleanup']: raise ValueError('confirmed deletion and completed owner run required')
    report['stage'] = 'actual_public_verifier'
    program = '''import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from tools.task_results import validate
from tools.cloud_task import RUN_NAME
from tools.qualify_evaluation import evaluate_receipts,qualify
root,inputs=map(Path,sys.argv[2:]);receipts=root/'receipts'
meta=json.loads((receipts/'task-result.json').read_text())
assert meta.get('protocol')==RUN_NAME and meta.get('budget')=={'session_seconds':300,'tool_calls':30,'llm_calls':50}
completed=True;failure=None
try: completion=validate(receipts,protocol=RUN_NAME)
except ValueError as error: completed=False;completion=None;failure=str(error)
if completed: result=evaluate_receipts(root/'evaluator/tasks.jsonl',inputs,receipts,root/'evaluation',protocol=RUN_NAME)
else: result=qualify(root/'evaluator/tasks.jsonl',inputs,receipts/'agent.patch',root/'evaluation',controls=False,partial=True)
print(json.dumps({'completed_agent_task':completed,'completion':completion,'completion_validation_error':failure,'original_task_result':meta,'evaluation':result},sort_keys=True))
'''
    with (root / 'evaluation-process.log').open('wb') as log:
        outcome = subprocess.run([str(runtime / 'venv/bin/python'), '-I', '-c', program, str(frozen.ROOT), str(root), str(inputs)],
            env=CLEAN, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log, check=True, timeout=360)
    report['result'] = json.loads(outcome.stdout.splitlines()[-1])
    report.update(status='PASS', stage='finished')


def main():
    logging.disable(logging.CRITICAL); os.umask(0o077)
    root = (frozen.ROOT / '.local/calibrated-evaluation').absolute()
    report = {'status': 'FAIL', 'stage': 'context', 'binding': BINDING,
        'gpu_allocations': 0, 'provider_mutations': 0, 'model_calls': 0, 'agent_runs': 0,
        'source_sha': os.environ['GITHUB_SHA'], 'run_id': os.environ['GITHUB_RUN_ID']}
    emit = lambda value: print(json.dumps(value, sort_keys=True), flush=True)
    try: run(root, report, emit)
    except Exception as error:
        report['failure'] = {'error_type': type(error).__name__}
        if root.is_dir(): (root / 'failure.log').write_text(traceback.format_exc())
    finally:
        evidence = frozen.ROOT / 'evidence'; evidence.mkdir(exist_ok=True)
        files = {name: root / name for name in ('failure.log', 'runtime.log', 'evaluation-process.log', 'receipt-manifest.json') if (root / name).is_file()}
        for tree in ('receipts', 'evaluation'):
            for path in (root / tree).rglob('*'):
                if path.is_file(): files[path.relative_to(root).as_posix()] = path
        if files:
            try: report['private_evidence'] = cloud_seal.seal(files, evidence / 'calibrated-evaluation.age', limit=16 * 1024**2)
            except Exception as error: report.update(status='FAIL', private_retention_error=type(error).__name__)
        (evidence / 'calibrated-evaluation.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    emit(report)
    return 0 if report['status'] == 'PASS' else 1

if __name__ == '__main__': raise SystemExit(main())
