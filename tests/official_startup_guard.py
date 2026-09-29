"""Actual pinned wrapper lifecycle; only the launched payload/env is a CPU fixture."""
import os
import ast
import hashlib
from pathlib import Path
import signal
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from tools.official_check import check_installed_wheels
from tools.guard_driver import prepare
from test_startup_guard import LifecycleCases


if __name__ == '__main__':
    if sys.prefix == sys.base_prefix or any(k in os.environ for k in ('OPENAI_API_KEY', 'KAGGLE_API_TOKEN', 'RUNPOD_API_KEY')):
        raise SystemExit('Use env -i with the pinned CPU venv')
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('CPU integration cap 60s')))
    signal.alarm(60)
    with tempfile.TemporaryDirectory(prefix='backtrace-official-startup-') as directory:
        os.chdir(directory)
        tempfile.tempdir = directory
        os.environ.update(HOME=directory, OTEL_SDK_DISABLED='true', PYTHON_DOTENV_DISABLED='1',
                          LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_TELEMETRY='False',
                          HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        # Allow ONLY loopback sockets and disposable process execution. No model imported.
        def audit(event, args):
            if event == 'socket.connect':
                address = args[1]
                if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', '::1'):
                    raise RuntimeError('CPU integration blocked non-loopback connection')
        sys.addaudithook(audit)
        check_installed_wheels(ROOT / '.local/official')
        from adk_submission import VllmConfig, VllmServer
        from adk_submission.errors import ServerStartupError

        class OfficialStartupTests(LifecycleCases, unittest.TestCase):
            lifecycle = VllmServer
            error_type = ServerStartupError
            boundary = 'REAL adk-submission 0.2.11 lifecycle/HTTP; INJECTED CPU payload/env; no vLLM/model'

            def configuration(self, port, directory):
                return VllmConfig(model='unused-cpu-fixture', port=port,
                                  startup_timeout=4)  # Preserve real 1s poll interval.

            def test_retained_driver_transform_reproducible_no_overwrite(self):
                source = ROOT / '.local/smoke/no-custom-ar/one_task.py'
                with tempfile.TemporaryDirectory() as temporary:
                    first, second = Path(temporary) / 'a', Path(temporary) / 'b'
                    self.assertEqual(prepare(source, first), prepare(source, second))
                    with self.assertRaises(FileExistsError):
                        prepare(source, first)
                    def constants(path):
                        return [ast.dump(node) for node in ast.parse(path.read_text()).body
                                if isinstance(node, ast.Assign)]
                    self.assertEqual(constants(source), constants(first / 'one_task.py'))
                    self.assertEqual((first / 'startup_guard.py').read_bytes(),
                                     (ROOT / 'tools/startup_guard.py').read_bytes())
                    print('private_driver_sha256=' + hashlib.sha256((first / 'one_task.py').read_bytes()).hexdigest())

        result = unittest.main(exit=False, verbosity=2).result
    signal.alarm(0)
    sys.exit(not result.wasSuccessful())
