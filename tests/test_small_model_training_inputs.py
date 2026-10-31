import json
import unittest
from unittest.mock import patch
from tools import small_model_training_inputs as training
from tools import abductive_benchmark as base, temporal_benchmark as temporal
from tools import abductive_scoring as score, small_model_readiness as ready
from tools import small_model_pretrained_scope as scope, small_model_minimum as minimum


class TrainingInputTests(unittest.TestCase):
    def test_paid_offer_excludes_timed_out_route_without_mutating_account_evidence(self):
        offers=[{'region':'EU-SE-1'},{'region':'US-TX-1'},{'region':'CA-MTL-1'}]
        snapshot={'offers':offers,'account':{'credit_balance_usd':'2.41'}}
        def select(value,now):
            self.assertEqual(value['offers'],offers[1:])
            return {'region':'US-TX-1','costs':{'maximum_projection':'0.370'}}
        with patch.object(scope,'original_choose',select):
            self.assertEqual(scope.choose(snapshot,1)['region'],'US-TX-1')
        self.assertEqual(snapshot['offers'],offers)

    def test_four_targets_are_exact_train_partition_records_without_evaluation_overlap(self):
        spec=training.specification();self.assertEqual(len(spec['rows']),4)
        family=min(f for f,(split,_) in base.catalog().items() if split=='train')
        candidates=list(base.episode_inputs(base.make_question(family,1)))+list(temporal.episode_inputs(family,1))
        by_id={base.exact.sha(base.exact.canonical(p)):p for p in candidates}
        evaluation={r['id'] for r in ready.selected_cases(8)}
        for row in spec['rows']:
            self.assertNotIn(row['id'],evaluation);payload=by_id[row['id']]
            self.assertEqual(json.loads(row['messages'][1]['content']),payload)
            ref=temporal.reference(payload) if payload['task']=='temporal_revision' else base.reference(payload)
            converted=temporal.as_revision(payload) if payload['task']=='temporal_revision' else payload
            self.assertEqual(json.loads(row['answer']),score.optimal_response(converted,ref))
        self.assertEqual(len({r['id'] for r in spec['rows']}),4)

    def test_token_audit_includes_answer_terminal_and_refuses_overflow(self):
        class Tokenizer:
            def apply_chat_template(self,*a,**k):return {'input_ids':[2,3,4]}
            def encode(self,*a,**k):return [5,6]
        result=training.verify_tokens(Tokenizer())
        self.assertTrue(all(r['supervised_tokens']==3 for r in result['rows']))
        class Overflow(Tokenizer):
            def encode(self,*a,**k):return [5]*2048
        with self.assertRaises(ValueError):training.verify_tokens(Overflow())

    def test_shorter_paid_claim_uses_bound_contract_and_keeps_cleanup_budget(self):
        with scope.configured():
            self.assertEqual(minimum.CONTRACT['total_seconds'],2200)
            self.assertEqual(minimum.CONTRACT['work_seconds'],1780)
            self.assertEqual(minimum.CONTRACT['cleanup_seconds'],300)
            self.assertEqual(minimum.CONTRACT['export_seconds'],120)
            state=minimum.State('fixture','a'*40,True)
            claim={'source_sha':state.source,'contract_sha256':minimum.life.digest(minimum.CONTRACT),
                'namespace':state.namespace,'run_id':'123','actual':True,'owner_boot':'a'*64,
                'watch_boot':'b'*64,'name':'backtrace-small-minimum-'+'c'*32,'requested_at':1,
                'total_seconds':2200,'cleanup_seconds':300,'poll_seconds':90,'unknown_create_seconds':90}
            self.assertIs(minimum.check_claim(claim,state,123),claim)
            with self.assertRaises(minimum.StateError):minimum.check_claim(dict(claim,total_seconds=3000),state,123)


if __name__=='__main__':unittest.main()
