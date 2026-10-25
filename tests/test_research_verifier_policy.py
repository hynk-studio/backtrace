from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

from tools import research_comparison as c
from tools.research_verifier_policy import check_exception, identity, inspect_xml


class VersionSkipPolicyTests(unittest.TestCase):
    def setUp(self):
        self.task = SimpleNamespace(instance_id='authored_task', test_patch='authored original tests')
        self.rule = {'instance_id': self.task.instance_id, 'python_version': '3.12.14',
                     'test_patch_sha256': c.digest(self.task.test_patch.encode()),
                     'skipped_function_name_sha256': c.digest(b'test_old_python')}
        self.xml = ('<testsuites><testsuite tests="3" failures="0" errors="0" skipped="1">'
                    '<testcase classname="test_module" name="test_old_python"><skipped/></testcase>'
                    '<testcase classname="test_module" name="test_current_python"/>'
                    '<testcase classname="test_module" name="test_existing"/>'
                    '</testsuite></testsuites>')
        self.required = ['test_old_python', 'test_current_python']
        self.validate = Mock(return_value=(True, None))

    def check(self, xml=None, version='3.12.14', required=None, task=None):
        return check_exception(xml or self.xml, task or self.task, version, self.rule,
                               self.required if required is None else required, self.validate)

    def test_excludes_only_pinned_requirement_and_preserves_original_xml(self):
        self.assertEqual(self.check(), 'test_old_python')
        self.validate.assert_called_once_with(self.xml, fail_to_pass=('test_current_python',))

    def test_rejects_other_python_or_test_patch(self):
        for version, task in [('3.13.0', self.task), ('3.12.14',
                SimpleNamespace(instance_id='authored_task', test_patch='different')),
                ('3.12.14', SimpleNamespace(instance_id='other', test_patch=self.task.test_patch))]:
            with self.subTest(version=version, task=task), self.assertRaises(ValueError):
                self.check(version=version, task=task)
        self.validate.assert_not_called()

    def test_skipped_function_cannot_be_missing_or_substituted(self):
        for name in ('test_other', 'test_old_python[param]'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.check(self.xml.replace('test_old_python', name))
        for required in ([], ['test_old_python'], ['test_current_python'],
                         ['test_old_python', 'test_old_python', 'test_current_python']):
            with self.subTest(required=required), self.assertRaises(ValueError):
                self.check(required=required)

    def test_remaining_requirements_still_use_original_validator(self):
        self.validate.return_value = (False, 'required node absent')
        with self.assertRaisesRegex(ValueError, 'remaining original'):
            self.check()

    def test_extra_skip_failure_or_error_rejected_even_with_consistent_counts(self):
        for tag, count in [('skipped', 'skipped'), ('failure', 'failures'), ('error', 'errors')]:
            root = ET.fromstring(self.xml)
            ET.SubElement(root.findall('.//testcase')[1], tag)
            root.find('testsuite').set(count, '2' if tag == 'skipped' else '1')
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.check(ET.tostring(root, encoding='unicode'))

    def test_duplicate_case_or_fabricated_suite_counts_rejected(self):
        root = ET.fromstring(self.xml)
        suite = root.find('testsuite')
        suite.append(ET.fromstring('<testcase classname="test_module" name="test_existing"/>'))
        suite.set('tests', '4')
        with self.assertRaises(ValueError): self.check(ET.tostring(root, encoding='unicode'))
        with self.assertRaises(ValueError): self.check(self.xml.replace('tests="3"', 'tests="4"'))

    def test_no_test_or_ambiguous_case_is_not_execution_evidence(self):
        for body in ('<testsuites/>', '<bad', self.xml.replace('<skipped/>', '<skipped/><failure/>')):
            with self.subTest(body=body), self.assertRaises(ValueError): inspect_xml(body)

    def test_amendment_keeps_eighteen_slots_and_no_paid_authorization(self):
        result = identity()
        self.assertEqual(result['planned_slots'], 18)
        self.assertEqual(result['compute_authorization'], 'NONE')
        self.assertEqual(result['protocol'], 'R012-matched-pilot-v3-version-skip')


if __name__ == '__main__': unittest.main()
