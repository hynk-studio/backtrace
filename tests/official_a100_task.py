"""Private A100 driver construction against the real wrapper; no model start.

Requires the qualified private CPython 3.12 venv and retained artifacts. CUDA
identity is injected. Only the generated server function's pre-start statements
execute; a start spy and process/network audit independently reject execution.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.a100_task import prepare
from tools.compile_probe import FROZEN_SHA256, NoExecution
from tools.official_check import check_installed_wheels
from tools.r0 import expected_candidate, inspect_candidate


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
        function = next(n for n in ast.parse((root / 'driver/one_task.py').read_text()).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'server_phase')
        stop = next(i for i, n in enumerate(function.body) if isinstance(n, ast.Try))
        prefix = ast.Module(body=function.body[:stop], type_ignores=[])
        namespace = dict(driver.__dict__)
        namespace['check_gpu'] = lambda cuda: {'fixture': 'injected A100 SM80 / TP1 / BF16'}
        events = []
        namespace['event'] = lambda name, **fields: events.append(name)
        guard = NoExecution()
        guard.install()
        with patch.dict(os.environ, dict(driver.OFFICIAL_ENV, BACKTRACE_USEFUL_DEADLINE=str(time.time() + 2700))), \
                patch.object(torch.cuda, 'is_available', return_value=True), \
                patch.object(torch.cuda, 'device_count', return_value=1), \
                patch.object(torch.cuda, 'get_device_capability', return_value=(8, 0)), \
                patch.object(torch.cuda, 'get_device_name', return_value='NVIDIA A100-PCIE-80GB'), \
                patch.object(torch.cuda, 'is_bf16_supported', return_value=True) as bf16, \
                patch.object(VllmServer, 'start', side_effect=AssertionError('CPU check must not start')) as start:
            exec(compile(prefix, '<prepared-private-pre-start>', 'exec'), namespace)
            start.assert_not_called()
            assert all(call.kwargs == {'including_emulation': False} for call in bf16.call_args_list)
        guard.assert_unused()
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
                          'requested_dtype': server.config.dtype, 'tp': 1,
                          'argv': argv, 'guard_constructed': True,
                          'hardware': 'INJECTED', 'server_start': 'NOT RUN',
                          'task_execution': 'NOT RUN', 'denied_execution_attempts': guard.attempts}))


if __name__ == '__main__':
    main()
