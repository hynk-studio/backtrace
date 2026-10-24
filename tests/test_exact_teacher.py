"""Analytic probability/decision witnesses and leakage/reproducibility checks."""
from copy import deepcopy
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import exact_teacher as teacher


def sensor_question():
    """H~Bernoulli(1/2), P(S=H)=3/4: hand-computable Bayes/EVSI."""
    return {'schema_version': 1, 'model': {'nodes': [
        {'id': 'h', 'parents': [], 'p_true': {'': '1/2'}},
        {'id': 's', 'parents': ['h'], 'p_true': {'0': '1/4', '1': '3/4'}},
    ]}, 'evidence': [],
        'hypotheses': [{'id': 'h_true', 'condition': [{'h': True}]},
                       {'id': 'h_false', 'condition': [{'h': False}]}],
        'queries': [{'id': 'h', 'condition': [{'h': True}]}],
        'actions': [{'id': 'yes', 'condition': [{'h': True}], 'if_true': '1', 'if_false': '0'},
                    {'id': 'no', 'condition': [{'h': False}], 'if_true': '1', 'if_false': '0'}],
        'inspections': [{'event': 's', 'cost': '1/10'}]}


class ExactProbabilityTests(unittest.TestCase):
    def test_bayes_revision_has_independent_analytic_answer(self):
        question = sensor_question()
        question['model']['nodes'][0]['p_true'][''] = '1/4'
        question['model']['nodes'][1]['p_true'] = {'0': '1/10', '1': '9/10'}
        question['evidence'] = [{'id': 'reading', 'event': 's', 'value': True}]
        answer = teacher.solve(question)
        # (1/4*9/10)/(1/4*9/10+3/4*1/10) = 3/4, reversing prior leader.
        self.assertEqual(answer['evidence_probability'], '3/10')
        self.assertEqual(answer['posterior']['h_true'], '3/4')
        self.assertEqual(answer['prior_leaders'], ['h_false'])
        self.assertEqual(answer['posterior_leaders'], ['h_true'])
        self.assertTrue(answer['leader_overturned'])
        self.assertEqual(answer['queries']['h']['logical_status'], 'UNKNOWN')

    def test_same_observation_copies_do_not_multiply_likelihood(self):
        question = sensor_question()
        observation = {'id': 'original', 'event': 's', 'value': True}
        question['evidence'] = [observation]
        baseline = teacher.solve(question)
        question['evidence'] += [dict(observation), dict(observation, id='copied')]
        repeated = teacher.solve(question)
        self.assertEqual(repeated['posterior'], baseline['posterior'])
        self.assertEqual(repeated['evidence_probability'], baseline['evidence_probability'])
        self.assertEqual(repeated['observations']['duplicate_records_ignored'], 2)
        self.assertEqual(repeated['posterior']['h_true'], '3/4')

    def test_distinct_but_dependent_sensors_still_do_not_double_count(self):
        question = sensor_question()
        question['model']['nodes'].append({'id': 'copy', 'parents': ['s'], 'p_true': {'0': '0', '1': '1'}})
        question['evidence'] = [{'id': 'first', 'event': 's', 'value': True},
                                {'id': 'second', 'event': 'copy', 'value': True}]
        answer = teacher.solve(question)
        self.assertEqual(answer['posterior']['h_true'], '3/4')
        self.assertNotEqual(answer['posterior']['h_true'], '9/10')
        self.assertEqual(answer['observations']['duplicate_records_ignored'], 0)

    def test_new_conditionally_independent_draw_does_update(self):
        question = sensor_question()
        question['model']['nodes'].append({'id': 'new_draw', 'parents': ['h'], 'p_true': {'0': '1/4', '1': '3/4'}})
        question['evidence'] = [{'id': 'first', 'event': 's', 'value': True},
                                {'id': 'second', 'event': 'new_draw', 'value': True}]
        self.assertEqual(teacher.solve(question)['posterior']['h_true'], '9/10')

    def test_simultaneous_causes_are_not_forced_into_one_normalized_label(self):
        question = sensor_question()
        question['model']['nodes'] = [
            {'id': 'a', 'parents': [], 'p_true': {'': '1/2'}},
            {'id': 'b', 'parents': [], 'p_true': {'': '1/2'}},
            {'id': 'alarm', 'parents': ['a', 'b'], 'p_true': {'00': '0', '01': '1', '10': '1', '11': '1'}},
        ]
        question['hypotheses'] = [{'id': 'a', 'condition': [{'a': True}]},
                                  {'id': 'b', 'condition': [{'b': True}]},
                                  {'id': 'both', 'condition': [{'a': True, 'b': True}]}]
        question['queries'] = [{'id': 'either', 'condition': [{'a': True}, {'b': True}]}]
        question['actions'] = [{'id': 'wait', 'condition': [{}], 'if_true': '0', 'if_false': '0'}]
        question['inspections'] = []
        question['evidence'] = [{'id': 'reading', 'event': 'alarm', 'value': True}]
        answer = teacher.solve(question)
        self.assertEqual(answer['posterior'], {'a': '2/3', 'b': '2/3', 'both': '1/3'})
        self.assertEqual(answer['queries']['either']['logical_status'], 'ENTAILED')
        self.assertEqual(answer['posterior_leaders'], ['a', 'b'])

    def test_forward_prediction_uses_conditional_joint_not_prior(self):
        question = sensor_question()
        question['model']['nodes'].append({'id': 'next', 'parents': ['h'], 'p_true': {'0': '1/4', '1': '3/4'}})
        question['evidence'] = [{'id': 'reading', 'event': 's', 'value': True}]
        answer = teacher.solve(question)
        # 3/4*3/4 + 1/4*1/4 = 5/8.
        self.assertEqual(answer['predictions']['next'], '5/8')
        self.assertEqual(answer['hypothesis_predictions']['h_true']['predictions']['next'], '3/4')
        self.assertEqual(answer['hypothesis_predictions']['h_false']['predictions']['next'], '1/4')

    def test_zero_probability_hypothesis_has_undefined_forward_prediction(self):
        question = sensor_question()
        question['evidence'] = [{'id': 'seen', 'event': 'h', 'value': True}]
        answer = teacher.solve(question)
        self.assertEqual(answer['hypothesis_predictions']['h_false'],
                         {'status': 'ZERO_PROBABILITY_CONDITION', 'predictions': None})
        self.assertEqual(answer['hypothesis_predictions']['h_true']['predictions']['s'], '3/4')

    def test_contradiction_model_mismatch_and_unknown_are_distinct(self):
        question = sensor_question()
        self.assertEqual(teacher.solve(question)['queries']['h']['logical_status'], 'UNKNOWN')
        question['evidence'] = [{'id': 'first', 'event': 's', 'value': True},
                                {'id': 'second', 'event': 's', 'value': False}]
        conflict = teacher.solve(question)
        self.assertEqual(conflict['status'], 'INCONSISTENT_EVIDENCE')
        self.assertIsNone(conflict['posterior'])
        question['model']['nodes'][1]['p_true'] = {'0': '0', '1': '1'}
        question['evidence'] = [{'id': 'h_seen', 'event': 'h', 'value': False},
                                {'id': 's_seen', 'event': 's', 'value': True}]
        mismatch = teacher.solve(question)
        self.assertEqual(mismatch['status'], 'MODEL_MISMATCH')
        self.assertEqual(mismatch['evidence_probability'], '0')
        self.assertIsNone(mismatch['decision'])
        question['evidence'] = [{'id': 's_seen', 'event': 's', 'value': False}]
        self.assertEqual(teacher.solve(question)['queries']['h']['logical_status'], 'REFUTED')

    def test_conflicting_reuse_of_evidence_id_is_malformed_input(self):
        question = sensor_question()
        question['evidence'] = [{'id': 'same', 'event': 's', 'value': True},
                                {'id': 'same', 'event': 'h', 'value': True}]
        with self.assertRaisesRegex(ValueError, 'one evidence ID'):
            teacher.solve(question)


class ExactDecisionTests(unittest.TestCase):
    def test_one_step_inspection_value_and_cost_are_exact(self):
        answer = teacher.solve(sensor_question())
        inspection = answer['inspections']['s']
        self.assertEqual(answer['decision']['best_actions'], ['no', 'yes'])
        self.assertEqual(answer['decision']['best_value'], '1/2')
        self.assertEqual(inspection['expected_best_action_value'], '3/4')
        self.assertEqual(inspection['gross_value'], '1/4')
        self.assertEqual(inspection['net_value'], '3/20')
        self.assertEqual(answer['recommendation']['mode'], 'INSPECT')

    def test_informative_test_can_have_no_decision_value(self):
        question = sensor_question()
        # Positive action is profitable only above P(H)=9/10; neither outcome crosses it.
        question['actions'] = [{'id': 'act', 'condition': [{'h': True}], 'if_true': '1', 'if_false': '-9'},
                               {'id': 'defer', 'condition': [{}], 'if_true': '0', 'if_false': '0'}]
        answer = teacher.solve(question)
        inspection = answer['inspections']['s']
        self.assertTrue(inspection['informative_about_hypotheses'])
        self.assertEqual(inspection['gross_value'], '0')
        self.assertEqual(inspection['net_value'], '-1/10')
        self.assertEqual(answer['recommendation']['mode'], 'STOP')

    def test_high_cost_and_zero_net_tie_choose_stop(self):
        question = sensor_question()
        for cost in ('1/4', '1/2'):
            with self.subTest(cost=cost):
                question['inspections'][0]['cost'] = cost
                answer = teacher.solve(question)
                self.assertEqual(answer['recommendation']['mode'], 'STOP')
                self.assertEqual(answer['recommendation']['zero_net_ties'], ['s'] if cost == '1/4' else [])

    def test_all_optimal_tests_and_actions_are_retained(self):
        question = sensor_question()
        question['model']['nodes'].append({'id': 'twin', 'parents': ['h'], 'p_true': {'0': '1/4', '1': '3/4'}})
        question['inspections'].append({'event': 'twin', 'cost': '1/10'})
        answer = teacher.solve(question)
        self.assertEqual(answer['recommendation']['inspections'], ['s', 'twin'])
        self.assertEqual(answer['decision']['best_actions'], ['no', 'yes'])

    def test_reinspecting_observed_event_has_zero_gross_value(self):
        question = sensor_question()
        question['evidence'] = [{'id': 'seen', 'event': 's', 'value': True}]
        inspection = teacher.solve(question)['inspections']['s']
        self.assertTrue(inspection['already_observed'])
        self.assertEqual(inspection['gross_value'], '0')
        self.assertEqual(inspection['net_value'], '-1/10')


class TeacherValidationTests(unittest.TestCase):
    def test_bad_numeric_and_probability_inputs_are_rejected(self):
        for value in (True, 0.5, 'nan', '1/0', '-1/3', '4/3', '9'*80):
            question = sensor_question()
            question['model']['nodes'][0]['p_true'][''] = value
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                teacher.solve(question)

    def test_invalid_dag_missing_cpt_and_extra_answer_field_rejected(self):
        cases = []
        question = sensor_question(); question['model']['nodes'][0]['parents'] = ['s']; cases.append(question)
        question = sensor_question(); del question['model']['nodes'][1]['p_true']['0']; cases.append(question)
        question = sensor_question(); question['answer'] = {'h_true': '1/2'}; cases.append(question)
        question = sensor_question(); question['inspections'][0]['cost'] = '-1'; cases.append(question)
        for case in cases:
            with self.assertRaises(ValueError): teacher.solve(case)

    def test_resource_limit_is_error_not_world_label(self):
        question = sensor_question()
        question['model']['nodes'] += [
            {'id': f'extra{i}', 'parents': [], 'p_true': {'': '1/2'}} for i in range(7)]
        with self.assertRaisesRegex(ValueError, 'teacher bound'):
            teacher.solve(question)

    def test_signature_ignores_names_and_unused_declared_parents(self):
        first = sensor_question()
        renamed = json.loads(json.dumps(first).replace('"h"', '"cause"').replace('"s"', '"sensor"'))
        self.assertEqual(teacher.structural_signature(first), teacher.structural_signature(renamed))
        padded = deepcopy(first)
        padded['model']['nodes'][1]['p_true'] = {'0': '1/2', '1': '1/2'}
        independent = deepcopy(padded)
        independent['model']['nodes'][1]['parents'] = []
        independent['model']['nodes'][1]['p_true'] = {'': '1/2'}
        self.assertEqual(teacher.structural_signature(padded), teacher.structural_signature(independent))
        self.assertNotEqual(teacher.structural_signature(first), teacher.structural_signature(padded))


class DatasetTests(unittest.TestCase):
    def setUp(self):
        local = teacher.ROOT / '.local'
        local.mkdir(mode=0o700, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='teacher-test-', dir=local)
        self.addCleanup(self.temp.cleanup)

    def test_reproducible_files_and_exact_labels_audit(self):
        first, second = Path(self.temp.name) / 'first', Path(self.temp.name) / 'second'
        manifest = teacher.write_dataset(first)
        self.assertEqual(manifest, teacher.write_dataset(second))
        self.assertEqual(teacher.audit_dataset(first), manifest['audit'])
        for name in [*manifest['files'], 'manifest.json']:
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
            self.assertEqual(os.stat(first / name).st_mode & 0o777, 0o600)
        self.assertEqual(manifest['audit']['counts'], {'train': 24, 'eval': 24})
        self.assertFalse(set(manifest['audit']['structural_signatures']['train']) &
                         set(manifest['audit']['structural_signatures']['eval']))

    def test_no_overwrite_and_no_output_outside_local_root(self):
        target = Path(self.temp.name) / 'dataset'
        teacher.write_dataset(target, 1)
        before = (target / 'manifest.json').read_bytes()
        with self.assertRaises(FileExistsError): teacher.write_dataset(target, 1)
        self.assertEqual((target / 'manifest.json').read_bytes(), before)
        with self.assertRaises(ValueError): teacher.write_dataset('/tmp/teacher-output-not-allowed', 1)

    def test_agent_projection_has_no_answers_family_or_sampled_truth(self):
        data, audit = teacher.generate()
        forbidden = {'answer', 'family', 'split', 'true_world', 'latent_causes', 'future_observations',
                     'structural_signature', 'posterior', 'recommendation'}
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(set(value) & forbidden)
                for child in value.values(): check(child)
            elif isinstance(value, list):
                for child in value: check(child)
        for split in data:
            for row in data[split]['agent']: check(row)
            for key in ('INCONSISTENT_EVIDENCE', 'MODEL_MISMATCH', 'STOP', 'INSPECT',
                        'duplicate_evidence_cases', 'prior_leader_overturned', 'possible_simultaneous_causes',
                        'informative_zero_value_cases', 'cost_blocks_positive_value_cases',
                        'query_entailed', 'query_refuted', 'query_unknown'):
                self.assertGreater(audit['coverage'][split][key], 0, (split, key))
        choices = [row['answer']['recommendation']['inspections']
                   for split in data for row in data[split]['evaluator']
                   if row['answer']['status'] == 'OK'
                   and row['answer']['recommendation']['mode'] == 'INSPECT']
        self.assertTrue(any('v0' not in selected for selected in choices), choices)

    def test_generated_logic_cases_infer_unobserved_target(self):
        for family in teacher.FAMILIES:
            question = teacher.make_question(family, 6)
            self.assertNotIn('v0', {item['event'] for item in question['evidence']})
            answer = teacher.solve(question)
            self.assertEqual(answer['status'], 'OK')
            self.assertEqual(answer['queries']['h_true']['logical_status'], 'ENTAILED')
            self.assertEqual(answer['queries']['h_false']['logical_status'], 'REFUTED')

    def test_structural_family_mislabel_and_same_family_cross_split_rejected(self):
        data, _ = teacher.generate(1)
        data['train']['evaluator'][0]['family'] = 'shared_noise'
        with self.assertRaisesRegex(ValueError, 'declared family structure'):
            teacher.audit_records(data)
        data, _ = teacher.generate(1)
        data['eval']['agent'][0] = deepcopy(data['train']['agent'][0])
        data['eval']['evaluator'][0] = deepcopy(data['train']['evaluator'][0])
        with self.assertRaises(ValueError): teacher.audit_records(data)

    def test_label_tamper_and_leaked_agent_field_rejected(self):
        data, _ = teacher.generate(1)
        data['eval']['evaluator'][0]['answer']['status'] = 'MODEL_MISMATCH'
        with self.assertRaisesRegex(ValueError, 'exact label mismatch'): teacher.audit_records(data)
        data, _ = teacher.generate(1)
        data['eval']['agent'][0]['question']['answer'] = data['eval']['evaluator'][0]['answer']
        with self.assertRaises(ValueError): teacher.audit_records(data)

    def test_bounded_maximum_generation_is_unique_and_deterministic(self):
        data, audit = teacher.generate(teacher.MAX_VARIANTS)
        self.assertEqual(audit['counts'], {'train': 384, 'eval': 384})
        self.assertEqual(len({row['id'] for row in data['train']['agent']}), 384)

    def test_cli_round_trip_and_manifest_tamper(self):
        destination = Path(self.temp.name) / 'cli'
        generated = subprocess.run([sys.executable, '-m', 'tools.exact_teacher', 'generate',
                                    str(destination), '--variants-per-family', '8'],
                                   cwd=teacher.ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        audited = subprocess.run([sys.executable, '-m', 'tools.exact_teacher', 'audit', str(destination)],
                                 cwd=teacher.ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(audited.returncode, 0, audited.stderr)
        manifest_path = destination / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files']['train/agent.jsonl']['sha256'] = '0'*64
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'hash/count mismatch'): teacher.audit_dataset(destination)


if __name__ == '__main__':
    unittest.main()
