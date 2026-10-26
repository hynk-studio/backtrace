"""Independent analytic witnesses, partition/export boundaries and negative controls."""
from copy import deepcopy
from fractions import Fraction
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import abductive_benchmark as bench
from tools import abductive_scoring as score
from tools import exact_teacher as exact


def sensor():
    return {'schema_version': 1, 'model': {'nodes': [
        {'id': 'h', 'parents': [], 'p_true': {'': '1/2'}},
        {'id': 's', 'parents': ['h'], 'p_true': {'0': '1/4', '1': '3/4'}}]},
        'evidence': [], 'hypotheses': [{'id': 'h', 'condition': [{'h': True}]}],
        'queries': [{'id': 'h', 'condition': [{'h': True}]}],
        'actions': [{'id': 'yes', 'condition': [{'h': True}], 'if_true': '1', 'if_false': '0'},
                    {'id': 'no', 'condition': [{'h': False}], 'if_true': '1', 'if_false': '0'}],
        'inspections': [{'event': 's', 'cost': '1/10'}]}


def payload():
    return {'task': 'inference', 'question': sensor()}


class AnalyticScoringTests(unittest.TestCase):
    def test_regret_charges_inspection_and_actual_branch_actions(self):
        question = payload()
        answer = {'status': 'OK', 'posterior': {'h': '1/2'}, 'decision': {'mode': 'STOP', 'action': 'yes'}}
        result = score.score_case(question, answer)
        self.assertEqual(result['losses']['posterior_mae'], 0)
        self.assertAlmostEqual(result['losses']['normalized_decision_regret'], 3/22)
        answer['decision'] = {'mode': 'INSPECT', 'event': 's', 'outcome_actions': {'false': 'yes', 'true': 'yes'}}
        self.assertAlmostEqual(score.score_case(question, answer)['losses']['normalized_decision_regret'], 5/22)
        answer['decision']['outcome_actions']['false'] = 'no'
        self.assertEqual(score.score_case(question, answer)['losses']['normalized_decision_regret'], 0)

    def test_overlap_is_not_forced_to_sum_to_one(self):
        question = payload()
        question['question']['hypotheses'] += [{'id': 'another_name', 'condition': [{'h': True}]}]
        question['question']['evidence'] = [{'id': 'seen', 'event': 's', 'value': True}]
        response = score.optimal_response(question)
        self.assertEqual(response['posterior'], {'h': '3/4', 'another_name': '3/4'})
        self.assertEqual(score.score_case(question, response)['losses']['posterior_mae'], 0)

    def test_zero_range_and_impossible_inspection_branch(self):
        question = payload()
        question['question']['actions'] = [{'id': 'wait', 'condition': [{}], 'if_true': '0', 'if_false': '0'}]
        question['question']['inspections'][0]['cost'] = '0'
        question['question']['evidence'] = [{'id': 'known', 'event': 's', 'value': True}]
        response = score.optimal_response(question)
        self.assertEqual(response['decision'], {'mode': 'STOP', 'action': 'wait'})
        response['decision'] = {'mode': 'INSPECT', 'event': 's', 'outcome_actions': {'false': 'wait', 'true': 'wait'}}
        self.assertEqual(score.score_case(question, response)['losses']['normalized_decision_regret'], 0)

    def test_invalid_or_missing_predictions_receive_maximum_loss(self):
        for answer in (None, 'not json', '{"status":"OK","status":"OK"}', {'status': 'OK'},
                       dict(score.optimal_response(payload()), answer='leaked')):
            with self.subTest(answer=answer):
                result = score.score_case(payload(), answer)
                self.assertEqual(result['response_status'], 'INVALID')
                self.assertTrue(all(v == 1 for v in result['losses'].values()))
        result = score.score_case(payload(), None, missing=True)
        self.assertEqual(result['response_status'], 'MISSING')
        self.assertEqual(result['losses']['posterior_mae'], 1)

    def test_false_abstention_cannot_escape_probability_denominator(self):
        answer = {'status': 'MODEL_MISMATCH', 'posterior': None, 'decision': None}
        result = score.score_case(payload(), answer)
        self.assertEqual(result['response_status'], 'VALID')
        self.assertEqual(result['losses']['posterior_mae'], 1)
        self.assertEqual(result['losses']['normalized_decision_regret'], 1)

    def test_undefined_reference_scores_status_without_fabricated_probability(self):
        question = payload()
        question['question']['evidence'] = [{'id': 'a', 'event': 's', 'value': True},
                                             {'id': 'b', 'event': 's', 'value': False}]
        result = score.score_case(question, score.optimal_response(question))
        self.assertEqual(result['losses'], {'status_error': 0})
        self.assertNotIn('posterior_mae', result['losses'])

    def test_long_exact_rationals_float_nan_and_boolean_handling(self):
        self.assertEqual(score.probability('123456789/987654321'), Fraction(123456789, 987654321))
        self.assertEqual(score.probability(0.75), Fraction(3, 4))
        self.assertEqual(score.probability('0.75'), Fraction(3, 4))
        for bad in (True, float('nan'), float('inf'), -0.1, '1/0', '9'*200, 2):
            with self.subTest(bad=str(bad)), self.assertRaises(ValueError):
                score.probability(bad)


class AbductionAndTimeTests(unittest.TestCase):
    def test_ambiguous_simultaneous_causes_have_three_explanations(self):
        question = {'task': 'abduction', 'model': {'nodes': [
            {'id': 'a', 'parents': [], 'p_true': {'': '1/2'}},
            {'id': 'b', 'parents': [], 'p_true': {'': '1/2'}},
            {'id': 'alarm', 'parents': ['a', 'b'], 'p_true': {'00': '0', '01': '1', '10': '1', '11': '1'}}]},
            'evidence': [{'id': 'seen', 'event': 'alarm', 'value': True}],
            'cause_variables': ['a', 'b'], 'prediction_events': ['a', 'b'], 'max_explanations': 8}
        response = score.optimal_response(question)
        self.assertEqual(len(response['explanations']), 3)
        self.assertEqual({e['probability'] for e in response['explanations']}, {'1/3'})
        self.assertIn({'a': True, 'b': True}, [e['assignment'] for e in response['explanations']])
        response['explanations'].reverse()
        self.assertTrue(all(v == 0 for v in score.score_case(question, response)['losses'].values()))
        response['explanations'] = [response['explanations'][0]]
        response['explanations'][0]['probability'] = '1'
        losses = score.score_case(question, response)['losses']
        self.assertAlmostEqual(losses['posterior_mae'], 1/3)
        self.assertAlmostEqual(losses['hypothesis_recall_error'], 2/3)
        response['explanations'] *= 2
        self.assertEqual(score.score_case(question, response)['response_status'], 'INVALID')

    def test_duplicate_and_retraction_have_analytic_posteriors(self):
        question = sensor()
        stream = bench.timeline(question)
        answers = []
        for cutoff in (1, 2, 3):
            inp = {'task': 'revision', 'question': question, 'as_of': cutoff,
                   'records': [r for r in stream if r['available_at'] <= cutoff]}
            answers.append(bench.reference(inp))
        self.assertEqual([a['posterior']['h'] for a in answers], ['3/4', '3/4', '1/4'])
        self.assertEqual([a['active_evidence_ids'] for a in answers], [['first'], ['copy', 'first'], ['corrected']])

    def test_future_or_invalid_retraction_never_enters_projection(self):
        question = sensor()
        stream = bench.timeline(question)
        with self.assertRaisesRegex(ValueError, 'future'):
            bench.active_evidence(stream, 3, {'h', 's'})
        with self.assertRaisesRegex(ValueError, 'active prior'):
            bench.active_evidence([{'id': 'bad', 'kind': 'retraction', 'target': 'unseen', 'available_at': 1}], 1, {'h', 's'})
        stream[0]['observed_at'] = 2
        with self.assertRaises(ValueError):
            bench.active_evidence(stream[:1], 1, {'h', 's'})

    def test_duplicate_impossible_evidence_preserves_undefined_state(self):
        question = sensor()
        question['model']['nodes'][1]['p_true'] = {'0': '0', '1': '0'}
        agents, labels, predictions = [], [], []
        for cutoff in (1, 2, 3):
            inp = {'task': 'revision', 'question': question, 'as_of': cutoff,
                   'records': [r for r in bench.timeline(question) if r['available_at'] <= cutoff]}
            identifier = exact.sha(exact.canonical(inp))
            ref = bench.reference(inp)
            agents.append({'id': identifier, 'input': inp})
            labels.append({'id': identifier, 'family': 'analytic', 'episode': 'same', 'reference': ref})
            predictions.append({'id': identifier, 'response': score.optimal_response(inp, ref)})
        self.assertEqual(labels[0]['reference']['status'], 'MODEL_MISMATCH')
        report = score.score_records(agents, labels, predictions)
        self.assertEqual(report['revision_pairs']['duplicate_invariance']['error_rate'], 0)

    def test_extra_labels_and_timeline_bypass_fields_are_rejected(self):
        question = payload()
        question['reference'] = {'status': 'OK'}
        with self.assertRaises(ValueError): bench.reference(question)
        question = {'task': 'revision', 'question': sensor(), 'records': [], 'as_of': 1}
        question['question']['evidence'] = [{'id': 'future', 'event': 's', 'value': True}]
        with self.assertRaisesRegex(ValueError, 'only evidence source'): bench.reference(question)


class FamilyAndDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = {split: bench.generate_split(split, 1) for split in bench.SPLITS}
        local = exact.ROOT / '.local'
        local.mkdir(mode=0o700, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='abduction-tests-', dir=local)
        cls.source = Path(cls.temp.name) / 'source'
        cls.manifest = bench.write_dataset(cls.source, 1)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def target(self):
        directory = tempfile.TemporaryDirectory(dir=self.temp.name)
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def test_forty_new_families_and_episodes_stay_in_partition(self):
        audit = bench.audit_records(self.data)
        self.assertEqual(audit['family_counts'], {'train': 12, 'development': 8, 'reserved': 20})
        self.assertEqual(audit['counts'], {'train': 60, 'development': 40, 'reserved': 100})
        for family in bench.catalog():
            self.assertEqual(exact.structural_signature(bench.make_question(family, 3)), family)
        self.assertFalse(audit['confirmatory_ready'])

    def test_mislabeled_family_and_reference_tamper_rejected(self):
        for field in ('family', 'reference', 'id'):
            data = deepcopy(self.data)
            data['train']['evaluator'][0][field] = 'incorrect'
            with self.subTest(field=field), self.assertRaises(ValueError): bench.audit_records(data)

    def test_copying_train_case_to_reserved_is_rejected(self):
        data = deepcopy(self.data)
        for kind in ('agent', 'evaluator'):
            data['reserved'][kind][0] = deepcopy(data['train'][kind][0])
        with self.assertRaises(ValueError): bench.audit_records(data)

    def test_reproducible_private_files_and_full_audit(self):
        second = self.target() / 'copy'
        self.assertEqual(bench.write_dataset(second, 1), self.manifest)
        self.assertEqual(bench.audit_dataset(second), self.manifest['audit'])
        for name in ['manifest.json', *self.manifest['files']]:
            self.assertEqual((second / name).read_bytes(), (self.source / name).read_bytes())
            self.assertEqual(os.stat(second / name).st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError): bench.write_dataset(second, 1)

    def test_rehashed_semantic_tamper_still_fails_regeneration(self):
        copied = self.target() / 'copy'
        shutil.copytree(self.source, copied)
        path = copied / 'train/evaluator.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]['episode'] = 'f'*64
        content = b''.join(exact.canonical(row) for row in rows)
        path.write_bytes(content)
        manifest = deepcopy(self.manifest)
        manifest['files']['train/evaluator.jsonl'] = bench.file_info(content)
        (copied / 'manifest.json').write_bytes(exact.canonical(manifest))
        with self.assertRaises(ValueError): bench.audit_dataset(copied)

    def test_training_export_cannot_read_other_partition_files(self):
        original, accessed = Path.read_bytes, []
        def read(path):
            accessed.append(path.as_posix())
            if '/development/' in path.as_posix() or '/reserved/' in path.as_posix():
                raise AssertionError('held-out file read during training export')
            return original(path)
        with patch.object(Path, 'read_bytes', read):
            receipt = bench.export_view(self.source, self.target() / 'training', training=True)
        self.assertEqual(receipt['file']['records'], 60)
        self.assertTrue(any('train/evaluator.jsonl' in name for name in accessed))
        with self.assertRaises(ValueError):
            bench.export_view(self.source, self.target() / 'invalid', split='reserved', training=True)

    def test_input_export_does_not_open_labels_or_include_metadata(self):
        original = Path.read_bytes
        def read(path):
            if path.name == 'evaluator.jsonl':
                raise AssertionError('label read during inference export')
            return original(path)
        output = self.target() / 'input'
        with patch.object(Path, 'read_bytes', read):
            bench.export_view(self.source, output, split='reserved')
        rows = [json.loads(line) for line in (output / 'records.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows), 100)
        self.assertTrue(all(set(row) == {'id', 'input'} for row in rows))
        self.assertNotIn('reference', (output / 'records.jsonl').read_text())

    def test_symlink_unexpected_file_and_source_hash_tamper_rejected(self):
        copied = self.target() / 'copy'
        shutil.copytree(self.source, copied)
        (copied / 'unexpected').write_text('x')
        with self.assertRaises(ValueError): bench.audit_dataset(copied)
        (copied / 'unexpected').unlink()
        path = copied / 'reserved/agent.jsonl'
        path.unlink()
        path.symlink_to(self.source / 'reserved/agent.jsonl')
        with self.assertRaises(ValueError): bench.export_view(copied, self.target() / 'out', split='reserved')
        manifest = deepcopy(self.manifest)
        manifest['source_hashes']['tools/abductive_scoring.py'] = '0'*64
        (copied / 'manifest.json').write_bytes(exact.canonical(manifest))
        with self.assertRaises(ValueError): bench.read_manifest(copied)

    def test_complete_oracle_and_missing_predictions_have_fixed_denominators(self):
        rows = self.data['development']
        predictions = [{'id': a['id'], 'response': score.optimal_response(a['input'], l['reference'])}
                       for a, l in zip(rows['agent'], rows['evaluator'])]
        report = score.score_records(rows['agent'], rows['evaluator'], predictions)
        self.assertTrue(all(c['response_status'] == 'VALID' and not any(c['losses'].values()) for c in report['cases']))
        self.assertEqual(report['capability_claim'], 'NOT_ESTABLISHED')
        report = score.score_records(rows['agent'], rows['evaluator'], [])
        self.assertEqual(report['assigned'], 40)
        self.assertTrue(all(c['response_status'] == 'MISSING' for c in report['cases']))
        self.assertEqual(report['tasks']['inference']['metrics']['posterior_mae']['case_mean'], 1)
        self.assertEqual(report['revision_pairs']['duplicate_invariance']['error_rate'], 1)
        for bad in (predictions + predictions[:1], [{'id': 'not-assigned', 'response': {}}]):
            with self.assertRaises(ValueError): score.score_records(rows['agent'], rows['evaluator'], bad)

    def test_scoring_cli_empty_response_file_retains_every_case(self):
        directory = self.target()
        predictions = directory / 'empty.jsonl'
        predictions.write_text('')
        output = directory / 'score.json'
        run = subprocess.run([sys.executable, '-m', 'tools.abductive_scoring', str(self.source), str(predictions),
                              '--split', 'development', '--output', str(output)], cwd=exact.ROOT,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(output.read_text())['assigned'], 40)


if __name__ == '__main__':
    unittest.main()
