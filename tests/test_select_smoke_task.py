"""Authored metadata only; these tests do not execute a model or official task."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.select_smoke_task import select_task


def record(identifier):
    return dict(instance_id=identifier, repo='example/project', base_commit='a' * 40,
                problem_statement='Authored public issue', hints_text='',
                patch='EVALUATOR_ONLY_PATCH', test_patch='EVALUATOR_ONLY_TEST',
                FAIL_TO_PASS=['EVALUATOR_ONLY_NODE'], PASS_TO_PASS=[], extra='DO_NOT_FORWARD')


def encode(*records):
    return ('\n'.join(json.dumps(item) for item in records) + '\n').encode()


class SmokeTaskSelectionTests(unittest.TestCase):
    def test_smallest_id_and_exact_agent_fields_independent_of_input_order(self):
        a, z = record('a_20'), record('z_1')
        for data in (encode(z, a), encode(a, z)):
            task, receipt = select_task(data)
            self.assertEqual(task['instance_id'], 'a_20')
            self.assertEqual(set(task), {'instance_id', 'repo', 'base_commit',
                                         'problem_statement', 'hints_text'})
            self.assertEqual(receipt['distinct_ids'], 2)
            self.assertNotIn('EVALUATOR_ONLY', json.dumps((task, receipt)))
            self.assertNotIn('DO_NOT_FORWARD', json.dumps((task, receipt)))

    def test_identical_duplicates_are_one_distinct_id(self):
        task, receipt = select_task(encode(record('a_1'), record('a_1')))
        self.assertEqual(task['instance_id'], 'a_1')
        self.assertEqual(receipt['distinct_ids'], 1)

    def test_conflicting_duplicate_reference_fields_rejected_without_echo(self):
        original = record('a_1')
        changed = dict(original, patch='DIFFERENT_EVALUATOR_ONLY_PATCH')
        with self.assertRaisesRegex(ValueError, '^conflicting duplicate instance_id$'):
            select_task(encode(original, changed))

    def test_invalid_metadata_and_missing_required_field_rejected(self):
        missing = record('a_1')
        del missing['problem_statement']
        for data in (b'', b'{bad', encode([]), encode({'instance_id': ''}), encode(missing)):
            with self.subTest(data=data), self.assertRaises(ValueError):
                select_task(data)
        no_hints = record('a_1')
        del no_hints['hints_text']
        self.assertEqual(select_task(encode(no_hints))[0]['hints_text'], '')

    def test_real_cli_private_output_no_overwrite_and_failure_cleanup(self):
        script = Path(__file__).resolve().parents[1] / 'tools/select_smoke_task.py'
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'tasks.jsonl', Path(directory) / 'agent-task.json'
            source.write_bytes(encode(record('a_1')))
            command = [sys.executable, str(script), str(source), str(target)]
            success = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            before = target.read_bytes()
            repeated = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(repeated.returncode, 2)
            self.assertIn('FileExistsError', repeated.stderr)
            self.assertEqual(target.read_bytes(), before)
            target.unlink()
            source.write_bytes(encode(record('a_1'), dict(record('a_1'), patch='PRIVATE_CONFLICT')))
            failed = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(failed.returncode, 2)
            self.assertNotIn('PRIVATE_CONFLICT', failed.stdout + failed.stderr)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
