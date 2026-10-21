"""Free CPU public-task evaluation, isolated from every agent process/input.

The original public reference patch is used only as a verifier positive control.
It is never emitted, used as a model response, or copied into agent storage.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

TASKS_SHA256 = 'e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6'


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


def worker(root, task_inputs, *, controls=True):
    import asyncio
    from adk_submission import ModelRegistry
    from swegemma.config import EvalConfig
    from swegemma.models import Task
    from swegemma.harness.verification import verify_task
    from swegemma.sandbox import SubprocessManager
    from swegemma.deduplication import resolve_task_snapshot_paths
    if os.getuid() != 65533 or os.getgid() != 65533:
        raise ValueError('separate evaluator UID required')
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
        try:
            result = asyncio.run(verify_task(manager, config, task, snapshot,
                base_snapshot_path=base, patch_path=reconstruction, agent_patch=patch,
                start_time=time.perf_counter()))
        finally:
            manager.close()
        # Full test output remains private. Neither control writes the gold patch.
        (output / 'test-output.txt').write_text(result.test_output)
        summaries.append({'control': name, 'resolved': result.resolved,
                          'test_exit_code': result.test_exit_code,
                          'duration_seconds': result.duration_seconds,
                          'error_present': bool(result.error_message)})
    controls_failed = controls and (summaries[0]['resolved'] or summaries[0]['test_exit_code'] != 1
        or not summaries[1]['resolved'] or summaries[1]['test_exit_code'] != 0)
    evaluation_failed = not controls and summaries[0]['test_exit_code'] not in (0, 1)
    if controls_failed or evaluation_failed:
        (root / 'evaluation.json').write_text(json.dumps({'status': 'FAIL', 'controls': summaries}))
        raise ValueError('actual public-task verifier controls did not match; see private test logs')
    return {'status': 'PASS', 'controls': summaries, 'evaluator_uid': os.getuid(),
            'public_spec_sha256': TASKS_SHA256, 'gpu_allocations': 0,
            'reference_scope': 'evaluator-only positive control; no agent access' if controls else 'NOT USED',
            'model_score': 'NOT RUN; scripted transport patch and public reference only' if controls else
                           {'resolved': summaries[0]['resolved'], 'source': 'validated recovered task artifacts'}}


def qualify(evaluator, task_inputs, patch, output, *, controls=True):
    from tools.runpod_job import check_owner_host
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
        # The source checkout need not be traversable by the isolated evaluator.
        # Copy only this trusted, qualified worker, keeping agent access denied.
        script = root / 'verify.py'
        shutil.copyfile(__file__, script)
        script.chmod(0o400); os.chown(script, 65533, 65533)
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(root), 'LANG': 'C.UTF-8',
               'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'OTEL_SDK_DISABLED': 'true',
               'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'PYTHON_DOTENV_DISABLED': '1'}
        with (output / 'evaluator.log').open('wb') as log:
            result = subprocess.run(['setpriv', '--no-new-privs', '--bounding-set=-all', '--reuid=65533',
                '--regid=65533', '--clear-groups', sys.executable, '-I', str(script), '--worker',
                str(root), str(task_inputs), 'controls' if controls else 'result'], env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=log, timeout=300)
        (output / 'evaluator-stdout.log').write_bytes(result.stdout)
        for path in root.rglob('*'):
            if path.is_file() and path.name in ('evaluation.json', 'test-output.txt'):
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


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker'] and len(sys.argv) == 5 and sys.argv[4] in ('controls', 'result'):
        print(json.dumps(worker(Path(sys.argv[2]), Path(sys.argv[3]), controls=sys.argv[4] == 'controls'), sort_keys=True))
    else:
        raise ValueError('private evaluator worker entry only')
