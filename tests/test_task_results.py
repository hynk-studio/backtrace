"""Reject false completion and preserve failures across real artifact recovery."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import cloud_worker
from tools.private_delivery import emit, receive
from tools.task_results import TRACE, validate


def artifacts(root):
    result = {'instance_id': 'fastapi_11194', 'agent_error': None, 'tool_calls': 1, 'llm_calls': 1,
              'seconds': 1.0, 'patch_bytes': 5, 'patch_sha256': hashlib.sha256(b'patch').hexdigest()}
    (root / 'agent.patch').write_bytes(b'patch')
    (root / 'task-result.json').write_text(json.dumps(result))
    (root / 'wire.jsonl').write_text(json.dumps({'event': 'request', 'request_sha256': 'a' * 64,
        'path': '/v1/chat/completions'}) + '\n' + json.dumps({'event': 'response', 'status': 200,
        'request_sha256': 'a' * 64}) + '\n')
    path = root / TRACE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'schema_version': 'ATIF-v1.7', 'steps': [{'message': 'unit fixture'}]}))
    return result


class CompletionTests(unittest.TestCase):
    def test_actual_byte_transfer_preserves_validation_and_changed_patch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'; source.mkdir()
            artifacts(source)
            rows = [{'path': p.relative_to(source).as_posix(), 'bytes': p.stat().st_size,
                     'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in sorted(source.rglob('*')) if p.is_file()]
            manifest = json.dumps({'schema_version': 1, 'phase': 'task', 'files': rows}).encode()
            stream = io.BytesIO(); emit(source, manifest, stream); stream.seek(0)
            receive(root / 'receipts', hashlib.sha256(manifest).hexdigest(), stream)
            self.assertEqual(validate(source), validate(root / 'receipts'))
            (root / 'receipts/agent.patch').write_bytes(b'other')
            with self.assertRaises(ValueError): validate(root / 'receipts')

    def test_harness_error_zero_calls_wrong_identity_and_budget_are_not_success(self):
        for changes in ({'agent_error': 'Sandbox execution error'}, {'llm_calls': 0},
                        {'instance_id': 'other'}, {'tool_calls': 11}, {'llm_calls': True},
                        {'seconds': float('nan')}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); result = artifacts(root)
                (root / 'task-result.json').write_text(json.dumps(dict(result, **changes)))
                with self.assertRaises(ValueError): validate(root)

    def test_unanswered_failed_and_unrelated_http_cannot_qualify_completion(self):
        for wire in ([{'event': 'request', 'path': '/v1/chat/completions', 'request_sha256': 'a' * 64}],
                     [{'event': 'request', 'path': '/v1/chat/completions', 'request_sha256': 'a' * 64},
                      {'event': 'response', 'status': 400, 'request_sha256': 'a' * 64}],
                     [{'event': 'request', 'path': '/health', 'request_sha256': 'a' * 64},
                      {'event': 'response', 'status': 200, 'request_sha256': 'a' * 64}]):
            with self.subTest(wire=wire), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); artifacts(root)
                (root / 'wire.jsonl').write_text('\n'.join(map(json.dumps, wire)))
                with self.assertRaises(ValueError): validate(root)

    def test_missing_result_and_empty_trace_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); artifacts(root)
            (root / TRACE).write_text('{}')
            with self.assertRaises(ValueError): validate(root)
            (root / 'task-result.json').unlink()
            with self.assertRaises(ValueError): validate(root)


class RecoveryTests(unittest.TestCase):
    def test_zero_exit_without_receipts_and_expired_recovery_both_fail(self):
        for left in (10, 100):
            with self.subTest(left=left), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch.object(cloud_worker, 'remaining', return_value=left), \
                        patch.object(cloud_worker, 'retrieve', return_value={'files': 0}):
                    with self.assertRaises((ValueError, TimeoutError)):
                        cloud_worker.complete_workload(lambda *a, **k: None, [],
                            {'requested_at': 1}, root, io.BytesIO(), ['workload'])

    def test_first_workload_error_survives_retrieval_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary = subprocess.CalledProcessError(7, ['actual-workload-boundary'])
            def failed(*a, **k): raise primary
            with patch.object(cloud_worker, 'remaining', side_effect=TimeoutError('expired')):
                with self.assertRaises(subprocess.CalledProcessError) as caught:
                    cloud_worker.complete_workload(failed, [], {'requested_at': 1}, root, io.BytesIO(), ['workload'])
            self.assertIs(caught.exception, primary)
            self.assertEqual(json.loads((root / 'retrieval-error.json').read_text())['error_type'], 'TimeoutError')


if __name__ == '__main__': unittest.main()
