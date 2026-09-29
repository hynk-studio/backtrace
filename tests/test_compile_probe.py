"""CPU probe process boundaries; no official validation claimed by these mocks."""
import json
import os
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import compile_probe as probe
from tools.backtrace import InspectionError


class ProcessBoundaryTests(unittest.TestCase):
    def test_network_and_process_operations_fail_without_echoing_arguments(self):
        guard = probe.NoExecution()
        for event, args in [('socket.connect', ('private-address',)),
                            ('socket.getaddrinfo', ('private-host',)),
                            ('socket.__new__', (None, socket.AF_INET, 1, 0)),
                            ('socket.__new__', (None, socket.AF_INET6, 1, 0)),
                            ('subprocess.Popen', ('private-command',)), ('os.system', ())]:
            with self.subTest(event=event), self.assertRaises(InspectionError) as error:
                guard.audit(event, args)
            self.assertNotIn('private', str(error.exception))
        with self.assertRaises(InspectionError):
            guard.assert_unused()

    def test_sanitized_isolated_child_and_cleanup(self):
        seen = []
        def child(command, **kwargs):
            seen.append(kwargs['cwd'])
            self.assertTrue(kwargs['cwd'].is_dir())
            self.assertIn('-I', command)
            self.assertIn('-B', command)
            self.assertEqual(kwargs['timeout'], 45)
            self.assertEqual(kwargs['env']['PYTHON_DOTENV_DISABLED'], '1')
            self.assertEqual(kwargs['env']['TMPDIR'], str(kwargs['cwd']))
            self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
            self.assertNotIn('KAGGLE_API_TOKEN', kwargs['env'])
            return subprocess.CompletedProcess(command, 0, json.dumps({'construction': 'MOCK ONLY'}), '')
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-do-not-forward',
                                     'KAGGLE_API_TOKEN': 'synthetic-do-not-forward'}), \
                patch.object(probe.subprocess, 'run', side_effect=child):
            result = probe.run_probe('synthetic-input', 'synthetic.zip', sys.executable)
        self.assertEqual(result['construction'], 'MOCK ONLY')
        self.assertFalse(seen[0].exists())

    def test_timeout_and_failed_worker_cleanup(self):
        for mode in ('timeout', 'failure'):
            seen = []
            def child(command, **kwargs):
                seen.append(kwargs['cwd'])
                (kwargs['cwd'] / 'temporary.log').write_text('synthetic')
                if mode == 'timeout':
                    raise subprocess.TimeoutExpired(command, kwargs['timeout'])
                return subprocess.CompletedProcess(command, 2, '{"error":"synthetic failure"}',
                                                   'do-not-relay-dependency-log')
            with self.subTest(mode=mode), patch.object(probe.subprocess, 'run', side_effect=child):
                with self.assertRaises(InspectionError) as error:
                    probe.run_probe('synthetic-input', 'synthetic.zip', sys.executable)
                self.assertNotIn('do-not-relay', str(error.exception))
                self.assertFalse(seen[0].exists())

    def test_missing_cli_environment_fails(self):
        result = subprocess.run([sys.executable, '-B', str(Path(probe.__file__).resolve()),
                                 'missing', 'missing.zip'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertIn('provide --official-python', result.stderr)


if __name__ == '__main__':
    unittest.main()
