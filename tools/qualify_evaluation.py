"""Free CPU public-task evaluation, isolated from every agent process/input.

The original public reference patch is used only as a verifier positive control.
It is never emitted, used as a model response, or copied into agent storage.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET

TASKS_SHA256 = 'e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6'


def verified_tests(xml, exit_code, resolved, error_present):
    """An exit 1 without executed tests is infrastructure failure, not a score."""
    if not xml or len(xml.encode()) > 4 * 1024**2:
        raise ValueError('missing or oversized actual pytest JUnit receipt')
    try:
        root = ET.fromstring(xml)
        suites = [root] if root.tag == 'testsuite' else list(root.findall('.//testsuite'))
        counts = {k: sum(int(s.get(k, '0')) for s in suites)
                  for k in ('tests', 'failures', 'errors', 'skipped')}
    except (ET.ParseError, ValueError, TypeError) as error:
        raise ValueError('invalid actual pytest JUnit receipt') from error
    passed = counts['tests'] - sum(counts[k] for k in ('failures', 'errors', 'skipped'))
    if (not suites or counts['tests'] != len(root.findall('.//testcase'))
            or any(v < 0 for v in counts.values()) or passed < 0
            or counts['tests'] <= counts['skipped'] or counts['errors'] or error_present
            or exit_code not in (0, 1)
            or (exit_code == 0 and (not resolved or counts['failures'] or passed <= 0))
            or (exit_code == 1 and (resolved or counts['failures'] <= 0))):
        raise ValueError('public tests did not execute with a valid pass/fail outcome')
    return dict(counts, passed=passed, junit_sha256=hashlib.sha256(xml.encode()).hexdigest())


def install_evaluator_dependencies(root):
    rows = json.loads((root / 'evaluator-dependencies.json').read_text())['files']
    wheels = []
    for row in rows:
        path = root / 'wheels' / row['path']
        body = path.read_bytes()
        if (path.is_symlink() or Path(row['path']).name != row['path']
                or len(body) != row['bytes'] or hashlib.sha256(body).hexdigest() != row['sha256']):
            raise ValueError('CPU evaluator dependency identity mismatch')
        wheels.append(str(path))
    site = root / 'site-packages'
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps',
        '--target', str(site), *wheels], check=True, timeout=30, stdout=sys.stderr)
    # The official subprocess manager inherits actual site-packages directories
    # from this evaluator process. Nothing is added to the shared agent runtime.
    sys.path.insert(0, str(site))


def select(path, agent_input):
    body = Path(path).read_bytes()
    if len(body) != 1984455 or hashlib.sha256(body).hexdigest() != TASKS_SHA256:
        raise ValueError('original public evaluation specification required')
    records = [json.loads(line) for line in body.splitlines() if line]
    selected = [r for r in records if r.get('instance_id') == 'fastapi_11194']
    if len(selected) != 1:
        raise ValueError('unique selected public evaluation task required')
    record = selected[0]
    visible = json.loads(Path(agent_input).read_text())
    if any(record.get(k, '') != v for k, v in visible.items()):
        raise ValueError('evaluator and agent task identities disagree')
    return record


def worker(root, task_inputs, *, controls=True, partial=False):
    import asyncio
    from adk_submission import ModelRegistry
    from swegemma.config import EvalConfig
    from swegemma.models import Task
    from swegemma.harness.verification import verify_task
    from swegemma.sandbox import SubprocessManager
    from swegemma.deduplication import resolve_task_snapshot_paths
    if partial and controls:
        raise ValueError('partial diagnostics cannot use reference controls')
    if os.getuid() != 65533 or os.getgid() != 65533:
        raise ValueError('separate evaluator UID required')
    install_evaluator_dependencies(root)
    record = select(root / 'tasks.jsonl', task_inputs / 'agent-task.json')
    # The Task presented to verification contains test specifications, never the
    # reference implementation. The latter goes only to the positive control.
    keys = {'instance_id', 'repo', 'base_commit', 'problem_statement', 'hints_text',
            'test_patch', 'FAIL_TO_PASS', 'PASS_TO_PASS', 'created_at', 'environment_setup_commit'}
    task = Task(**{k: v for k, v in record.items() if k in keys})
    assert not task.patch and task.test_patch
    candidate = root / 'candidate'; candidate.mkdir()
    data = (task_inputs / 'r0-clean.zip').read_bytes()
    if hashlib.sha256(data).hexdigest() != '2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358':
        raise ValueError('frozen R0 candidate required')
    with zipfile.ZipFile(task_inputs / 'r0-clean.zip') as archive:
        archive.extractall(candidate)
    summaries = []
    # Both controls are verifier-only. No artificial patch can become a claimed
    # model result: every summary explicitly names the source of the patch.
    patches = [('recovered-patch', (root / 'agent.patch').read_text())]
    if controls:
        patches.append(('public-reference-control', record['patch']))
    for name, patch in patches:
        output = root / name; output.mkdir()
        config = EvalConfig(tasks_path=task_inputs / 'agent-task.json',
            snapshots_dir=task_inputs / 'snapshots', results_dir=output,
            submission_dir=candidate, models=ModelRegistry(), sandbox='subprocess',
            wheels_dir=task_inputs / 'wheels', timeout_seconds=60,
            max_time_minutes=1.0, max_tool_calls=10, max_turns=50, display_mode='quiet')
        snapshot, base, reconstruction = resolve_task_snapshot_paths(
            config.snapshots_dir, task.instance_id, task.repo)
        manager = SubprocessManager(timeout_seconds=60, base_dir=output / 'sandboxes')
        actual_exec, receipts = manager.exec, []
        def observed_exec(sandbox_id, command, *, timeout=None):
            outcome = actual_exec(sandbox_id, command, timeout=timeout)
            if ' -m pytest ' not in command or '--junitxml=' not in command:
                return outcome
            paths = [arg.split('=', 1)[1] for arg in shlex.split(command)
                     if arg.startswith('--junitxml=')]
            if paths:
                if len(paths) != 1 or not re.fullmatch(r'/tmp/_swegemma_junit_[0-9a-f]+\.xml', paths[0]):
                    raise ValueError('unexpected public verifier JUnit path')
                xml = actual_exec(sandbox_id, 'cat ' + shlex.quote(paths[0])
                    + ' 2>/dev/null || true', timeout=10).stdout
                (output / 'test-results.xml').write_text(xml)
                receipts.append(xml)
            return outcome
        manager.exec = observed_exec
        try:
            result = asyncio.run(verify_task(manager, config, task, snapshot,
                base_snapshot_path=base, patch_path=reconstruction, agent_patch=patch,
                start_time=time.perf_counter()))
        finally:
            manager.close()
        # Full test output remains private. Neither control writes the gold patch.
        (output / 'test-output.txt').write_text(result.test_output)
        tests, validation_error = None, None
        try:
            if len(receipts) != 1:
                raise ValueError('one actual public-test execution required')
            tests = verified_tests(receipts[0], result.test_exit_code, result.resolved,
                                   bool(result.error_message))
        except ValueError as error:
            validation_error = str(error)
        summaries.append({'control': name, 'resolved': result.resolved,
                          'test_exit_code': result.test_exit_code,
                          'duration_seconds': result.duration_seconds,
                          'error_present': bool(result.error_message),
                          'actual_tests': tests, 'validation_error': validation_error})
    controls_failed = controls and (summaries[0]['resolved'] or summaries[0]['test_exit_code'] != 1
        or not summaries[1]['resolved'] or summaries[1]['test_exit_code'] != 0)
    evaluation_failed = any(row['validation_error'] for row in summaries)
    if controls_failed or evaluation_failed:
        (root / 'evaluation.json').write_text(json.dumps({'status': 'FAIL', 'controls': summaries}))
        raise ValueError('actual public-task verifier controls did not match; see private test logs')
    return {'status': 'PASS', 'controls': summaries, 'evaluator_uid': os.getuid(),
            'public_spec_sha256': TASKS_SHA256, 'gpu_allocations': 0,
            'reference_scope': 'evaluator-only positive control; no agent access' if controls else 'NOT USED',
            'model_score': ('NOT CLAIMED; incomplete task patch diagnostic only' if partial else
                           'NOT RUN; scripted transport patch and public reference only' if controls else
                           {'resolved': summaries[0]['resolved'], 'source': 'validated recovered task artifacts'}),
            'completed_agent_task': False if partial else 'not assessed by verifier',
            'partial_patch_diagnostic': {'resolved': summaries[0]['resolved']} if partial else None}


def qualify(evaluator, task_inputs, patch, output, *, controls=True, partial=False):
    from tools.runpod_job import check_owner_host
    if partial and controls:
        raise ValueError('partial diagnostics cannot use reference controls')
    check_owner_host()
    select(evaluator, task_inputs / 'agent-task.json')
    # A private different UID prevents a concurrently surviving agent from
    # reading test specifications or the positive-control patch.
    output.mkdir(mode=0o700, parents=True)
    with tempfile.TemporaryDirectory(prefix='backtrace-evaluator-') as directory:
        root = Path(directory)
        root.chmod(0o700); os.chown(root, 65533, 65533)
        for source, name in ((evaluator, 'tasks.jsonl'), (patch, 'agent.patch')):
            target = root / name
            shutil.copyfile(source, target)
            target.chmod(0o400); os.chown(target, 65533, 65533)
        dependencies = Path(__file__).resolve().parents[1] / 'docs/a100-evaluator-dependencies.json'
        rows = json.loads(dependencies.read_text())['files']
        (root / 'wheels').mkdir(mode=0o700); os.chown(root / 'wheels', 65533, 65533)
        for source, name in [(dependencies, 'evaluator-dependencies.json')] + [
                (evaluator.parent / 'wheels' / row['path'], 'wheels/' + row['path']) for row in rows]:
            target = root / name
            shutil.copyfile(source, target); target.chmod(0o400); os.chown(target, 65533, 65533)
        # The source checkout need not be traversable by the isolated evaluator.
        # Copy only this trusted, qualified worker, keeping agent access denied.
        script = root / 'verify.py'
        shutil.copyfile(__file__, script)
        script.chmod(0o400); os.chown(script, 65533, 65533)
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(root), 'LANG': 'C.UTF-8',
               'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'OTEL_SDK_DISABLED': 'true',
               'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'PYTHON_DOTENV_DISABLED': '1',
               'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
        with (output / 'evaluator.log').open('wb') as log:
            result = subprocess.run(['setpriv', '--no-new-privs', '--bounding-set=-all', '--reuid=65533',
                '--regid=65533', '--clear-groups', sys.executable, '-I', str(script), '--worker',
                str(root), str(task_inputs), 'partial' if partial else 'controls' if controls else 'result'], env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=log, timeout=300)
        (output / 'evaluator-stdout.log').write_bytes(result.stdout)
        for path in root.rglob('*'):
            if path.is_file() and path.name in ('evaluation.json', 'test-output.txt', 'test-results.xml'):
                dest = output / path.relative_to(root)
                dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                shutil.copyfile(path, dest)
        if result.returncode != 0:
            raise RuntimeError('free CPU evaluation control failed; see private evidence')
        report = json.loads(result.stdout.splitlines()[-1])
        (output / 'evaluation.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
        return report


def evaluate_receipts(evaluator, task_inputs, receipts, output):
    """Score real recovered results on CPU after provider deletion, with no model call.

    Caller must first confirm provider cleanup. This function has no provider,
    inference, credential, submission, or positive-reference control operation.
    """
    from tools.task_results import validate
    validate(receipts)
    return qualify(Path(evaluator), Path(task_inputs), Path(receipts) / 'agent.patch',
                   Path(output), controls=False)


def diagnose_incomplete_receipts(evaluator, task_inputs, receipts, output, manifest):
    """Test a byte-bound partial patch, retaining its original incomplete status.

    This separate entry never relaxes evaluate_receipts/validate, never calls
    a model, and never labels the result a completed-task model score.
    """
    from tools.recovered_task import analyze
    evidence = analyze(receipts, manifest)
    report = qualify(Path(evaluator), Path(task_inputs), Path(receipts) / 'agent.patch',
                     Path(output), controls=False, partial=True)
    if (report.get('completed_agent_task') is not False
            or report.get('model_score') != 'NOT CLAIMED; incomplete task patch diagnostic only'):
        raise ValueError('partial patch must not become a completed-task score')
    report['original_task_result'] = evidence['task_result']
    return report


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker'] and len(sys.argv) == 5 and sys.argv[4] in ('controls', 'result', 'partial'):
        print(json.dumps(worker(Path(sys.argv[2]), Path(sys.argv[3]), controls=sys.argv[4] == 'controls',
                                partial=sys.argv[4] == 'partial'), sort_keys=True))
    else:
        raise ValueError('private evaluator worker entry only')
