"""Selected-task public verifier controls; reference data stays with root.

Only original test specifications and the selected candidate patch enter each
fresh evaluator sandbox. Agent processes never receive either reference field.
"""
import asyncio
from pathlib import Path
import re
import shlex
import time
import xml.etree.ElementTree as ET

from tools import research_comparison as c
from tools.qualify_evaluation import verified_tests
from tools.research_assets import FIELDS
from tools.research_isolation import Isolation
from tools.research_runner import checked_slot


def select(inputs, identifier):
    protocol = c.load_protocol()
    body = c.read_file(inputs / 'metadata/tasks.jsonl', protocol['selection']['metadata_bytes'])
    if len(body) != protocol['selection']['metadata_bytes'] or c.digest(body) != protocol['selection']['metadata_sha256']:
        raise ValueError('pinned public verifier specification required')
    selection = c.parse((c.ROOT / 'docs/research-selection-20261024.json').read_bytes())
    if c.select_tasks(body, protocol) != selection:
        raise ValueError('public verifier selection changed')
    visible, _ = checked_slot(inputs, identifier, 'R0')
    records = [c.parse(line) for line in body.splitlines() if line.strip()]
    selected = [r for r in records if r['instance_id'] == identifier]
    if len(selected) != 1 or visible != {k: selected[0].get(k, '') for k in FIELDS}:
        raise ValueError('agent and evaluator task identity mismatch')
    return selected[0]


def expected_baseline_nodes(xml, task):
    nodes = []
    for node in ET.fromstring(xml).findall('.//testcase'):
        name, classname = node.get('name', ''), node.get('classname', '')
        names = {name, name.split('[', 1)[0]}
        if classname:
            names.update((classname+'::'+name, classname+'.'+name,
                          classname.replace('.', '/')+'.py::'+name))
        state = ('error' if node.find('error') is not None else 'skipped' if node.find('skipped') is not None
                 else 'failed' if node.find('failure') is not None else 'passed')
        nodes.append((names, state))
    if not task.FAIL_TO_PASS and not task.PASS_TO_PASS:
        # A diff can add parameter rows to an existing test without containing
        # its function name. Do not manufacture F2P labels with a def-name regex.
        # The paired control requires actual failure here and all applicable
        # official test-file targets to pass with the reference patch below.
        failures = sum(state == 'failed' for _, state in nodes)
        if not failures:
            raise ValueError('unmodified baseline must contain an executed failing test')
        return {'source': 'original official test-file contrast', 'explicit_node_states': 'NOT PROVIDED',
                'failed_test_cases': failures, 'matched': True}
    from swegemma.harness.verification import _node_matches_requirement
    for requirements, state in ((task.FAIL_TO_PASS, 'failed'), (task.PASS_TO_PASS, 'passed')):
        for required in requirements:
            short = required.split('::')[-1]; base = short.split('[', 1)[0]
            matches = [actual for names, actual in nodes if any(
                _node_matches_requirement(n, required, short, base) for n in names)]
            if not matches or any(actual != state for actual in matches):
                raise ValueError('baseline required test states do not match public specification')
    return {'fail_to_pass': len(task.FAIL_TO_PASS), 'pass_to_pass': len(task.PASS_TO_PASS), 'matched': True}


def worker(inputs, output, identifier, wheels, evaluator_site):
    from adk_submission import ModelRegistry
    from swegemma.config import EvalConfig
    from swegemma.models import Task
    from swegemma.harness.verification import verify_task
    from swegemma.sandbox import SubprocessManager
    from swegemma.deduplication import resolve_task_snapshot_paths
    from tools.research_official import materialize_candidate
    record = select(inputs, identifier)
    keys = set(FIELDS) | {'test_patch', 'FAIL_TO_PASS', 'PASS_TO_PASS', 'created_at', 'environment_setup_commit'}
    task = Task(**{k: v for k, v in record.items() if k in keys})
    if task.patch or not task.test_patch or not record['patch']:
        raise ValueError('original tests and evaluator-only positive patch required')
    output.mkdir(mode=0o711)
    private = output / 'private'; private.mkdir(mode=0o700)
    candidate = private / 'candidate'
    materialize_candidate(inputs / 'candidates/R0.zip', 'R0', candidate)
    summaries = []
    for name, patch in [('unmodified-baseline', ''), ('public-reference-control', record['patch'])]:
        destination = output / name; destination.mkdir(mode=0o711)
        logs = private / name; logs.mkdir(mode=0o700)
        config = EvalConfig(tasks_path=inputs / 'agents' / identifier / 'agent-task.json',
            snapshots_dir=inputs / 'assets/snapshots', results_dir=logs,
            submission_dir=candidate, models=ModelRegistry(), sandbox='subprocess',
            wheels_dir=wheels, timeout_seconds=60, max_time_minutes=5,
            max_tool_calls=30, max_turns=50, display_mode='quiet')
        snapshot, base, reconstruction = resolve_task_snapshot_paths(config.snapshots_dir, identifier, task.repo)
        manager = SubprocessManager(timeout_seconds=60, base_dir=destination / 'sandboxes')
        isolation = Isolation(logs / 'isolation', 65533); isolation.attach(manager)
        isolated_start, actual_exec = manager.start, manager.exec
        receipts, provenance = [], []
        def start():
            sid = isolated_start()
            site = next(manager.sandboxes[sid]['venv'].glob('lib/python*/site-packages'))
            # Only evaluator task interpreters receive this separate overlay.
            (site / '_evaluator.pth').write_text(str(evaluator_site) + '\n')
            return sid
        manager.start = start
        def observed_exec(sid, command, *, timeout=None):
            is_test = ' -m pytest ' in command and '--junitxml=' in command
            if is_test:
                # The pinned SubprocessManager explicitly skips editable installs.
                # Do the actual offline install as the evaluator UID, with no mocks.
                installed = actual_exec(sid, 'python3 -m pip install --no-index --no-deps '
                    '--no-build-isolation -e /workspace', timeout=60)
                c._new_output(logs / 'editable-install.log', (installed.stdout + installed.stderr).encode())
                if installed.exit_code != 0:
                    raise ValueError('offline workspace editable installation failed')
                module = task.repo.split('/')[-1].lower()
                code = ('import importlib,os,pathlib; assert os.getuid()==65533; p=pathlib.Path(importlib.import_module('
                        + repr(module) + ').__file__).resolve(); '
                        + "assert p.is_relative_to(pathlib.Path('/workspace').resolve()); print('WORKSPACE_IMPORT')")
                imported = actual_exec(sid, 'python3 -s -c ' + shlex.quote(code), timeout=10)
                provenance.append(imported.exit_code == 0 and imported.stdout.strip() == 'WORKSPACE_IMPORT')
                if not provenance[-1]:
                    c._new_output(logs / 'import-error.log', (imported.stdout + imported.stderr).encode())
                    raise ValueError('verifier imported a package outside its workspace')
            result = actual_exec(sid, command, timeout=timeout)
            if is_test:
                paths = [arg.split('=', 1)[1] for arg in shlex.split(command) if arg.startswith('--junitxml=')]
                if len(paths) != 1 or not re.fullmatch(r'/tmp/_swegemma_junit_[0-9a-f]+\.xml', paths[0]):
                    raise ValueError('unexpected official verifier JUnit path')
                xml = actual_exec(sid, 'cat ' + shlex.quote(paths[0]) + ' 2>/dev/null || true', timeout=10).stdout
                c._new_output(logs / 'test-results.xml', xml.encode()); receipts.append(xml)
            return result
        manager.exec = observed_exec
        result = None; error_type = None
        try:
            result = asyncio.run(verify_task(manager, config, task, snapshot,
                base_snapshot_path=base, patch_path=reconstruction, agent_patch=patch,
                start_time=time.perf_counter()))
        except Exception as error:
            import traceback
            error_type = type(error).__name__
            c._new_output(logs / 'exception.log', traceback.format_exc().encode())
        finally:
            manager.close(); isolation.finish()
        tests = None; validation_error = None; expected_nodes = None; observed_junit = None
        if result is not None:
            c._new_output(logs / 'test-output.txt', result.test_output.encode())
            if result.error_message:
                c._new_output(logs / 'official-error.txt', result.error_message.encode())
            if len(receipts) == 1 and len(receipts[0].encode()) <= 4 * 1024**2:
                try:
                    xml = ET.fromstring(receipts[0])
                    suites = [xml] if xml.tag == 'testsuite' else xml.findall('.//testsuite')
                    observed_junit = {k: sum(int(s.get(k, '0')) for s in suites)
                                      for k in ('tests', 'failures', 'errors', 'skipped')}
                    observed_junit['junit_sha256'] = c.digest(receipts[0].encode())
                except (ValueError, ET.ParseError): pass
            try:
                if len(receipts) != 1 or provenance != [True]:
                    raise ValueError('one executed verifier and workspace import required')
                tests = verified_tests(receipts[0], result.test_exit_code, result.resolved, bool(result.error_message))
                if name == 'unmodified-baseline': expected_nodes = expected_baseline_nodes(receipts[0], task)
            except ValueError as error:
                validation_error = str(error)
        expected = name == 'public-reference-control'
        passed = (result is not None and error_type is None and validation_error is None
                  and result.resolved == expected and result.test_exit_code == (0 if expected else 1)
                  and isolation.report()['live_namespaces'] == 0 and not manager.sandboxes)
        summaries.append({'control': name, 'status': 'PASS' if passed else 'FAIL',
            'resolved': result.resolved if result is not None else None,
            'test_exit_code': result.test_exit_code if result is not None else None,
            'duration_seconds': result.duration_seconds if result is not None else None,
            'error_type': error_type, 'official_error_present': bool(result and result.error_message),
            'actual_tests': tests, 'validation_error': validation_error, 'expected_baseline_nodes': expected_nodes,
            'observed_junit': observed_junit,
            'workspace_import': provenance, 'isolation': isolation.report()})
    report = {'status': 'PASS' if all(r['status'] == 'PASS' for r in summaries) else 'FAIL',
              'instance_id': identifier, 'controls': summaries, 'model_score': 'NOT RUN',
              'reference_scope': 'root coordinator and positive-control sandbox only',
              'test_scope': 'original official verification command and test-file targets'}
    c._new_output(output / 'receipt.json', c.encoded(report))
    return report
