"""Explicit cloud-policy preparation of the retained, private A100 driver.

First reproduce the historical operational derivative, then apply the explicit
five-minute/search calibration. Historical inputs and paid heads stay immutable.
"""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import shutil

from tools import a100_task as legacy
from tools.a100_delivery import DRIVER_SHA256 as LEGACY_PREPARED_SHA256
from tools.private_delivery import digest, parse_manifest, verify
from tools import task_calibration

POLICY = 'prepaid10-actions-v1'
SETUP, USEFUL, TOTAL = 5400, 6900, 7200
CLOUD_DRIVER_SHA256 = 'eca5e2ee5065419272e99f8407d09e63798801640f2a8005e5189e7aba9f1b79'
RUN_NAME = task_calibration.PROTOCOL
POD_TOOLS = legacy.POD_TOOLS + ('task_budget.py', 'task_calibration.py')
POD_DOCS = legacy.POD_DOCS


def preserve_finally(source, function):
    """Retain a phase failure even when its finalizer raises a second error."""
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == function)
    finalizers = [n for n in node.body if isinstance(n, ast.Try) and n.finalbody]
    if len(finalizers) != 1:
        raise ValueError('one outer finalizer required in ' + function)
    body = finalizers[0].finalbody
    lines = source.splitlines(keepends=True)
    start, end = body[0].lineno - 1, body[-1].end_lineno
    old = lines[start:end]
    indent = ' ' * body[0].col_offset
    new = [indent + 'phase_failure=sys.exc_info()[1]\n', indent + 'try:\n']
    new += [' ' + line if line.strip() else line for line in old]
    new += [indent + 'except BaseException as cleanup_failure:\n',
            indent + ' if phase_failure is None: raise\n',
            indent + " phase_failure.add_note('Separate cleanup failure: '+type(cleanup_failure).__name__)\n",
            indent + ' raise phase_failure\n']
    return ''.join(lines[:start] + new + lines[end:])


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
        " env.update(OFFICIAL_ENV)\n env['PYTHONPATH']=str(CODE)\n return env\n")
    # The official context accepts string directories and its graph loaders call
    # str.endswith. Preserve the same pinned paths at that API boundary.
    result = legacy._replace(result,
        "graph_dir=ns['GRAPH_DIR'],embeddings_dir=ns['EMBEDDINGS_DIR']",
        "graph_dir=str(ns['GRAPH_DIR']),embeddings_dir=str(ns['EMBEDDINGS_DIR'])")
    result = legacy._replace(result,
        " server=ns['server_instance'];assert not ns['adapters'].adapters\n",
        " server=ns['server_instance'];assert not ns['adapters'].adapters\n"
        " from tools.runtime_config import MIDDLEWARE\n"
        " server.config.extra_args += ['--middleware',MIDDLEWARE]\n")
    result = legacy._replace(result,
        " assert ns['vllm_cfg'].extra_args==['--disable-custom-all-reduce']\n",
        " assert ns['vllm_cfg'].extra_args==['--disable-custom-all-reduce','--middleware',MIDDLEWARE]\n")
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
    result = legacy._replace(result, "  manager.close();httpx.AsyncClient.send=original\n",
        "  try: manager.close()\n  finally: httpx.AsyncClient.send=original\n")
    result = legacy._replace(result,
        "  if Path(server.log_path).is_file(): shutil.copyfile(server.log_path,WORK/'server.log')\n  server.stop()\n",
        "  try:\n   if Path(server.log_path).is_file(): shutil.copyfile(server.log_path,WORK/'server.log')\n"
        "  finally: server.stop()\n")
    for function in ('server_phase', 'agent_phase', 'main'):
        result = preserve_finally(result, function)
    # Prompt, task/answer separation, sampling, model and budgets are still the
    # byte-pinned definitions. Changed functions are only the named operations.
    def definitions(source):
        return {n.targets[0].id: ast.dump(n) for n in ast.parse(source).body
                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
    if definitions(original) != definitions(result):
        raise ValueError('scientific input or driver constant changed')
    compile(result, '<private-cloud-driver>', 'exec')
    return task_calibration.driver_source(result)


def prepare(source, output):
    source, output = Path(source), Path(output)
    result = transform(source.read_bytes())
    if hashlib.sha256(result.encode()).hexdigest() != CLOUD_DRIVER_SHA256:
        raise ValueError('cloud driver differs from qualified bytes')
    receipt = legacy.prepare(source, output)
    for name in set(POD_TOOLS) - set(legacy.POD_TOOLS):
        shutil.copyfile(legacy.ROOT / 'tools' / name, output / 'tools' / name)
    (output / 'one_task.py').write_text(result)
    (output / 'driver.diff').write_text(''.join(difflib.unified_diff(
        source.read_text().splitlines(True), result.splitlines(True),
        fromfile='retained-t4/one_task.py', tofile='cloud-a100/one_task.py')))
    receipt.update(prepared_driver_sha256=CLOUD_DRIVER_SHA256, policy=POLICY,
                   protocol=RUN_NAME, task_budget=task_calibration.BUDGET,
                   scientific_changes=['five-minute/30-tool budget', 'generic search/completion guidance',
                                       'bare-symbol/text-search guidance; official tools unchanged'],
                   setup_seconds=SETUP, useful_seconds=USEFUL, total_seconds=TOTAL,
                   server_and_agent_ast_equal_to_legacy=False,
                   operational_changes=['narrow initialized-engine metadata middleware', 'shared real HTTP contract',
                                        'model response receipts', 'task artifact validation',
                                        'string paths at official graph context boundary'])
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
    references.update({'tools/' + name: legacy.ROOT / 'tools' / name for name in POD_TOOLS})
    references.update({'docs/' + name: legacy.ROOT / 'docs' / name for name in POD_DOCS})
    value = {'schema_version': 1, 'phase': 'bootstrap', 'files': [
        {'path': name, 'bytes': path.stat().st_size, 'sha256': digest(path)}
        for name, path in sorted(references.items())]}
    data = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    parse_manifest(data)
    verify(prepared, data)
    return data
