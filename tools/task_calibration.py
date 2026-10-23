"""Explicit five-minute/search calibration of the byte-pinned public baseline.

No reference answer, task-specific symbol, provider API, permit or model call.
The original input ZIP and retained driver remain immutable inputs.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import time

from tools.task_budget import PROPOSAL, check

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = 'R1-budget5m-search-guidance-v1/A10080-TP1'
BUDGET = dict(PROPOSAL, protocol=PROTOCOL, status='IMPLEMENTED_FREE_CPU_ONLY')
SERVER_STOP_SECONDS = 30
BASE_DRIVER_SHA256 = '174bd6359c3e3f53e149a2ec5210cb220ab46ec41e1e9b34b6b0c915631c55b1'
BASE_FILES = {
    'agent.yaml': 'de80dff58c1ab3e758a814b915c21113a16ddf632ac4d5fee238b8d6a1b6b5a8',
    'configs/sampling.yaml': '3dab0b2506dae34ce92fef7b380d6073729104b23fe2cf66d44ac1d2f213aa6a',
    'eval_config.yaml': 'adb486b67535fa59b427b79d44dafc131176f1f1964d184e16046ed520ede02d',
    'prompts/analyzer.md': 'c762b062032cc8463015e589ad8b4f0e17296062e1b0ff1e78712eef9f5e2d43',
    'prompts/system.md': 'f1cbf7943ee9687382321b1dfd9cd88581d608c1c8b8e6ea61a763bd1a3234af',
    'sub_agents/code_analyzer.yaml': '73ff867103879db19d42ab2fd24673090793290e33170b06d2e377f3ae89b6d3',
}
GUIDANCE = b'''\n\n## Search and completion budget
- Graph similarity uses indexed function/class identifiers, not arbitrary prose embeddings.
- Pass a bare identifier, without a def/class prefix. After an empty graph result,
  use run_command for a narrow, read-only repository text search, for example
  git grep -n -F -- 'symbol_name'. Read its output before another graph query.
  Both searches consume the declared shared tool budget.
- If both searches are empty, read a likely source file or revise the hypothesis;
  do not repeat the same empty search. Do not spend the session polishing repro scripts.
- Use get_status to inspect the shared budget. Keep the last two tool calls and
  45 seconds for verification already in progress, submit_patch, and a final text reply.
- Submit an implementation change, not only a reproduction script. If no fix was
  established, report that limitation; never describe a partial patch as resolved.
'''
ANALYZER_GUIDANCE = b'''\n\n## Search and shared budget
- Use bare indexed function/class identifiers, without a def/class prefix.
- After an empty graph query, read a likely file with read_file or return the
  missing symbol and a suggested text-search query to the parent agent.
- The parent owns repository command execution, editing and patch submission.
  Use only your declared read-only tools. Do not repeat empty graph searches.
- Keep the diagnosis concise so the parent retains time to implement and submit.
'''


def _replace(data, before, after):
    if data.count(before) != 1:
        raise ValueError('unexpected pinned calibration input shape')
    return data.replace(before, after, 1)


def candidate_files(files):
    if (set(files) != set(BASE_FILES)
            or any(hashlib.sha256(files[k]).hexdigest() != v for k, v in BASE_FILES.items())):
        raise ValueError('calibration requires the exact original six-file baseline')
    result = dict(files)
    result['eval_config.yaml'] = _replace(result['eval_config.yaml'], b'max_tool_calls: 10', b'max_tool_calls: 30')
    result['eval_config.yaml'] = _replace(result['eval_config.yaml'], b'max_time_minutes: 1', b'max_time_minutes: 5')
    result['prompts/system.md'] = _replace(result['prompts/system.md'], b'(under 8\xe2\x80\x9310 turns)', b'(within the declared shared task budget)')
    result['prompts/system.md'] = _replace(result['prompts/system.md'],
        b'use `search_similar_code` with keywords from the error message',
        b'use `search_similar_code` with an indexed function or class identifier')
    result['prompts/system.md'] += GUIDANCE
    result['prompts/analyzer.md'] += ANALYZER_GUIDANCE
    return result


def apply_candidate(root):
    """Apply only after all original bytes pass; refuse symlinks/extra files."""
    root = Path(root).absolute()
    paths = list(root.rglob('*'))
    if (root.is_symlink() or any(p.is_symlink() for p in paths)
            or {p.relative_to(root).as_posix() for p in paths if p.is_file()} != set(BASE_FILES)):
        raise ValueError('exact extracted baseline directory required')
    before = {name: (root / name).read_bytes() for name in BASE_FILES}
    after = candidate_files(before)
    for name, data in after.items():
        if data != before[name]:
            (root / name).write_bytes(data)
    return {'protocol': PROTOCOL, 'budget': BUDGET,
            'files': {name: hashlib.sha256(data).hexdigest() for name, data in after.items()}}


def require_window(phase, *, env=None, now=None):
    """Allocation-inclusive wall clocks, checked before startup and agent entry."""
    env = os.environ if env is None else env
    now = time.time() if now is None else now
    useful, total = (float(env[k]) for k in ('BACKTRACE_USEFUL_DEADLINE', 'BACKTRACE_TOTAL_DEADLINE'))
    if (phase not in ('server', 'agent') or any(not math.isfinite(v) for v in (now, useful, total))
            or total < useful):
        raise ValueError('valid nested allocation deadlines required')
    if check(BUDGET, 10**9, 10**9)['status'] != 'PASS':
        raise ValueError('agent child must cover the full session and teardown')
    startup = BUDGET['server_startup_seconds'] if phase == 'server' else 0
    work = startup + BUDGET['agent_child_seconds'] + SERVER_STOP_SECONDS + BUDGET['retrieval_seconds']
    all_work = work + BUDGET['provider_cleanup_seconds']
    if useful - now < work or total - now < all_work:
        raise TimeoutError('insufficient time for startup/task, server stop, retrieval and provider cleanup')
    return {'phase': phase, 'minimum_useful_seconds': work, 'minimum_total_seconds': all_work}


def driver_source(source):
    """Apply the declared scientific delta after reproducing the old derivative."""
    if hashlib.sha256(source.encode()).hexdigest() != BASE_DRIVER_SHA256:
        raise ValueError('calibration requires the exact previous cloud driver')
    changes = [
        ("RUN_NAME='R0-clean-v2-one-public-task/A10080-TP1'", 'RUN_NAME=' + repr(PROTOCOL)),
        (" env['BACKTRACE_USEFUL_DEADLINE']=str(useful_deadline)\n",
         " env['BACKTRACE_USEFUL_DEADLINE']=str(useful_deadline)\n env['BACKTRACE_TOTAL_DEADLINE']=str(requested_at+7200)\n"),
        ("  for p in (WORK/'candidate').rglob('*'): os.chown(p,65534,65534)\n",
         "  from tools.task_calibration import apply_candidate\n  event('task_calibration',**apply_candidate(WORK/'candidate'))\n"
         "  for p in (WORK/'candidate').rglob('*'): os.chown(p,65534,65534)\n"),
        ("==(60,10,1.0,50)\n", "==(60,30,5.0,50)\n"),
        (" start=time.time()\n event('task_start',instance_id=task.instance_id)\n",
         " start=time.time()\n event('task_start',instance_id=task.instance_id,protocol=RUN_NAME)\n"),
        ("result={'instance_id':task.instance_id,'agent_error':error,",
         "result={'instance_id':task.instance_id,'protocol':RUN_NAME,'patch_submitted':bool(context.patch_submitted),"
         "'budget':{'session_seconds':300,'tool_calls':30,'llm_calls':50},'agent_error':error,"),
        ("  validate(WORK)\n", "  validate(WORK,protocol=RUN_NAME)\n"),
        (" start=time.time()\n try:\n  server.start()",
         " from tools.task_calibration import require_window\n require_window('server')\n start=time.time()\n try:\n  server.start()"),
        ("  assert time.time()+180<float(os.environ['BACKTRACE_USEFUL_DEADLINE']),'insufficient time for one task and cleanup'\n",
         "  require_window('agent')\n"),
        ("stdin=subprocess.DEVNULL,timeout=180)\n", "stdin=subprocess.DEVNULL,timeout=330)\n"),
        ("policy='prepaid10-actions-v1',setup_seconds=5400)",
         "policy='prepaid10-actions-v1',setup_seconds=5400,expected_run=RUN_NAME)"),
    ]
    for before, after in changes:
        source = _replace(source, before, after)
    compile(source, '<calibrated-private-driver>', 'exec')
    return source
