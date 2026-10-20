import unittest

from tools.cloud_launch import validate_context
from tools.cloud_state import REPOSITORY, StateError


class LaunchContextTests(unittest.TestCase):
    def context(self, branch, attempt):
        return {'GITHUB_REPOSITORY': REPOSITORY, 'GITHUB_REF_NAME': branch,
                'GITHUB_RUN_ATTEMPT': attempt}

    def test_free_preflight_can_repeat_only_on_its_review_branch(self):
        for attempt in ('1', '2'):
            validate_context('preflight', self.context('bt-001-a100-cpu-qualification', attempt))
        with self.assertRaises(StateError):
            validate_context('preflight', self.context('bt-001-a100-start-20261020b', '1'))

    def test_paid_mode_still_requires_first_run_on_the_exact_start_branch(self):
        validate_context('paid', self.context('bt-001-a100-start-20261020b', '1'))
        for branch, attempt in (('bt-001-a100-start-20261020b', '2'),
                                ('bt-001-a100-cpu-qualification', '1'),
                                ('bt-001-a100-start-20261020b', '0'),
                                ('bt-001-a100-start-20261019', '1')):
            with self.assertRaises(StateError):
                validate_context('paid', self.context(branch, attempt))


if __name__ == '__main__':
    unittest.main()
