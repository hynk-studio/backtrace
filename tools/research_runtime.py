"""Minimal CPU dependency closure selected only from the frozen Linux inventory.

This is compiler/runner qualification, not the full GPU deployment image. No
version resolver is used: dependencies must fit already pinned wheel versions.
"""
from email.parser import BytesParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from tools import research_comparison as c, cloud_resolver as resolver
from tools.direct_delivery import pull
from tools.linux_runtime import BOOTSTRAP, offline_child


def prepare(root, official_wheels):
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    root = Path(root); root.mkdir(mode=0o700)
    wheels = root / 'wheels'; wheels.mkdir(mode=0o700)
    records = {canonicalize_name(r['name']): r for r in c.parse((c.ROOT / 'docs/linux-wheel-manifest.json').read_bytes())}
    queue = [Requirement(n) for n in ('adk-eval-core', 'adk-submission', 'swegemma', 'google-adk',
                                     'google-genai', 'numpy', 'networkx', 'PyYAML', 'pytest', 'setuptools')]
    extras, scanned, selected = {}, {}, {}
    total = 0
    omitted = []
    while queue:
        requirement = queue.pop(0); name = canonicalize_name(requirement.name)
        if name not in records:
            raise ValueError('CPU dependency absent from frozen inventory: ' + name)
        row = records[name]
        if not requirement.specifier.contains(row['version'], prereleases=True):
            raise ValueError('CPU dependency contradicts frozen version: ' + name)
        extras.setdefault(name, set()).update(requirement.extras)
        if name in scanned and scanned[name] == extras[name]:
            continue
        target = wheels / row['path']
        if name not in selected:
            total += row['bytes']
            if total > 600 * 1024**2 or len(selected) >= 200:
                raise ValueError('CPU dependency closure exceeded bounds')
            original = official_wheels / row['path']
            if original.exists():
                data = c.read_file(original, 4 * 1024**2)
                if len(data) != row['bytes'] or c.digest(data) != row['sha256']:
                    raise ValueError('official wheel changed')
                c._new_output(target, data)
            else:
                manifest = c.encoded({'schema_version': 1, 'phase': 'bootstrap', 'files': [
                    {k: row[k] for k in ('path', 'bytes', 'sha256')}]})
                source = resolver.retry_read(lambda: resolver.pypi_source(row))
                destination = root / ('download-' + name)
                pull(destination, manifest, {row['path']: source}, c.digest(manifest), 180)
                shutil.move(destination / row['path'], target); shutil.rmtree(destination)
            selected[name] = row
        with zipfile.ZipFile(target) as archive:
            meta = BytesParser().parsebytes(archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))))
        for value in meta.get_all('Requires-Dist', []):
            dependency = Requirement(value)
            if name == 'swegemma' and canonicalize_name(dependency.name) in (
                    'torchvision', 'transformers', 'safetensors', 'accelerate'):
                # The pinned package declares serving dependencies eagerly but
                # its inspected compiler/agent_runner path imports none of them.
                # This CPU-only subset cannot qualify model loading or serving.
                omitted.append({'package': name, 'requirement': value})
                continue
            if dependency.marker is None or any(dependency.marker.evaluate({'extra': extra})
                                                for extra in extras[name] | {''}):
                queue.append(dependency)
        scanned[name] = set(extras[name])
    environment = {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'HOME': str(root),
                   'OTEL_SDK_DISABLED': 'true', 'PYTHON_DOTENV_DISABLED': '1',
                   'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'HF_HUB_OFFLINE': '1',
                   'TRANSFORMERS_OFFLINE': '1'}
    venv = root / 'venv'; log = root / 'install.log'
    with log.open('wb') as stream:
        subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(venv)],
                       env=environment, stdout=stream, stderr=stream, check=True, timeout=45)
        manifest = c.encoded({'schema_version': 1, 'phase': 'bootstrap', 'files': [BOOTSTRAP]})
        pull(root / 'bootstrap', manifest, {BOOTSTRAP['path']: resolver.pypi_source(BOOTSTRAP)},
             c.digest(manifest), 180)
        subprocess.run(offline_child(venv / 'bin/python', 'bootstrap-pip', str(root / 'bootstrap' / BOOTSTRAP['path']),
            'install', '--no-index', '--no-deps', '--disable-pip-version-check',
            *map(str, sorted(wheels.glob('*.whl')))), env=environment, stdout=stream,
            stderr=stream, check=True, timeout=240)
    return venv / 'bin/python', {'status': 'PASS', 'scope': 'MINIMAL_CPU_CLOSURE_NOT_GPU_RUNTIME',
        'packages': len(selected), 'bytes': total, 'files': list(selected.values()), 'offline_install': True,
        'excluded_serving_requirements': omitted, 'full_distribution_dependency_closure': False}


def qualify(root, output):
    root, output = Path(root), Path(output)
    python, runtime = prepare(root / 'cpu-runtime', root / 'wheels')
    env = {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'HOME': str(root),
           'OTEL_SDK_DISABLED': 'true', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True',
           'LITELLM_TELEMETRY': 'False', 'PYTHON_DOTENV_DISABLED': '1',
           'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
    with (root / 'official-compile.log').open('wb') as log:
        completed = subprocess.run([str(python), '-I', '-B', str(c.ROOT / 'tools/research_official.py'),
            str(root / 'wheels'), str(root / 'candidates'), str(root / 'compiler-work')],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log, timeout=120)
    report = {'runtime': runtime, 'status': 'PASS' if completed.returncode == 0 else 'FAILED'}
    if completed.returncode == 0:
        report['compiler'] = c.parse(completed.stdout)
    else:
        report['stage'] = 'official_compiler'; report['exit_code'] = completed.returncode
    c._new_output(output, c.encoded(report))
    return report
