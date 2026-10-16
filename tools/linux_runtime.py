"""Offline Linux CPython 3.12 closure check; no resolver/network during GPU use.

Uses 38 unchanged v25 wheels plus three owner-approved replacements, AND a
complete supplemental hash lock. The historical v25 manifest stays unchanged.
Never substitutes the historical macOS CPU lock for a Linux runtime closure.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.backtrace import MANIFEST

RUNTIME_PROFILE = MANIFEST.with_name('a100-runtime-amendment.json')
APPROVED_REPLACEMENTS = {'opentelemetry-exporter-otlp': '1.41.1',
                         'prometheus-fastapi-instrumentator': '7.1.0',
                         'xgrammar': '0.2.8'}
REQUIRED = {'swegemma': '0.2.7', 'adk-submission': '0.2.11',
            'adk-eval-core': '0.1.0', 'google-adk': '1.36.1',
            'google-genai': '2.11.0', 'vllm': '0.19.1',
            'torch': '2.10.0+cu128', 'compressed-tensors': '0.15.0.1',
            'transformers': '5.13.1'}
LOCK_ROW = re.compile(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)'
                      r' --hash=sha256:([a-f0-9]{64})')


OFFLINE_CHILD = """
import runpy, sys
def audit(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.sendmsg'):
        raise RuntimeError('offline qualification blocked network access')
sys.addaudithook(audit)
mode = sys.argv.pop(1)
if mode == 'pip':
    runpy.run_module('pip', run_name='__main__')
else:
    exec(mode, {'__name__': '__main__'})
"""


def offline_child(python, *arguments):
    return [str(python), '-I', '-c', OFFLINE_CHILD, *arguments]


def normalized(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def supplied_records():
    """Original v25 acquisition evidence; never rewrite it as the runtime recipe."""
    records = json.loads(MANIFEST.read_text())['native_dtype_continuation']['mounted_wheelhouse']['files']
    if len(records) != 41 or sum(r['bytes'] for r in records) != 880829403:
        raise ValueError('unexpected v25 manifest identity')
    return records


def runtime_records():
    """Apply only the three approved substitutions to the pinned source inventory."""
    profile = json.loads(RUNTIME_PROFILE.read_text())
    try:
        if profile['schema_version'] != 1 or profile['status'] != 'approved':
            raise ValueError('runtime amendment is not approved')
        if profile['source_manifest_sha256'] != hashlib.sha256(MANIFEST.read_bytes()).hexdigest():
            raise ValueError('runtime amendment source manifest mismatch')
        records = supplied_records()
        originals = {normalized(r['path'].split('-')[0]): r for r in records}
        replacements = {}
        for amendment in profile['replacements']:
            name = amendment['package']
            if name not in APPROVED_REPLACEMENTS or name in replacements:
                raise ValueError('unexpected or duplicate runtime substitution')
            if amendment['original'] != originals[name]:
                raise ValueError('runtime substitution original identity mismatch')
            record = amendment['replacement']
            filename = record['path']
            parts = filename.split('-')
            if (Path(filename).name != filename or not filename.endswith('.whl')
                    or len(parts) < 5 or normalized(parts[0]) != name
                    or parts[1] != APPROVED_REPLACEMENTS[name]
                    or type(record['bytes']) is not int or record['bytes'] <= 0
                    or not re.fullmatch(r'[a-f0-9]{64}', record['sha256'])):
                raise ValueError('invalid approved replacement wheel identity')
            replacements[name] = record
        if replacements.keys() != APPROVED_REPLACEMENTS.keys():
            raise ValueError('runtime amendment must contain exactly three substitutions')
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('invalid runtime amendment schema') from error
    return [replacements.get(normalized(r['path'].split('-')[0]), r) for r in records]


def verify_supplied(wheels, records):
    """Stream hashes (including large wheels) before any wheel is installed."""
    for record in records:
        name = record['path']
        if Path(name).name != name or not name.endswith('.whl'):
            raise ValueError('invalid wheel manifest path')
        path = wheels / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('missing pinned wheel: ' + name)
        if path.stat().st_size != record['bytes']:
            raise ValueError('supplied wheel size mismatch: ' + name)
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        if digest.hexdigest() != record['sha256']:
            raise ValueError('supplied wheel hash mismatch: ' + name)


def combined_lock(supplemental, records):
    """Strict offline locks: one selected wheel hash per name/version, no URLs.

    A real pip install below checks transitive requirements and Linux wheel tags.
    Merely producing these lines is not a dependency-closure result.
    """
    pins = {}
    for line in supplemental.splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        match = LOCK_ROW.fullmatch(line)
        if not match:
            raise ValueError('supplemental lock needs exact version and one wheel SHA256 per row')
        name, release, digest = match.groups()
        key = normalized(name)
        if key in pins:
            raise ValueError('duplicate supplemental dependency')
        pins[key] = (release, digest)
    supplied = {}
    for record in records:
        name, release = record['path'].split('-')[:2]
        key = normalized(name)
        pin = (release, record['sha256'])
        if key in supplied or (key in pins and pins[key] != pin):
            raise ValueError('selected runtime wheel cannot be repinned')
        supplied[key] = pin
        pins[key] = pin
    for name, release in REQUIRED.items():
        if name not in pins or pins[name][0] != release:
            raise ValueError('missing or changed frozen dependency: ' + name)
    def render(items):
        return ''.join(f'{name}=={release} --hash=sha256:{digest}\n'
                       for name, (release, digest) in sorted(items.items()))
    return render(pins), render(supplied)


def qualify(wheels, supplemental, output):
    """Create a fresh private venv, install offline, check imports; rollback on failure.

    Run this on the pinned base before allocation. Success on a different Linux
    host must be reported as that host, not qualification of the container image.
    Full model/task/source verification remains in the existing official tools.
    """
    if (sys.version_info[:2] != (3, 12) or platform.python_implementation() != 'CPython'
            or platform.system() != 'Linux' or platform.machine() != 'x86_64'):
        raise ValueError('Linux x86_64 CPython 3.12 required')
    wheels = wheels.resolve(strict=True)
    records = runtime_records()
    verify_supplied(wheels, records)
    complete, supplied = combined_lock(supplemental.read_text(), records)
    output = output.absolute()
    output.mkdir(mode=0o700)  # Never overwrite a prior environment/receipt.
    try:
        (output / 'linux-runtime.lock').write_text(complete)
        (output / 'runtime-pins.lock').write_text(supplied)
        profile_bytes = RUNTIME_PROFILE.read_bytes()
        (output / 'runtime-profile.json').write_bytes(profile_bytes)
        with tempfile.TemporaryDirectory(prefix='backtrace-offline-') as home:
            env = dict(PATH='/usr/bin:/bin', HOME=home, LANG='C.UTF-8',
                       PIP_CONFIG_FILE=os.devnull, PIP_NO_INDEX='1',
                       PYTHON_DOTENV_DISABLED='1', OTEL_SDK_DISABLED='true',
                       HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                       LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_TELEMETRY='False')
            python = output / 'venv/bin/python'
            commands = [
                [sys.executable, '-I', '-m', 'venv', str(output / 'venv')],
                offline_child(python, 'pip', 'install', '--disable-pip-version-check',
                 '--no-index', '--require-hashes', '--only-binary=:all:',
                 '--find-links=' + str(wheels), '-r', str(output / 'linux-runtime.lock')),
                offline_child(python, 'pip', 'install', '--disable-pip-version-check',
                 '--no-index', '--require-hashes', '--no-deps', '--force-reinstall',
                 '--only-binary=:all:', '--find-links=' + str(wheels),
                 '-r', str(output / 'runtime-pins.lock')),
                offline_child(python, 'pip', 'check'),
                offline_child(python,
                 'import torch, vllm, compressed_tensors, transformers, swegemma; '
                 'import adk_submission, adk_eval_core, google.adk, google.genai'),
            ]
            for command in commands:
                subprocess.run(command, env=env, check=True, timeout=1200)
            inventory = subprocess.check_output(
                offline_child(python, 'pip', 'list', '--format=json',
                              '--disable-pip-version-check'), env=env, timeout=30)
        (output / 'inventory.json').write_bytes(inventory)
        return {'offline_closure': 'PASS', 'runtime_wheels': len(records),
                'runtime_profile_sha256': hashlib.sha256(profile_bytes).hexdigest(),
                'lock_sha256': hashlib.sha256(complete.encode()).hexdigest(),
                'inventory_sha256': hashlib.sha256(inventory).hexdigest(),
                'model_execution': 'NOT RUN', 'official_candidate_checks': 'NOT RUN'}
    except BaseException:
        shutil.rmtree(output)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheels', type=Path)
    parser.add_argument('supplemental_lock', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(qualify(args.wheels, args.supplemental_lock, args.output)))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        detail = str(error) if isinstance(error, ValueError) else type(error).__name__
        parser.exit(2, 'Linux runtime not qualified: ' + detail + '\n')
