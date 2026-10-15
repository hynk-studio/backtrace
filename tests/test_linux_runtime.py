"""Offline lock boundaries; synthetic bytes are not official wheel validation."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import linux_runtime as runtime


class LinuxRuntimeTests(unittest.TestCase):
    def test_offline_child_blocks_direct_network_requests(self):
        result = subprocess.run(runtime.offline_child(
            runtime.sys.executable,
            "import socket; socket.create_connection(('127.0.0.1', 9))"),
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('offline qualification blocked network access', result.stderr)

    def test_real_manifest_inventory_and_frozen_torch(self):
        records = runtime.supplied_records()
        supplemental = 'torch==2.10.0+cu128 --hash=sha256:' + 'a' * 64 + '\n'
        complete, supplied = runtime.combined_lock(supplemental, records)
        self.assertEqual(len(supplied.splitlines()), 41)
        self.assertEqual(len(complete.splitlines()), 42)
        self.assertIn('vllm==0.19.1', complete)
        with self.assertRaisesRegex(ValueError, 'torch'):
            runtime.combined_lock('', records)

    def test_no_repin_urls_unpinned_or_duplicate_dependencies(self):
        records = runtime.supplied_records()
        for text in ('vllm==0.19.2 --hash=sha256:' + 'a' * 64,
                     'torch==2.10.0', '--index-url=https://example.test',
                     'torch @ https://example.test/wheel.whl',
                     ('torch==2.10.0+cu128 --hash=sha256:' + 'a' * 64 + '\n') * 2):
            with self.subTest(text=text), self.assertRaises(ValueError):
                runtime.combined_lock(text, records)

    def test_changed_or_missing_bytes_fail_before_install(self):
        with tempfile.TemporaryDirectory() as directory:
            wheels = Path(directory)
            data = b'authored wheel identity fixture'
            record = dict(path='fixture-1.0-py3-none-any.whl', bytes=len(data),
                          sha256=hashlib.sha256(data).hexdigest())
            with self.assertRaisesRegex(ValueError, 'missing pinned wheel'):
                runtime.verify_supplied(wheels, [record])
            (wheels / record['path']).write_bytes(data)
            runtime.verify_supplied(wheels, [record])
            (wheels / record['path']).write_bytes(b'x' * len(data))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                runtime.verify_supplied(wheels, [record])

    def test_missing_actual_wheels_leave_no_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(runtime.platform, 'system', return_value='Linux'), \
                    patch.object(runtime.platform, 'machine', return_value='x86_64'), \
                    patch.object(runtime.sys, 'version_info', (3, 12)), \
                    patch.object(runtime.subprocess, 'run') as install:
                with self.assertRaisesRegex(ValueError, 'missing pinned wheel'):
                    runtime.qualify(root, root / 'absent.lock', root / 'output')
                install.assert_not_called()
            self.assertFalse((root / 'output').exists())

    @unittest.skipUnless(runtime.platform.system() == 'Linux' and
                         runtime.platform.machine() == 'x86_64' and
                         runtime.sys.version_info[:2] == (3, 12),
                         'real offline pip probe requires Linux CPython 3.12')
    def test_real_offline_resolver_failure_rolls_back_environment(self):
        # Exercise actual venv/pip subprocesses, not a mocked resolver. The
        # intentionally absent dependency must fail despite any host packages.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / 'backtrace_fixture-1.0-py3-none-any.whl'
            with zipfile.ZipFile(wheel, 'w') as archive:
                prefix = 'backtrace_fixture-1.0.dist-info/'
                archive.writestr(prefix + 'METADATA',
                                 'Metadata-Version: 2.1\nName: backtrace-fixture\n'
                                 'Version: 1.0\nRequires-Dist: absent-backtrace-dependency==1.0\n')
                archive.writestr(prefix + 'WHEEL',
                                 'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
                archive.writestr(prefix + 'RECORD', '')
            record = dict(path=wheel.name, bytes=wheel.stat().st_size,
                          sha256=hashlib.sha256(wheel.read_bytes()).hexdigest())
            lock = root / 'supplemental.lock'
            lock.write_text('')
            with patch.object(runtime, 'supplied_records', return_value=[record]), \
                    patch.object(runtime, 'REQUIRED', {'backtrace-fixture': '1.0'}):
                with self.assertRaises(subprocess.CalledProcessError):
                    runtime.qualify(root, lock, root / 'output')
            self.assertFalse((root / 'output').exists())
