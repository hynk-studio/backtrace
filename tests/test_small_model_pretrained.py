import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from tools import small_model_pretrained as entry, small_model_pretrained_scope as scope
from tools import small_model_minimum as minimum


class PretrainedTests(unittest.TestCase):
    def test_no_failed_partial_or_cpu_hardware_record_authorizes_a_job(self):
        good={'status':'PASS_ACTUAL_HARDWARE_ONLY','actual_gpu':True,
              'checks':{'boundary':True,'deadline':True},'initial_gpu':{'uuid':'fixture'}}
        for row in ({},dict(good,status='DIAGNOSTIC_RECORDED'),dict(good,actual_gpu=False),
                    dict(good,checks={}),dict(good,checks={'boundary':False})):
            with self.subTest(row=row),self.assertRaises(ValueError):entry.qualified_job(row,{})
        job=entry.qualified_job(good,{'vision_tower.weight':{},'language_model.weight':{}})
        self.assertEqual(job['mode'],'pretrained_cuda');self.assertEqual(job['container_model'],'E2B')
        self.assertEqual(job['hardware_receipt_sha256'],minimum.life.digest(good))

    def test_replay_arms_have_same_facts_and_no_rubric_or_later_outcomes(self):
        with mock.patch.object(entry.ready,'encode',return_value={'overflow':False,'input_tokens':100,'token_ids_sha256':'a'*64}):
            rows=entry.replay_schedule(mock.Mock())
        self.assertEqual(len(rows),6);self.assertEqual(len({r['id'] for r in rows}),3)
        for b0,b1 in zip(rows[::2],rows[1::2]):
            self.assertEqual(b0['messages'][1],b1['messages'][1])
            self.assertNotEqual(b0['messages'][0],b1['messages'][0])
            payload=json.loads(b0['messages'][1]['content'])
            self.assertEqual(set(payload),{'id','cutoff','facts','question','output_contract'})
            self.assertNotIn('historical_action',b0['messages'][1]['content'])
            self.assertNotIn('expected_decision',b0['messages'][1]['content'])

    def test_paid_permit_keeps_denominators_no_training_and_cumulative_cap(self):
        now=time.time();source='a'*40
        p={'source_sha':source,'contract_sha256':minimum.life.digest(scope.CONTRACT),
            'namespace':scope.NAMESPACE,'instruction':scope.INSTRUCTION,'mode':'OWNER_APPROVED_E2B_DEVELOPMENT',
            'additional_cap_usd':'1.00','allocation_inclusive_seconds':3000,'single_use':True,
            'automatic_retry':False,'top_up_allowed':False,'weight_bytes':10246621918,
            'pretrained_requests':24,'training_steps':0,'qualification_run_id':'123',
            'approved_at':now-1,'expires_at':now+3600,'continuation_observed_spend_usd':'0.10',
            'maximum_projection_usd':'0.505'}
        self.assertIs(scope.validate_permit(p,source,now),p)
        for key,value in [('source_sha','b'*40),('pretrained_requests',25),('training_steps',1),
                ('automatic_retry',True),('single_use',1),('namespace','cuda-trace-paid-20261031'),
                ('continuation_observed_spend_usd','0.60')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                scope.validate_permit(dict(p,**{key:value}),source,now)

    def test_scope_restores_original_owner_and_cleanup_entry(self):
        original=(minimum.State,minimum.prepare_runtime,minimum.CONTRACT,minimum.choose)
        with scope.configured():
            self.assertIs(minimum.prepare_runtime,entry.prepare_runtime)
            self.assertEqual(minimum.REMOTE_MODULE,'tools.small_model_pretrained_scope')
            self.assertEqual(minimum.State('fixture','a'*40,True).namespace,scope.NAMESPACE)
        self.assertEqual((minimum.State,minimum.prepare_runtime,minimum.CONTRACT,minimum.choose),original)


if __name__=='__main__':unittest.main()
