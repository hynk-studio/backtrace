"""Free post-deletion CPU diagnosis of exactly one recovered partial task.

Only Kaggle immutable input reads and a separate encrypted handoff namespace.
No RunPod key, provider operation, launch permit, model weights or agent entry.
"""
import base64
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from tools import a100_delivery as frozen, cloud_resolver as resolver, cloud_state as state
from tools import cloud_seal, recovered_task
from tools.direct_delivery import pull
from tools.pod_bootstrap import readonly
from tools.runpod_job import check_owner_host

BRANCH = 'bt-001-task-budget-evaluation-20261023'


def receiver(store, run_id, source):
    import pyrage
    if not str(run_id).isdigit() or not state.SHA.fullmatch(source):
        raise ValueError('exact free run and source required')
    prefix = 'a100-followup/' + str(run_id) + '-' + source
    identity = pyrage.x25519.Identity.generate()
    value = {'run_id': str(run_id), 'source_sha': source,
             'recipient': str(identity.to_public()), 'purpose': 'recovered-task-cpu-analysis-only'}
    store.request('PUT', '/contents/' + prefix + '/receiver.json', {
        'branch': state.BRANCH, 'message': 'Open free recovered-task receiver',
        'content': base64.b64encode(state.encoded(value)).decode()})
    return identity, prefix


def receive(store, identity, prefix, root, manifest):
    import pyrage
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        result = store.request('GET', '/contents/' + prefix + '/receipts.age.b64?ref=' + state.BRANCH,
                               missing=True)
        if result is None:
            time.sleep(5); continue
        if result.get('type') != 'file' or result.get('encoding') != 'base64':
            raise ValueError('invalid encrypted recovered-task object')
        encoded = base64.b64decode(result['content'])
        if len(encoded) > 2 * recovered_task.MAX_BYTES:
            raise ValueError('encrypted recovered-task bound exceeded')
        ciphertext = base64.b64decode(encoded, validate=True)
        recovered_task.restore(pyrage.decrypt(ciphertext, [identity]), root, manifest)
        return {'ciphertext_bytes': len(ciphertext),
                'ciphertext_sha256': hashlib.sha256(ciphertext).hexdigest()}
    raise TimeoutError('recovered-task handoff deadline')


def run(root, report, emit):
    check_owner_host()
    if (os.environ.get('GITHUB_REPOSITORY') != state.REPOSITORY
            or os.environ.get('GITHUB_REF_NAME') != BRANCH
            or os.environ.get('GITHUB_RUN_ATTEMPT') != '1'
            or 'RUNPOD_API_KEY' in os.environ):
        raise ValueError('exact free CPU followup context required')
    root.mkdir(mode=0o700, parents=True)
    store = state.GitHubState(os.environ['GITHUB_TOKEN'])
    claim, cleanup = store.read('claim')[0], store.read('cleanup')[0]
    if (claim['run_id'] != '39878045521'
            or claim['source_sha'] != '626e3a619a025f64e3713af11b8e4097471470ab'
            or cleanup['attempt'] != claim['attempt'] or cleanup['pod_id'] != 'virbb2jab7fi8v'
            or cleanup['phase'] != 'deleted' or cleanup['absence_reads'] != 2
            or store.run(claim['run_id'])['status'] != 'completed'):
        raise ValueError('confirmed deletion of the original paid attempt required')
    report['cleanup'] = cleanup
    manifest = json.loads((frozen.ROOT / 'docs/task-followup-input-20261023.json').read_text())
    identity, prefix = receiver(store, os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_SHA'])
    emit({'stage': 'receiver', 'path': prefix, 'status': 'READY'})
    report['stage'] = 'encrypted_handoff'
    report['handoff'] = receive(store, identity, prefix, root / 'receipts', manifest)
    report['analysis'] = recovered_task.analyze(root / 'receipts', manifest)
    report['stage'] = 'resolve_frozen_cpu_inputs'
    with resolver.kaggle_client() as client:
        (root / 'retained-driver.py').write_bytes(resolver.retained_literal(resolver.get_source(client)))
        wheel_sources = resolver.resolve_wheels(client,
            progress=lambda stage, count: emit({'stage': stage, 'files': count}))
        task_sources = resolver.resolve_task(client)
        evaluator_manifest, evaluator_sources = resolver.resolve_evaluator(client)
    report['stage'] = 'download_frozen_cpu_inputs'
    data = frozen.manifest('wheels')
    report['wheels'] = pull(root / 'wheels', data, wheel_sources,
                            hashlib.sha256(data).hexdigest(), 1800)
    data = frozen.manifest('task')
    report['task'] = pull(root / 'task', data, task_sources,
                          hashlib.sha256(data).hexdigest(), 600)
    report['evaluator'] = pull(root / 'evaluator', evaluator_manifest, evaluator_sources,
                               hashlib.sha256(evaluator_manifest).hexdigest(), 120)
    rows = json.loads((frozen.ROOT / 'docs/a100-evaluator-dependencies.json').read_text())['files']
    data = json.dumps({'schema_version': 1, 'phase': 'bootstrap', 'files': [
        {k: row[k] for k in ('path', 'bytes', 'sha256')} for row in rows]}).encode()
    sources = {row['path']: resolver.pypi_source(row) for row in rows}
    pull(root / 'evaluator/wheels', data, sources, hashlib.sha256(data).hexdigest(), 120)
    report['stage'] = 'offline_runtime'
    runtime = Path('/opt/backtrace-runtime')
    clean = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
             'PYTHON_DOTENV_DISABLED': '1', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
             'OTEL_SDK_DISABLED': 'true', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True',
             'PIP_NO_INDEX': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    with (root / 'runtime.log').open('wb') as log:
        subprocess.run([sys.executable, '-I', str(frozen.ROOT / 'tools/linux_runtime.py'),
            str(root / 'wheels'), str(frozen.ROOT / 'docs/linux-supplemental.lock'), str(runtime)],
            env=clean, stdin=subprocess.DEVNULL, stdout=log, stderr=log, check=True, timeout=1800)
    readonly(runtime)
    # The evaluator subprocesses may read only this original public task tree.
    inputs = Path('/opt/backtrace-followup-inputs')
    shutil.copytree(root / 'task', inputs)
    readonly(inputs)
    report['stage'] = 'actual_cpu_analysis'
    with (root / 'analysis-process.log').open('wb') as log:
        result = subprocess.run([str(runtime / 'venv/bin/python'), '-I',
            str(frozen.ROOT / 'tests/official_task_followup.py'), str(root), str(inputs)],
            env=clean, stdin=subprocess.DEVNULL, stdout=log, stderr=log, timeout=900)
        result.check_returncode()
    report['result'] = json.loads((root / 'followup-result.json').read_text())
    report.update(status='PASS', stage='finished')


def main():
    logging.disable(logging.CRITICAL); os.umask(0o077)
    root = frozen.ROOT / '.local/task-followup'
    report = {'status': 'FAIL', 'stage': 'context', 'gpu_allocations': 0,
              'provider_mutations': 0, 'model_calls': 0, 'agent_runs': 0,
              'source_sha': os.environ['GITHUB_SHA'], 'run_id': os.environ['GITHUB_RUN_ID']}
    emit = lambda row: print(json.dumps(row, sort_keys=True), flush=True)
    try:
        run(root, report, emit)
    except Exception as error:
        report['failure'] = {'error_type': type(error).__name__}
        if root.is_dir():
            (root / 'failure.log').write_text(traceback.format_exc())
    finally:
        evidence = frozen.ROOT / 'evidence'; evidence.mkdir(exist_ok=True)
        names = ('failure.log', 'runtime.log', 'analysis-process.log', 'followup-result.json')
        files = {name: root / name for name in names if (root / name).is_file()}
        for tree in ('verifier-controls', 'partial-verification'):
            for p in (root / tree).rglob('*'):
                if p.is_file():
                    files[p.relative_to(root).as_posix()] = p
        if files:
            try:
                report['private_evidence'] = cloud_seal.seal(files, evidence / 'task-followup.age',
                                                           limit=16 * 1024**2)
            except Exception as error:
                report.update(status='FAIL', private_retention_error=type(error).__name__)
        (evidence / 'task-followup.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    emit(report)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
