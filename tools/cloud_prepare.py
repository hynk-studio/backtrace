"""Free Actions input/runtime qualification. There is no provider allocation path."""
import contextlib
import base64
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
from tools.direct_delivery import pull, DownloadError
from tools.runpod_job import private_json
from tools import cloud_reference, cloud_state, cloud_image, pod_system, qualify_api, cloud_sources
from tools.probe_results import ProbeResults
from tools import qualification_evidence, cloud_qualification


def qualify(root, emit):
    root = Path(root).absolute(); root.mkdir(mode=0o700, parents=True)
    if shutil.disk_usage(root).free < 45 * 1024**3:
        raise ValueError('free CPU disk space below 45 GiB for host and pinned image')
    report = {'gpu_allocations': 0, 'gpu_model_server_starts': 0, 'gpu_model_task_executions': 0,
              'scripted_cpu_checks': 'reported separately per stage', 'stages': {},
              'source_sha': os.environ['GITHUB_SHA'], 'run_id': os.environ['GITHUB_RUN_ID'],
              'files': cloud_qualification.file_hashes(frozen.ROOT)}
    probes = ProbeResults(report['stages'])
    stage = 'private_source'
    try:
        transfer = cloud_state.GitHubState(os.environ['GITHUB_TOKEN'])
        identity, prefix = cloud_reference.open_receiver(transfer, os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_SHA'])
        emit({'stage': 'reference_receiver', 'status': 'READY', 'path': prefix})
        stage = 'transport_build'
        report['stages'][stage] = cloud_transport.build(root / 'transport')
        emit({'stage': stage, 'status': 'PASS', **report['stages'][stage]})
        stage = 'transport_loopback'
        binaries = root / 'transport/dropbear-DROPBEAR_2026.94'
        with (root / 'transport-loopback.log').open('xb') as log:
            result = subprocess.run(['sudo', sys.executable, '-I',
                str(frozen.ROOT / 'tests/official_cloud_transport.py'), str(binaries / 'dropbear'),
                str(binaries / 'dropbearkey'), 'actions-20261019'], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=log, check=True, timeout=120,
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        report['stages'][stage] = json.loads(result.stdout)
        emit({'stage': stage, 'status': 'PASS', **report['stages'][stage]})
        stage = 'private_evidence_permissions'
        import pyrage
        sites = str(Path(pyrage.__file__).resolve().parent.parent)
        with (root / 'evidence-permissions.log').open('xb') as log:
            result = subprocess.run(['sudo', sys.executable, '-I',
                str(frozen.ROOT / 'tests/official_private_evidence.py'), sites],
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
                stdout=subprocess.PIPE, stderr=log, check=True, timeout=60)
        report['stages'][stage] = json.loads(result.stdout)
        emit({'stage': stage, **report['stages'][stage]})
        stage = 'private_source'
        with resolver.kaggle_client() as client:
            source = resolver.get_source(client)
            (root / 'retained-source.ipynb').write_bytes(source)
            resolver.retained_literal(source)  # Never execute saved notebook cells.
            emit({'stage': stage, 'status': 'PASS', 'source_sha256': resolver.NOTEBOOK_SHA256})
            stage = 'resolve_wheels'
            wheel_sources = resolver.resolve_wheels(client,
                progress=lambda name, count: emit({'stage': name, 'count': count}))
            stage = 'resolve_task_model'
            task_sources = resolver.resolve_task(client)
            evaluator_manifest, evaluator_sources = resolver.resolve_evaluator(client)
            model_sources = resolver.resolve_model(client)
        private_json(root / 'private-sources.json', {'wheels': wheel_sources, 'task': task_sources,
                                                     'model': model_sources})
        report['stages']['sources'] = {'wheels': len(wheel_sources), 'task': len(task_sources),
                                       'model': len(model_sources), 'urls_published': False}
        emit({'stage': 'sources', 'status': 'PASS', **report['stages']['sources']})
        stage = 'source_lifetime_before_setup'
        maps = {'wheels': wheel_sources, 'task': task_sources, 'model': model_sources}
        report['stages'][stage] = cloud_sources.snapshot(maps)
        emit({'stage': stage, **report['stages'][stage]})
        # The same frozen manifests and production setup orchestrator now run
        # through real pinned SSH, including installation, on a free CPU image.
        raw_driver = root / 'ssh-retained-driver.py'
        raw_driver.write_bytes(resolver.retained_literal(source))
        cloud_task.prepare(raw_driver, root / 'ssh-driver')
        streams = {}
        for kind, sources in maps.items():
            data = frozen.manifest(kind)
            streams[kind] = {'manifest': data.decode(), 'sha256': hashlib.sha256(data).hexdigest(),
                             'sources': sources}
        private_json(root / 'full-ssh-streams.json', streams)
        stage = 'full_setup_ssh'
        def full_setup():
            with (root / 'full-setup-process.log').open('xb') as log:
                subprocess.run(['sudo', sys.executable, '-I',
                    str(frozen.ROOT / 'tests/official_full_setup.py'), str(root)],
                    env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8',
                         'GITHUB_RUN_ID':os.environ['GITHUB_RUN_ID']},
                    stdin=subprocess.DEVNULL, stderr=log, timeout=3000)
            return json.loads((root / 'full-setup-result.json').read_text())
        probes.run(stage, full_setup)
        emit({'stage': stage, **report['stages'][stage]})
        stage = 'model_sources_after_real_setup'
        def check_model_sources():
            for row in json.loads(frozen.manifest('model'))['files']:
                original = model_sources[row['path']]
                checked = resolver.retry_read(lambda: resolver.public_source(original['url'], row))
                if checked != original:
                    raise ValueError('model source header/encoding changed after setup')
            return {'status':'PASS','files':len(model_sources),'body_read':False,
                    'declared_lifetime':cloud_sources.snapshot({'model':model_sources})}
        probes.run(stage, check_model_sources)
        emit({'stage': stage, **report['stages'][stage]})
        stage = 'download_system_packages'
        system_manifest = json.loads((frozen.ROOT / 'docs/a100-system-packages.json').read_text())
        report['stages'][stage] = pod_system.download(system_manifest, root / 'system', deadline=time.time() + 180)
        emit({'stage': stage, **report['stages'][stage]})
        stage = 'download_wheels'
        data = frozen.manifest('wheels')
        report['stages'][stage] = pull(root / 'wheels', data, wheel_sources, hashlib.sha256(data).hexdigest(), 1800)
        emit({'stage': stage, 'status': 'PASS', 'verified_files': len(wheel_sources)})
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(root), 'LANG': 'C.UTF-8',
               'PYTHON_DOTENV_DISABLED': '1', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
               'OTEL_SDK_DISABLED': 'true', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True'}
        stage = 'offline_runtime'
        runtime = Path('/opt/backtrace-runtime')
        with (root / 'offline-runtime.log').open('xb') as log:
            subprocess.run(['sudo', sys.executable, '-I', str(frozen.ROOT / 'tools/linux_runtime.py'),
                str(root / 'wheels'), str(frozen.ROOT / 'docs/linux-supplemental.lock'), str(runtime)],
                env=env, cwd=frozen.ROOT, stdout=log, stderr=log, check=True, timeout=1800)
            # Build at its final workload-readable path, as on the Pod. Do not
            # relocate venvs or expose the private source/URL staging directory.
            program = ('import sys;from pathlib import Path;sys.path.insert(0,'
                       + repr(str(frozen.ROOT)) + ');from tools.pod_bootstrap import readonly;readonly('
                       + repr(str(runtime)) + ')')
            subprocess.run(['sudo', sys.executable, '-I', '-c', program], env=env,
                           stdout=log, stderr=log, check=True, timeout=120)
        report['stages'][stage] = {'status': 'PASS', 'application_distributions': 245,
                                    'installation_network': 'AUDIT BLOCKED', 'host': 'Actions Ubuntu 24.04 CPU'}
        emit({'stage': stage, **report['stages'][stage]})
        stage = 'actual_api_http'
        old = json.loads((frozen.ROOT / 'docs/a100-api-runtime-amendment.json').read_text())['original']
        old_manifest = json.dumps({'schema_version': 1, 'phase': 'bootstrap', 'files': [
            {k: old[k] for k in ('path', 'bytes', 'sha256')}]}).encode()
        old_source = resolver.pypi_source(old)
        pull(root / 'api-negative', old_manifest, {old['path']: old_source},
             hashlib.sha256(old_manifest).hexdigest(), 120)
        with (root / 'actual-api-http.log').open('xb') as log:
            probes.run(stage, lambda: qualify_api.run_checks(runtime / 'venv/bin/python',
                root / 'api-negative' / old['path'], root / 'api-http-result', log))
        emit({'stage': stage, **report['stages'][stage]})
        stage = 'restore_official'
        # Require the original manifest-verified encrypted handoff.
        report['stages'][stage] = cloud_reference.receive(transfer, identity, prefix, root / 'official')
        emit({'stage': stage, 'status': 'PASS', **report['stages'][stage]})
        stage = 'cuda_runtime'
        # Exercise the actual version reader against the frozen installed
        # libcudart on CPU, with no developer toolkit manifest or GPU needed.
        program = ('import sys,json;sys.path.insert(0,' + repr(str(frozen.ROOT))
                   + ');from tools.a100_task import cuda_runtime_info;'
                   + 'print(json.dumps(cuda_runtime_info()))')
        with (root / 'cuda-runtime.log').open('xb') as log:
            result = subprocess.run([str(runtime / 'venv/bin/python'), '-I', '-c', program],
                env=env, stdout=subprocess.PIPE, stderr=log, check=True, timeout=30)
        report['stages'][stage] = {'status': 'PASS', **json.loads(result.stdout),
                                  'gpu_initialization': 'NOT RUN', 'model_execution': 'NOT RUN'}
        emit({'stage': stage, **report['stages'][stage]})
        stage = 'download_task'
        data = frozen.manifest('task')
        report['stages'][stage] = pull(root / 'task', data, task_sources, hashlib.sha256(data).hexdigest(), 600)
        emit({'stage': stage, 'status': 'PASS', 'verified_files': len(task_sources)})
        stage = 'private_public_evaluator'
        report['stages'][stage] = pull(root / 'evaluator', evaluator_manifest, evaluator_sources,
            hashlib.sha256(evaluator_manifest).hexdigest(), 120)
        # This root-private tree is not included in the task/driver manifests.
        emit({'stage': stage, 'status': 'PASS', 'agent_access': False})
        stage = 'cpu_evaluator_dependencies'
        rows = json.loads((frozen.ROOT / 'docs/a100-evaluator-dependencies.json').read_text())['files']
        data = json.dumps({'schema_version': 1, 'phase': 'bootstrap', 'files': [
            {k: row[k] for k in ('path', 'bytes', 'sha256')} for row in rows]}).encode()
        sources = {row['path']: resolver.pypi_source(row) for row in rows}
        report['stages'][stage] = pull(root / 'evaluator/wheels', data, sources,
            hashlib.sha256(data).hexdigest(), 120)
        emit({'stage': stage, 'status': 'PASS', 'verified_files': len(rows), 'agent_access': False})
        stage = 'restore_cpu_inputs'
        report['stages'][stage] = resolver.restore_cpu_inputs(source, frozen.ROOT, root / 'wheels', root / 'task', root / 'official')
        prepared = cloud_task.prepare(frozen.ROOT / '.local/smoke/no-custom-ar/one_task.py', root / 'driver')
        manifest = cloud_task.manifest(root / 'driver')
        (root / 'driver-manifest.json').write_bytes(manifest)
        report['stages']['driver'] = {key: prepared[key] for key in (
            'prepared_driver_sha256', 'policy', 'setup_seconds', 'useful_seconds', 'total_seconds',
            'server_and_agent_ast_equal_to_legacy')}
        stage = 'cpu_task_layout'
        # The retained wrapper discovers inputs at the same fixed logical path
        # as the Pod. A plain Actions VM has no Kaggle mounts. Install the actual
        # verified task bytes there, with the same read-only permissions, before
        # testing construction. Never patch away the driver's discovery check.
        task_sha = hashlib.sha256(frozen.manifest('task')).hexdigest()
        layout = ('import sys,shutil\nfrom pathlib import Path\n'
                  + 'sys.path.insert(0,' + repr(str(frozen.ROOT)) + ')\n'
                  + 'from tools.pod_bootstrap import checked_tree,readonly,input_parent\n'
                  + 'source=Path(' + repr(str(root / 'task')) + ')\n'
                  + 'checked_tree(source,' + repr(task_sha) + ')\n'
                  + "target=Path('/kaggle/input/r0-inputs')\n"
                  + 'assert not target.exists() and not target.is_symlink()\n'
                  + 'input_parent(target)\n'
                  + 'shutil.copytree(source,target)\n'
                  + "(target/'delivery-manifest.json').unlink()\n"
                  + 'readonly(target)\n')
        with (root / 'cpu-task-layout.log').open('xb') as log:
            subprocess.run(['sudo', sys.executable, '-I', '-c', layout], env=env,
                           stdout=log, stderr=log, check=True, timeout=60)
        report['stages'][stage] = {'status': 'PASS', 'verified_files': len(task_sources),
                                  'discovery_path': '/kaggle/input/r0-inputs', 'permissions': 'READ ONLY'}
        emit({'stage': stage, **report['stages'][stage]})
        stage = 'official_cloud_driver'
        with (root / 'official-cloud-driver.log').open('xb') as log:
            result = probes.run(stage, lambda: subprocess.run([str(runtime / 'venv/bin/python'), '-I',
                str(frozen.ROOT / 'tests/official_a100_task.py'), '--cloud-policy'],
                env=env, cwd=frozen.ROOT, stdout=log, stderr=log, check=True, timeout=300))
        if result is not None:
            report['stages'][stage] = {'status': 'PASS', 'driver_sha256': cloud_task.CLOUD_DRIVER_SHA256,
                                  'model_execution': 'NOT RUN', 'hardware': 'INJECTED A100 SM80',
                                  'event_writer': 'ACTUAL', 'hardware_name_preserved': True,
                                  'post_start_boundary_cases': 7,
                                  'boundary_replies': 'AUTHORED; GPU/HTTP/TASK ENTRY SPIED',
                                  'agent_construction': 'ACTUAL; RUNNER ENTRY NOT RUN'}
        stage = 'actual_cpu_prerequisites'
        with (root / 'actual-cpu-prerequisites.log').open('xb') as log:
            result = probes.run(stage, lambda: subprocess.run(['sudo', sys.executable, '-I',
                str(frozen.ROOT / 'tests/official_cloud_prerequisites.py'), str(root / 'driver')],
                env=env, cwd=frozen.ROOT, stdout=subprocess.PIPE, stderr=log, check=True, timeout=300))
        if result is not None:
            report['stages'][stage] = json.loads(result.stdout)
        emit({'stage': stage, **report['stages'][stage]})
        stage = 'connected_task_path'
        with (root / 'connected-task.log').open('xb') as log:
            result = probes.run(stage, lambda: subprocess.run(['sudo', str(runtime / 'venv/bin/python'), '-I',
                str(frozen.ROOT / 'tests/official_connected_task.py'), str(root / 'driver'),
                str(root / 'connected-task'), str(root / 'evaluator/tasks.jsonl')], env=env, cwd=frozen.ROOT,
                stdout=subprocess.PIPE, stderr=log, check=True, timeout=900))
        if result is not None:
            report['stages'][stage] = json.loads(result.stdout)
        emit({'stage': stage, **report['stages'][stage]})
        if probes.failed:
            # Do not wait for a second image installation to expose the host's
            # first failure. Only bounded owner-encrypted diagnostics leave here.
            try:
                output = root / 'host-failure.age'
                checkpoint = qualification_evidence.privileged(root, output, early=True)
                encoded = base64.b64encode(output.read_bytes())
                path = prefix + '/host-diagnostic.age.b64'
                transfer.request('PUT', '/contents/' + path, {'branch': cloud_state.BRANCH,
                    'message': 'Preserve owner-encrypted free host diagnostics',
                    'content': base64.b64encode(encoded).decode()})
                report['early_private_diagnostic'] = dict(checkpoint, path=path)
                emit({'stage': 'host_failure_evidence', 'status': 'SEALED', 'path': path, **checkpoint})
            except Exception as error:
                report['early_private_diagnostic'] = {'status': 'FAILED', 'error_type': type(error).__name__}
        stage = 'pinned_image_cpu'
        with (root / 'pinned-image.log').open('xb') as log:
            probes.run(stage, lambda: cloud_image.qualify(root, log))
        emit({'stage': stage, 'status': report['stages'][stage].get('status', 'PASS'),
              'image': report['stages'][stage].get('image'),
              'gpu_allocations': 0, 'gpu_model_server_starts': 0, 'gpu_model_task_executions': 0})
        stage = 'concurrent_controller'
        with (root / 'concurrent-controller.log').open('xb') as log:
            result = probes.run(stage, lambda: subprocess.run(['sudo', sys.executable, '-I',
                str(frozen.ROOT / 'tests/official_cloud_lifecycle.py')], env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log, check=True, timeout=300))
        if result is not None:
            report['stages'][stage] = json.loads(result.stdout)
        emit({'stage': stage, **report['stages'][stage]})
        report['status'], report['failed_stages'] = probes.status, probes.failed
    except Exception as error:
        report.update(status='FAIL', failed_stage=stage, failure=failure(error))
        if isinstance(error, resolver.ResolutionError):
            report['failure'].update(input_path=error.input_path, cause_type=error.error_type)
        if isinstance(error, subprocess.CalledProcessError):
            report['failure']['exit_code'] = error.returncode
        if isinstance(error, DownloadError):
            report['failure'].update({key: getattr(error, key) for key in
                ('input_path', 'cause_type', 'attempts', 'received_bytes') if getattr(error, key, None) is not None})
        if isinstance(error, DownloadError) and str(error) in {
                'archive must contain only the expected regular file', 'downloaded input identity mismatch',
                'storage HTTP failure', 'storage Content-Length differs from resolved size',
                'resolve the final storage URL on the owner host', 'bounded storage retries exhausted',
                'invalid encoded input', 'unexpected HTTP content encoding', 'download deadline reached'}:
            report['failure']['reason'] = str(error)
    try:
        report['private_evidence'] = qualification_evidence.privileged(root,
            frozen.ROOT / 'evidence/cloud-private.age')
    except Exception as error:
        # Keep the complete stage report even if encrypted export fails.
        report.update(status='FAIL', evidence_failure=failure(error))
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
