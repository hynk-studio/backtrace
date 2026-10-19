"""Free Actions input/runtime qualification. There is no provider allocation path."""
import contextlib
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from tools import a100_delivery as frozen, cloud_resolver as resolver, cloud_task, cloud_transport, cloud_seal
from tools.cloud_probe import failure
from tools.direct_delivery import pull
from tools.runpod_job import private_json


def qualify(root, emit):
    root = Path(root).absolute(); root.mkdir(mode=0o700, parents=True)
    if shutil.disk_usage(root).free < 23 * 1024**3:
        raise ValueError('free CPU disk space below 23 GiB')
    report = {'gpu_allocations': 0, 'server_starts': 0, 'task_executions': 0, 'stages': {}}
    stage = 'private_source'
    try:
        with resolver.kaggle_client() as client:
            source = resolver.get_source(client)
            (root / 'retained-source.ipynb').write_bytes(source)
            resolver.packed_inputs(source)  # Refuse missing source before large downloads.
            emit({'stage': stage, 'status': 'PASS', 'source_sha256': resolver.NOTEBOOK_SHA256})
            stage = 'resolve_wheels'
            wheel_sources = resolver.resolve_wheels(client,
                progress=lambda name, count: emit({'stage': name, 'count': count}))
            stage = 'resolve_task_model'
            task_sources = resolver.resolve_task(client)
            model_sources = resolver.resolve_model(client)
        private_json(root / 'private-sources.json', {'wheels': wheel_sources, 'task': task_sources,
                                                     'model': model_sources})
        report['stages']['sources'] = {'wheels': len(wheel_sources), 'task': len(task_sources),
                                       'model': len(model_sources), 'urls_published': False}
        emit({'stage': 'sources', 'status': 'PASS', **report['stages']['sources']})
        stage = 'download_wheels'
        data = frozen.manifest('wheels')
        report['stages'][stage] = pull(root / 'wheels', data, wheel_sources, hashlib.sha256(data).hexdigest(), 1800)
        emit({'stage': stage, 'status': 'PASS', 'verified_files': len(wheel_sources)})
        stage = 'download_task'
        data = frozen.manifest('task')
        report['stages'][stage] = pull(root / 'task', data, task_sources, hashlib.sha256(data).hexdigest(), 600)
        emit({'stage': stage, 'status': 'PASS', 'verified_files': len(task_sources)})
        stage = 'restore_cpu_inputs'
        report['stages'][stage] = resolver.restore_cpu_inputs(source, frozen.ROOT, root / 'wheels')
        prepared = cloud_task.prepare(frozen.ROOT / '.local/smoke/no-custom-ar/one_task.py', root / 'driver')
        manifest = cloud_task.manifest(root / 'driver')
        (root / 'driver-manifest.json').write_bytes(manifest)
        report['stages']['driver'] = {key: prepared[key] for key in (
            'prepared_driver_sha256', 'policy', 'setup_seconds', 'useful_seconds', 'total_seconds',
            'server_and_agent_ast_equal_to_legacy')}
        stage = 'transport_build'
        report['stages'][stage] = cloud_transport.build(root / 'transport')
        emit({'stage': stage, 'status': 'PASS', **report['stages'][stage]})
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(root), 'LANG': 'C.UTF-8',
               'PYTHON_DOTENV_DISABLED': '1', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
               'OTEL_SDK_DISABLED': 'true', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True'}
        stage = 'offline_runtime'
        with (root / 'offline-runtime.log').open('xb') as log:
            subprocess.run([sys.executable, '-I', str(frozen.ROOT / 'tools/linux_runtime.py'),
                str(root / 'wheels'), str(frozen.ROOT / 'docs/linux-supplemental.lock'), str(root / 'runtime')],
                env=env, cwd=frozen.ROOT, stdout=log, stderr=log, check=True, timeout=1800)
        report['stages'][stage] = {'status': 'PASS', 'application_distributions': 245,
                                    'installation_network': 'AUDIT BLOCKED', 'host': 'Actions Ubuntu 24.04 CPU'}
        emit({'stage': stage, **report['stages'][stage]})
        stage = 'official_cloud_driver'
        with (root / 'official-cloud-driver.log').open('xb') as log:
            subprocess.run([str(root / 'runtime/venv/bin/python'), '-I',
                str(frozen.ROOT / 'tests/official_a100_task.py'), '--cloud-policy'],
                env=env, cwd=frozen.ROOT, stdout=log, stderr=log, check=True, timeout=300)
        report['stages'][stage] = {'status': 'PASS', 'driver_sha256': cloud_task.CLOUD_DRIVER_SHA256,
                                  'model_execution': 'NOT RUN', 'hardware': 'INJECTED A100 SM80'}
        report['status'] = 'PASS'
    except Exception as error:
        report.update(status='FAIL', failed_stage=stage, failure=failure(error))
        if isinstance(error, resolver.ResolutionError):
            report['failure'].update(input_path=error.input_path, cause_type=error.error_type)
        if isinstance(error, subprocess.CalledProcessError):
            report['failure']['exit_code'] = error.returncode
    private = {}
    for name in ('retained-source.ipynb', 'offline-runtime.log', 'official-cloud-driver.log'):
        path = root / name
        if path.is_file():
            private[name] = path
    if private:
        report['private_evidence'] = cloud_seal.seal(private,
            frozen.ROOT / 'evidence/cloud-private.age', limit=16 * 1024**2)
    return report


def main():
    logging.disable(logging.CRITICAL)
    os.umask(0o077)
    stream = sys.stdout
    emit = lambda value: print(json.dumps(value, sort_keys=True), file=stream, flush=True)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            report = qualify(frozen.ROOT / '.local/cloud-free', emit)
        except Exception as error:
            report = {'status': 'FAIL', 'gpu_allocations': 0, 'failure': failure(error)}
    emit(report)
    # Only the explicitly projected report is suitable for a public artifact.
    evidence = frozen.ROOT / 'evidence/cloud-prepare.json'
    evidence.parent.mkdir(exist_ok=True)
    evidence.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
