"""Private A100 driver construction against the real wrapper; no model start.

Requires the qualified private CPython 3.12 venv and retained artifacts. CUDA
identity and post-start replies are injected. Actual construction and response
handling execute; spies and the process/network audit reject real execution.
"""
import ast
import contextlib
import hashlib
import importlib.util
import io
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import subprocess
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.a100_task import prepare
from tools.a100_driver import qualify_hardware
from tools.compile_probe import FROZEN_SHA256, NoExecution
from tools.official_check import check_installed_wheels
from tools.r0 import expected_candidate, inspect_candidate


def server_boundaries(function, namespace, vllm_server):
    """Run the actual post-start code with explicitly authored boundary replies.

    Real GPU startup, HTTP and task-process entry are replaced by spies; all
    response handling, registry setup, assertions, logging and teardown execute.
    The process/network audit remains active throughout.
    """
    stop = next(i for i, n in enumerate(function.body) if isinstance(n, ast.Try))
    tail = compile(ast.Module(body=function.body[stop:], type_ignores=[]),
                   '<actual-private-post-start>', 'exec')
    cases = []
    for case in ('ready', 'agent_exit', 'agent_timeout', 'startup_failure',
                 'wrong_dtype', 'wrong_model', 'wrong_tp'):
        server = namespace['server']
        # The real GuardedServer can start only once. A fresh real wrapper is
        # constructed with the identical frozen config for each authored case.
        namespace = dict(namespace, server=type(server)(
            server.config, adapter_manifest=namespace['ns']['adapters']))
        server = namespace['server']
        namespace['ns'] = dict(namespace['ns'], server_instance=server)
        info = {'vllm_config': {
            'model_config': {'dtype': 'float16' if case == 'wrong_dtype' else 'bfloat16'},
            'parallel_config': {'disable_custom_all_reduce': True,
                                'tensor_parallel_size': 2 if case == 'wrong_tp' else 1}}}
        models = {'data': [{'id': 'wrong-model' if case == 'wrong_model' else str(namespace['MODEL'])}]}
        responses = [io.BytesIO(json.dumps(row).encode()) for row in (info, models)]
        outcome = subprocess.CompletedProcess(['authored-agent-boundary'], 7 if case == 'agent_exit' else 0)
        caught = None
        with patch.object(vllm_server, 'start', side_effect=(
                RuntimeError('authored startup failure') if case == 'startup_failure' else None)) as start, \
                patch('tools.serving_contract.inspect_server', return_value=(info, models)), \
                patch('urllib.request.urlopen', side_effect=responses) as http, \
                patch.object(subprocess, 'run', side_effect=(
                    subprocess.TimeoutExpired('authored-agent-boundary', 180)
                    if case == 'agent_timeout' else None), return_value=outcome) as task, \
                patch.object(server, 'stop', wraps=server.stop) as teardown:
            try:
                exec(tail, namespace)
            except (AssertionError, RuntimeError, subprocess.TimeoutExpired) as error:
                caught = error
            start.assert_called_once_with()
            teardown.assert_called_once_with()
            if case == 'ready':
                assert caught is None
                task.assert_called_once()
                assert task.call_args.kwargs['timeout'] == (330 if namespace['RUN_NAME'].startswith('R1-') else 180)
            else:
                assert caught is not None, 'failed boundary was reported as success: ' + case
                if case in ('agent_exit', 'agent_timeout'):
                    task.assert_called_once()
                else:
                    task.assert_not_called()
            if case == 'startup_failure':
                http.assert_not_called()
            if case == 'agent_exit':
                assert isinstance(caught, RuntimeError) and str(caught) == 'agent child failed; see retained task log'
            assert server.process is None and server._closed
        Path(server.log_path).unlink(missing_ok=True)
        cases.append({'case': case, 'status': 'PASS', 'exception': type(caught).__name__ if caught else None})
    return cases


def agent_construction(driver):
    """Actual task-side setup and real runner signature, stopping before entry."""
    import httpx
    function = next(n for n in ast.parse(Path(driver.__file__).read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'agent_phase')
    stop = next(i for i, n in enumerate(function.body) if isinstance(n, ast.Try))
    namespace = dict(driver.__dict__)
    original = httpx.AsyncClient.send
    try:
        exec(compile(ast.Module(body=function.body[:stop], type_ignores=[]),
                     '<actual-private-agent-construction>', 'exec'), namespace)
        invocation = function.body[stop].body[0].value
        assert isinstance(invocation, ast.Call) and len(invocation.args) == 5
        evaluate = lambda node: eval(compile(ast.Expression(node), '<actual-runner-argument>', 'eval'), namespace)
        bound = inspect.signature(namespace['run_agent_sandbox']).bind(
            *map(evaluate, invocation.args[1:]),
            **{argument.arg: evaluate(argument.value) for argument in invocation.keywords})
        assert bound.arguments['context'] is namespace['context']
        assert namespace['context'].tool_calls_used == namespace['context'].llm_calls_used == 0
        assert namespace['snapshot'].is_file()
        assert namespace['task'].instance_id == 'fastapi_11194'
        assert namespace['config'].models is namespace['ns']['models']
        return {'status': 'PASS', 'runner_signature': 'ACTUAL', 'task_model_setup': 'ACTUAL',
                'runner_entry': 'NOT RUN', 'tool_calls': 0, 'llm_calls': 0}
    finally:
        httpx.AsyncClient.send = original
        if 'manager' in namespace:
            namespace['manager'].close()


def main():
    cloud = sys.argv[1:] == ['--cloud-policy']
    if sys.argv[1:] and not cloud:
        raise ValueError('unsupported qualification mode')
    prepare_driver = prepare
    if cloud:
        from tools.cloud_task import prepare as prepare_driver
    if sys.prefix == sys.base_prefix or any(k in os.environ for k in ('KAGGLE_API_TOKEN', 'RUNPOD_API_KEY', 'OPENAI_API_KEY')):
        raise RuntimeError('clean qualified private venv required')
    check_installed_wheels(ROOT / '.local/official')
    report, files = inspect_candidate(ROOT / '.local/r0-clean/build-a.zip',
                                      expected_candidate(ROOT / '.local/official'))
    assert report['sha256'] == FROZEN_SHA256
    if cloud:
        from tools.task_calibration import candidate_files
        files = candidate_files(files)
    from adk_submission import VllmServer
    import torch
    with tempfile.TemporaryDirectory(prefix='backtrace-a100-construct-') as directory:
        root = Path(directory)
        receipt = prepare_driver(ROOT / '.local/smoke/no-custom-ar/one_task.py', root / 'driver')
        spec = importlib.util.spec_from_file_location('prepared_private_driver', root / 'driver/one_task.py')
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)  # Definitions only; __main__ is not executed.
        driver.WORK = root / 'work'
        for name, data in files.items():
            target = driver.WORK / 'candidate' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        from tools.official_check import check_directory
        candidate_check = check_directory(driver.WORK / 'candidate', candidate=True)
        assert candidate_check['official_cpu_checks'] == 'PASS'
        function = next(n for n in ast.parse((root / 'driver/one_task.py').read_text()).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'server_phase')
        stop = next(i for i, n in enumerate(function.body) if isinstance(n, ast.Try))
        prefix = ast.Module(body=function.body[:stop], type_ignores=[])
        namespace = dict(driver.__dict__)
        # Keep the real event writer and hardware validator. The previous
        # fixture removed hardware.name and replaced event(), masking the
        # production keyword collision before server construction.
        namespace['check_gpu'] = lambda cuda: qualify_hardware(
            'NVIDIA A100 80GB PCIe, GPU-cpu-fixture, 81920, 595.91.07, Disabled\n',
            cuda, runtime_version='12.8.90')
        event_output = io.StringIO()
        guard = NoExecution()
        guard.install()
        boundaries = None
        agent_setup = None
        with patch.dict(os.environ, dict(driver.OFFICIAL_ENV, BACKTRACE_USEFUL_DEADLINE=str(time.time() + 2700),
                                        BACKTRACE_TOTAL_DEADLINE=str(time.time() + 3000))), \
                patch.object(torch.cuda, 'is_available', return_value=True), \
                patch.object(torch.cuda, 'device_count', return_value=1), \
                patch.object(torch.cuda, 'get_device_capability', return_value=(8, 0)), \
                patch.object(torch.cuda, 'get_device_name', return_value='NVIDIA A100-PCIE-80GB'), \
                patch.object(torch.cuda, 'is_bf16_supported', return_value=True) as bf16, \
                patch.object(VllmServer, 'start', side_effect=AssertionError('CPU check must not start')) as start, \
                contextlib.redirect_stdout(event_output):
            exec(compile(prefix, '<prepared-private-pre-start>', 'exec'), namespace)
            start.assert_not_called()
            assert all(call.kwargs == {'including_emulation': False} for call in bf16.call_args_list)
            # Keep the prefix's never-started wrapper for its separate checks.
            # The post-start cases construct their own wrapper instances.
            boundaries = server_boundaries(function, namespace, VllmServer)
            agent_setup = agent_construction(driver)
        guard.assert_unused()
        events = [json.loads(line.removeprefix('BACKTRACE '))
                  for line in event_output.getvalue().splitlines() if line.startswith('BACKTRACE ')]
        hardware_events = [row for row in events if row.get('event') == 'qualified_hardware']
        assert len(hardware_events) == 1
        assert hardware_events[0]['name'] == 'NVIDIA A100 80GB PCIe'
        assert hardware_events[0]['native_bf16'] is True and hardware_events[0]['tp'] == 1
        server = namespace['server']
        assert server.config.dtype == 'bfloat16' and server.config.tensor_parallel_size == 1
        assert server.config.max_model_len == 32768 and server.config.startup_timeout == 1200
        argv = server.build_cmd()
        assert type(server) is not VllmServer and isinstance(server, VllmServer)
        assert str(root / 'driver/startup_guard.py') in argv and argv.count('--exec') == 1
        # The observer is created only at start(); absence is required here.
        assert not hasattr(server, 'startup_observation')
        print(json.dumps({'actual_private_driver_sha256': receipt['prepared_driver_sha256'],
                          'policy': 'prepaid10-actions-v1' if cloud else 'prepaid10-external-v2',
                          'candidate_sha256': report['sha256'], 'actual_wrapper': 'adk-submission 0.2.11',
                          'candidate_protocol': driver.RUN_NAME, 'official_candidate_check': candidate_check,
                          'requested_dtype': server.config.dtype, 'tp': 1,
                          'argv': argv, 'guard_constructed': True,
                          'hardware': 'INJECTED', 'server_start': 'NOT RUN',
                          'actual_event_writer': 'PASS', 'hardware_name_preserved': True,
                          'post_start_boundaries': boundaries, 'agent_construction': agent_setup,
                          'boundary_replies': 'AUTHORED; GPU/HTTP/TASK ENTRY SPIED',
                          'task_execution': 'NOT RUN', 'denied_execution_attempts': guard.attempts}))


if __name__ == '__main__':
    main()
