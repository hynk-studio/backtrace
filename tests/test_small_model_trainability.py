import base64
from collections import Counter
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from tools import small_model_trainability_data as data, small_model_trainability as entry
from tools import small_model_trainability_scope as scope, small_model_minimum as minimum


class Tokenizer:
    pad_token_id=0
    def apply_chat_template(self,messages,*,add_generation_prompt,**kwargs):
        return {'input_ids':[2,3,4] if add_generation_prompt else [2,3,4]+[200+ord(c) for c in messages[-1]['content']]+[106]}
    def decode(self,ids,**kwargs):return ''.join(chr(i-200) for i in ids)


class TrainabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rows=data.examples();cls.materialized=data.materialize(Tokenizer())

    def test_examples_are_train_only_and_format_answers_match_reasoning(self):
        self.assertEqual(len(self.rows),16)
        self.assertEqual(Counter(r['kind'] for r in self.rows),{'reasoning':8,'format':8})
        self.assertEqual(Counter(r['task'] for r in self.rows if r['kind']=='reasoning'),dict.fromkeys(data.prior.TASKS,2))
        for row in self.rows:
            self.assertEqual(data.prior.base.catalog()[row['family']][0],'train')
            self.assertEqual(json.loads(row['answer'])['status'],'OK')
            if row['kind']=='format':
                self.assertEqual(dict(json.loads(row['messages'][1]['content'])['fields']),json.loads(row['answer']))

    def test_same_full_targets_and_updates_only_projection_count_differs(self):
        q1=self.materialized['specifications']['Q1'];q4=self.materialized['specifications']['Q4']
        self.assertEqual(q1['rows'],q4['rows']);self.assertEqual(q1['steps'],640)
        self.assertEqual((q1['projection_count'],q4['projection_count']),(1,4))
        self.assertTrue(all('supervised_positions' not in r for r in q1['rows']))

    def test_48_identical_label_free_generation_inputs(self):
        with patch.object(entry.ready,'encode',return_value={'overflow':False,'input_tokens':3,'token_ids_sha256':'a'*64}):
            rows=entry.schedule(None)
        self.assertEqual(len(rows),48)
        blocks=[[{k:v for k,v in r.items() if k!='arm'} for r in rows if r['arm']==a] for a in data.ARMS]
        self.assertEqual(blocks[0],blocks[1]);self.assertEqual(blocks[1],blocks[2])
        self.assertTrue(all('answer' not in r for r in rows))

    def test_baseline_job_contains_no_training_or_restore(self):
        hardware={'status':'PASS_ACTUAL_HARDWARE_ONLY','actual_gpu':True,'checks':{'all':True},'initial_gpu':{}}
        job=entry.base_job(hardware,{})
        self.assertFalse({'adapter_feasibility','candidate_training','candidate_restore','trainability_training','trainability_restore'}&set(job))

    def test_incomplete_rows_keep_all_original_denominators(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'.local/trainability-collections/BASE';p.mkdir(parents=True)
            rows=[{'model':'E2B','arm':a,'id':str(i)} for a in data.ARMS for i in range(16)]
            (p/'collection.json').write_text(json.dumps({'records':[dict(rows[0],status='INVALID_OUTPUT',raw_text='bad')]}))
            with patch.object(entry,'ROOT',root):result=entry.aggregate(root/'out',rows)
        self.assertEqual(result['assigned'],48);self.assertEqual(result['coverage'],{'INVALID_OUTPUT':1,'NOT_RUN':47})

    def test_scope_preserves_controller_and_caps(self):
        old=(minimum.State,minimum.CONTRACT,minimum.REMOTE_MODULE)
        with scope.configured():
            self.assertEqual(minimum.CONTRACT['training_steps'],1280)
            self.assertEqual(minimum.CONTRACT['pretrained_requests'],48)
            self.assertEqual(minimum.CONTRACT['maximum_additional_usd'],'0.75')
        self.assertEqual(old,(minimum.State,minimum.CONTRACT,minimum.REMOTE_MODULE))

    def test_permit_rejects_old_scope_and_over_budget(self):
        now=time.time();source='a'*40
        permit={'source_sha':source,'contract_sha256':minimum.life.digest(scope.CONTRACT),'namespace':scope.NAMESPACE,
            'instruction':scope.INSTRUCTION,'mode':'OWNER_APPROVED_E2B_TRAINABILITY','additional_cap_usd':'0.75',
            'allocation_inclusive_seconds':4200,'single_use':True,'automatic_retry':False,'top_up_allowed':False,
            'weight_bytes':10246621918,'pretrained_requests':48,'training_steps':1280,'qualification_run_id':'123',
            'approved_at':now-1,'expires_at':now+3600,'continuation_observed_spend_usd':'1.5012529416','maximum_projection_usd':'0.70'}
        self.assertIs(scope.validate_permit(permit,source,now),permit)
        for change in ({'namespace':'matched-candidate-paid-20261031'},{'training_steps':640},
                       {'maximum_projection_usd':'0.751'},{'continuation_observed_spend_usd':'1.61'}):
            with self.assertRaises(ValueError):scope.validate_permit(dict(permit,**change),source,now)

    def test_partial_or_wrong_projection_export_is_rejected(self):
        raw=b'test fixture'
        result={'status':'PASS_TRAINABILITY_UPDATES','arm':'Q1','projection_count':1,'training_steps':640,'updates_in_worker':640,
            'training_input_sha256':'a'*64,'adapter_bytes':len(raw),'adapter_sha256':minimum.life.digest(raw),
            'adapter_safetensors_base64':base64.b64encode(raw).decode(),'target_modules':['q'],
            'probe_messages':[],'probe_input_ids_sha256':'b'*64,'trained_probe_logits_sha256':'c'*64}
        self.assertEqual(entry.restore_spec(result,'Q1','a'*64)['schema'],'trainability_restore_v1')
        for change in ({'projection_count':4},{'training_steps':639},{'adapter_sha256':'0'*64}):
            with self.assertRaises(ValueError):entry.restore_spec(dict(result,**change),'Q1','a'*64)

    def test_authored_oracle_and_missing_control_keep_all_48_denominators(self):
        records=[{'model':'E2B','arm':a,'id':r['id'],'status':'OK','answer_text':r['answer']}
                 for a in data.ARMS for r in self.rows]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path=root/'all-assignment-outcomes.json'
            path.write_text(json.dumps({'assigned':48,'records':records}))
            result=entry.evaluate(root)
            self.assertTrue(all(a['strict_fit'] and a['task_correct']==16 for a in result['arms'].values()))
            for r in records:r['status']='NOT_RUN'
            path.write_text(json.dumps({'assigned':48,'records':records}))
            result=entry.evaluate(root)
            self.assertTrue(all(a['assigned']==16 and a['task_correct']==0 for a in result['arms'].values()))

    def test_schema_valid_wrong_answer_does_not_count_as_learning(self):
        records=[{'model':'E2B','arm':a,'id':r['id'],'status':'OK',
                  'answer_text':json.dumps({'status':'MODEL_MISMATCH',**({'explanations':[]} if r['task']=='abduction'
                    else {'posterior':None,'decision':None,**({'active_evidence_ids':[]} if r['task'] in ('revision','temporal_revision') else {})})})}
                 for a in data.ARMS for r in self.rows]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'all-assignment-outcomes.json').write_text(json.dumps({'assigned':48,'records':records}))
            result=entry.evaluate(root)
        self.assertTrue(all(a['schema_valid']==16 and a['task_correct']==0 for a in result['arms'].values()))


if __name__=='__main__':unittest.main()
