import unittest
from collections import Counter
from copy import deepcopy
from tools import small_model_matched_data as data
from tools import abductive_benchmark as base


def sensor():
    return {'task':'inference','question':{'schema_version':1,
        'model':{'nodes':[{'id':'c','parents':[],'p_true':{'':'1/2'}},
            {'id':'s','parents':['c'],'p_true':{'0':'1/4','1':'3/4'}}]},
        'evidence':[{'id':'r','event':'s','value':True}],
        'hypotheses':[{'id':'cause','condition':[{'c':True}]}],
        'queries':[{'id':'cause','condition':[{'c':True}]}], 'actions':[
            {'id':'yes','condition':[{'c':True}],'if_true':'1','if_false':'0'},
            {'id':'no','condition':[{'c':False}],'if_true':'1','if_false':'0'}],
        'inspections':[]}}


class CountTokenizer:
    """Count-only fixture; actual pinned token IDs are qualified separately."""
    def apply_chat_template(self,messages,**kwargs):
        return {'input_ids':list(range(3,3+sum(len(m['content']) for m in messages)//12))}
    def encode(self,text,**kwargs):
        return list(range(3,3+max(1,len(text)//4)))


class MatchedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pairs=data.training_pairs()
        cls.development=data.development_inputs()
        cls.materialized=data.materialize(CountTokenizer())

    def test_forward_control_has_prior_not_observed_posterior(self):
        question=sensor();original=deepcopy(question)
        self.assertEqual(base.reference(question)['posterior']['cause'],'3/4')
        result=data.forward_answer(question)
        self.assertEqual(result['posterior']['cause'],'1/2')
        self.assertEqual(result['decision']['mode'],'STOP')
        self.assertEqual(question,original)

    def test_control_keeps_generic_contradiction_check(self):
        question=sensor();question['question']['evidence'].append({'id':'other','event':'s','value':False})
        result=data.forward_answer(question)
        self.assertEqual(result,{'status':'INCONSISTENT_EVIDENCE','posterior':None,'decision':None})

    def test_control_bookkeeping_does_not_condition_probability(self):
        q=sensor()['question'];q['evidence']=[]
        p={'task':'revision','question':q,'as_of':3,
           'records':[r for r in base.timeline(q) if r['available_at']<=3]}
        original=base.reference(p)
        self.assertEqual(original['posterior']['cause'],'1/4')
        result=data.forward_answer(p)
        self.assertEqual(result['active_evidence_ids'],['corrected'])
        self.assertEqual(result['posterior']['cause'],'1/2')

    def test_shared_facts_and_format_practice_are_exact(self):
        self.assertEqual(Counter(p['kind'] for p in self.pairs),{'reasoning':256,'common_format':64})
        self.assertEqual(len({p['episode'] for p in self.pairs}),64)
        for pair in self.pairs:
            self.assertEqual(pair['split'],'train')
            self.assertEqual(pair['arms']['S']['messages'][1],pair['arms']['B2']['messages'][1])
            if pair['kind']=='common_format':self.assertEqual(pair['arms']['S'],pair['arms']['B2'])
            else:self.assertTrue(pair['arms']['B2']['messages'][0]['content'].endswith(data.FORWARD))

    def test_fresh_development_is_separate_and_label_free(self):
        train={p['family'] for p in self.pairs}
        self.assertFalse(train & {p['family'] for p in self.development})
        self.assertEqual(len({p['episode'] for p in self.development}),96)
        self.assertEqual(Counter(p['task'] for p in self.development),dict.fromkeys(data.TASKS,24))
        self.assertEqual(Counter(p['variant']%8 for p in self.development),dict.fromkeys(range(8),12))
        excluded=data.exposed_development_episodes()
        for row in self.development:
            self.assertEqual(row['split'],'development')
            self.assertNotIn((row['family'],row['variant']),excluded)
            self.assertNotIn('answer',row);self.assertNotIn('reference',row)
        reserved={f for f,(split,_) in base.catalog().items() if split=='reserved'}
        self.assertFalse(reserved & (train|{p['family'] for p in self.development}))

    def test_loss_budget_updates_and_padded_lengths_match(self):
        result=self.materialized
        for key in ('steps','padded_tokens','supervised_tokens'):
            self.assertEqual(result['totals']['B2'][key],result['totals']['S'][key])
        self.assertEqual(result['totals']['B2']['steps'],320)
        for arm in data.ARMS:
            self.assertLessEqual(result['totals'][arm]['effective_sequence_tokens'],1_000_000)
        for left,right in zip(result['specifications']['B2']['rows'],result['specifications']['S']['rows']):
            self.assertEqual(left['id'],right['id'])
            self.assertEqual(left['padded_tokens'],right['padded_tokens'])
            self.assertEqual(len(left['supervised_positions']),len(right['supervised_positions']))
            for row in (left,right):
                positions=row['supervised_positions']
                self.assertEqual(positions,sorted(set(positions)))
                self.assertEqual(positions[-1],row['answer_tokens']-1)
                self.assertGreaterEqual(positions[0],0)
                self.assertLessEqual(row['prompt_tokens']+row['answer_tokens'],row['padded_tokens'])

    def test_invalid_label_quota_is_rejected(self):
        for length,quota in ((0,0),(5,0),(5,6)):
            with self.assertRaises(ValueError):data.mask_positions('id',length,quota)


if __name__=='__main__':unittest.main()
