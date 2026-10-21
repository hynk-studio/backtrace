"""Reject infrastructure exit 1 and empty/errored verifier runs as model scores."""
import unittest
from tools.qualify_evaluation import verified_tests


def xml(*, failures=0, errors=0, skipped=0, tests=1):
    result = '<failure/>' if failures else '<error/>' if errors else '<skipped/>' if skipped else ''
    return (f'<testsuites><testsuite tests="{tests}" failures="{failures}" errors="{errors}" '
            f'skipped="{skipped}"><testcase name="public-case">{result}</testcase></testsuite></testsuites>')


class VerifierTests(unittest.TestCase):
    def test_actual_test_failure_and_actual_pass_are_distinct_valid_outcomes(self):
        self.assertEqual(verified_tests(xml(failures=1), 1, False, False)['failures'], 1)
        self.assertEqual(verified_tests(xml(), 0, True, False)['passed'], 1)

    def test_missing_pytest_cannot_become_an_unresolved_model_score(self):
        with self.assertRaises(ValueError): verified_tests('', 1, False, False)

    def test_collection_errors_skips_zero_tests_and_inconsistent_results_are_rejected(self):
        for body, code, resolved, error in (
                (xml(errors=1), 1, False, False), (xml(skipped=1), 0, True, False),
                (xml(tests=0), 0, True, False), (xml(tests=2), 0, True, False),
                (xml(), 1, False, False), (xml(failures=1), 0, True, False),
                (xml(), 0, True, True), ('invalid xml', 1, False, False)):
            with self.subTest(code=code, resolved=resolved, error=error):
                with self.assertRaises(ValueError): verified_tests(body, code, resolved, error)


if __name__ == '__main__': unittest.main()
