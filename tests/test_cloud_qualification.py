import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import cloud_qualification as gate


class Store:
    def __init__(self, result): self.result = result
    def request(self, *args, **kwargs): return copy.deepcopy(self.result)


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.sha = 'a' * 40
        self.run = {'id': 123, 'status': 'completed', 'conclusion': 'success', 'run_attempt': 1,
                    'head_sha': self.sha, 'head_branch': 'bt-001-a100-cpu-qualification',
                    'path': '.github/workflows/a100-prepare.yml'}
        self.receipt = {'schema_version': 1, 'source_sha': self.sha, 'run_id': 123,
                        'report_sha256': 'b' * 64, 'files': {'pinned': 'c' * 64}, 'transport': {}}

    def test_real_success_requires_both_exact_run_and_unchanged_qualified_files(self):
        with patch.object(gate, 'file_hashes', return_value=self.receipt['files']):
            result = gate.require_receipt(Store(self.run), Path('/fixture'), self.receipt)
            self.assertEqual(result['source_sha'], self.sha)
            for key, value in (('conclusion', 'failure'), ('head_sha', 'd' * 40), ('run_attempt', 2),
                               ('path', '.github/workflows/a100-cpu.yml')):
                changed = dict(self.run, **{key: value})
                with self.assertRaises(ValueError): gate.require_receipt(Store(changed), Path('/fixture'), self.receipt)
        with patch.object(gate, 'file_hashes', return_value={'pinned': 'changed'}):
            with self.assertRaises(ValueError): gate.require_receipt(Store(self.run), Path('/fixture'), self.receipt)

    def test_current_cpu_failure_and_pending_run_are_not_qualification(self):
        run = dict(self.run, path='.github/workflows/a100-cpu.yml')
        self.assertEqual(gate.require_current_cpu(Store({'workflow_runs': [run]}), self.sha)['run_id'], 123)
        run['conclusion'] = 'failure'
        with self.assertRaises(ValueError): gate.require_current_cpu(Store({'workflow_runs': [run]}), self.sha)
        run.update(status='in_progress', conclusion=None)
        times = iter([0, 0, 0, 11])
        with self.assertRaises(TimeoutError):
            gate.require_current_cpu(Store({'workflow_runs': [run]}), self.sha,
                                     timeout=10, wall=lambda: next(times), sleep=lambda _: None)


if __name__ == '__main__': unittest.main()
