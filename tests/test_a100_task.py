import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.a100_task import check_inventory, inherit_runtime, prepare, cuda_runtime_info, check_gpu


class CudaRuntimeObservationTests(unittest.TestCase):
    def observe(self, root, *, version='12.8.90', api=12080, status=0):
        library = root / 'nvidia/cuda_runtime/lib/libcudart.so.12'
        library.parent.mkdir(parents=True, exist_ok=True)
        library.write_bytes(b'authored-runtime-fixture')
        distribution = SimpleNamespace(version=version, locate_file=lambda name: root / name)
        def get_version(pointer):
            pointer._obj.value = api
            return status
        loaded = SimpleNamespace(cudaRuntimeGetVersion=Mock(side_effect=get_version))
        return distribution, loaded

    def test_runtime_probe_needs_no_developer_manifest_and_reports_loaded_component(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            distribution, loaded = self.observe(root)
            with patch('tools.a100_task.importlib.metadata.distribution', return_value=distribution), \
                    patch('tools.a100_task.ctypes.CDLL', return_value=loaded), \
                    patch.object(Path, 'read_text', side_effect=AssertionError('no developer manifest')):
                observed = cuda_runtime_info()
            self.assertEqual(observed['version'], '12.8.90')
            self.assertEqual(observed['api_version'], 12080)
            loaded.cudaRuntimeGetVersion.assert_called_once()

    def test_component_patch_floor_and_loaded_api_must_both_match(self):
        for values in ({'version': '12.8.57'}, {'version': '12.8'},
                       {'api': 12070}, {'status': 35}):
            with self.subTest(values=values), tempfile.TemporaryDirectory() as directory:
                distribution, loaded = self.observe(Path(directory), **values)
                with patch('tools.a100_task.importlib.metadata.distribution', return_value=distribution), \
                        patch('tools.a100_task.ctypes.CDLL', return_value=loaded), \
                        self.assertRaises(ValueError):
                    cuda_runtime_info()

    def test_missing_qualified_runtime_library_is_not_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            distribution = SimpleNamespace(version='12.8.90', locate_file=lambda name: root / name)
            with patch('tools.a100_task.importlib.metadata.distribution', return_value=distribution), \
                    self.assertRaisesRegex(ValueError, 'library missing'):
                cuda_runtime_info()

    def test_gpu_check_uses_observed_runtime_without_toolkit_manifest(self):
        runtime = {'version': '12.8.90', 'api_version': 12080}
        device = object()
        with patch('tools.a100_task.subprocess.check_output', return_value='actual-smi-read'), \
                patch('tools.a100_task.cuda_runtime_info', return_value=runtime), \
                patch('tools.a100_driver.qualify_hardware', return_value={'native_bf16': True}) as qualify:
            hardware = check_gpu(device)
        qualify.assert_called_once_with('actual-smi-read', device, runtime_version='12.8.90')
        self.assertEqual(hardware['runtime_evidence'], runtime)


class A100TaskPreparationTests(unittest.TestCase):
    def test_rejects_missing_extra_changed_and_duplicate_runtime(self):
        expected = [{'name': 'a-package', 'version': '1'}, {'name': 'b', 'version': '2'}]
        self.assertEqual(check_inventory(expected, [
            {'name': 'A_package', 'version': '1'}, expected[1]]), {'a-package': '1', 'b': '2'})
        for installed in (expected[:1], expected + [{'name': 'c', 'version': '3'}],
                          [expected[0], {'name': 'b', 'version': '3'}], expected + expected[:1]):
            with self.subTest(installed=installed), self.assertRaises(ValueError):
                check_inventory(expected, installed)

    def test_untrusted_private_source_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source.py').write_text('raise RuntimeError("do not run")')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                prepare(root / 'source.py', root / 'output')
            self.assertFalse((root / 'output').exists())

    def test_nested_venv_inherits_parent_and_task_overlay_wins(self):
        if sys.version_info[:2] != (3, 12):
            self.skipTest('qualified runtime is CPython 3.12')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / 'runtime'
            task = root / 'task'
            subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(parent)], check=True, timeout=30)
            subprocess.run([str(parent / 'bin/python'), '-m', 'venv', '--without-pip', str(task)], check=True, timeout=30)
            parent_sites = parent / 'lib/python3.12/site-packages'
            task_sites = task / 'lib/python3.12/site-packages'
            (parent_sites / 'backtrace_inheritance_fixture.py').write_text('value="runtime"\n')
            command = [str(task / 'bin/python'), '-I', '-c',
                       'import backtrace_inheritance_fixture as f; print(f.value)']
            before = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(before.returncode, 0)
            inherit_runtime(task, parent)
            self.assertEqual(subprocess.check_output(command, text=True, timeout=10).strip(), 'runtime')
            (task_sites / 'backtrace_inheritance_fixture.py').write_text('value="task"\n')
            self.assertEqual(subprocess.check_output(command, text=True, timeout=10).strip(), 'task')
            parent_command = [str(parent / 'bin/python'), *command[1:]]
            self.assertEqual(subprocess.check_output(parent_command, text=True, timeout=10).strip(), 'runtime')
            with self.assertRaises(FileExistsError):
                inherit_runtime(task, parent)
