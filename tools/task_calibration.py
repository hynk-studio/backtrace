"""Explicit five-minute/search calibration of the byte-pinned public baseline.

No reference answer, task-specific symbol, provider API, permit or model call.
The original input ZIP and retained driver remain immutable inputs.
"""
import functools
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import time

from tools.task_budget import PROPOSAL, check

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = 'R1-budget5m-search-fallback-v1/A10080-TP1'
BUDGET = dict(PROPOSAL, protocol=PROTOCOL, status='IMPLEMENTED_FREE_CPU_ONLY')
SERVER_STOP_SECONDS = 30
SUBMIT_RESERVE_SECONDS = 45
SUBMIT_RESERVE_TOOLS = 2
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
- The runtime normalizes simple def/class identifiers. An empty graph result includes
  a bounded, read-only git text search when the shared tool/time budget permits.
  Read the returned text_search output before issuing another graph query.
- If both searches are empty, read a likely source file or revise the hypothesis;
  do not repeat the same empty search. Do not spend the session polishing repro scripts.
- Use get_status to inspect the shared budget. Keep the last two tool calls and
  45 seconds for verification already in progress, submit_patch, and a final text reply.
- Submit an implementation change, not only a reproduction script. If no fix was
  established, report that limitation; never describe a partial patch as resolved.
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
    for name in ('prompts/system.md', 'prompts/analyzer.md'):
        result[name] += GUIDANCE
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


def normalized_query(query):
    match = re.fullmatch(r'\s*(?:(?:async\s+)?def|class)\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*[:(]?\s*', query)
    return match.group(1) if match else query


def install_search_fallback(context_type):
    """Wrap the official bound tool; fallback calls the real budget-gated command.

    Installation is local to one short-lived agent interpreter. Never mutate
    installed wheels or use a second model. Both internal operations are counted.
    """
    original = context_type.create_tools
    if getattr(original, '_backtrace_calibration', False):
        return

    @functools.wraps(original)
    def create_tools(context):
        tools = original(context)
        search, command = tools['search_similar_code'], tools['run_command']

        @functools.wraps(search)
        def search_with_fallback(query: str, k: int = 10) -> str:
            normalized = normalized_query(query)
            result = json.loads(search(normalized, k))
            result['query_original'] = query
            left = context.budget.tool_calls - context.tool_calls_used
            seconds = context.budget.time_minutes * 60 - context.elapsed_seconds
            result['submission_reserve'] = {'remaining_tool_calls': left, 'remaining_seconds': seconds,
                'reserve_tool_calls': SUBMIT_RESERVE_TOOLS, 'reserve_seconds': SUBMIT_RESERVE_SECONDS}
            if result.get('status') == 'ok' and result.get('count') == 0:
                if (left > SUBMIT_RESERVE_TOOLS and seconds > SUBMIT_RESERVE_SECONDS + 5
                        and isinstance(normalized, str) and 0 < len(normalized) <= 200
                        and '\n' not in normalized and '\x00' not in normalized):
                    # timeout is coreutils in the pinned image; actual CPU probes
                    # exercise the command. -F/--/shell quoting keep it literal.
                    text = 'timeout 5s git grep -n -F -m 2 -- ' + shlex.quote(normalized) + ' | head -n 40'
                    result['text_search'] = json.loads(command(text))
                    result['text_search_command'] = text
                    result['submission_reserve']['remaining_tool_calls'] = context.budget.tool_calls - context.tool_calls_used
                else:
                    result['text_search'] = {'status': 'not_run', 'reason': 'preserve submission reserve or invalid literal query'}
            return json.dumps(result, sort_keys=True)

        tools['search_similar_code'] = search_with_fallback
        return tools

    create_tools._backtrace_calibration = True
    context_type.create_tools = create_tools


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
         " from tools.task_calibration import install_search_fallback\n install_search_fallback(SwegemmaContext)\n"
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
