import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import small_model_matched as entry, small_model_matched_scope as scope
from tools import small_model_minimum as minimum, small_model_delivery as delivery
from tools import small_model_worker as worker
from tests.test_small_model_matched_data import CountTokenizer


class MatchedEntryTests(unittest.TestCase):
    def test_full_denominator_and_identical_arm_inputs(self):
        # This checks assignment/factual equality, not actual tokenizer behavior.
        # The real pinned tokenizer is independently required in free qualification.
        with patch.object(entry.ready,'encode',side_effect=lambda t,m,n:{
                'overflow':False,'input_tokens':len(str(m)),'token_ids_sha256':entry.worker_spec_sha(m)}):
            rows=entry.schedule(None)
        self.assertEqual(len(rows),348)
        blocks=[[{k:v for k,v in r.items() if k!='arm'} for r in rows if r['arm']==arm] for arm in entry.ARMS]
        self.assertEqual(blocks[0],blocks[1]);self.assertEqual(blocks[1],blocks[2])
        self.assertEqual(len({r['id'] for r in blocks[0]}),116)
        self.assertEqual(sum(r['id'].startswith('augnes-screen-') for r in blocks[0]),20)

    def test_unicode_training_identity_uses_worker_encoding(self):
        value={'messages':[{'role':'user','content':'원인 α'}]}
        self.assertEqual(entry.worker_spec_sha(value),minimum.life.digest(worker.canonical(value)))

    def receipt(self):
        raw=b'authored export validation fixture'
        return {'status':'PASS_MATCHED_CANDIDATE_TRAINING','arm':'S','training_steps':320,
            'updates_in_worker':320,'training_input_sha256':'a'*64,'adapter_bytes':len(raw),
            'adapter_sha256':minimum.life.digest(raw),'adapter_safetensors_base64':base64.b64encode(raw).decode(),
            'target_module':'model.layers.34.self_attn.q_proj','probe_messages':[{'role':'user','content':'train only'}],
            'probe_input_ids_sha256':'b'*64,'trained_probe_logits_sha256':'c'*64}

    def test_export_cannot_cross_arm_spec_or_partial_training(self):
        good=self.receipt()
        self.assertEqual(entry.restore_spec(good,'S','a'*64)['schema'],'matched_candidate_restore_v1')
        for change in ({'arm':'B2'},{'training_steps':319},{'updates_in_worker':0},
                {'training_input_sha256':'b'*64},{'adapter_sha256':'0'*64},{'adapter_bytes':1},
                {'status':'INCOMPLETE'}):
            with self.subTest(change=change),self.assertRaises(ValueError):entry.restore_spec(dict(good,**change),'S','a'*64)

    def test_baseline_job_has_no_training_or_restore_data(self):
        hardware={'status':'PASS_ACTUAL_HARDWARE_ONLY','actual_gpu':True,'checks':{'all':True},'initial_gpu':{'uuid':'GPU-fixture'}}
        job=entry.base_job(hardware,{})
        self.assertFalse({'adapter_feasibility','candidate_training','candidate_restore'} & set(job))
        self.assertEqual((job['max_input_tokens'],job['max_new_tokens']),(4096,768))

    def test_incomplete_and_unstarted_arms_stay_in_original_denominator(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'.local/matched-collections/B1';p.mkdir(parents=True)
            rows=[{'model':'E2B','arm':a,'id':i} for a in entry.ARMS for i in ('one','two')]
            (p/'collection.json').write_text(json.dumps({'status':'INCOMPLETE','records':[
                dict(rows[0],status='INVALID_OUTPUT',raw_text='bad'),dict(rows[1],status='TIMEOUT')]}))
            with patch.object(entry,'ROOT',root):
                first=entry.aggregate(root/'out',rows);second=entry.aggregate(root/'out',rows)
            self.assertEqual(first,second)
            self.assertEqual(first['coverage'],{'INVALID_OUTPUT':1,'TIMEOUT':1,'NOT_RUN':4})
            self.assertEqual(first['records'][0]['raw_text'],'bad')

    def test_scope_restores_all_existing_controller_transport_bindings(self):
        before=(minimum.State,minimum.CONTRACT,minimum.REMOTE_MODULE,minimum.prepare_runtime,delivery.push)
        with self.assertRaisesRegex(RuntimeError,'fixture'):
            with scope.configured():
                self.assertEqual(minimum.CONTRACT['training_steps'],640)
                self.assertEqual(minimum.CONTRACT['pretrained_requests'],348)
                self.assertEqual(minimum.State('fixture','a'*40,True).namespace,'matched-candidate-paid-20261031')
                raise RuntimeError('fixture')
        self.assertEqual(before,(minimum.State,minimum.CONTRACT,minimum.REMOTE_MODULE,minimum.prepare_runtime,delivery.push))

    def test_new_permit_cannot_reuse_old_scope_or_exceed_bound(self):
        now=time.time();source='a'*40
        value={'source_sha':source,'contract_sha256':minimum.life.digest(scope.CONTRACT),'namespace':scope.NAMESPACE,
            'instruction':scope.INSTRUCTION,'mode':'OWNER_APPROVED_E2B_MATCHED_CANDIDATE','additional_cap_usd':'0.90',
            'allocation_inclusive_seconds':5340,'single_use':True,'automatic_retry':False,'top_up_allowed':False,
            'weight_bytes':10246621918,'pretrained_requests':348,'training_steps':640,'qualification_run_id':'123',
            'approved_at':now-1,'expires_at':now+3600,'continuation_observed_spend_usd':'1.19','maximum_projection_usd':'0.898'}
        self.assertIs(scope.validate_permit(value,source,now),value)
        for change in ({'namespace':'e2b-public-route-paid-20261031'},{'training_steps':4},
                {'pretrained_requests':360},{'maximum_projection_usd':'0.901'},
                {'continuation_observed_spend_usd':'1.5'},{'single_use':1}):
            with self.subTest(change=change),self.assertRaises(ValueError):scope.validate_permit(dict(value,**change),source,now)

    def test_live_budget_and_excluded_create_pair_are_retained(self):
        allowed={'gpu':'NVIDIA A40','region':'EU-SE-1'};excluded={'gpu':'NVIDIA RTX A6000','region':'US-TX-1'}
        snapshot={'offers':[allowed,excluded],'account':{'credit_balance_usd':'1.71'}}
        with patch.object(scope,'original_choose',return_value={'costs':{'maximum_projection':'.8974166667'}}) as choose:
            self.assertEqual(scope.choose(snapshot,1)['costs']['additional_cap'],'0.90')
            self.assertEqual(choose.call_args.args[0]['offers'],[allowed])
            with self.assertRaises(ValueError):scope.choose(dict(snapshot,account={'credit_balance_usd':'1.50'}),1)


if __name__=='__main__':unittest.main()
