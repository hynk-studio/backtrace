import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.a100_task import check_inventory, inherit_runtime, prepare


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
