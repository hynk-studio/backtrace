"""Incomplete-task diagnostics cannot become accepted model task results."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import recovered_task, qualify_evaluation
from tools.task_budget import PROPOSAL, check


class Budgets(unittest.TestCase):
    def test_longer_inner_budget_requires_a_longer_child_deadline(self):
        r = check(dict(PROPOSAL, agent_child_seconds=180), 5800, 6100)
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertIn('agent child', r['reasons'][0])

    def test_startup_retrieval_and_provider_cleanup_are_reserved(self):
        self.assertEqual(check(PROPOSAL, 1710, 2010)['status'], 'PASS')
        for useful, total in [(1709, 2010), (1710, 2009), (1500, 1800)]:
            self.assertEqual(check(PROPOSAL, useful, total)['status'], 'BLOCKED')

    def test_invalid_deadlines_and_boolean_budgets_are_rejected(self):
        for useful in [float('nan'), float('inf'), -1, True]:
            with self.assertRaises(ValueError): check(PROPOSAL, useful, 6100)
        with self.assertRaises(ValueError): check(dict(PROPOSAL, tool_calls=True), 5800, 6100)

    def test_passing_budget_check_does_not_authorize_compute_or_predict_success(self):
        r = check(PROPOSAL, 5800, 6100)
        self.assertEqual(r['compute_authorization'], 'NONE')
        self.assertIs(r['predicts_task_success'], False)


class RecoveredTask(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'input'; self.root.mkdir()
        patch_body = b'diff --git a/reproduce_issue.py b/reproduce_issue.py\n--- /dev/null\n+++ b/reproduce_issue.py\n'
        task = {'instance_id': 'fastapi_11194', 'agent_error': 'Agent exceeded session timeout (1.0 min)',
                'llm_calls': 10, 'tool_calls': 10, 'seconds': 62.95, 'patch_bytes': len(patch_body),
                'patch_sha256': hashlib.sha256(patch_body).hexdigest()}
        wire = []
        for n in range(11):
            wire.append({'event': 'request', 'request_sha256': str(n)})
            if n < 10: wire.append({'event': 'response', 'request_sha256': str(n), 'status': 200})
        bodies = {'agent.patch': patch_body, 'task-result.json': json.dumps(task).encode(),
                  'wire.jsonl': '\n'.join(map(json.dumps, wire)).encode(),
                  recovered_task.NAMES[3]: b'{"schema_version":"ATIF-v1","steps":[]}',
                  'execution.log': b'private execution', 'server.log': b'private server'}
        for name, data in bodies.items():
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        self.manifest = {'paid_source_sha': '626e3a619a025f64e3713af11b8e4097471470ab',
                         'paid_run_id': 39878045521, 'pod_id': 'virbb2jab7fi8v',
                         'files': {n: {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
                                   for n, b in bodies.items()}}

    def test_partial_analysis_preserves_failure_and_identifies_reproduction_only_patch(self):
        r = recovered_task.analyze(self.root, self.manifest)
        self.assertFalse(r['completed_agent_task'])
        self.assertEqual(r['patch_scope'], 'reproduction scripts only')
        self.assertEqual(r['wire_requests'], 11)
        self.assertEqual(r['successful_responses'], 10)
        self.assertEqual(r['counterfactual_success_after_more_budget'], 'NOT ESTABLISHED')

    def test_corruption_wrong_attempt_and_symlinks_are_rejected(self):
        with self.subTest('attempt'):
            with self.assertRaises(ValueError): recovered_task.verify(self.root, dict(self.manifest, paid_run_id=1))
        p = self.root / 'agent.patch'; body = p.read_bytes(); p.write_bytes(body + b'changed')
        with self.assertRaises(ValueError): recovered_task.verify(self.root, self.manifest)
        p.unlink(); target = Path(self.temp.name) / 'outside'; target.write_bytes(body); p.symlink_to(target)
        with self.assertRaises(ValueError): recovered_task.verify(self.root, self.manifest)

    def test_exact_archive_restores_without_extra_or_duplicate_members(self):
        def archive(extra=False):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as z:
                for n in recovered_task.NAMES: z.write(self.root / n, n)
                if extra: z.writestr('../escape', 'bad')
            return stream.getvalue()
        recovered_task.restore(archive(), Path(self.temp.name) / 'restored', self.manifest)
        with self.assertRaises(ValueError):
            recovered_task.restore(archive(True), Path(self.temp.name) / 'bad', self.manifest)

    def test_existing_completed_task_entry_still_rejects_timed_out_artifacts(self):
        with patch.object(qualify_evaluation, 'qualify') as run:
            with self.assertRaises(ValueError):
                qualify_evaluation.evaluate_receipts('evaluator', 'inputs', self.root, 'output')
            run.assert_not_called()

    def test_diagnostic_entry_selects_partial_mode_and_keeps_original_error(self):
        answer = {'completed_agent_task': False,
                  'model_score': 'NOT CLAIMED; incomplete task patch diagnostic only'}
        with patch.object(qualify_evaluation, 'qualify', return_value=answer) as run:
            r = qualify_evaluation.diagnose_incomplete_receipts('evaluator', 'inputs', self.root, 'output', self.manifest)
            self.assertTrue(run.call_args.kwargs['partial'])
            self.assertFalse(run.call_args.kwargs['controls'])
            self.assertIn('timeout', r['original_task_result']['agent_error'])

    def test_success_promotion_from_diagnostic_worker_is_rejected(self):
        with patch.object(qualify_evaluation, 'qualify', return_value={'completed_agent_task': True}):
            with self.assertRaises(ValueError):
                qualify_evaluation.diagnose_incomplete_receipts('evaluator', 'inputs', self.root, 'output', self.manifest)


if __name__ == '__main__': unittest.main()
