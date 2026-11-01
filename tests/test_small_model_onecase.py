import base64
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from tools import small_model_onecase as profile, small_model_onecase_data as data
from tools import small_model_onecase_scope as scope, small_model_trainability as entry
from tools import small_model_minimum as minimum, small_model_trainability_scope as previous
from tests.test_small_model_trainability import Tokenizer


class OneCaseTests(unittest.TestCase):
    def test_fixed_case_is_reasoning_train_only_and_has_no_format_examples(self):
        rows = data.examples()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['id'], rows[0]['kind'], rows[0]['split']),
                         (data.SELECTED_ID, 'reasoning', 'train'))
        self.assertEqual(rows[0]['task'], 'temporal_revision')
        self.assertNotIn('fields', json.loads(rows[0]['messages'][1]['content']))
        spec = data.materialize(Tokenizer())['specifications']['Q4']
        self.assertEqual((len(spec['rows']), spec['steps'], spec['projection_count']), (1, 640, 4))

    def test_only_two_identical_label_free_generation_inputs(self):
        with profile.configured(), patch.object(entry.ready, 'encode', return_value={
                'overflow': False, 'input_tokens': 3, 'token_ids_sha256': 'a'*64}):
            rows = entry.schedule(None)
        self.assertEqual([r['arm'] for r in rows], ['BASE', 'Q4'])
        self.assertEqual(rows[0]['messages'], rows[1]['messages'])
        self.assertTrue(all('answer' not in r for r in rows))

    def test_scoring_requires_both_original_assignments_and_full_correctness(self):
        example = data.examples()[0]
        records = [{'model': 'E2B', 'arm': a, 'id': example['id'], 'status': 'OK',
                    'answer_text': example['answer']} for a in data.ARMS]
        with tempfile.TemporaryDirectory() as directory, profile.configured():
            root = Path(directory); path = root/'all-assignment-outcomes.json'
            path.write_text(json.dumps({'assigned': 2, 'records': records}))
            result = entry.evaluate(root)
            self.assertTrue(all(r['strict_fit'] and r['exact_target_json_match'] == 1
                                and r['format_correct'] == 0 for r in result['arms'].values()))
            records[1]['answer_text'] = json.dumps({'status': 'MODEL_MISMATCH',
                'posterior': None, 'decision': None, 'active_evidence_ids': []})
            path.write_text(json.dumps({'assigned': 2, 'records': records}))
            result = entry.evaluate(root)
            self.assertEqual(result['arms']['Q4']['schema_valid'], 1)
            self.assertFalse(result['arms']['Q4']['strict_fit'])
            records[1]['status'] = 'NOT_RUN'
            path.write_text(json.dumps({'assigned': 2, 'records': records}))
            self.assertEqual(entry.evaluate(root)['arms']['Q4']['task_correct'], 0)
            path.write_text(json.dumps({'assigned': 1, 'records': records[:1]}))
            with self.assertRaises(ValueError): entry.evaluate(root)

    def test_profile_restores_historical_contract_and_binds_all_new_sources(self):
        old = (entry.data, entry.ARMS, previous.CONTRACT, minimum.State, minimum.CONTRACT)
        with scope.configured():
            self.assertEqual((minimum.REVIEW, minimum.CONTRACT['training_steps'],
                minimum.CONTRACT['pretrained_requests']), (scope.REVIEW, 640, 2))
            self.assertEqual(minimum.REMOTE_MODULE, 'tools.small_model_onecase_scope')
            self.assertEqual(minimum.State('token', 'a'*40, False).namespace, 'reasoning-onecase-retry-free-'+'a'*40)
            self.assertTrue(set(('tools/small_model_onecase_data.py', scope.WORKFLOW)) <= set(minimum.sources()))
        self.assertEqual(old, (entry.data, entry.ARMS, previous.CONTRACT, minimum.State, minimum.CONTRACT))

    def test_new_permit_rejects_old_scope_and_excess_cost(self):
        now = time.time(); source = 'a'*40
        permit = {'source_sha': source, 'contract_sha256': minimum.life.digest(scope.CONTRACT),
            'namespace': scope.NAMESPACE, 'instruction': scope.INSTRUCTION, 'mode': scope.PERMIT_MODE,
            'additional_cap_usd': '0.55', 'allocation_inclusive_seconds': 3000, 'single_use': True,
            'automatic_retry': False, 'top_up_allowed': False, 'weight_bytes': 10246621918,
            'pretrained_requests': 2, 'training_steps': 640, 'qualification_run_id': '123',
            'approved_at': now-1, 'expires_at': now+3600,
            'continuation_observed_spend_usd': '1.7135017444', 'maximum_projection_usd': '0.5041666667'}
        self.assertIs(scope.validate_permit(permit, source, now), permit)
        for change in ({'namespace': 'reasoning-onecase-paid-20261101'}, {'namespace': 'trainability-paid-20261101'}, {'maximum_projection_usd': '0.551'},
                       {'continuation_observed_spend_usd': '1.9'}, {'pretrained_requests': 48}):
            with self.assertRaises(ValueError): scope.validate_permit(dict(permit, **change), source, now)

    def test_restore_receipt_uses_new_profile_and_rejects_partial_training(self):
        raw = b'fixture'
        receipt = {'status': 'PASS_TRAINABILITY_UPDATES', 'arm': 'Q4', 'projection_count': 4,
            'training_steps': 640, 'updates_in_worker': 640, 'training_input_sha256': 'a'*64,
            'adapter_bytes': len(raw), 'adapter_sha256': minimum.life.digest(raw),
            'adapter_safetensors_base64': base64.b64encode(raw).decode(), 'target_modules': ['q']*4,
            'probe_messages': [], 'probe_input_ids_sha256': 'b'*64, 'trained_probe_logits_sha256': 'c'*64}
        with profile.configured():
            self.assertEqual(entry.restore_spec(receipt, 'Q4', 'a'*64)['schema'], data.RESTORE_SCHEMA)
            with self.assertRaises(ValueError): entry.restore_spec(dict(receipt, training_steps=639), 'Q4', 'a'*64)


if __name__ == '__main__': unittest.main()
