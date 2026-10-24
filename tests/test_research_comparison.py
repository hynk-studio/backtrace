"""Authored CPU fixtures: no public task content, model or provider execution."""
import copy
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import research_comparison as research


def task(identifier, repo, commit='b' * 40):
    return {'instance_id': identifier, 'repo': repo, 'base_commit': commit,
        'problem_statement': 'PRIVATE_ISSUE_SENTINEL', 'hints_text': 'PRIVATE_HINT_SENTINEL',
        'patch': 'EVALUATOR_REFERENCE_SENTINEL', 'test_patch': 'EVALUATOR_TEST_SENTINEL',
        'FAIL_TO_PASS': ['PRIVATE_TEST_NAME_SENTINEL'], 'PASS_TO_PASS': []}


def metadata_fixture(protocol, repository_count=6, tasks_per_repo=2, extra=()):
    rows = [task('fastapi_11194', 'fastapi/fastapi', 'a7f2dbe976bf72703376f0cd04487bfc4a849f83'),
            task('fastapi_12000', 'tiangolo/fastapi')]
    rows += [task('project' + str(i) + '_' + str(j), 'example/project' + str(i))
             for i in range(repository_count) for j in range(tasks_per_repo)]
    rows += list(extra)
    return pinned_metadata(protocol, rows)


def pinned_metadata(protocol, rows):
    data = b'\n'.join(json.dumps(row, sort_keys=True).encode() for row in rows) + b'\n'
    value = copy.deepcopy(protocol)
    value['selection'].update(metadata_bytes=len(data), metadata_sha256=research.digest(data),
                             distinct_ids=len(rows))
    return data, value


def candidate_fixture(protocol):
    value = copy.deepcopy(protocol)
    files = {name: b'unchanged fixture\n' for name in value['baseline']['files']}
    files['eval_config.yaml'] = b'max_tool_calls: 10\nmax_time_minutes: 1\nmax_llm_calls: 50\ncommand_timeout_seconds: 60\n'
    files['prompts/system.md'] = ('(under 8\u201310 turns)\n'
        'use `search_similar_code` with keywords from the error message\n').encode()
    files['prompts/analyzer.md'] = b'original read-only instructions\n'
    value['baseline']['files'] = {name: research.digest(data) for name, data in files.items()}
    archive = research.archive_bytes(files)
    value['baseline'].update(archive_bytes=len(archive), archive_sha256=research.digest(archive))
    prompts = {name: (research.ROOT / name).read_bytes() for name in value['prompt_files']}
    return files, archive, value, prompts


class FrozenProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = research.load_protocol()

    def test_current_runtime_and_prompts_match_recorded_pins(self):
        self.assertEqual(len(self.protocol['frozen_source_files']), 105)
        self.assertEqual(self.protocol['budget'], research.BUDGET)
        self.assertEqual(self.protocol['compute_authorization'], 'NONE')
        self.assertEqual(len(self.protocol['model']['files']), 8)

    def test_protocol_rejects_changed_prompt_or_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = copy.deepcopy(self.protocol)
            value['frozen_source_files'] = {}
            for name in value['prompt_files']:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((research.ROOT / name).read_bytes())
            path = root / 'protocol.json'
            path.write_bytes(research.encoded(value))
            self.assertEqual(research.load_protocol(path, root)['budget'], research.BUDGET)
            first = next(iter(value['prompt_files']))
            (root / first).write_bytes(b'changed prompt')
            with self.assertRaisesRegex(ValueError, 'prompt identity'):
                research.load_protocol(path, root)
            value['budget']['session_seconds'] = 330
            path.write_bytes(research.encoded(value))
            with self.assertRaisesRegex(ValueError, 'unequal budget'):
                research.load_protocol(path, root)

    def test_new_generic_control_has_no_added_diagnostic_treatment(self):
        for role in ('system', 'analyzer'):
            text = (research.ROOT / ('research/prompts/r1-' + role + '.md')).read_text().lower()
            for phrase in ('leading explanation', 'hypothes', 'posterior', 'discriminating', 'dependen'):
                self.assertNotIn(phrase, text)


class CandidateAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = research.load_protocol()

    def test_interventions_are_only_nested_prompts_and_budget_is_common(self):
        files, _, protocol, prompts = candidate_fixture(self.protocol)
        original = copy.deepcopy(files)
        arms = research.candidate_files(files, protocol, prompts)
        self.assertEqual(files, original)
        for name in files:
            if name not in ('prompts/system.md', 'prompts/analyzer.md'):
                self.assertEqual(len({arms[arm][name] for arm in research.ARMS}), 1)
        self.assertIn(b'max_tool_calls: 30', arms['R0']['eval_config.yaml'])
        self.assertIn(b'max_time_minutes: 5', arms['R0']['eval_config.yaml'])
        for role in ('system', 'analyzer'):
            name = 'prompts/' + role + '.md'
            self.assertTrue(arms['R1'][name].startswith(arms['R0'][name]))
            self.assertTrue(arms['R2'][name].startswith(arms['R1'][name]))
        arms['R2']['configs/sampling.yaml'] = b'different sampling'
        with self.assertRaisesRegex(ValueError, 'nonprompt'):
            research.validate_matched(arms, files)

    def test_changed_baseline_or_prompt_and_missing_or_extra_file_are_rejected(self):
        files, _, protocol, prompts = candidate_fixture(self.protocol)
        variants = [dict(files, **{'configs/sampling.yaml': b'changed'}),
                    dict(files, extra=b'evaluator answer'),
                    {k: v for k, v in files.items() if k != 'agent.yaml'}]
        for variant in variants:
            with self.subTest(variant=list(variant)), self.assertRaises(ValueError):
                research.candidate_files(variant, protocol, prompts)
        changed = dict(prompts)
        changed[next(iter(changed))] = b'changed'
        with self.assertRaisesRegex(ValueError, 'prompt bytes'):
            research.candidate_files(files, protocol, changed)

    def test_actual_archive_assembly_is_deterministic_private_and_never_overwrites(self):
        _, archive, protocol, _ = candidate_fixture(self.protocol)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'baseline.zip'
            source.write_bytes(archive)
            first = research.build(source, root / 'first', protocol)
            second = research.build(source, root / 'second', protocol)
            self.assertEqual(first, second)
            for name in ('R0.zip', 'R1.zip', 'R2.zip', 'assembly-receipt.json'):
                self.assertEqual((root / 'first' / name).read_bytes(), (root / 'second' / name).read_bytes())
                self.assertEqual((root / 'first' / name).stat().st_mode & 0o777, 0o600)
            before = (root / 'first' / 'R0.zip').read_bytes()
            with self.assertRaises(FileExistsError):
                research.build(source, root / 'first', protocol)
            self.assertEqual((root / 'first' / 'R0.zip').read_bytes(), before)
            source.write_bytes(archive + b'changed')
            with self.assertRaisesRegex(ValueError, 'archive identity'):
                research.build(source, root / 'third', protocol)
            self.assertFalse((root / 'third').exists())

    def test_symlink_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'real').write_bytes(b'private')
            (root / 'link').symlink_to(root / 'real')
            with self.assertRaisesRegex(ValueError, 'regular bounded'):
                research.read_file(root / 'link', 100)


class PreselectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = research.load_protocol()

    def test_six_distinct_repos_and_balanced_orders_with_no_answer_projection(self):
        data, protocol = metadata_fixture(self.protocol)
        selected = research.select_tasks(data, protocol)
        self.assertEqual(selected['status'], 'SELECTED')
        self.assertEqual(selected['planned_model_runs'], 18)
        self.assertEqual(selected['excluded_tasks'], 2)
        self.assertEqual(len({r['repo'] for r in selected['primary']}), 6)
        self.assertEqual([r['arm_order'] for r in selected['primary']],
                         [list(v) for v in itertools.permutations(research.ARMS)])
        self.assertEqual(len(selected['reserves']), 6)
        for sentinel in ('SENTINEL', 'problem_statement', 'patch', 'hints_text', 'fastapi_12000'):
            self.assertNotIn(sentinel, json.dumps(selected))
        research.validate_selection(selected)
        for position in range(3):
            for arm in research.ARMS:
                self.assertEqual(sum(r['arm_order'][position] == arm for r in selected['primary']), 2)

    def test_order_is_metadata_only_and_source_order_independent(self):
        data, protocol = metadata_fixture(self.protocol, repository_count=8, tasks_per_repo=3)
        original = research.select_tasks(data, protocol)
        rows = [json.loads(line) for line in data.splitlines()]
        for row in rows:
            row['patch'] = 'DIFFERENT_PRIVATE_ANSWER'
            row['problem_statement'] = 'DIFFERENT_PRIVATE_ISSUE'
        altered, altered_protocol = pinned_metadata(protocol, list(reversed(rows)))
        alternate = research.select_tasks(altered, altered_protocol)
        self.assertEqual(original['primary'], alternate['primary'])
        self.assertEqual(original['reserves'], alternate['reserves'])
        self.assertEqual(original['metadata_projection_sha256'], alternate['metadata_projection_sha256'])
        self.assertNotEqual(original['source_sha256'], alternate['source_sha256'])

    def test_insufficient_families_or_reserves_are_explicit_shortfalls(self):
        data, protocol = metadata_fixture(self.protocol, repository_count=3)
        result = research.select_tasks(data, protocol)
        self.assertEqual(result['status'], 'SELECTION_SHORTFALL')
        self.assertEqual(result['shortfall'], {'primary_tasks': 3, 'reserve_tasks': 3})
        self.assertEqual(result['planned_model_runs'], 9)
        data, protocol = metadata_fixture(self.protocol, tasks_per_repo=1)
        result = research.select_tasks(data, protocol)
        self.assertEqual(result['shortfall'], {'primary_tasks': 0, 'reserve_tasks': 6})

    def test_duplicate_id_even_identical_and_unknown_schema_are_rejected(self):
        data, protocol = metadata_fixture(self.protocol)
        rows = [json.loads(line) for line in data.splitlines()]
        malformed = [rows + [rows[-1]],
                     [dict(rows[0], unknown='PRIVATE_UNKNOWN_SENTINEL')] + rows[1:],
                     [dict(rows[0], repo='private invalid repo')] + rows[1:],
                     [dict(rows[0], patch=7)] + rows[1:],
                     [dict(rows[0], FAIL_TO_PASS={'hidden': 'value'})] + rows[1:]]
        for variant in malformed:
            bad, policy = pinned_metadata(protocol, variant)
            with self.subTest(variant=variant[0]['instance_id']), self.assertRaises(ValueError) as caught:
                research.select_tasks(bad, policy)
            self.assertNotIn('SENTINEL', str(caught.exception))

    def test_missing_known_exposure_or_changed_repository_fails_closed(self):
        data, protocol = metadata_fixture(self.protocol)
        rows = [json.loads(line) for line in data.splitlines()]
        for variant in (rows[1:], [dict(rows[0], repo='different/project')] + rows[1:]):
            bad, policy = pinned_metadata(protocol, variant)
            with self.assertRaises(ValueError):
                research.select_tasks(bad, policy)

    def test_wrong_pin_and_duplicate_json_key_are_rejected(self):
        data, protocol = metadata_fixture(self.protocol)
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            research.select_tasks(data + b' ', protocol)
        duplicate = data.replace(b'"instance_id": "fastapi_11194"',
            b'"instance_id": "fastapi_11194", "instance_id": "PRIVATE_DUPLICATE"', 1)
        protocol['selection'].update(metadata_sha256=research.digest(duplicate), metadata_bytes=len(duplicate))
        with self.assertRaisesRegex(ValueError, 'ambiguous JSON'):
            research.select_tasks(duplicate, protocol)

    def test_cli_rejects_unpinned_private_input_without_output_or_leak(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root / 'tasks.jsonl', root / 'result.json'
            source.write_text('PRIVATE_REFERENCE_SENTINEL')
            result = subprocess.run([sys.executable, '-m', 'tools.research_comparison',
                'select', str(source), str(target)], cwd=research.ROOT,
                capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('PRIVATE_REFERENCE_SENTINEL', result.stdout + result.stderr)
            self.assertFalse(target.exists())

    def test_exclusive_output_does_not_replace_existing_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'selection.json'
            research._new_output(target, b'first')
            with self.assertRaises(FileExistsError):
                research._new_output(target, b'second')
            self.assertEqual(target.read_bytes(), b'first')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)


class OutcomeBookkeepingTests(unittest.TestCase):
    def setUp(self):
        data, protocol = metadata_fixture(research.load_protocol())
        self.selection = research.select_tasks(data, protocol)

    def rows(self):
        return [dict(instance_id=task['instance_id'], arm=arm,
                     outcome='RESOLVED' if arm == 'R2' else 'TIMEOUT',
                     independent_evaluator_resolved=True, within_matched_budget=True)
                for task in self.selection['primary'] for arm in research.ARMS]

    def test_missing_runs_remain_in_denominator_and_have_no_effect_estimate(self):
        result = research.summarize_outcomes(self.selection, self.rows()[:3])
        self.assertEqual(result['denominator_per_arm'], 6)
        self.assertEqual(result['planned_runs'], 18)
        self.assertEqual(result['counts']['R0']['NOT_RUN'], 5)
        self.assertEqual(result['counts']['R0']['TIMEOUT'], 1)
        self.assertEqual(result['status'], 'INCOMPLETE_NO_EFFECT_ESTIMATE')
        self.assertIsNone(result['contrasts']['R2-R1']['resolved_rate_difference'])

    def test_complete_rows_produce_descriptive_paired_counts_only(self):
        rows = self.rows()
        rows[0]['outcome'] = 'INFRA_FAILURE'
        result = research.summarize_outcomes(self.selection, rows)
        self.assertEqual(result['status'], 'COMPLETE_DESCRIPTIVE_PILOT')
        self.assertEqual(result['counts']['R0']['INFRA_FAILURE'], 1)
        self.assertEqual(result['contrasts']['R2-R1']['wins'], 6)
        self.assertEqual(result['contrasts']['R2-R1']['losses'], 0)
        self.assertEqual(result['contrasts']['R2-R1']['resolved_rate_difference'], 1)
        self.assertIn('DESCRIPTIVE', result['contrasts']['R2-R1']['inference'])

    def test_false_resolution_duplicates_and_unassigned_runs_are_rejected(self):
        rows = self.rows()
        false = copy.deepcopy(rows)
        false[2]['within_matched_budget'] = False
        for variant in (false, rows + [rows[0]], [dict(rows[0], arm='R3')]):
            with self.assertRaises(ValueError):
                research.summarize_outcomes(self.selection, variant)

    def test_shortfall_or_duplicate_primary_cannot_become_complete_study(self):
        data, protocol = metadata_fixture(research.load_protocol(), repository_count=3)
        short = research.select_tasks(data, protocol)
        with self.assertRaisesRegex(ValueError, 'shortfall'):
            research.summarize_outcomes(short, [])
        duplicate = copy.deepcopy(self.selection)
        duplicate['primary'][1]['instance_id'] = duplicate['primary'][0]['instance_id']
        with self.assertRaisesRegex(ValueError, 'identities'):
            research.summarize_outcomes(duplicate, [])
        duplicate = copy.deepcopy(self.selection)
        duplicate['primary'][1]['repo'] = duplicate['primary'][0]['repo']
        with self.assertRaisesRegex(ValueError, 'diversity'):
            research.summarize_outcomes(duplicate, [])


if __name__ == '__main__':
    unittest.main()
