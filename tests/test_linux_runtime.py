"""Offline lock boundaries; synthetic bytes are not official wheel validation."""
import hashlib
import copy
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import linux_runtime as runtime


class LinuxRuntimeTests(unittest.TestCase):
    def copy_bootstrap(self, directory):
        # Reuse CPython's exact bundled wheel without downloading test inputs.
        try:
            import ensurepip
        except ImportError:
            self.skipTest('pinned bootstrap fixture is unavailable')
        source = Path(ensurepip.__file__).parent / '_bundled' / runtime.BOOTSTRAP['path']
        if not source.is_file():
            self.skipTest('tests require the pinned pip 25.0.1 wheel')
        shutil.copyfile(source, directory / source.name)
        runtime.verify_supplied(directory, [runtime.BOOTSTRAP])

    def test_offline_child_blocks_direct_network_requests(self):
        result = subprocess.run(runtime.offline_child(
            runtime.sys.executable,
            "import socket; socket.create_connection(('127.0.0.1', 9))"),
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('offline qualification blocked network access', result.stderr)

    def test_real_manifest_inventory_and_frozen_torch(self):
        original = runtime.supplied_records()
        records = runtime.runtime_records()
        before = {r['path'].split('-')[0]: r for r in original}
        after = {r['path'].split('-')[0]: r for r in records}
        changed = {runtime.normalized(name) for name in before if before[name] != after[name]}
        self.assertEqual(changed, set(runtime.APPROVED_REPLACEMENTS))
        self.assertEqual(runtime.supplied_records(), original)
        supplemental = 'torch==2.10.0+cu128 --hash=sha256:' + 'a' * 64 + '\n'
        complete, supplied = runtime.combined_lock(supplemental, records)
        self.assertEqual(len(supplied.splitlines()), 41)
        self.assertEqual(len(complete.splitlines()), 42)
        self.assertIn('vllm==0.19.1', complete)
        for name, version in runtime.APPROVED_REPLACEMENTS.items():
            self.assertIn(f'{name}=={version} --hash=sha256:', supplied)
        with self.assertRaisesRegex(ValueError, 'torch'):
            runtime.combined_lock('', records)

    def test_no_repin_urls_unpinned_or_duplicate_dependencies(self):
        records = runtime.runtime_records()
        for text in ('vllm==0.19.2 --hash=sha256:' + 'a' * 64,
                     'pip==25.0.1 --hash=sha256:' + runtime.BOOTSTRAP['sha256'],
                     'torch==2.10.0', '--index-url=https://example.test',
                     'torch @ https://example.test/wheel.whl',
                     ('torch==2.10.0+cu128 --hash=sha256:' + 'a' * 64 + '\n') * 2):
            with self.subTest(text=text), self.assertRaises(ValueError):
                runtime.combined_lock(text, records)

    def test_superseded_versions_cannot_reenter_the_runtime_lock(self):
        records = runtime.runtime_records()
        for original in runtime.supplied_records():
            name, version = original['path'].split('-')[:2]
            if runtime.normalized(name) in runtime.APPROVED_REPLACEMENTS:
                row = f"{name}=={version} --hash=sha256:{original['sha256']}"
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'cannot be repinned'):
                    runtime.combined_lock(row, records)

    def test_stale_or_unapproved_amendments_fail_closed(self):
        profile = json.loads(runtime.RUNTIME_PROFILE.read_text())
        mutations = []
        stale = copy.deepcopy(profile)
        stale['source_manifest_sha256'] = '0' * 64
        mutations.append(stale)
        unapproved = copy.deepcopy(profile)
        unapproved['status'] = 'proposal'
        mutations.append(unapproved)
        wrong_original = copy.deepcopy(profile)
        wrong_original['replacements'][0]['original']['sha256'] = '0' * 64
        mutations.append(wrong_original)
        missing = copy.deepcopy(profile)
        missing['replacements'].pop()
        mutations.append(missing)
        extra = copy.deepcopy(profile)
        extra['replacements'].append({'package': 'vllm'})
        mutations.append(extra)
        duplicate = copy.deepcopy(profile)
        duplicate['replacements'].append(copy.deepcopy(duplicate['replacements'][0]))
        mutations.append(duplicate)
        wrong_version = copy.deepcopy(profile)
        wrong_version['replacements'][2]['replacement']['path'] = 'xgrammar-0.2.9-py3-none-any.whl'
        mutations.append(wrong_version)
        unsafe_path = copy.deepcopy(profile)
        unsafe_path['replacements'][0]['replacement']['path'] = '../' + unsafe_path['replacements'][0]['replacement']['path']
        mutations.append(unsafe_path)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'amendment.json'
            for index, altered in enumerate(mutations):
                path.write_text(json.dumps(altered))
                with self.subTest(index=index), patch.object(runtime, 'RUNTIME_PROFILE', path):
                    with self.assertRaises(ValueError):
                        runtime.runtime_records()

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

    def test_missing_or_tampered_bootstrap_fails_before_environment_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / runtime.BOOTSTRAP['path']
            for tampered in (False, True):
                if tampered:
                    wheel.write_bytes(b'x' * runtime.BOOTSTRAP['bytes'])
                with self.subTest(tampered=tampered), \
                        patch.object(runtime.platform, 'system', return_value='Linux'), \
                        patch.object(runtime.platform, 'machine', return_value='x86_64'), \
                        patch.object(runtime.sys, 'version_info', (3, 12)), \
                        patch.object(runtime, 'runtime_records', return_value=[]), \
                        patch.object(runtime.subprocess, 'run') as install:
                    with self.assertRaisesRegex(ValueError, 'missing pinned wheel|hash mismatch'):
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
            self.copy_bootstrap(root)
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
            with patch.object(runtime, 'runtime_records', return_value=[record]), \
                    patch.object(runtime, 'REQUIRED', {'backtrace-fixture': '1.0'}):
                with self.assertRaises(subprocess.CalledProcessError):
                    runtime.qualify(root, lock, root / 'output')
            self.assertFalse((root / 'output').exists())

    @unittest.skipUnless(runtime.platform.system() == 'Linux' and
                         runtime.platform.machine() == 'x86_64' and
                         runtime.sys.version_info[:2] == (3, 12),
                         'real offline pip probe requires Linux CPython 3.12')
    def test_real_offline_replacement_survives_force_reinstall(self):
        # Both versions are physically present. Exercise actual venv, offline
        # hash installation, force-reinstall and pip check with authored wheels.
        # Only the large official import probe is replaced by fixture identity.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.copy_bootstrap(root)
            for version in ('1.0', '2.0'):
                wheel = root / f'backtrace_fixture-{version}-py3-none-any.whl'
                with zipfile.ZipFile(wheel, 'w') as archive:
                    prefix = f'backtrace_fixture-{version}.dist-info/'
                    archive.writestr(prefix + 'METADATA',
                                     'Metadata-Version: 2.1\nName: backtrace-fixture\n'
                                     f'Version: {version}\n')
                    archive.writestr(prefix + 'WHEEL',
                                     'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
                    archive.writestr(prefix + 'RECORD', '')
            record = dict(path=wheel.name, bytes=wheel.stat().st_size,
                          sha256=hashlib.sha256(wheel.read_bytes()).hexdigest())
            lock = root / 'supplemental.lock'
            lock.write_text('')
            real_child = runtime.offline_child

            def child(python, *arguments):
                if arguments[0].startswith('import torch,'):
                    return real_child(python, 'from importlib.metadata import version; '
                                      'assert version("backtrace-fixture") == "2.0"')
                return real_child(python, *arguments)

            with patch.object(runtime, 'runtime_records', return_value=[record]), \
                    patch.object(runtime, 'REQUIRED', {'backtrace-fixture': '2.0'}), \
                    patch.object(runtime, 'offline_child', side_effect=child):
                result = runtime.qualify(root, lock, root / 'output')
            self.assertEqual(result['offline_closure'], 'PASS')
            self.assertEqual(result['bootstrap_wheel'], runtime.BOOTSTRAP)
            inventory = json.loads((root / 'output/inventory.json').read_text())
            self.assertEqual(next(p['version'] for p in inventory if p['name'] == 'pip'), '25.0.1')
            self.assertEqual(next(p['version'] for p in inventory if p['name'] == 'backtrace-fixture'), '2.0')
            self.assertEqual(result['runtime_profile_sha256'],
                             hashlib.sha256(runtime.RUNTIME_PROFILE.read_bytes()).hexdigest())
