import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import task_calibration, task_verification
from tools.task_trace_review import review
from tools.task_results import validate, TRACE
from tests import test_task_calibration as fixtures
from tests.verification_fixture import SOURCE, tool_result


def event(name, result):
    return {'tool_calls': [{'function_name': name, 'arguments': {}}],
            'observation': {'content': json.dumps(result)}}


class RevisionTests(unittest.TestCase):
    def test_pinned_revision_changes_only_generic_prompts_after_previous_calibration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before, hashes = fixtures.CandidateTests().baseline(root)
            with patch.object(task_calibration, 'BASE_FILES', hashes):
                old = task_calibration.candidate_files(before)
                new = task_verification.candidate_files(before)
                receipt = task_verification.apply_candidate(root)
                with self.assertRaises(ValueError): task_verification.apply_candidate(root)
            self.assertEqual({k for k in new if new[k] != old[k]}, {'prompts/system.md', 'prompts/analyzer.md'})
            self.assertEqual(receipt['protocol'], task_verification.PROTOCOL)
            self.assertEqual(receipt['files'], {k: hashlib.sha256(v).hexdigest() for k, v in new.items()})
            for word in (b'fastapi', b'multipart', b'11194', b'reference patch'):
                self.assertNotIn(word, task_verification.GUIDANCE.lower())
            for tool in (b'run_command', b'get_status', b'submit_patch'):
                self.assertNotIn(tool, new['prompts/analyzer.md'])

    def test_historical_receipt_and_revised_receipt_cannot_be_relabelled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); result = fixtures.CalibratedCompletionTests().fixture(root)
            self.assertEqual(validate(root, protocol=task_calibration.PROTOCOL)['status'], 'PASS')
            with self.assertRaises(ValueError): validate(root, protocol=task_verification.PROTOCOL)
            result['protocol'] = task_verification.PROTOCOL
            (root / 'task-result.json').write_text(json.dumps(result))
            self.assertEqual(validate(root, protocol=task_verification.PROTOCOL)['status'], 'PASS')
            with self.assertRaises(ValueError): validate(root, protocol=task_calibration.PROTOCOL)


class EvidenceTests(unittest.TestCase):
    def test_original_command_error_details_and_adk_result_wrapper_are_read(self):
        value = {'status': 'error', 'error_type': 'CommandError', 'details': {
            'stdout': '', 'stderr': 'AssertionError', 'exit_code': 1}}
        message = {'role': 'tool', 'content': json.dumps({'result': json.dumps(value)})}
        self.assertEqual(tool_result([message]), value)
        audit = review({'steps': [event('edit_file', {'status': 'ok'}), event('run_command', value)]})
        self.assertEqual(audit['nonzero_commands'], 1)
        self.assertEqual(audit['last_post_mutation_exit_code'], 1)
        self.assertIn('LAST_POST_MUTATION_COMMAND_HAS_FAILURE_EVIDENCE', audit['flags'])

    def test_actual_swallowed_assertion_is_not_treated_as_passing_test(self):
        result = subprocess.run([sys.executable, '-c',
            "try:\n assert False\nexcept AssertionError:\n print('test_probe failed: AssertionError')"],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        audit = review({'steps': [event('write_file', {'status': 'ok'}),
            event('run_command', {'status': 'ok', 'exit_code': result.returncode,
                                 'stdout': result.stdout, 'stderr': result.stderr}),
            event('edit_file', {'status': 'error', 'error_type': 'BudgetExceeded'}),
            event('submit_patch', {'status': 'ok'})]})
        self.assertEqual(audit['rejected_mutations'], 1)
        self.assertIn('TOOL_BUDGET_EXHAUSTED', audit['flags'])
        self.assertIn('ZERO_EXIT_WITH_FAILURE_TEXT', audit['flags'])
        self.assertIn('LAST_POST_MUTATION_COMMAND_HAS_FAILURE_EVIDENCE', audit['flags'])

    def test_same_real_assertion_discriminates_wrong_correct_and_later_wrong_edit(self):
        outcomes = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'probe.py'
            for expression in ('number', 'number + 2', 'number + 1', 'number + 3', 'number + 1'):
                path.write_text(SOURCE.replace('return number', 'return ' + expression))
                p = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, timeout=10)
                outcomes.append(p.returncode)
        self.assertEqual(outcomes, [1, 1, 0, 1, 0])

    def test_edit_after_success_leaves_verification_stale_and_zero_command_is_not_correctness(self):
        steps = [event('write_file', {'status': 'ok'}),
                 event('run_command', {'status': 'ok', 'exit_code': 0, 'stdout': 'a search result'})]
        self.assertIn('NOT ESTABLISHED', review({'steps': steps})['correctness'])
        steps.append(event('edit_file', {'status': 'ok'}))
        self.assertIn('NO_COMMAND_AFTER_LAST_ACCEPTED_MUTATION', review({'steps': steps})['flags'])

    def test_unknown_or_multiple_tool_observations_do_not_invent_success(self):
        audit = review({'steps': [{'tool_calls': [{'function_name': 'edit_file'}], 'observation': {'content': 'unknown'}},
            {'tool_calls': [{'function_name': 'edit_file'}, {'function_name': 'run_command'}],
             'observation': {'content': '{"status":"ok"}'}}]})
        self.assertEqual(audit['accepted_mutations'], 0)
        self.assertEqual(audit['unrecognized_tool_observations'], 3)


if __name__ == '__main__': unittest.main()
