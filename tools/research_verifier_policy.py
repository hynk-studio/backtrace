"""Versioned research verdict beside the unchanged official verdict.

No test, patch, XML, or installed official code is modified. The only exception
is one hash-bound original version skip, before any matched model outcome.
"""
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

from tools import research_comparison as c
from tools.qualify_evaluation import verified_tests

PATH = c.ROOT / 'docs/research-verifier-amendment-20261025.json'


def load_policy():
    data = c.read_file(PATH, 16384)
    value = c.parse(data)
    if (value['schema_version'] != 1 or value['protocol'] != 'R012-matched-pilot-v3-version-skip'
            or value['status'] != 'ACTIVE_FOR_CPU_QUALIFICATION'
            or value['compute_authorization'] != 'NONE'
            or value['applies_to_arms'] != list(c.ARMS)
            or value['planned_tasks'] != 6 or value['planned_slots'] != 18):
        raise ValueError('unrecognized research verifier amendment')
    c.load_protocol()
    for name, expected in value['bindings'].items():
        if c.digest(c.read_file(c.ROOT / name, 1024**2)) != expected:
            raise ValueError('research amendment base identity changed')
    return value


def identity():
    value = load_policy()
    return {'protocol': value['protocol'], 'amendment_sha256': c.digest(PATH.read_bytes()),
            'base_protocol_sha256': value['bindings']['docs/research-comparison-protocol.json'],
            'planned_slots': value['planned_slots'], 'compute_authorization': 'NONE'}


def inspect_xml(xml):
    """Reconcile actual testcase states, not just self-reported suite counts."""
    if not xml or len(xml.encode()) > 4 * 1024**2:
        raise ValueError('bounded actual JUnit required')
    try:
        root = ET.fromstring(xml)
        suites = [root] if root.tag == 'testsuite' else root.findall('.//testsuite')
        counts = {k: sum(int(s.get(k, '0')) for s in suites)
                  for k in ('tests', 'failures', 'errors', 'skipped')}
        nodes = root.findall('.//testcase')
        keys = [(n.get('classname', ''), n.get('name', '')) for n in nodes]
        actual = {'tests': len(nodes), 'failures': 0, 'errors': 0, 'skipped': 0}
        for node in nodes:
            flags = [node.find(k) is not None for k in ('failure', 'error', 'skipped')]
            if sum(flags) > 1:
                raise ValueError('ambiguous testcase status')
            for key, present in zip(('failures', 'errors', 'skipped'), flags):
                actual[key] += present
        if (not suites or not nodes or counts != actual or len(set(keys)) != len(keys)
                or any(not name for _, name in keys)):
            raise ValueError('inconsistent or duplicate actual JUnit cases')
    except (ET.ParseError, TypeError, ValueError) as error:
        raise ValueError('invalid actual JUnit structure') from error
    return counts, nodes


def check_exception(xml, task, python_version, rule, required, validate):
    """Return the single excluded requirement; validate all others unchanged."""
    if (task.instance_id != rule['instance_id'] or python_version != rule['python_version']
            or c.digest(task.test_patch.encode()) != rule['test_patch_sha256']):
        raise ValueError('version-skip identity mismatch')
    counts, nodes = inspect_xml(xml)
    skipped = [n for n in nodes if n.find('skipped') is not None]
    if (counts['errors'] or counts['failures'] or counts['skipped'] != 1
            or c.digest(skipped[0].get('name', '').encode()) != rule['skipped_function_name_sha256']):
        raise ValueError('only the one original version skip is permitted')
    name = skipped[0].get('name')
    if required.count(name) != 1 or len(required) < 2:
        raise ValueError('original skipped and applicable required nodes must both exist')
    remaining = [r for r in required if r != name]
    valid, _ = validate(xml, fail_to_pass=tuple(remaining))
    if not valid:
        raise ValueError('remaining original required tests did not all pass')
    return name


def score(xml, task, result, python_version):
    """Actual official implementation supplies requirements and both checks."""
    policy = load_policy()
    verdict = {'protocol': policy['protocol'], 'official_resolved': result.resolved,
               'research_resolved': result.resolved, 'exception_applied': False}
    if task.instance_id != policy['exception']['instance_id'] or result.test_exit_code != 0:
        verdict['actual_tests'] = verified_tests(xml, result.test_exit_code, result.resolved,
                                                bool(result.error_message))
        return verdict
    from swegemma.harness import verification as official
    rule = policy['exception']
    if c.digest(Path(official.__file__).read_bytes()) != rule['official_verification_source_sha256']:
        raise ValueError('original official verifier source changed')
    required = list(task.FAIL_TO_PASS) + list(task.PASS_TO_PASS)
    if not required:
        required = official._extract_test_functions_from_patch(task.test_patch)
    name = check_exception(xml, task, python_version, rule, required, official._validate_junit_xml)
    valid, reason = official._validate_junit_xml(xml, task.FAIL_TO_PASS, task.PASS_TO_PASS, task.test_patch)
    if (valid or result.resolved or reason != 'Required test node did not pass: ' + name
            or result.error_message != reason):
        raise ValueError('official rejection is not solely the pinned version skip')
    # Do not hide setup/agent errors or a no-tests stdout behind this exception.
    stdout = result.test_output.split('STDERR:', 1)[0].lower()
    import re
    if ('passed' not in stdout or 'no tests ran' in stdout or 'collected 0 items' in stdout
            or re.search(r'\b0 passed\b', stdout)):
        raise ValueError('actual pytest passing summary required')
    verdict.update(research_resolved=True, exception_applied=True,
                   excluded_required_node_sha256=c.digest(name.encode()),
                   applicable_required_nodes=len(required)-1,
                   actual_tests=verified_tests(xml, 0, True, False))
    return verdict


def mutation_controls(xml, task, result, python_version):
    """Counterfactual JUnit controls, explicitly never model scores."""
    root = ET.fromstring(xml)
    nodes = root.findall('.//testcase')
    skipped = next(n for n in nodes if n.find('skipped') is not None)
    passed = next(n for n in nodes if all(n.find(k) is None for k in ('failure', 'error', 'skipped')))
    copies = []
    def mutated(label, change):
        copy = ET.fromstring(xml)
        change(copy)
        copies.append((label, ET.tostring(copy, encoding='unicode'), task, result, python_version))
    def target(copy, name):
        return next(n for n in copy.findall('.//testcase') if n.get('name') == name)
    def remove(copy, name):
        node = target(copy, name)
        next(p for p in copy.iter() if node in list(p)).remove(node)
    def reconcile(copy):
        for suite in copy.iter('testsuite'):
            cases = suite.findall('testcase')
            for key, tag in (('failures', 'failure'), ('errors', 'error'), ('skipped', 'skipped')):
                suite.set(key, str(sum(n.find(tag) is not None for n in cases)))
            suite.set('tests', str(len(cases)))
    for state in ('skipped', 'failure', 'error'):
        def change(copy, state=state):
            ET.SubElement(target(copy, passed.get('name')), state); reconcile(copy)
        mutated('additional_'+state, change)
    def missing(copy): remove(copy, skipped.get('name')); reconcile(copy)
    mutated('missing_original_skip', missing)
    def renamed(copy): target(copy, skipped.get('name')).set('name', 'unrelated_skip')
    mutated('different_skip', renamed)
    mutated('inconsistent_counts', lambda copy: next(copy.iter('testsuite')).set('tests', '99999'))
    def duplicate(copy):
        suite = next(copy.iter('testsuite'))
        suite.append(ET.fromstring(ET.tostring(passed))); reconcile(copy)
    mutated('duplicate_case', duplicate)
    from swegemma.harness.verification import _extract_test_functions_from_patch
    required = list(task.FAIL_TO_PASS) + list(task.PASS_TO_PASS) or _extract_test_functions_from_patch(task.test_patch)
    applicable = next(n for n in nodes if n.get('name') in required and n is not skipped)
    def missing_required(copy): remove(copy, applicable.get('name')); reconcile(copy)
    mutated('missing_applicable_required', missing_required)
    copies.append(('wrong_python', xml, task, result, '3.11.0'))
    copies.append(('different_test_patch', xml, SimpleNamespace(instance_id=task.instance_id,
        test_patch=task.test_patch+'\n', FAIL_TO_PASS=task.FAIL_TO_PASS, PASS_TO_PASS=task.PASS_TO_PASS),
        result, python_version))
    altered = SimpleNamespace(resolved=False, test_exit_code=0, test_output=result.test_output,
                              error_message='unrelated evaluation failure')
    copies.append(('different_official_error', xml, task, altered, python_version))
    checks = {}
    for label, body, candidate_task, candidate_result, version in copies:
        try:
            outcome = score(body, candidate_task, candidate_result, version)
            checks[label] = not outcome['research_resolved']
        except ValueError:
            checks[label] = True
    if not all(checks.values()):
        raise ValueError('version-skip mutation control failed')
    return {'status': 'PASS', 'cases': checks, 'scope': 'mutated evaluator receipts; no model result'}
