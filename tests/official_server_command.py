"""Opt-in pinned-wrapper argv check; actual candidate/source, no server execution."""
import ast
from dataclasses import asdict
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compile_probe import FROZEN_SHA256, MODEL_PATH, NoExecution
from tools.native_dtype import NO_CUSTOM_AR, no_custom_ar_source, serving_sources
from tools.official_check import check_installed_wheels
from tools.r0 import expected_candidate, inspect_candidate
from tools.startup_guard import guarded_server


class OfficialServerCommandTests(unittest.TestCase):
    def test_actual_wrapper_command_adds_exactly_one_flag(self):
        from adk_submission import VllmConfig, VllmServer, discover_adapters
        _, native = serving_sources((ROOT / '.local/starter.ipynb').read_bytes())
        report, files = inspect_candidate(ROOT / '.local/r0-clean/build-a.zip',
                                          expected_candidate(ROOT / '.local/official'))
        self.assertEqual(report['sha256'], FROZEN_SHA256)
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / 'candidate'
            for name, data in files.items():
                target = sample / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            adapters = discover_adapters(sample)
            self.assertFalse(adapters.adapters)
            configurations, commands = [], []
            for source, tp, bf16 in ((native, 2, False), (no_custom_ar_source(native), 2, False),
                                     (no_custom_ar_source(native), 1, True)):
                assignments = [n for n in ast.parse(source).body if isinstance(n, ast.Assign)
                               and any(isinstance(t, ast.Name) and t.id == 'vllm_cfg'
                                       for t in n.targets)]
                self.assertEqual(len(assignments), 1)
                # Only the config expression executes. The CPU substitutes T4 capability
                # results/TP; the real pinned wrapper builds the actual argv.
                scope = dict(VllmConfig=VllmConfig, MODEL_PATH=Path(MODEL_PATH), tp_size=tp,
                             torch=SimpleNamespace(cuda=SimpleNamespace(
                                 is_available=lambda: True,
                                 is_bf16_supported=lambda **_: bf16)))
                config = eval(compile(ast.Expression(assignments[0].value),
                                      '<pinned-serving-config>', 'eval'), scope)
                configurations.append(asdict(config))
                server = VllmServer(config, adapter_manifest=adapters)
                try:
                    commands.append(server.build_cmd())
                    self.assertIsNone(server.process)
                    guarded = guarded_server(VllmServer, total_deadline=time.monotonic() + 1200)(
                        config, adapter_manifest=adapters)
                    try:
                        shim_command = guarded.build_cmd()
                        self.assertEqual(shim_command[5:], commands[-1])
                        self.assertEqual(shim_command[4], '--exec')
                    finally:
                        guarded.stop()
                        Path(guarded.log_path).unlink(missing_ok=True)
                finally:
                    server.stop()
                    Path(server.log_path).unlink(missing_ok=True)
            self.assertEqual(configurations[1].pop('extra_args'), [NO_CUSTOM_AR])
            self.assertEqual(configurations[0].pop('extra_args'), [])
            self.assertEqual(configurations[0], configurations[1])
            self.assertEqual(commands[1], commands[0] + [NO_CUSTOM_AR])
            self.assertEqual(commands[1].count(NO_CUSTOM_AR), 1)
            self.assertEqual(configurations[1]['dtype'], 'auto')
            self.assertEqual(configurations[1]['max_model_len'], 32768)
            self.assertEqual(configurations[1]['tensor_parallel_size'], 2)
            self.assertTrue(configurations[1]['enable_lora'])
            self.assertEqual(configurations[2].pop('extra_args'), [NO_CUSTOM_AR])
            expected_config = dict(configurations[1], dtype='bfloat16', tensor_parallel_size=1)
            self.assertEqual(configurations[2], expected_config)
            expected_cmd = list(commands[1])
            expected_cmd[expected_cmd.index('--dtype') + 1] = 'bfloat16'
            tp_index = expected_cmd.index('--tensor-parallel-size')
            del expected_cmd[tp_index:tp_index + 2]  # Pinned wrapper omits the default TP=1.
            self.assertEqual(commands[2], expected_cmd)
            print(json.dumps({'official_argv_check': 'PASS', 'argv': commands[1],
                              'a100_tp1_argv': commands[2],
                              'candidate_sha256': report['sha256'],
                              'boundary': 'injected T4/A100 capability and TP; no server/process request'}))


if __name__ == '__main__':
    if sys.prefix == sys.base_prefix or any(k in os.environ for k in
                                           ('OPENAI_API_KEY', 'KAGGLE_API_TOKEN')):
        raise SystemExit('Use env -i with the pinned CPU venv')
    def expired(*_):
        raise KeyboardInterrupt('official argv check exceeded 40 seconds')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(40)
    with tempfile.TemporaryDirectory(prefix='backtrace-server-command-') as temporary:
        os.chdir(temporary)
        tempfile.tempdir = temporary
        os.environ.update(OTEL_SDK_DISABLED='true', PYTHON_DOTENV_DISABLED='1',
                          LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_TELEMETRY='False',
                          HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        guard = NoExecution()
        guard.install()
        check_installed_wheels(ROOT / '.local/official')
        result = unittest.main(exit=False, verbosity=2).result
        guard.assert_unused()
    signal.alarm(0)
    sys.exit(not result.wasSuccessful())
