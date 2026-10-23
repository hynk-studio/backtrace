"""Failure controls for real budget boundaries, counted fallback and completion."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import task_calibration as calibration
from tools.task_results import TRACE, validate
from tests.test_task_results import artifacts


class WindowTests(unittest.TestCase):
    def test_both_actual_boundaries_include_server_stop_retrieval_and_deletion(self):
        for phase, useful, total in (('server', 1740, 2040), ('agent', 540, 840)):
            env = {'BACKTRACE_USEFUL_DEADLINE': str(1000 + useful),
                   'BACKTRACE_TOTAL_DEADLINE': str(1000 + total)}
            result = calibration.require_window(phase, env=env, now=1000)
            self.assertEqual((result['minimum_useful_seconds'], result['minimum_total_seconds']), (useful, total))
            for key in env:
                too_late = dict(env, **{key: str(float(env[key]) - 1)})
                with self.assertRaises(TimeoutError):
                    calibration.require_window(phase, env=too_late, now=1000)

    def test_bad_clock_and_inner_only_extension_are_blocked(self):
        for useful, total in (('nan', '9000'), ('9000', 'inf'), ('9000', '8999')):
            with self.assertRaises(ValueError):
                calibration.require_window('server', env={'BACKTRACE_USEFUL_DEADLINE': useful,
                    'BACKTRACE_TOTAL_DEADLINE': total}, now=1000)
        with patch.dict(calibration.BUDGET, agent_child_seconds=180), self.assertRaises(ValueError):
            calibration.require_window('server', env={'BACKTRACE_USEFUL_DEADLINE': '9000',
                'BACKTRACE_TOTAL_DEADLINE': '9300'}, now=1000)


class CandidateTests(unittest.TestCase):
    def baseline(self, root):
        values = {name: b'unchanged' for name in calibration.BASE_FILES}
        values['eval_config.yaml'] = b'max_tool_calls: 10\nmax_time_minutes: 1\n'
        values['prompts/system.md'] = ('(under 8\u201310 turns)\nuse `search_similar_code` with keywords from the error message\n').encode()
        values['prompts/analyzer.md'] = b'analysis instructions\n'
        for name, data in values.items():
            target = root / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        hashes = {name: hashlib.sha256(data).hexdigest() for name, data in values.items()}
        return values, hashes

    def test_derivative_changes_only_budget_and_generic_prompts_and_refuses_reapplication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); values, hashes = self.baseline(root)
            with patch.object(calibration, 'BASE_FILES', hashes):
                receipt = calibration.apply_candidate(root)
                for name in ('agent.yaml', 'configs/sampling.yaml', 'sub_agents/code_analyzer.yaml'):
                    self.assertEqual((root / name).read_bytes(), values[name])
                self.assertIn('max_tool_calls: 30', (root / 'eval_config.yaml').read_text())
                self.assertEqual(receipt['protocol'], calibration.PROTOCOL)
                with self.assertRaises(ValueError): calibration.apply_candidate(root)

    def test_tampered_or_extra_input_fails_before_any_file_is_modified(self):
        for extra in (False, True):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); values, hashes = self.baseline(root)
                if extra: (root / 'unexpected').write_text('extra')
                else: (root / 'configs/sampling.yaml').write_text('changed')
                with patch.object(calibration, 'BASE_FILES', hashes), self.assertRaises(ValueError):
                    calibration.apply_candidate(root)
                self.assertEqual((root / 'eval_config.yaml').read_bytes(), values['eval_config.yaml'])


class CalibratedCompletionTests(unittest.TestCase):
    def fixture(self, root):
        value = artifacts(root)
        value.update(protocol=calibration.PROTOCOL, patch_submitted=True, tool_calls=14,
                     budget={'session_seconds': 300, 'tool_calls': 30, 'llm_calls': 50})
        (root / 'task-result.json').write_text(json.dumps(value))
        (root / TRACE).write_text(json.dumps({'schema_version': 'ATIF-v1.7', 'steps': [
            {'tool_calls': [{'function_name': 'submit_patch', 'arguments': {}}]}]}))
        return value

    def test_new_budget_requires_explicit_expected_protocol_and_real_submission_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            with self.assertRaises(ValueError): validate(root)
            self.assertEqual(validate(root, protocol=calibration.PROTOCOL)['tool_calls'], 14)
            (root / TRACE).write_text(json.dumps({'schema_version': 'ATIF-v1.7', 'steps': [
                {'message': 'I will call submit_patch', 'content': {'name': 'submit_patch'}}]}))
            with self.assertRaises(ValueError): validate(root, protocol=calibration.PROTOCOL)

    def test_error_missing_submit_or_wrong_budget_never_becomes_completed_task(self):
        for changes in ({'agent_error': 'timeout'}, {'patch_submitted': False},
                        {'tool_calls': 31}, {'seconds': 331}, {'budget': {'session_seconds': 60}}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); result = self.fixture(root)
                (root / 'task-result.json').write_text(json.dumps(dict(result, **changes)))
                with self.assertRaises(ValueError): validate(root, protocol=calibration.PROTOCOL)


if __name__ == '__main__':
    unittest.main()
