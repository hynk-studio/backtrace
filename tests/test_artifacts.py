"""Authored local artifact-pin fixtures, not competition assets."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import artifacts
from tools.backtrace import InspectionError, ROOT, digest


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / 'sample_submission' / 'agent.yaml'
        self.file.parent.mkdir()
        self.file.write_bytes(b'Synthetic fixture\n')
        self.records = [{'local_path': 'sample_submission/agent.yaml',
                         'size_bytes': self.file.stat().st_size,
                         'sha256': digest(self.file.read_bytes())}]

    def check(self):
        return artifacts.verify_artifacts(self.root, self.records)

    def test_exact_pins_read_only(self):
        before = self.file.read_bytes()
        self.assertEqual(self.check()['artifact_pins'], 'PASS')
        self.assertEqual(self.file.read_bytes(), before)

    def test_missing_and_changed_bytes(self):
        for data in (b'x', b'synthetic fixture\n'):
            self.file.write_bytes(data)
            with self.assertRaises(InspectionError):
                self.check()
        self.file.unlink()
        with self.assertRaises(InspectionError):
            self.check()

    def test_unrelated_starter_file(self):
        (self.file.parent / 'extra.txt').write_text('unrelated')
        with self.assertRaisesRegex(InspectionError, 'file set'):
            self.check()

    def test_symlink_input_and_extra_directory(self):
        original = self.file.read_bytes()
        self.file.unlink()
        target = self.root / 'target.txt'
        target.write_bytes(original)
        self.file.symlink_to(target)
        with self.assertRaisesRegex(InspectionError, 'symlink'):
            self.check()
        self.file.unlink()
        self.file.write_bytes(original)
        (self.file.parent / 'extra').symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(InspectionError, 'symlink'):
            self.check()

    def test_ambiguous_and_escaping_manifest_paths(self):
        for name in ('../agent.yaml', 'sample_submission/Agent.yaml'):
            with self.subTest(name=name):
                records = [*self.records, {**self.records[0], 'local_path': name}]
                with self.assertRaises(InspectionError):
                    artifacts.verify_artifacts(self.root, records)

    def test_cli_missing_artifacts_fails(self):
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run(
                [sys.executable, '-B', str(ROOT / 'tools/backtrace.py'),
                 'verify-artifacts', str(Path(cwd) / 'private-missing-path')],
                cwd=cwd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr, 'FAILED: missing artifact directory; '
                             'follow docs/r0.md acquisition steps\n')
            self.assertNotIn('private-missing-path', result.stderr)
            self.assertEqual(list(Path(cwd).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
