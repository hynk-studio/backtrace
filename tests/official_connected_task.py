"""Run the prepared driver through real HTTP, official task/tools and recovery.

GPU identity/start and the chat generation handler are CPU fixtures. Metadata
routes, chat request/response schemas, middleware, registry, official runner,
task snapshot, sandbox, tools, trace, patch, artifact validation and byte transfer
execute. This is plumbing evidence, never a model result or task score.
"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(path):
    spec = importlib.util.spec_from_file_location('connected_driver', path)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    return driver


def child():
    from unittest.mock import patch
    driver = load(Path(__file__).with_name('one_task.py'))
    import torch
    from adk_submission import VllmServer
    from tools.a100_driver import qualify_hardware
    if os.getuid() != 65534:
        raise ValueError('actual workload UID required')

    def start(server):
        if not server.is_healthy():
            raise RuntimeError('actual CPU HTTP health is not ready')
        return server

    with patch.object(torch.cuda, 'is_available', return_value=True), \
            patch.object(torch.cuda, 'device_count', return_value=1), \
            patch.object(torch.cuda, 'get_device_capability', return_value=(8, 0)), \
            patch.object(torch.cuda, 'get_device_name', return_value='NVIDIA A100-PCIE-80GB'), \
            patch.object(torch.cuda, 'is_bf16_supported', return_value=True), \
            patch.object(driver, 'check_gpu', side_effect=lambda cuda: qualify_hardware(
                'NVIDIA A100 80GB PCIe, GPU-cpu-fixture, 81920, 595.91.07, Disabled\n',
                cuda, runtime_version='12.8.90')), \
            patch.object(VllmServer, 'start', new=start):
        driver.server_phase()  # Complete function; no AST prefix/tail extraction.


class GeneratedTokens:
    """Deterministic content at the model boundary, without a reference answer."""
    def __init__(self, case):
        self.case, self.requests = case, []

    async def create_chat_completion(self, request, raw):
        from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionResponse
        from vllm.entrypoints.openai.engine.protocol import ErrorResponse
        data = await raw.json()
        self.requests.append(data)
        if self.case == 'model-error':
            return ErrorResponse.model_validate({'error': {'message': 'CPU negative model control',
                'type': 'BadRequestError', 'code': 400}})
        number = len(self.requests)
        names = {row['function']['name'] for row in data.get('tools', [])}
        if not {'run_command', 'submit_patch'}.issubset(names):
            raise AssertionError('real official tool schemas were not sent')
        if number == 1:
            command = ('python -c "from pathlib import Path; p=Path(\'README.md\'); '
                       'p.write_text(p.read_text()+\'\\nBacktrace CPU transport probe.\\n\'); '
                       'print(\'BACKTRACE_REAL_TOOL_EXECUTED\')"')
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                'id': 'call_cpu_command', 'type': 'function',
                'function': {'name': 'run_command', 'arguments': json.dumps({'command': command})}}]}
        elif number == 2:
            if 'BACKTRACE_REAL_TOOL_EXECUTED' not in json.dumps(data['messages']):
                raise AssertionError('real sandbox tool result did not reach the model client')
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                'id': 'call_cpu_submit', 'type': 'function',
                'function': {'name': 'submit_patch', 'arguments': '{}'}}]}
        elif number == 3:
            message = {'role': 'assistant', 'content': 'CPU plumbing probe completed.'}
        else:
            raise AssertionError('unexpected additional model request in deterministic probe')
        usage = {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}
        reason = 'tool_calls' if number < 3 else 'stop'
        body = {'id': 'chatcmpl-cpu-' + str(number), 'object': 'chat.completion',
                'created': int(time.time()), 'model': request.model,
                'choices': [{'index': 0, 'message': message, 'finish_reason': reason}], 'usage': usage}
        if not request.stream:
            return ChatCompletionResponse.model_validate(body)

        async def stream():
            delta = dict(message)
            if 'tool_calls' in delta:
                delta['tool_calls'] = [dict(row, index=i) for i, row in enumerate(delta['tool_calls'])]
            chunk = dict(body, object='chat.completion.chunk', choices=[
                {'index': 0, 'delta': delta, 'finish_reason': reason}])
            yield 'data: ' + json.dumps(chunk) + '\n\n'
            yield 'data: [DONE]\n\n'
        return stream()


def run_case(source, output, case):
    import uvicorn
    from tools.api_probe import build
    from tools.a100_task import inherit_runtime
    from tools.cloud_task import manifest
    from tools.pod_bootstrap import readonly
    from tools.private_delivery import emit, receive
    from tools.runpod_job import check_owner_host
    from tools.task_results import validate
    check_owner_host()
    manifest(source)
    driver = load(source / 'one_task.py')
    if driver.ROOT.exists():
        raise ValueError('fresh fixed driver scratch required')
    output.mkdir(mode=0o700, parents=True)
    os.umask(0o022)
    driver.ROOT.mkdir(mode=0o755)
    driver.CODE.mkdir(mode=0o755)
    driver.WORK.mkdir(mode=0o700)
    os.chown(driver.WORK, 65534, 65534)
    for folder in ('tmp', 'hf'):
        target = driver.WORK / folder
        target.mkdir(mode=0o700)
        os.chown(target, 65534, 65534)
    try:
        for name in ('one_task.py', 'startup_guard.py', 'tools', 'docs'):
            src, dst = source / name, driver.CODE / name
            shutil.copytree(src, dst) if src.is_dir() else shutil.copyfile(src, dst)
        shutil.copyfile(__file__, driver.CODE / 'connected_child.py')
        readonly(driver.CODE)
        data = driver.input_dir()
        with zipfile.ZipFile(data / 'r0-clean.zip') as archive:
            archive.extractall(driver.WORK / 'candidate')  # Previously manifest/hash checked.
        for target in [driver.WORK / 'candidate', *(driver.WORK / 'candidate').rglob('*')]:
            os.chown(target, 65534, 65534)
        subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(driver.VENV)],
                       check=True, timeout=30)
        inherit_runtime(driver.VENV)
        subprocess.run([str(driver.VENV / 'bin/python'), '-m', 'pip', 'install', '--no-index',
            '--no-deps', '--ignore-installed', *map(str, sorted((data / 'wheels').glob('*.whl')))],
            check=True, timeout=30, stdout=sys.stderr)
        app, engine = build('vllm')
        generated = GeneratedTokens(case)
        app.state.openai_serving_chat = generated
        sock = socket.socket()
        sock.bind(('127.0.0.1', 8000))
        server = uvicorn.Server(uvicorn.Config(app, lifespan='off', log_config=None,
            log_level='info', access_log=True, timeout_graceful_shutdown=2))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        try:
            thread.start()
            deadline = time.monotonic() + 10
            while not server.started:
                if not thread.is_alive() or time.monotonic() >= deadline:
                    raise RuntimeError('CPU HTTP fixture did not start')
                time.sleep(.02)
            env = driver.child_env()
            env['BACKTRACE_USEFUL_DEADLINE'] = str(time.time() + 300)
            env['VLLM_SERVER_DEV_MODE'] = os.environ['VLLM_SERVER_DEV_MODE']
            with (output / 'execution.log').open('wb') as log:
                command = ['setpriv', '--no-new-privs', '--bounding-set=-all', '--reuid=65534',
                    '--regid=65534', '--clear-groups', sys.executable, '-I',
                    str(driver.CODE / 'connected_child.py'), '--child']
                result = subprocess.run(command, cwd=driver.WORK, env=env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, timeout=240)
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            sock.close()
        if thread.is_alive():
            raise RuntimeError('CPU server did not stop')
        if case == 'missing-route':
            if (result.returncode == 0 or generated.requests
                    or b'HTTP Error 404' not in (output / 'execution.log').read_bytes()):
                raise AssertionError('actual retained driver missed the missing metadata route')
        elif case == 'model-error':
            task_result = json.loads((driver.WORK / 'task-result.json').read_text())
            wire = [json.loads(line) for line in (driver.WORK / 'wire.jsonl').read_text().splitlines()]
            if (result.returncode == 0 or not generated.requests or not task_result['agent_error']
                    or not any(row.get('event') == 'response' and row.get('status') == 400 for row in wire)):
                raise AssertionError('actual task/model error was reported as successful')
        else:
            if result.returncode != 0:
                raise RuntimeError('connected driver failed; see encrypted execution log')
            verified = validate(driver.WORK)
            if verified['wire_requests'] != 3 or b'Backtrace CPU transport probe.' not in (driver.WORK / 'agent.patch').read_bytes():
                raise AssertionError('real model/tool/patch path did not complete')
            rows = []
            for name in ('agent.patch', 'task-result.json', 'wire.jsonl',
                         'results/traces/trace_fastapi_11194.json'):
                path = driver.WORK / name
                rows.append({'path': name, 'bytes': path.stat().st_size,
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            transfer_manifest = json.dumps({'schema_version': 1, 'phase': 'task', 'files': rows}).encode()
            stream = io.BytesIO()
            emit(driver.WORK, transfer_manifest, stream)
            stream.seek(0)
            transfer = receive(output / 'retrieved', hashlib.sha256(transfer_manifest).hexdigest(), stream)
            if validate(output / 'retrieved') != verified:
                raise AssertionError('recovered task artifacts differ')
            # A missing result after otherwise valid byte transfer must fail.
            (output / 'retrieved/task-result.json').unlink()
            try:
                validate(output / 'retrieved')
            except ValueError:
                pass
            else:
                raise AssertionError('missing recovered result was accepted')
        for name in ('task-result.json', 'wire.jsonl', 'agent.patch'):
            if (driver.WORK / name).is_file():
                shutil.copyfile(driver.WORK / name, output / name)
        return {'case': case, 'status': 'PASS', 'driver_exit': result.returncode,
                'actual_model_http_requests': len(generated.requests), 'gpu_allocations': 0,
                'model_generation': 'SCRIPTED CPU CONTENT; NOT A MODEL RESULT'}
    finally:
        shutil.rmtree(driver.ROOT)


def main(source, output, evaluator):
    if any(k in os.environ for k in ('KAGGLE_API_TOKEN', 'RUNPOD_API_KEY', 'GITHUB_TOKEN', 'GH_STATE_TOKEN')):
        raise ValueError('connected task qualification must not inherit account credentials')
    reports = []
    # Check the actual OS boundary, not just an input-key allowlist.
    check = subprocess.run(['setpriv', '--no-new-privs', '--bounding-set=-all', '--reuid=65534',
        '--regid=65534', '--clear-groups', sys.executable, '-I', '-c',
        'import os,sys;raise SystemExit(1 if os.access(sys.argv[1],os.R_OK) else 0)', str(evaluator)],
        env={'PATH': '/usr/bin:/bin'}, check=True, timeout=10)
    for case in ('missing-route', 'success', 'model-error'):
        env = dict(os.environ, VLLM_SERVER_DEV_MODE='0' if case == 'missing-route' else '1')
        result = subprocess.run([sys.executable, '-I', __file__, '--case', str(source), str(output / case), case],
            env=env, check=True, stdout=subprocess.PIPE, timeout=300)
        reports.append(json.loads(result.stdout.splitlines()[-1]))
    from tools.qualify_evaluation import qualify
    evaluation = qualify(evaluator, Path('/kaggle/input/r0-inputs'), output / 'success/agent.patch',
                         output / 'evaluation')
    return {'status': 'PASS', 'cases': reports, 'gpu_allocations': 0, 'public_evaluation': evaluation,
            'evaluator_agent_access': 'DENIED by actual UID read check',
            'driver': 'entire actual server_phase and actual agent child',
            'http': 'installed vLLM routes/middleware/schemas, real loopback TCP',
            'task': 'actual official runner, selected snapshot, sandbox, tools, patch and ATIF trace',
            'recovery': 'actual manifest/hash transport and production artifact validator',
            'substitutions': ['GPU identity', 'GPU process start', 'chat generation handler with scripted content'],
            'not_established': ['GPU token generation', 'Gemma tool/reasoning parser', 'patch correctness']}


if __name__ == '__main__':
    if sys.argv[1:] == ['--child']:
        child()
    elif sys.argv[1:2] == ['--case']:
        print(json.dumps(run_case(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]), sort_keys=True))
    elif len(sys.argv) == 4:
        print(json.dumps(main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])), sort_keys=True))
    else:
        raise ValueError('prepared driver and private evidence directory required')
