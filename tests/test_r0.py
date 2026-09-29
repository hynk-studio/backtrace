"""Authored synthetic inputs; mocked CPU checks do not certify official validation."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import r0
from tools import official_check
from tools.backtrace import InspectionError, ROOT, digest


class R0Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifacts = self.root / 'official'
        self.sample = self.artifacts / 'sample_submission'
        self.original = {name: b'Synthetic fixture\n' for name in r0.RETAINED + r0.EXCLUDED}
        self.original['agent.yaml'] = (b'name: synthetic\nadapter: main_lora\n'
                                       b'tools:\n  - agent_tool:\n'
                                       b'      config_path: sub_agents/code_analyzer.yaml\n'
                                       b'      skip_summarization: true\n')
        self.original['sub_agents/code_analyzer.yaml'] = (
            b'name: synthetic_analyzer\nadapter: tool_lora\n'
            b'instruction: !include ../prompts/analyzer.md\n')
        for name, data in self.original.items():
            path = self.sample / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.records = self.pins()
        self.output = self.root / 'candidate.zip'

    def pins(self):
        return [{'local_path': 'sample_submission/' + name,
                 'size_bytes': (self.sample / name).stat().st_size,
                 'sha256': digest((self.sample / name).read_bytes())} for name in self.original]

    def fake_cpu(self, artifacts, archive, python, sha256):
        self.assertTrue(Path(archive).is_file())
        self.assertFalse(self.output.exists())
        return {'official_cpu_checks': 'MOCK ONLY', 'candidate_sha256': sha256}

    def build(self, output=None, cpu=None):
        with patch.object(r0, 'run_official_check', side_effect=cpu or self.fake_cpu):
            return r0.build_candidate(self.artifacts, output or self.output, sys.executable, self.records)

    def assert_original(self):
        self.assertEqual({p.relative_to(self.sample).as_posix(): p.read_bytes()
                          for p in self.sample.rglob('*') if p.is_file()}, self.original)

    def assert_no_staged_output(self):
        self.assertEqual(list(self.root.iterdir()), [self.artifacts])

    def test_exact_delta_and_reference_preserved(self):
        report = self.build()
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.namelist(), list(r0.RETAINED))
            for name in r0.RETAINED:
                expected = self.original[name]
                if name in r0.REMOVED_LINES:
                    expected = expected.replace(r0.REMOVED_LINES[name], b'')
                self.assertEqual(archive.read(name), expected)
            self.assertIn(b'skip_summarization: true', archive.read('agent.yaml'))
            self.assertIn(b'!include ../prompts/analyzer.md',
                          archive.read('sub_agents/code_analyzer.yaml'))
        self.assertEqual(report['local_inspection']['exact_delta'], 'PASS')
        self.assertEqual(report['official_cpu_validation']['official_cpu_checks'], 'MOCK ONLY')
        self.assert_original()

    def test_reproducible_metadata_and_hash(self):
        first = self.build()
        # A different source mtime must not affect output; production pins bind bytes.
        os.utime(self.sample / 'agent.yaml', (1_700_000_000, 1_700_000_000))
        second_path = self.root / 'second.zip'
        second = self.build(second_path, cpu=lambda *args: {'mock': True})
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertEqual(self.output.read_bytes(), second_path.read_bytes())
        with zipfile.ZipFile(self.output) as archive:
            for info in archive.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(info.external_attr >> 16, 0o100644)
                self.assertEqual((info.comment, info.extra), (b'', b''))

    def test_input_config_and_adapter_drift(self):
        for name in ('prompts/system.md', 'configs/sampling.yaml', 'eval_config.yaml',
                     'agent.yaml', 'adapters/main_lora/adapter_model.safetensors'):
            with self.subTest(name=name):
                (self.sample / name).write_bytes(self.original[name] + b'changed')
                with self.assertRaisesRegex(InspectionError, 'size mismatch'):
                    self.build()
                (self.sample / name).write_bytes(self.original[name])
                self.assert_no_staged_output()

    def test_declaration_location_and_multiplicity(self):
        for name, line in r0.REMOVED_LINES.items():
            for replacement in (b'', b'  ' + line, line + line, line.replace(b'\n', b'\r\n')):
                with self.subTest(name=name, replacement=replacement):
                    (self.sample / name).write_bytes(self.original[name].replace(line, replacement))
                    with self.assertRaisesRegex(InspectionError, 'root-level adapter declaration'):
                        r0.expected_candidate(self.artifacts, self.pins())
                    (self.sample / name).write_bytes(self.original[name])
        self.assert_no_staged_output()

    def test_no_overwrite(self):
        self.output.write_bytes(b'keep existing output')
        with self.assertRaisesRegex(InspectionError, 'no overwrite'):
            self.build()
        self.assertEqual(self.output.read_bytes(), b'keep existing output')
        self.assert_original()

    def test_original_destination_and_resolved_alias_rejected(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.sample, target_is_directory=True)
        for target in (self.sample / 'new.zip', self.artifacts / 'new.zip',
                       alias / 'new.zip', self.artifacts):
            with self.subTest(target=target):
                with self.assertRaisesRegex(InspectionError, 'separate'):
                    self.build(target)
        alias.unlink()
        self.assert_no_staged_output()
        self.assert_original()

    def test_official_failure_cleans_up(self):
        def fail(*args):
            raise InspectionError('synthetic official check failure')
        with self.assertRaisesRegex(InspectionError, 'synthetic official check failure'):
            self.build(cpu=fail)
        self.assert_no_staged_output()
        self.assert_original()

    def test_candidate_mutation_rejected_and_cleans_up(self):
        def mutate(artifacts, archive, python, sha256):
            with zipfile.ZipFile(archive) as source:
                files = {name: source.read(name) for name in r0.RETAINED}
            files['prompts/system.md'] += b'changed'
            with zipfile.ZipFile(archive, 'w') as output:
                for name, data in files.items():
                    output.writestr(name, data)
            return {'mock': True}
        with self.assertRaisesRegex(InspectionError, 'authorized R0-clean byte delta'):
            self.build(cpu=mutate)
        self.assert_no_staged_output()

    def test_candidate_missing_extra_and_adapter_reintroduction(self):
        expected = r0.expected_candidate(self.artifacts, self.records)
        for mutation in ('missing', 'extra', 'adapter'):
            files = dict(expected)
            if mutation == 'missing':
                del files['eval_config.yaml']
            elif mutation == 'extra':
                files['unrelated.txt'] = b'extra'
            else:
                files['agent.yaml'] = self.original['agent.yaml']
            with zipfile.ZipFile(self.output, 'w') as archive:
                for name, data in files.items():
                    archive.writestr(name, data)
            with self.assertRaises(InspectionError):
                r0.inspect_candidate(self.output, expected)
        self.assert_original()

    def test_publish_race_never_overwrites(self):
        def competing_output(*args):
            self.output.write_bytes(b'created by another process')
            return {'mock': True}
        with self.assertRaises(FileExistsError):
            self.build(cpu=competing_output)
        self.assertEqual(self.output.read_bytes(), b'created by another process')
        self.assertEqual(set(self.root.iterdir()), {self.artifacts, self.output})

    def test_official_subprocess_failure_and_wrong_receipt(self):
        for code, stdout in ((2, 'private exception'), (0, '{}'), (0, 'not json'),
                             (0, json.dumps({'official_cpu_checks': 'PASS',
                                             'subject': 'unchanged official starter'}))):
            completed = subprocess.CompletedProcess([], code, stdout, 'private error')
            with patch.object(r0.subprocess, 'run', return_value=completed):
                with self.assertRaises(InspectionError) as caught:
                    r0.build_candidate(self.artifacts, self.output, sys.executable, self.records)
                self.assertNotIn('private', str(caught.exception))
            self.assert_no_staged_output()

    def test_missing_cli_inputs_no_output(self):
        with tempfile.TemporaryDirectory() as cwd:
            for args, message in (([], 'R0-clean requires pinned artifacts'),
                                  (['missing', 'candidate.zip', '--official-python', sys.executable],
                                   'missing artifact directory')):
                result = subprocess.run(
                    [sys.executable, '-B', str(ROOT / 'tools/backtrace.py'), 'baseline', *args],
                    cwd=cwd, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertIn(message, result.stderr)
                self.assertEqual(list(Path(cwd).iterdir()), [])

    def test_cpu_wrapper_checks_archived_bytes_and_cleans_temporary_root(self):
        self.build()
        expected = r0.expected_candidate(self.artifacts, self.records)
        checked_roots = []
        def check(sample, candidate):
            self.assertTrue(candidate)
            self.assertNotEqual(sample, self.sample.resolve())
            self.assertEqual(sample, sample.resolve())
            self.assertEqual({p.relative_to(sample).as_posix(): p.read_bytes()
                              for p in sample.rglob('*') if p.is_file()}, expected)
            checked_roots.append(sample)
            return {'official_cpu_checks': 'MOCK ONLY'}
        with patch.object(sys, 'argv', ['official_check', str(self.artifacts),
                                      '--candidate', str(self.output)]), \
                patch.object(sys, 'prefix', '/synthetic-venv'), \
                patch.object(official_check, 'verify_artifacts'), \
                patch.object(official_check, 'check_installed_wheels'), \
                patch.object(official_check, 'expected_candidate', return_value=expected), \
                patch.object(official_check, 'check_directory', side_effect=check), \
                patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(official_check.main(), 0)
        report = json.loads(stdout.getvalue())
        self.assertEqual(report['subject'], 'R0-clean candidate archive')
        self.assertEqual(report['candidate_sha256'], digest(self.output.read_bytes()))
        self.assertEqual(len(checked_roots), 1)
        self.assertFalse(checked_roots[0].exists())
        self.assert_original()


if __name__ == '__main__':
    unittest.main()
