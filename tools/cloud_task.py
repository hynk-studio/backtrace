"""Explicit cloud-policy preparation of the retained, private A100 driver.

Only allocation-inclusive deadlines and the matching permit policy change.
The consumed legacy driver and its default permit remain on their old limits.
"""
import ast
import difflib
import hashlib
import json
from pathlib import Path

from tools import a100_task as legacy
from tools.a100_delivery import DRIVER_SHA256 as LEGACY_PREPARED_SHA256
from tools.private_delivery import digest, parse_manifest, verify

POLICY = 'prepaid10-actions-v1'
SETUP, USEFUL, TOTAL = 5400, 6900, 7200
CLOUD_DRIVER_SHA256 = '458f18446f1e988822f8cd43b772d40f4a01ed0b0bd240cd1b3cab5224c4f54d'


def transform(data):
    original = legacy.transform(data)
    if hashlib.sha256(original.encode()).hexdigest() != LEGACY_PREPARED_SHA256:
        raise ValueError('legacy prepared driver changed')
    changes = (
        ('setup_deadline=min(start+1200,requested_at+1200)',
         'setup_deadline=min(start+5400,requested_at+5400)'),
        ('useful_deadline=min(start+2700,requested_at+2700)',
         'useful_deadline=min(start+6900,requested_at+6900)'),
        ('provider_expiry_seconds=3000', 'provider_expiry_seconds=7200'),
        ("consume_permit('/root/backtrace/launch-permit.json',Path(__file__))",
         "consume_permit('/root/backtrace/launch-permit.json',Path(__file__),policy='prepaid10-actions-v1',setup_seconds=5400)"),
    )
    result = original
    for before, after in changes:
        result = legacy._replace(result, before, after)
    # Every top-level definition except main is identical, including actual
    # server construction, task budget, prompts, model, isolation and cleanup.
    def frozen(source):
        return [ast.dump(node) for node in ast.parse(source).body
                if not isinstance(node, ast.If)
                and not (isinstance(node, ast.FunctionDef) and node.name == 'main')]
    if frozen(original) != frozen(result):
        raise ValueError('non-policy driver definition changed')
    # Deliberate operational corrections, applied only after the old policy-only
    # derivative is reproduced. The historical driver and paid heads stay intact.
    result = legacy._replace(result,
        " env.update(OFFICIAL_ENV)\n return env\n",
        " env.update(OFFICIAL_ENV)\n env['VLLM_SERVER_DEV_MODE']='1'\n return env\n")
    before = ("  with urllib.request.urlopen('http://127.0.0.1:8000/server_info?config_format=json',timeout=10) as response: info=json.load(response)\n"
              "  with urllib.request.urlopen('http://127.0.0.1:8000/v1/models',timeout=10) as response: models=json.load(response)\n")
    result = legacy._replace(result, before,
        "  from tools.serving_contract import inspect_server\n"
        "  info,models=inspect_server(server.base_url,MODEL)\n")
    result = legacy._replace(result,
        "'request_sha256':hashlib.sha256(request.content).hexdigest()}",
        "'request_sha256':hashlib.sha256(request.content).hexdigest(),'event':'request'}")
    result = legacy._replace(result,
        "  if request.url.path.endswith('/chat/completions'): event('model_http_response',status=result.status_code)\n",
        "  if request.url.path.endswith('/chat/completions'):\n"
        "   with wire.open('a') as stream: stream.write(json.dumps({'event':'response','status':result.status_code,'request_sha256':hashlib.sha256(request.content).hexdigest()},sort_keys=True)+'\\n')\n"
        "   event('model_http_response',status=result.status_code)\n")
    result = legacy._replace(result, "  event('task_end',**result)\n",
        "  event('task_end',**result)\n"
        "  from tools.task_results import validate\n"
        "  validate(WORK)\n")
    # Prompt, task/answer separation, sampling, model and budgets are still the
    # byte-pinned definitions. Changed functions are only the named operations.
    def definitions(source):
        return {n.targets[0].id: ast.dump(n) for n in ast.parse(source).body
                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
    if definitions(original) != definitions(result):
        raise ValueError('scientific input or driver constant changed')
    compile(result, '<private-cloud-driver>', 'exec')
    return result


def prepare(source, output):
    source, output = Path(source), Path(output)
    result = transform(source.read_bytes())
    if hashlib.sha256(result.encode()).hexdigest() != CLOUD_DRIVER_SHA256:
        raise ValueError('cloud driver differs from qualified bytes')
    receipt = legacy.prepare(source, output)
    (output / 'one_task.py').write_text(result)
    (output / 'driver.diff').write_text(''.join(difflib.unified_diff(
        source.read_text().splitlines(True), result.splitlines(True),
        fromfile='retained-t4/one_task.py', tofile='cloud-a100/one_task.py')))
    receipt.update(prepared_driver_sha256=CLOUD_DRIVER_SHA256, policy=POLICY,
                   setup_seconds=SETUP, useful_seconds=USEFUL, total_seconds=TOTAL,
                   server_and_agent_ast_equal_to_legacy=False,
                   operational_changes=['loopback developer metadata route', 'shared real HTTP contract',
                                        'model response receipts', 'task artifact validation'])
    receipt['files'] = {str(path.relative_to(output)): digest(path)
                        for path in sorted(output.rglob('*'))
                        if path.is_file() and path.name != 'prepare-receipt.json'}
    (output / 'prepare-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def manifest(prepared):
    prepared = Path(prepared)
    if digest(prepared / 'one_task.py') != CLOUD_DRIVER_SHA256:
        raise ValueError('private cloud driver changed')
    references = {'one_task.py': prepared / 'one_task.py',
                  'startup_guard.py': legacy.ROOT / 'tools/startup_guard.py'}
    references.update({'tools/' + name: legacy.ROOT / 'tools' / name for name in legacy.POD_TOOLS})
    references.update({'docs/' + name: legacy.ROOT / 'docs' / name for name in legacy.POD_DOCS})
    value = {'schema_version': 1, 'phase': 'bootstrap', 'files': [
        {'path': name, 'bytes': path.stat().st_size, 'sha256': digest(path)}
        for name, path in sorted(references.items())]}
    data = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    parse_manifest(data)
    verify(prepared, data)
    return data
