"""Prepare the private A100 task driver and qualify its CPU prerequisites.

The retained organizer/task source is never committed here. Provider integration
is still unqualified: the generated entry point permits only CPU prerequisites
and their isolated dependency check, not model or agent execution.
"""
import argparse
import ast
import difflib
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from tools.guard_driver import DRIVER_SHA256, transform as guard_transform

ROOT = Path(__file__).resolve().parents[1]
WHEEL_MANIFEST_SHA256 = '3c5decd1c9aa3a71543242d1ac0e1c3e98ddf07fa26f7e4bf2cc6c7b66dfad6a'


def canonical(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def check_inventory(records, installed):
    expected = {canonical(r['name']): r['version'] for r in records}
    observed = {canonical(r['name']): r['version'] for r in installed}
    if (len(expected) != len(records) or len(observed) != len(installed)
            or observed != expected):
        raise ValueError('installed runtime differs from qualified wheel inventory')
    return observed


def check_runtime():
    """Check the actual active venv; never run the original online setup cell."""
    if sys.version_info[:2] != (3, 12) or sys.prefix == sys.base_prefix:
        raise ValueError('qualified isolated CPython 3.12 runtime required')
    data = (ROOT / 'docs/linux-wheel-manifest.json').read_bytes()
    if hashlib.sha256(data).hexdigest() != WHEEL_MANIFEST_SHA256:
        raise ValueError('wheel inventory hash mismatch')
    installed = [{'name': d.metadata['Name'], 'version': d.version}
                 for d in importlib.metadata.distributions()]
    return check_inventory(json.loads(data), installed)


def inherit_runtime(task_venv, runtime_prefix=None):
    """An inner venv does not inherit its parent venv's packages by default.

    Append the credential-free qualified runtime after task-local packages so
    the separately pinned task overlay wins without modifying serving packages.
    """
    prefix = Path(sys.prefix if runtime_prefix is None else runtime_prefix).resolve()
    sites = prefix / 'lib/python3.12/site-packages'
    target = Path(task_venv) / 'lib/python3.12/site-packages'
    if not sites.is_dir() or not target.is_dir() or '\n' in str(sites):
        raise ValueError('expected CPython 3.12 runtime and fresh task venv')
    with (target / 'backtrace-runtime.pth').open('x') as stream:
        stream.write(str(sites) + '\n')


def check_gpu(cuda):
    """Observe the exact assigned GPU; CPU tests may inject only the CUDA API."""
    from tools.a100_driver import qualify_hardware
    smi = subprocess.check_output([
        'nvidia-smi', '--query-gpu=name,uuid,memory.total,driver_version,mig.mode.current',
        '--format=csv,noheader,nounits'], text=True, timeout=10)
    toolkit = json.loads(Path('/usr/local/cuda/version.json').read_text())['cuda']['version']
    return qualify_hardware(smi, cuda, toolkit_version=toolkit)


def require_local_procfs():
    # The retained UID cleanup must never inspect/signal a foreign PID namespace.
    if int(Path('/proc/self/stat').read_bytes().split(b' ', 1)[0]) != os.getpid():
        raise RuntimeError('foreign procfs PID namespace; no worker operations allowed')


def _replace(source, before, after):
    if source.count(before) != 1:
        raise ValueError('unexpected retained driver shape')
    return source.replace(before, after, 1)


def transform(data):
    if hashlib.sha256(data).hexdigest() != DRIVER_SHA256:
        raise ValueError('retained no-custom-ar driver hash mismatch')
    original = data.decode()
    source = guard_transform(original)
    source = _replace(source, 'from pathlib import Path\n',
                      'from pathlib import Path\n'
                      'sys.path.insert(0,str(Path(__file__).resolve().parent))\n'
                      'from tools.a100_task import check_runtime, inherit_runtime, check_gpu, require_local_procfs\n')
    changes = [
        ("RUN_NAME='R0-clean-v2-one-public-task/T4-native-no-custom-ar'",
         "RUN_NAME='R0-clean-v2-one-public-task/A10080-TP1'"),
        ("ROOT=Path('/tmp/backtrace-smoke')", "ROOT=Path('/tmp/backtrace-a100-smoke')"),
        ("OUTPUT=Path('/kaggle/working/backtrace-receipts')",
         "OUTPUT=Path('/kaggle/working/backtrace-a100-receipts')"),
        (" assert torch.cuda.device_count()==2\n assert all(torch.cuda.get_device_capability(i)==(7,5) and 'T4' in torch.cuda.get_device_name(i) for i in range(2))\n",
         " hardware=check_gpu(torch.cuda)\n event('qualified_hardware',**hardware)\n"),
        ("requested=='auto' and ns['vllm_cfg'].tensor_parallel_size==2",
         "requested=='bfloat16' and ns['vllm_cfg'].tensor_parallel_size==1"),
        ("capabilities=[list(torch.cuda.get_device_capability(i)) for i in range(2)]",
         "capabilities=[list(torch.cuda.get_device_capability(0))]"),
        ("gpu_names=[torch.cuda.get_device_name(i) for i in range(2)]",
         "gpu_names=[torch.cuda.get_device_name(0)]"),
        ("assert parallel['tensor_parallel_size']==2", "assert parallel['tensor_parallel_size']==1"),
        ("resolved in ('torch.float16','float16')", "resolved in ('torch.bfloat16','bfloat16')"),
        (" start=time.time();cpu_only='--cpu-prerequisites' in sys.argv\n",
         " require_local_procfs()\n start=time.time();cpu_only='--cpu-prerequisites' in sys.argv\n"),
        ('setup_deadline=min(start+300,requested_at+300)',
         'setup_deadline=min(start+1200,requested_at+1200)'),
        ('useful_deadline=min(start+1620,requested_at+1620)',
         'useful_deadline=min(start+2700,requested_at+2700)'),
        ('provider_expiry_seconds=1680', 'provider_expiry_seconds=3000'),
        (" shutil.copyfile(Path(__file__).with_name('startup_guard.py'),CODE/'startup_guard.py')\n",
         " shutil.copyfile(Path(__file__).with_name('startup_guard.py'),CODE/'startup_guard.py')\n"
         " for folder in ('tools','docs'):\n"
         "  shutil.copytree(Path(__file__).parent/folder,CODE/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))\n"),
        ("'venv','--system-site-packages','--without-pip'", "'venv','--without-pip'"),
        ('gpu_peak=[0,0]', 'gpu_peak=[0]'),
        ('assert len(used)==2', 'assert len(used)==1'),
    ]
    for before, after in changes:
        source = _replace(source, before, after)
    # Remove the entire original v25/online-install block, retaining its constant
    # bytes as history. Actual installation is the separately qualified bootstrap.
    begin = source.index("  wheelhouse=Path('/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse')\n")
    end = source.index('  versions={name:importlib.metadata.version(name) for name in PINS}\n', begin)
    source = source[:begin] + "  runtime_inventory=check_runtime()\n  event('offline_runtime',package_count=len(runtime_inventory))\n" + source[end:]
    source = _replace(source,
        "  subprocess.run([str(VENV/'bin/python'),'-m','pip','install'",
        "  inherit_runtime(VENV)\n  subprocess.run([str(VENV/'bin/python'),'-m','pip','install'")
    source = _replace(source, "if __name__=='__main__':\n",
        "if __name__=='__main__':\n"
        " if sys.argv[1:]!=['--cpu-prerequisites'] and not (len(sys.argv)==4 and sys.argv[1]=='isolation'):\n"
        "  raise SystemExit('Provider controller is not qualified; only CPU prerequisites may execute')\n")
    old, new = ast.parse(original), ast.parse(source)
    # These contain the actual prompts, budget, agent, input/model identities and
    # isolation checks. Preserve ASTs exactly, not merely a count of substitutions.
    preserved = ('OFFICIAL_SETUP', 'NATIVE_SERVING', 'EVAL_SETUP', 'OFFICIAL_ENV',
                 'WHEEL_PINS', 'PINS', 'INPUT_PINS', 'MODEL', 'agent_phase',
                 'isolation_check', 'shared_namespace', 'child_env')
    def node(tree, name):
        return next(n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name == name)
                    or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)))
    for name in preserved:
        if ast.dump(node(old, name)) != ast.dump(node(new, name)):
            raise ValueError('frozen driver component changed: ' + name)
    compile(source, '<private-a100-driver>', 'exec')
    return source


def prepare(source, output):
    data = source.read_bytes()
    result = transform(data)
    output.mkdir(mode=0o700)
    try:
        (output / 'one_task.py').write_text(result)
        shutil.copyfile(ROOT / 'tools/startup_guard.py', output / 'startup_guard.py')
        shutil.copytree(ROOT / 'tools', output / 'tools', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (output / 'docs').mkdir()
        for name in ('source-manifest.json', 'linux-wheel-manifest.json'):
            shutil.copyfile(ROOT / 'docs' / name, output / 'docs' / name)
        (output / 'driver.diff').write_text(''.join(difflib.unified_diff(
            data.decode().splitlines(True), result.splitlines(True),
            fromfile='retained-t4/one_task.py', tofile='prepared-a100/one_task.py')))
        receipt = {'retained_driver_sha256': DRIVER_SHA256,
                   'prepared_driver_sha256': hashlib.sha256(result.encode()).hexdigest(),
                   'frozen_components_ast_equal': True, 'provider_launch': 'BLOCKED',
                   'files': {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(output.rglob('*')) if p.is_file()}}
        (output / 'prepare-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return receipt
    except BaseException:
        shutil.rmtree(output)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output)))
