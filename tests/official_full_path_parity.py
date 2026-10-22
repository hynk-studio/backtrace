"""Free exact-image SSH boundary check; no account key, model or task run.

Fixture transfers and one public pinned pip wheel exercise the full worker's
wire encoding. They do not stand in for the scientific task/model inputs.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import bootstrap_probe as probe, cloud_worker as worker, cloud_transport
from tools import cloud_resolver, cloud_seal, runpod_control as control, ssh_bootstrap as ssh
from tools.private_delivery import push, ssh_command
from tools.runpod_job import check_owner_host, private_json


def qualify(root, report):
    check_owner_host()
    if any(k in os.environ for k in ('RUNPOD_API_KEY', 'GITHUB_TOKEN', 'GH_STATE_TOKEN', 'KAGGLE_API_TOKEN')):
        raise ValueError('credential-free CPU qualification required')
    stages = report['stages']
    built = cloud_transport.build(root / 'transport')
    if not built['matches_prior_transport']:
        raise ValueError('fixed transport build mismatch')
    stages['transport_build'] = {'status': 'PASS', 'binaries': built['binaries']}
    binaries = root / 'transport/dropbear-DROPBEAR_2026.94'
    initializer = ssh.prepare(binaries / 'dropbear', binaries / 'dropbearkey', root / 'ssh', profile=worker.PROFILE)
    private_json(root / 'ssh/initializer.json', initializer)
    full = control.make_request('a' * 32, 1, initializer, region='CA-MTL-3', transport_profile=worker.PROFILE)
    with probe.scope():
        diagnostic = control.make_request('a' * 32, 1, initializer, region='CA-MTL-3', transport_profile=probe.PROFILE)
    if full != diagnostic or worker.PROFILE != probe.PROFILE:
        raise ValueError('diagnostic and full allocation/transport profile differ')
    stages['request_parity'] = {'status': 'PASS', 'image': full['image'], 'disk_gb': full['disk'],
        'ports': full['ports'], 'initializer_sha256': hashlib.sha256(ssh.START.encode()).hexdigest(),
        'create_wire_bytes': len(control.encode_create_request(full)), 'provider_calls': 0}
    env_file = root / 'image.env'
    env_file.write_text('\n'.join(k + '=' + v for k, v in initializer['env'].items()) + '\n')
    env_file.chmod(0o600)
    name = 'backtrace-free-parity-' + os.environ['GITHUB_RUN_ID']
    with (root / 'image.log').open('wb') as image_log, (root / 'ssh.log').open('wb') as log:
        subprocess.run(['docker', 'pull', control.BASE], stdout=image_log, stderr=image_log, check=True, timeout=900)
        image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', control.BASE], timeout=20))[0]
        if (image['Architecture'] != 'amd64' or image['Os'] != 'linux'
                or not any(x.endswith('@' + control.BASE.split('@')[1]) for x in image['RepoDigests'])):
            raise ValueError('exact deployment image required')
        try:
            subprocess.run(['docker', 'run', '-d', '--rm', '--name', name, '--env-file', str(env_file),
                '-p', '127.0.0.1::22', '--entrypoint', initializer['entrypoint'][0], control.BASE,
                *initializer['entrypoint'][1:], *initializer['cmd']],
                stdout=image_log, stderr=image_log, check=True, timeout=30)
            value = json.loads(subprocess.check_output(['docker', 'inspect', name], timeout=20))[0]
            port = int(value['NetworkSettings']['Ports']['22/tcp'][0]['HostPort'])
            # Fixture readiness only: Docker's published proxy precedes LISTEN.
            listener = ("from pathlib import Path;raise SystemExit(0 if any("
                "x.split()[1].endswith(':0016') and x.split()[3]=='0A' for x in "
                "Path('/proc/net/tcp').read_text().splitlines()[1:]) else 1)")
            deadline = time.monotonic() + 30
            while True:
                ready = subprocess.run(['docker', 'exec', name, '/usr/bin/python3.12', '-I', '-c', listener],
                    stdout=image_log, stderr=image_log, timeout=5)
                if ready.returncode == 0: break
                if time.monotonic() >= deadline: raise TimeoutError('CPU image listener deadline')
                time.sleep(.2)
            stages['image_connection'] = probe.connect(root / 'ssh', {'host': '127.0.0.1', 'port': port}, gpu_required=False)
            prefix = ssh_command('127.0.0.1', port, root / 'ssh/owner-key', root / 'ssh/known-hosts',
                                 '/root/backtrace/unused', '0' * 64)[:-1]
            def remote(argv, data=None, *, timeout=240, check=True):
                result = subprocess.run(prefix + [shlex.join(argv)], input=data,
                    stdin=subprocess.DEVNULL if data is None else None,
                    capture_output=True, timeout=timeout, env=worker.CLEAN)
                log.write(result.stdout); log.write(result.stderr); log.flush()
                if check: result.check_returncode()
                return result
            source = root / 'fixture'; source.mkdir(mode=0o700)
            data = b'CPU transport fixture; no scientific input\n' * 4096
            (source / 'fixture.txt').write_bytes(data)
            manifest = json.dumps({'schema_version': 1, 'phase': 'bootstrap', 'files': [
                {'path': 'fixture.txt', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}]}).encode()
            path = root / 'fixture-manifest.json'; path.write_bytes(manifest)
            command = ssh_command('127.0.0.1', port, root / 'ssh/owner-key', root / 'ssh/known-hosts',
                '/root/backtrace/parity-input', hashlib.sha256(manifest).hexdigest())
            stages['private_input_transfer'] = dict(push(source, path, command, 60), status='PASS', inputs='FIXTURE')
            program = "# remote envelope fixture\n" * 3000 + (
                "from pathlib import Path\nimport hashlib,json\n"
                "p=Path('/root/backtrace/parity-input/fixture.txt')\n"
                "print(json.dumps({'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))\n")
            argv, envelope = worker.code_envelope(program)
            result = json.loads(remote(argv, envelope).stdout)
            if result['sha256'] != hashlib.sha256(data).hexdigest():
                raise ValueError('SSH fixture readback mismatch')
            changed = json.loads(envelope); changed['source'] += "raise RuntimeError('tampered')\n"
            rejected = remote(argv, json.dumps(changed).encode(), check=False)
            if rejected.returncode == 0 or rejected.stdout:
                raise ValueError('tampered remote envelope was not rejected')
            stages['large_code_envelope'] = {'status': 'PASS', 'stdin_bytes': len(envelope),
                'command_bytes': len(shlex.join(argv).encode()), 'tampered_source': 'REJECTED'}
            required = sum(row['bytes'] for kind in ('wheels', 'task', 'model')
                           for row in json.loads(worker.frozen.manifest(kind))['files']) + 16 * 1024**3
            preflight = (ROOT / 'tools/pod_preflight.py').read_text()
            argv, envelope = worker.code_envelope(preflight + '\nprint(json.dumps(base(' + repr(required) + ')))\n')
            stages['base_environment_over_ssh'] = json.loads(remote(argv, envelope).stdout)
            # Exercise the actual private URL envelope and HTTPS downloader with
            # one public frozen wheel. No private task/model URLs or bytes.
            rows = json.loads((ROOT / 'docs/linux-wheel-manifest.json').read_text())
            if isinstance(rows, dict): rows = rows['files']
            wheel = next(row for row in rows if row['path'] == 'pip-25.0.1-py3-none-any.whl')
            download = cloud_resolver.pypi_source(wheel)
            streams = {}
            for kind in ('wheels', 'task'):
                value = {'schema_version': 1, 'phase': 'bootstrap' if kind == 'wheels' else 'task',
                         'files': [{k: wheel[k] for k in ('path', 'bytes', 'sha256')}]}
                raw = json.dumps(value)
                streams[kind] = {'manifest': raw, 'sha256': hashlib.sha256(raw.encode()).hexdigest(),
                                 'sources': {wheel['path']: download}}
            raw = json.dumps({'schema_version': 1, 'phase': 'model', 'files': [
                {'path': 'not-requested.bin', 'bytes': 0, 'sha256': hashlib.sha256(b'').hexdigest()}]})
            streams['model'] = {'manifest': raw, 'sha256': hashlib.sha256(raw.encode()).hexdigest(), 'sources': {}}
            # Enter the production setup orchestrator, not a copied sequence.
            # Stop explicitly at the first unqualified runtime-install boundary.
            # No runtime, activation, permit or model step may execute here.
            class RuntimeBoundary(Exception): pass
            history = []; active = [None]
            def progress(row):
                if row == {'stage': 'runtime_installation', 'status': 'STARTED'}:
                    raise RuntimeBoundary()
                history.append(row); active[0] = row['stage']
            def setup_call(argv, *, input):
                response = remote(argv, input)
                values = [json.loads(line) for line in response.stdout.splitlines() if line.startswith(b'{')]
                if active[0] == 'system_packages':
                    stages['system_packages_over_ssh'] = dict(values[-1], status='PASS')
                elif active[0] == 'runtime_inputs':
                    if [x.get('stream') for x in values] != ['wheels', 'task']:
                        raise ValueError('actual HTTPS stream replies incomplete')
            try:
                worker.setup_remote(setup_call, streams, manifest, time.time(), emit=progress)
            except RuntimeBoundary:
                pass
            else:
                raise ValueError('free CPU setup crossed its runtime boundary')
            completed = [row['stage'] for row in history if row['status'] == 'PASS']
            if completed != ['base_environment', 'system_packages', 'runtime_inputs']:
                raise ValueError('production setup prefix did not complete')
            stages['production_setup_prefix'] = {'status': 'PASS', 'stages': completed,
                'stopped': 'BEFORE_RUNTIME_INSTALLATION', 'stream_inputs': 'FIXTURES'}
            stages['direct_https_envelope'] = {'status': 'PASS', 'streams': ['wheels', 'task'],
                'inputs': 'PUBLIC PINNED PIP WHEEL FIXTURES', 'bytes': 2 * wheel['bytes'],
                'sha256': wheel['sha256'], 'task_model_bytes': 0}
        finally:
            with (root / 'container.log').open('wb') as container_log:
                subprocess.run(['docker', 'logs', '--tail', '100', name], stdout=container_log,
                               stderr=container_log, timeout=10)
            subprocess.run(['docker', 'rm', '-f', name], stdout=image_log, stderr=image_log, timeout=20)
    report.update(status='PASS', image=control.BASE, image_id=image['Id'])


def main():
    os.umask(0o077)
    root = ROOT / '.local/full-path-parity'; root.mkdir(mode=0o700, parents=True)
    output = ROOT / 'evidence'; output.mkdir(exist_ok=True)
    report = {'status': 'FAIL', 'source_sha': os.environ['GITHUB_SHA'], 'stages': {},
        'provider_operations': 0, 'gpu_allocations': 0, 'model_execution': 'NOT RUN',
        'runtime_installation': 'NOT RUN; separately qualified historically',
        'public_task_execution': 'NOT RUN'}
    try: qualify(root, report)
    except Exception as error:
        report['failure'] = {'error_type': type(error).__name__, 'returncode': getattr(error, 'returncode', None)}
    logs = {name: root / name for name in ('image.log', 'ssh.log', 'container.log', 'transport/build.log')
            if (root / name).is_file()}
    if logs:
        try: report['private_evidence'] = cloud_seal.seal(logs, output / 'full-path-parity-private.age')
        except Exception as error:
            report.update(status='FAIL', retention_failure=type(error).__name__)
    (output / 'full-path-parity.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
