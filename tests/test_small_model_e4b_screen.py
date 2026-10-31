import json
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import Mock,patch

from tools import small_model_e4b_screen as entry, small_model_e4b_screen_scope as scope
from tools import small_model_augnes_screen as screen, small_model_minimum as minimum
from tools import augnes_screening_review as review


class E4BScreenTests(unittest.TestCase):
    def test_all_twenty_messages_match_actual_e2b_inputs_without_prior_answers(self):
        with patch.object(screen.ready,'encode',return_value={'overflow':False,'input_tokens':100,'token_ids_sha256':'a'*64}):
            rows=entry.checked_schedule(Mock())
        prior=json.loads(entry.PRIOR_INPUTS.read_bytes())['requests']
        self.assertEqual(len(rows),20)
        for a,b in zip(prior,rows):
            self.assertEqual(b['model'],'E4B');self.assertEqual(b['arm'],'B1')
            self.assertEqual(a['id'],b['id']);self.assertEqual(a['messages'],b['messages'])
            self.assertNotIn('answer_text',json.loads(b['messages'][1]['content']))

    def test_changed_comparison_message_or_unpinned_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'prior.json';prior=json.loads(entry.PRIOR_INPUTS.read_bytes())
            prior['requests'][0]['messages'][1]['content']+=' altered'
            p.write_text(json.dumps(prior))
            with patch.object(entry,'PRIOR_INPUTS',p),patch.object(screen.ready,'encode',return_value={
                    'overflow':False,'input_tokens':100,'token_ids_sha256':'a'*64}),self.assertRaises(ValueError):
                entry.checked_schedule(Mock())
        with self.assertRaises(ValueError):screen.schedule(Mock(),model='unknown')
        with self.assertRaises(ValueError):entry.baseline.prepare('unused','unused',model_name='unknown')

    def test_shared_preparation_selects_the_pinned_e4b_and_job_cannot_train(self):
        with patch.object(entry.baseline,'prepare',return_value={'fixture':True}) as prepare:
            self.assertEqual(entry.prepare('output','archive'),{'fixture':True})
            prepare.assert_called_once_with('output','archive',model_name='E4B')
        hardware={'status':'PASS_ACTUAL_HARDWARE_ONLY','actual_gpu':True,'checks':{'fixture':True},'initial_gpu':{}}
        job=entry.qualified_job(hardware,{})
        self.assertEqual(job['container_model'],'E4B');self.assertNotIn('adapter_feasibility',job)
        self.assertEqual((job['max_input_tokens'],job['max_new_tokens']),(4096,768))
        with self.assertRaises(ValueError):entry.qualified_job(dict(hardware,actual_gpu=False),{})

    def test_collector_is_untrained_with_the_same_per_request_limits_and_raw_retention(self):
        import sys
        module=types.ModuleType('transformers');module.AutoTokenizer=Mock()
        rows=[{'model':'E4B','arm':'B1','id':str(i)} for i in range(20)]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'.local').mkdir();spec=root/'spec.json'
            spec.write_text(json.dumps({'prefix':['fixture'],'gpu_uuid':'fixture'}))
            with patch.object(entry,'ROOT',root),patch.dict(sys.modules,{'transformers':module}),\
                    patch.object(entry,'checked_schedule',return_value=rows),\
                    patch.object(entry.runner,'collect',return_value={'status':'INCOMPLETE'}) as collect,\
                    patch.object(entry.container,'ContainerChannel') as channel:
                self.assertEqual(entry.collect(spec,root)['status'],'INCOMPLETE')
                args,kw=collect.call_args;factory=args[2];self.assertFalse(factory.training_requested)
                self.assertEqual(args[0],rows);self.assertEqual((kw['max_new_tokens'],kw['request_seconds']),(768,60))
                self.assertEqual((kw['startup_seconds'],kw['total_seconds']),(180,1500))
                factory('E4B',root);self.assertIn('E4B-screening 1500 pretrained',channel.call_args.args[0][-1])
                with self.assertRaises(ValueError):factory('E2B',root)
                source=root/'.local/e4b-screening-collection';source.mkdir();(source/'ledger.jsonl').write_text('retained\n')
                self.assertEqual(entry.preserve_collection(root)['files'],1)
                self.assertEqual((root/'collection/ledger.jsonl').read_bytes(),b'retained\n')

    def test_source_bound_zero_training_permit_and_current_wallet_limits(self):
        now=time.time();source='a'*40
        p={'source_sha':source,'contract_sha256':minimum.life.digest(scope.CONTRACT),
            'namespace':scope.NAMESPACE,'instruction':scope.INSTRUCTION,'mode':'OWNER_APPROVED_E4B_SCREENING',
            'additional_cap_usd':'0.51','allocation_inclusive_seconds':3000,'single_use':True,
            'automatic_retry':False,'top_up_allowed':False,'weight_bytes':15992595884,
            'pretrained_requests':20,'training_steps':0,'qualification_run_id':'123',
            'approved_at':now-1,'expires_at':now+3600,'continuation_observed_spend_usd':'1.1','maximum_projection_usd':'0.51'}
        self.assertIs(scope.validate_permit(p,source,now),p)
        for key,value in [('source_sha','b'*40),('pretrained_requests',21),('training_steps',4),
                ('automatic_retry',True),('single_use',1),('maximum_projection_usd','0.52'),
                ('namespace','e2b-completion-paid-20261031'),('continuation_observed_spend_usd','1.30')]:
            with self.subTest(key=key),self.assertRaises(ValueError):scope.validate_permit(dict(p,**{key:value}),source,now)
        snapshot={'offers':[],'account':{'credit_balance_usd':'1.7'}}
        with patch.object(scope,'original_choose',return_value={'costs':{'maximum_projection':'0.51'}}):
            self.assertEqual(scope.choose(snapshot,1)['costs']['additional_cap'],'0.51')
            with self.assertRaises(ValueError):scope.choose(dict(snapshot,account={'credit_balance_usd':'1.615'}),1)

    def test_scope_restores_existing_controller_after_failure(self):
        before=(minimum.State,minimum.CONTRACT,minimum.REMOTE_MODULE,minimum.prepare_runtime)
        with self.assertRaisesRegex(RuntimeError,'fixture'):
            with scope.configured():
                self.assertEqual(minimum.REMOTE_MODULE,'tools.small_model_e4b_screen_scope')
                self.assertEqual(minimum.State('fixture','a'*40,True).namespace,scope.NAMESPACE)
                self.assertEqual(minimum.CONTRACT['training_steps'],0)
                self.assertEqual(minimum.CONTRACT['model_transfer_maximum_seconds'],960)
                raise RuntimeError('fixture')
        self.assertEqual((minimum.State,minimum.CONTRACT,minimum.REMOTE_MODULE,minimum.prepare_runtime),before)

    def test_existing_structural_reviewer_requires_one_exact_model_cohort(self):
        packet=json.loads(screen.PACKET.read_bytes());rubric=json.loads((screen.ROOT/'docs/augnes-screening-rubric-20261031.json').read_bytes())
        collection={'training':False,'records':[{'id':c['id'],'model':'E4B','arm':'B1','status':'NOT_RUN'} for c in packet['cases']]}
        result=review.review(packet,rubric,collection,model='E4B')
        self.assertEqual(result['collector_coverage'],{'NOT_RUN':20});self.assertEqual(result['strict_json_objects'],0)
        with self.assertRaises(ValueError):review.review(packet,rubric,collection)
        collection['records'][0]['model']='E2B'
        with self.assertRaises(ValueError):review.review(packet,rubric,collection,model='E4B')


if __name__=='__main__':unittest.main()
