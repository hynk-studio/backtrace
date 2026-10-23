"""Validate protocol-bound artifacts; process exit alone is not task completion."""
import hashlib
import json
import math
from pathlib import Path

TASK = 'fastapi_11194'
TRACE = 'results/traces/trace_' + TASK + '.json'


def read(root, name, limit):
    path = root / name
    if (path.is_symlink() or not path.is_file() or path.resolve() != path.absolute()
            or path.stat().st_size > limit):
        raise ValueError('missing or invalid task artifact: ' + name)
    return path.read_bytes()


LEGACY_PROTOCOL = 'R0-clean-v2-one-public-task/A10080-TP1'


def validate(root, *, protocol=LEGACY_PROTOCOL):
    root = Path(root).absolute()
    result = json.loads(read(root, 'task-result.json', 64 * 1024))
    patch = read(root, 'agent.patch', 64 * 1024**2)
    wire = [json.loads(line) for line in read(root, 'wire.jsonl', 16 * 1024**2).splitlines() if line]
    trace = json.loads(read(root, TRACE, 64 * 1024**2))
    tools = 10
    if protocol != LEGACY_PROTOCOL:
        from tools.task_calibration import PROTOCOL as R1
        from tools.task_verification import PROTOCOL as R1_REVISED
        if (protocol not in (R1, R1_REVISED) or not isinstance(trace, dict) or result.get('protocol') != protocol
                or result.get('budget') != {'session_seconds': 300, 'tool_calls': 30, 'llm_calls': 50}
                or result.get('patch_submitted') is not True or not patch
                or type(result.get('seconds')) not in (int, float) or not 0 <= result['seconds'] <= 330
                or not any(_submitted(step) for step in trace.get('steps', []))):
            raise ValueError('calibrated task requires explicit budget, trace and patch submission')
        tools = 30
    if (result.get('instance_id') != TASK or result.get('agent_error') not in (None, '')
            or type(result.get('llm_calls')) is not int or not 0 < result['llm_calls'] <= 50
            or type(result.get('tool_calls')) is not int or not 0 <= result['tool_calls'] <= tools
            or type(result.get('seconds')) not in (int, float)
            or not math.isfinite(result['seconds']) or result['seconds'] < 0
            or result.get('patch_bytes') != len(patch)
            or result.get('patch_sha256') != hashlib.sha256(patch).hexdigest()):
        raise ValueError('task did not complete successfully within its expected budget or its artifacts disagree')
    requests = [row for row in wire if row.get('event') == 'request']
    responses = [row for row in wire if row.get('event') == 'response']
    if (not requests or len(requests) != len(responses) or len(wire) != len(requests) * 2
            or len(requests) < result['llm_calls'] or len(requests) > 50
            or any(r.get('path') != '/v1/chat/completions' for r in requests)
            or [r.get('request_sha256') for r in requests] != [r.get('request_sha256') for r in responses]
            or any(r.get('status') != 200 for r in responses)
            or not isinstance(trace, dict) or not str(trace.get('schema_version', '')).startswith('ATIF')
            or not trace.get('steps')):
        raise ValueError('actual model requests, responses or trace are incomplete')
    report = {'status': 'PASS', 'instance_id': TASK, 'llm_calls': result['llm_calls'],
            'wire_requests': len(requests), 'tool_calls': result['tool_calls'],
            'patch_bytes': len(patch), 'patch_sha256': result['patch_sha256'],
            'trace_sha256': hashlib.sha256(read(root, TRACE, 64 * 1024**2)).hexdigest(),
            'verification': 'NOT RUN; task completion is not patch correctness'}
    if protocol != LEGACY_PROTOCOL:
        from tools.task_trace_review import review
        report['trace_review'] = review(trace)
    return report


def _submitted(value):
    """ATIF versions nest tool calls differently; require a named invocation."""
    if isinstance(value, dict):
        return ((value.get('function_name') == 'submit_patch' or value.get('name') == 'submit_patch')
                or any(_submitted(v) for k, v in value.items() if k not in ('message', 'content')))
    return isinstance(value, list) and any(_submitted(v) for v in value)
