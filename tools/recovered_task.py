"""Integrity and diagnostic analysis of one immutable, incomplete GPU task.

No model calls, evaluator answers, paid operations, or success promotion.
"""
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

NAMES = ('agent.patch', 'task-result.json', 'wire.jsonl',
         'results/traces/trace_fastapi_11194.json', 'execution.log', 'server.log')
MAX_BYTES = 1024**2


def verify(root, manifest):
    root = Path(root).absolute()
    if (set(manifest['files']) != set(NAMES)
            or manifest['paid_source_sha'] != '626e3a619a025f64e3713af11b8e4097471470ab'
            or manifest['paid_run_id'] != 39878045521
            or manifest['pod_id'] != 'virbb2jab7fi8v'):
        raise ValueError('exact consumed GPU task binding required')
    for name, row in manifest['files'].items():
        path = root / name
        if (path.is_symlink() or not path.is_file() or path.resolve() != path
                or path.stat().st_size != row['bytes'] or row['bytes'] > MAX_BYTES
                or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']):
            raise ValueError('recovered task evidence differs: ' + name)


def restore(data, root, manifest):
    if len(data) > MAX_BYTES:
        raise ValueError('recovered archive bound exceeded')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        rows = archive.infolist()
        if (len(rows) != len(NAMES) or {x.filename for x in rows} != set(NAMES)
                or any(x.is_dir() or (x.external_attr >> 16) & 0o170000 == 0o120000
                       or x.file_size != manifest['files'][x.filename]['bytes'] for x in rows)):
            raise ValueError('exact recovered archive members required')
        bodies = {x.filename: archive.read(x) for x in rows}
    for name, body in bodies.items():
        if hashlib.sha256(body).hexdigest() != manifest['files'][name]['sha256']:
            raise ValueError('archive member hash mismatch')
    root = Path(root); root.mkdir(mode=0o700)
    for name, body in bodies.items():
        path = root / name; path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(body)
    verify(root, manifest)


def analyze(root, manifest):
    verify(root, manifest)
    root = Path(root)
    task = json.loads((root / 'task-result.json').read_text())
    patch = (root / 'agent.patch').read_bytes()
    if (task.get('instance_id') != 'fastapi_11194'
            or task.get('agent_error') != 'Agent exceeded session timeout (1.0 min)'
            or task.get('patch_sha256') != hashlib.sha256(patch).hexdigest()
            or task.get('patch_bytes') != len(patch)
            or task.get('tool_calls') != 10 or task.get('llm_calls') != 10):
        raise ValueError('original incomplete task status must remain intact')
    wire = [json.loads(x) for x in (root / 'wire.jsonl').read_text().splitlines()]
    requests = [x for x in wire if x.get('event') == 'request']
    responses = [x for x in wire if x.get('event') == 'response']
    if (len(requests) != 11 or len(responses) != 10 or len(wire) != 21
            or [x['request_sha256'] for x in requests[:-1]] !=
               [x['request_sha256'] for x in responses]
            or any(x.get('status') != 200 for x in responses)):
        raise ValueError('original model HTTP evidence is incomplete in an unexpected way')
    trace = json.loads((root / NAMES[3]).read_text())
    tools = []
    for step in trace['steps']:
        for call in step.get('tool_calls', []):
            observation = step.get('observation', {})
            content = observation.get('content', '')
            try:
                value = json.loads(content)
            except (ValueError, TypeError):
                value = {}
            row = {'tool': call['function_name'],
                   'elapsed_seconds': call.get('extra', {}).get('elapsed_s'),
                   'status': value.get('status')}
            if call['function_name'] == 'search_similar_code':
                row.update(query=call.get('arguments', {}).get('query'), count=value.get('count'))
            tools.append(row)
    changed = re.findall(r'^\+\+\+ b/(.+)$', patch.decode(), flags=re.MULTILINE)
    return {'status': 'ANALYZED_INCOMPLETE_TASK', 'task_result': task,
            'wire_requests': len(requests), 'successful_responses': len(responses),
            'unpaired_request_count': 1, 'trace_tool_events': tools,
            'changed_files': changed,
            'patch_scope': 'reproduction scripts only' if changed and all(
                re.fullmatch(r'reproduce_issue(?:_v2)?\.py', x) for x in changed) else 'inspect separately',
            'completed_agent_task': False, 'patch_correctness': 'NOT RUN',
            'counterfactual_success_after_more_budget': 'NOT ESTABLISHED',
            'model_or_provider_calls': 0}
