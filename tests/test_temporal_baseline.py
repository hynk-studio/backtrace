"""Analytic temporal witnesses, counterexamples, and input-only prompt boundaries."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools import abductive_baseline as prompts
from tools import abductive_benchmark as base
from tools import abductive_scoring as original_score
from tools import exact_teacher as exact
from tools import temporal_benchmark as bench
from tools import temporal_scoring as score


def witness(flip='1/2'):
    q = Fraction(flip)
    hypotheses = [{'id': 'past', 'condition': [{'old': True}]},
                  {'id': 'current', 'condition': [{'now': True}]},
                  {'id': 'changed', 'condition': [{'old': True, 'now': False}, {'old': False, 'now': True}]}]
    return {'task': 'temporal_revision', 'as_of': 2, 'event_times': {'old': 0, 'now': 2},
            'records': [{'id': 'delayed', 'kind': 'observation', 'event': 'old', 'value': True,
                         'observed_at': 0, 'available_at': 2}],
            'question': {'schema_version': 1, 'model': {'nodes': [
                {'id': 'old', 'parents': [], 'p_true': {'': '1/2'}},
                {'id': 'now', 'parents': ['old'], 'p_true': {'0': str(q), '1': str(1-q)}}]},
                'evidence': [], 'hypotheses': hypotheses, 'queries': deepcopy(hypotheses),
                'actions': [{'id': 'yes', 'condition': [{'now': True}], 'if_true': '1', 'if_false': '0'},
                            {'id': 'no', 'condition': [{'now': False}], 'if_true': '1', 'if_false': '0'}],
                'inspections': [{'event': 'now', 'cost': '1/10'}]}}


def oracle(payload):
    return original_score.optimal_response(bench.as_revision(payload), bench.reference(payload))


class TemporalAnalyticTests(unittest.TestCase):
    def test_family_weight_is_not_snapshot_count(self):
        rows = [{'family': 'a', 'losses': {'error': 0.0}} for _ in range(4)]
        rows.append({'family': 'b', 'losses': {'error': 1.0}})
        metric = score.aggregate(rows)['error']
        self.assertEqual(metric['case_mean'], 0.2)
        self.assertEqual(metric['family_mean'], 0.5)
        self.assertEqual(metric['families'], 2)

    def test_late_old_evidence_does_not_become_current_evidence(self):
        payload = witness()
        self.assertEqual(bench.reference(payload)['posterior'], {'past': '1', 'current': '1/2', 'changed': '1/2'})
        self.assertEqual(oracle(payload)['decision'], {'mode': 'INSPECT', 'event': 'now',
                                                     'outcome_actions': {'false': 'no', 'true': 'yes'}})

    def test_forced_change_and_persistent_state_are_distinct(self):
        for flip, current, changed in [('0', '1', '0'), ('1', '0', '1')]:
            answer = oracle(witness(flip))
            self.assertEqual(answer['posterior'], {'past': '1', 'current': current, 'changed': changed})
            self.assertEqual(answer['decision']['mode'], 'STOP')

    def test_opposite_values_at_different_times_are_not_a_contradiction(self):
        payload = witness('1/4')
        payload['as_of'] = 4
        payload['records'].append({'id': 'new', 'kind': 'observation', 'event': 'now', 'value': False,
                                   'observed_at': 2, 'available_at': 4})
        answer = oracle(payload)
        self.assertEqual(answer['status'], 'OK')
        self.assertEqual(answer['posterior'], {'past': '1', 'current': '0', 'changed': '1'})

    def test_new_state_evidence_can_smooth_old_state(self):
        payload = witness('1/4')
        payload['records'] = [{'id': 'new', 'kind': 'observation', 'event': 'now', 'value': True,
                               'observed_at': 2, 'available_at': 2}]
        self.assertEqual(oracle(payload)['posterior'], {'past': '3/4', 'current': '1', 'changed': '1/4'})

    def test_timestamp_collapse_and_fixed_world_answers_are_penalized(self):
        payload = witness()
        wrong = oracle(witness('0'))
        result = score.score_case(payload, wrong)
        self.assertEqual(result['losses']['current_posterior_mae'], 0.5)
        self.assertEqual(result['losses']['change_posterior_mae'], 0.5)
        self.assertAlmostEqual(result['losses']['normalized_decision_regret'], 4/11)

    def test_conflicting_same_event_and_zero_support_remain_distinct(self):
        payload = witness('0')
        payload['records'].append(dict(payload['records'][0], id='conflict', value=False))
        self.assertEqual(oracle(payload)['status'], 'INCONSISTENT_EVIDENCE')
        payload['records'][-1].update(event='now', observed_at=2)
        self.assertEqual(oracle(payload)['status'], 'MODEL_MISMATCH')
        result = score.score_case(payload, oracle(payload))
        self.assertEqual(result['losses'], {'status_error': 0.0, 'evidence_selection_error': 0.0})

    def test_future_time_mismatch_and_backwards_edges_rejected(self):
        changes = [lambda p: p['records'][0].update(available_at=3),
                   lambda p: p['records'][0].update(observed_at=1),
                   lambda p: p['event_times'].update(old=2, now=0),
                   lambda p: p['event_times'].update(now=3),
                   lambda p: p.update(as_of=True),
                   lambda p: p['question']['inspections'][0].update(event='old')]
        for change in changes:
            payload = witness()
            change(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                bench.as_revision(payload)

    def test_missing_invalid_and_false_abstention_keep_temporal_endpoints(self):
        for response, missing in [(None, True), ('bad json', False),
                                  ({'status': 'MODEL_MISMATCH', 'posterior': None, 'decision': None,
                                    'active_evidence_ids': ['delayed']}, False)]:
            result = score.score_case(witness(), response, missing=missing)
            for name in ('current_posterior_mae', 'change_posterior_mae', 'past_posterior_mae',
                         'posterior_mae', 'normalized_decision_regret'):
                self.assertEqual(result['losses'][name], 1)

    def test_retraction_updates_current_but_retains_old_record(self):
        payload = witness()
        payload['as_of'] = 5
        payload['records'] += [
            {'id': 'old_copy', 'kind': 'observation', 'event': 'old', 'value': True, 'observed_at': 0, 'available_at': 3},
            {'id': 'new', 'kind': 'observation', 'event': 'now', 'value': True, 'observed_at': 2, 'available_at': 4},
            {'id': 'retract', 'kind': 'retraction', 'target': 'new', 'available_at': 5},
            {'id': 'corrected', 'kind': 'observation', 'event': 'now', 'value': False, 'observed_at': 2, 'available_at': 5}]
        answer = oracle(payload)
        self.assertEqual(answer['active_evidence_ids'], ['corrected', 'delayed', 'old_copy'])
        self.assertEqual(answer['posterior'], {'past': '1', 'current': '0', 'changed': '1'})


class GeneratedTemporalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # All selected graphs, five transition modes; not merely a single template.
        cls.data = {s: bench.generate_split(s, 5) for s in base.SPLITS}

    def test_original_episode_and_family_membership_preserved(self):
        audit = bench.audit_records(self.data, 5)
        self.assertEqual(audit['counts'], {'train': 240, 'development': 160, 'reserved': 400})
        for split in base.SPLITS:
            static = base.generate_split(split, 5)
            old = {(l['episode'], l['family']) for l in static['evaluator']}
            new = {(l['episode'], l['family']) for l in self.data[split]['evaluator']}
            self.assertEqual(old, new)

    def test_oracle_and_missing_controls_all_graphs(self):
        for data in self.data.values():
            predictions = [{'id': a['id'], 'response': original_score.optimal_response(bench.as_revision(a['input']), l['reference'])}
                           for a, l in zip(data['agent'], data['evaluator'])]
            report = score.score_records(data['agent'], data['evaluator'], predictions)
            self.assertTrue(all(not any(c['losses'].values()) for c in report['cases'] + report['pairs']))
            missing = score.score_records(data['agent'], data['evaluator'], [])
            self.assertTrue(all(all(v == 1 for v in c['losses'].values()) for c in missing['cases'] + missing['pairs']))

    def test_duplicate_foreign_and_incomplete_assignments_rejected(self):
        data = self.data['development']
        row = {'id': data['agent'][0]['id'], 'response': None}
        for predictions in ([row, row], [{'id': 'foreign', 'response': None}]):
            with self.assertRaises(ValueError):
                score.score_records(data['agent'], data['evaluator'], predictions)
        with self.assertRaises(ValueError):
            score.score_records(data['agent'][:-1], data['evaluator'][:-1], [])

    def test_zero_delta_is_scored_against_needless_reversal(self):
        data = deepcopy(self.data['development'])
        predictions = deepcopy([{'id': a['id'], 'response': original_score.optimal_response(bench.as_revision(a['input']), l['reference'])}
                                for a, l in zip(data['agent'], data['evaluator'])])
        # At cutoff 4 the delayed cause determines 'past'; the current-signal
        # correction cannot reverse that known past value at cutoff 5.
        target = next(i for i, (a, l) in enumerate(zip(data['agent'], data['evaluator']))
                      if a['input']['as_of'] == 5 and l['reference']['status'] == 'OK')
        answer = predictions[target]['response']
        answer['posterior']['past'] = str(1 - Fraction(answer['posterior']['past']))
        report = score.score_records(data['agent'], data['evaluator'], predictions)
        self.assertGreater(report['paired_metrics']['correction_direction_error']['case_mean'], 0)

    def test_future_record_absent_and_state_model_declared(self):
        for data in self.data.values():
            for agent in data['agent']:
                self.assertNotIn('future_unavailable', json.dumps(agent['input']))
                self.assertEqual(len(agent['input']['question']['model']['nodes']), 8)
                self.assertTrue(all(r['available_at'] <= agent['input']['as_of'] for r in agent['input']['records']))


class ExportAndPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (exact.ROOT / '.local').mkdir(exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix='temporal-test-', dir=exact.ROOT / '.local'))
        cls.dataset = cls.root / 'dataset'
        bench.write_dataset(cls.dataset, 1)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root)

    def new_path(self, name):
        return self.root / (self._testMethodName + '-' + name)

    def test_dataset_audit_tamper_and_symlink_rejection(self):
        self.assertEqual(bench.audit_dataset(self.dataset)['status'], 'PASS')
        modified = self.new_path('modified')
        shutil.copytree(self.dataset, modified)
        path = modified / 'development/agent.jsonl'
        rows = [base.strict_json(line) for line in path.read_bytes().splitlines()]
        rows[0]['input']['as_of'] = 3
        raw = b''.join(exact.canonical(r) for r in rows)
        path.write_bytes(raw)
        manifest = base.strict_json((modified / 'manifest.json').read_bytes())
        manifest['files']['development/agent.jsonl'] = base.file_info(raw)
        (modified / 'manifest.json').write_bytes(exact.canonical(manifest))
        with self.assertRaises(ValueError):
            bench.audit_dataset(modified)
        path.unlink()
        path.symlink_to(self.dataset / 'development/agent.jsonl')
        with self.assertRaises(ValueError):
            bench.audit_dataset(modified)

    def test_exports_never_read_prohibited_labels_or_splits(self):
        original = Path.read_bytes
        reads = []
        def guard(path):
            if path.is_relative_to(self.dataset):
                relative = path.relative_to(self.dataset).as_posix()
                reads.append(relative)
                if relative not in {'manifest.json', 'train/agent.jsonl', 'train/evaluator.jsonl'}:
                    raise AssertionError('training opened another split')
            return original(path)
        with patch.object(Path, 'read_bytes', guard):
            bench.export_view(self.dataset, self.new_path('training'), training=True)
        self.assertEqual(set(reads), {'manifest.json', 'train/agent.jsonl', 'train/evaluator.jsonl'})
        def input_guard(path):
            if path.is_relative_to(self.dataset) and path.name == 'evaluator.jsonl':
                raise AssertionError('input export opened labels')
            return original(path)
        with patch.object(Path, 'read_bytes', input_guard), patch.object(bench, 'reference', side_effect=AssertionError('solved')):
            bench.export_view(self.dataset, self.new_path('inputs'), split='development')
        with self.assertRaises(ValueError):
            bench.export_view(self.dataset, self.new_path('invalid'), split='reserved', training=True)

    def test_prepared_packets_are_paired_input_only_and_not_model_results(self):
        view = self.new_path('view')
        bench.export_view(self.dataset, view, split='development')
        original = Path.read_bytes
        def guard(path):
            if path.is_relative_to(self.dataset) or path.name == 'evaluator.jsonl':
                raise AssertionError('compiler read the source dataset or labels')
            return original(path)
        output = self.new_path('packets')
        with patch.object(Path, 'read_bytes', guard), patch.object(exact, 'solve', side_effect=AssertionError('solver access')):
            manifest = prompts.prepare([view], output)
        self.assertEqual(manifest['assigned_cases_per_packet'], 32)
        self.assertEqual(manifest['status'], 'PREPARED_NOT_EXECUTABLE')
        self.assertEqual(manifest['model_evaluation'], 'NOT_RUN')
        packets = {name: [base.strict_json(line) for line in (output / name).read_bytes().splitlines()]
                   for name in manifest['files']}
        ids = [[r['id'] for r in rows] for rows in packets.values()]
        self.assertTrue(all(value == ids[0] for value in ids))
        for rows in packets.values():
            for row in rows:
                self.assertEqual(set(row), {'id', 'messages'})
                self.assertEqual([m['role'] for m in row['messages']], ['system', 'user'])
                self.assertNotIn(row['id'], row['messages'][1]['content'])
                self.assertNotIn('reference', row['messages'][1]['content'])
        for rendering in ('json', 'controlled_text'):
            for a, b in zip(packets[f'B0-{rendering}.jsonl'], packets[f'B1-{rendering}.jsonl']):
                self.assertEqual(a['messages'][1], b['messages'][1])
                self.assertEqual(b['messages'][0]['content'], a['messages'][0]['content'] + prompts.GUIDANCE)
        with self.assertRaises(FileExistsError):
            prompts.prepare([view], output)

    def test_reserved_training_and_duplicate_views_refused(self):
        for split, training in [('reserved', False), ('train', False), ('train', True)]:
            view = self.new_path(split + str(training))
            bench.export_view(self.dataset, view, split=split, training=training)
            with self.assertRaises(ValueError):
                prompts.prepare([view], self.new_path('rejected-' + split + str(training)))
        view = self.new_path('development')
        bench.export_view(self.dataset, view, split='development')
        with self.assertRaises(ValueError):
            prompts.prepare([view, view], self.new_path('duplicates'))

    def test_text_preserves_cpt_parent_associations_times_and_actions(self):
        payload = witness('1/4')
        rendered = prompts.render_text(payload)
        self.assertIn('P(now=true | old=false) = 1/4.', rendered)
        self.assertIn('P(now=true | old=true) = 3/4.', rendered)
        self.assertIn('Variable now at state time 2.', rendered)
        self.assertIn('observed old=true at observed_at=0; available_at=2.', rendered)
        self.assertIn('utility 1 when (now=true); utility 0 otherwise.', rendered)
        self.assertIn('Allowed inspection: now, cost 1/10.', rendered)
        self.assertIn('hypotheses changed: (now=false AND old=true) OR (now=true AND old=false).', rendered)
        self.assertEqual(prompts.condition_text([]), 'false')
        self.assertEqual(prompts.condition_text([{}]), '(true)')

    def test_text_supports_all_static_task_views_without_solver(self):
        family = next(iter(base.catalog()))
        with patch.object(exact, 'solve', side_effect=AssertionError('solver access')):
            for payload in base.episode_inputs(base.make_question(family, 1)):
                rendered = prompts.render_text(payload)
                self.assertIn('Task: ' + payload['task'], rendered)
                if payload['task'] == 'abduction':
                    for variable in payload['cause_variables'] + payload['prediction_events']:
                        self.assertIn(variable, rendered)
                    self.assertIn('At most 8 explanations.', rendered)


if __name__ == '__main__':
    unittest.main()
