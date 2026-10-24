from types import SimpleNamespace
import unittest
from tools.research_verifier import expected_baseline_nodes


class BaselineEvidenceTests(unittest.TestCase):
    def test_parameter_rows_need_no_added_function_definition(self):
        task = SimpleNamespace(FAIL_TO_PASS=(), PASS_TO_PASS=(), test_patch='@@ -3,1 +3,2 @@\n old\n+new parameter\n')
        xml = '<testsuites><testsuite><testcase name="test_existing[new-case]"><failure/></testcase><testcase name="test_other"/></testsuite></testsuites>'
        result = expected_baseline_nodes(xml, task)
        self.assertEqual(result['explicit_node_states'], 'NOT PROVIDED')
        self.assertEqual(result['failed_test_cases'], 1)

    def test_skipped_or_passing_cases_do_not_establish_negative_control(self):
        task = SimpleNamespace(FAIL_TO_PASS=(), PASS_TO_PASS=(), test_patch='')
        for content in ('', '<skipped/>', '<error/>'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                expected_baseline_nodes('<testsuites><testsuite><testcase name="test_original">'+content+'</testcase></testsuite></testsuites>', task)


if __name__ == '__main__': unittest.main()
