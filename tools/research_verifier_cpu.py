"""Free, credential-free child qualification of selected verifier and isolation.

The only networked parent work resolves pinned inputs/packages. Each disposable
child has an independent PID namespace and a 330-second total lifetime envelope.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import research_comparison as c, cloud_resolver as resolver
from tools.direct_delivery import pull
from tools.research_isolation import Isolation, bounded_child
from tools.research_runtime import prepare as prepare_runtime
from tools.linux_runtime import BOOTSTRAP, offline_child


def dependencies(root, python, env):
    manifest_path = c.ROOT / 'docs/research-evaluator-dependencies.json'
    lock = c.parse(manifest_path.read_bytes())
    rows = lock['files']; root.mkdir(mode=0o700)
    def fetch(row):
        manifest = c.encoded({'schema_version': 1, 'phase': 'bootstrap', 'files': [
            {k: row[k] for k in ('path', 'bytes', 'sha256')}]})
        target = root / row['name']
        source = resolver.retry_read(lambda: resolver.pypi_source(row))
        pull(target, manifest, {row['path']: source}, c.digest(manifest), 180)
        return target / row['path']
    with ThreadPoolExecutor(max_workers=8) as pool:
        wheels = list(pool.map(fetch, rows))
    site = root / 'site-packages'
    with (root / 'install.log').open('wb') as stream:
        subprocess.run(offline_child(python, 'bootstrap-pip',
            str(root.parent / 'runtime/bootstrap' / BOOTSTRAP['path']),
            'install', '--no-index', '--no-deps', '--target', str(site), *map(str, wheels)),
            env=env, stdout=stream, stderr=stream,
            check=True, timeout=60)
    return site, {'status': 'PASS', 'packages': len(rows), 'files': rows,
                  'lock_sha256': c.digest(manifest_path.read_bytes()), 'agent_runtime_modified': False}


def readable_tree(root):
    for path in [root, *root.rglob('*')]:
        if path.is_symlink(): continue
        path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)


def qualify(inputs, output):
    if os.getuid() != 0: raise ValueError('root coordinator required')
    report = {'status': 'INCOMPLETE', 'source_sha': os.environ.get('GITHUB_SHA'),
        'run_id': os.environ.get('GITHUB_RUN_ID'), 'kind': 'SELECTED_VERIFIER_AND_ISOLATION_CPU',
        'real_model_runs': 0, 'provider_operations': 0, 'stages': {}}
    retained = inputs / 'verifier-evidence'; retained.mkdir(mode=0o700)
    with tempfile.TemporaryDirectory(prefix='backtrace-research-', dir='/var/tmp') as temp:
        public = Path(temp); public.chmod(0o711)
        private = public / 'private'; private.mkdir(mode=0o700)
        work = public / 'work'; work.mkdir(mode=0o711)
        env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'HOME': str(private),
            'OTEL_SDK_DISABLED': 'true', 'LITELLM_LOCAL_MODEL_COST_MAP': 'True',
            'LITELLM_TELEMETRY': 'False', 'PYTHON_DOTENV_DISABLED': '1',
            'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
        try:
            python, runtime = prepare_runtime(public / 'runtime', inputs / 'wheels')
            readable_tree(public / 'runtime'); report['runtime'] = runtime
            site, dep_report = dependencies(public / 'evaluator', python, env)
            readable_tree(public / 'evaluator'); report['dependencies'] = dep_report
            selection = c.parse((c.ROOT / 'docs/research-selection-20261024.json').read_bytes())
            def execute(kind, name, args, receipt='receipt.json'):
                destination = work / name
                row = bounded_child([python, '-I', '-B', Path(__file__).resolve(), '--worker', kind,
                    inputs, destination, public / 'runtime/wheels', site, *args], private / (name+'.log'), env)
                path = destination / receipt
                if path.is_file(): row['result'] = c.parse(path.read_bytes())
                row['status'] = ('PASS' if row['exit_code']==0 and not row['child_timeout']
                    and row.get('result', {}).get('status')=='PASS' else 'FAIL')
                print(json.dumps({'cpu_stage': kind, 'slot': name, 'status': row['status'],
                                  'wall_seconds': row['wall_seconds']}), file=sys.__stdout__, flush=True)
                return row
            report['stages']['isolation'] = execute('isolation', 'isolation', [])
            # Independent tasks preserve failures; no task replacement or skipped
            # denominator. Each reference pair uses fresh per-control sandboxes.
            controls = []
            for task in selection['primary']:
                controls.append(execute('verifier', task['instance_id'], [task['instance_id']]))
            report['stages']['verifier'] = {'status': 'PASS' if all(r['status']=='PASS' for r in controls) else 'FAIL',
                                           'tasks': controls}
            fixtures = []
            for task in selection['primary']:
                for arm in task['arm_order']:
                    fixtures.append(execute('fixture', task['instance_id']+'-'+arm,
                        [task['instance_id'], arm], 'fixture-receipt.json'))
            report['stages']['isolated_runner'] = {'status': 'PASS' if all(r['status']=='PASS' for r in fixtures) else 'FAIL',
                                                  'planned_slots': 18, 'slots': fixtures}
            report['status'] = 'PASS' if all(r['status']=='PASS' for r in report['stages'].values()) else 'FAIL'
        except Exception as error:
            report.update(status='FAIL', error_type=type(error).__name__)
            c._new_output(private / 'controller-error.log', traceback.format_exc().encode())
        finally:
            # Export only root-owned allowlisted receipts/logs after all children
            # are dead. Workspaces are removed by each original manager.
            for path in public.rglob('*'):
                if (path.is_file() and not path.is_symlink() and path.stat().st_uid==0
                        and (path.suffix in ('.log', '.json', '.xml') or path.name in
                             ('agent.patch', 'agent-error.txt', 'test-output.txt', 'official-error.txt'))
                        and 'sandboxes' not in path.relative_to(public).parts
                        and ('work' in path.relative_to(public).parts or 'private' in path.relative_to(public).parts
                             or path.name=='install.log')):
                    destination = retained / path.relative_to(public)
                    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    shutil.copyfile(path, destination); destination.chmod(0o600)
    report['temporary_runtime_removed'] = not public.exists()
    sources = ['tools/research_isolation.py', 'tools/research_isolation_probe.py', 'tools/research_verifier.py',
        'tools/research_verifier_cpu.py', 'tools/research_fixture.py', 'tools/research_runner.py',
        'tools/research_assets.py', 'tools/research_runtime.py', 'tools/research_meter.py',
        'docs/research-evaluator-dependencies.json', '.github/workflows/research-verifier-cpu.yml']
    report['implementation'] = {p: c.digest((c.ROOT/p).read_bytes()) for p in sources}
    c._new_output(output, c.encoded(report))
    return report


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        kind = sys.argv[2]
        inputs, output, wheels, site = map(Path, sys.argv[3:7])
        if kind == 'isolation':
            from tools.research_isolation_probe import qualify as probe
            result = probe(output)
        elif kind == 'verifier':
            from tools.research_verifier import worker
            result = worker(inputs, output, sys.argv[7], wheels, site)
        elif kind == 'fixture':
            from tools.research_fixture import run_fixture
            isolation = Isolation(output.parent / (output.name+'-private-isolation'), 65532)
            result = run_fixture(inputs, output, sys.argv[7], sys.argv[8], wheels, isolation=isolation)
        else: raise ValueError('unknown private CPU worker')
        print(json.dumps({'status': result['status'], 'kind': kind}))
    else:
        from tools.research_assets import prepare
        result = prepare(Path(sys.argv[1]), qualification=qualify)
        print(json.dumps({'status': result['status'], 'phase': result.get('phase'),
                          'error_type': result.get('error_type')}))
    raise SystemExit(0 if result['status']=='PASS' else 1)
