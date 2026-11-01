"""Sixteen fixed train-only examples; a memorization diagnostic, not evaluation."""
from copy import deepcopy
import json
from tools import small_model_matched_data as prior
from tools.small_model_sft_inputs import full_completion_example

ARMS = ('BASE', 'Q1', 'Q4')
SEED = 17
STEPS = 640
ROW_COUNT = 16
RESTORE_SCHEMA = 'trainability_restore_v1'


def examples():
    candidates = [p for p in prior.training_pairs() if p['kind'] == 'reasoning'
                  and json.loads(p['arms']['S']['answer'])['status'] == 'OK']
    selected = []
    for task in prior.TASKS:
        rows = sorted((p for p in candidates if p['task'] == task),
                      key=lambda p: prior.digest(['trainability-v1', p['id']]))
        families = set()
        for row in rows:
            if row['family'] in families: continue
            selected.append(row); families.add(row['family'])
            if len(families) == 2: break
        if len(families) != 2: raise ValueError('two train families per task required')
    result = []
    for pair in selected:
        row = deepcopy(pair['arms']['S'])
        metadata = {k: pair[k] for k in ('family', 'variant', 'task', 'episode', 'split')}
        result.append(dict(row, **metadata, kind='reasoning'))
        fields = list(json.loads(row['answer']).items())
        result.append(dict(metadata, id=prior.digest(['trainability-format-v1', row['id']]),
            kind='format', answer=row['answer'], messages=[{'role':'system','content':prior.FORMAT},
            {'role':'user','content':prior.base.exact.canonical({'fields':fields}).decode().strip()}]))
    result.sort(key=lambda r: prior.digest(['trainability-order-v1', r['id']]))
    if len(result) != 16 or len({r['id'] for r in result}) != 16:
        raise AssertionError('sixteen distinct train examples required')
    if any(prior.base.catalog()[r['family']][0] != 'train' for r in result):
        raise ValueError('only train families are permitted')
    return result


def materialize(tokenizer):
    rows = []
    for example in examples():
        batch = full_completion_example(tokenizer, example['messages'], example['answer'],
                                        eos_token_ids=[1, 106, 50])
        rows.append({k: example[k] for k in ('id','messages','answer')} | {
            'sequence_sha256': prior.digest(batch['input_ids']),
            'prompt_tokens': batch['prompt_tokens'], 'answer_tokens': batch['completion_tokens']})
    effective = sum(r['prompt_tokens'] + r['answer_tokens'] for r in rows) * (STEPS // 16)
    if effective > 1_000_000: raise ValueError('per-arm training token ceiling exceeded')
    specs = {arm: {'schema':'trainability_adapter_v1','arm':arm,'rows':deepcopy(rows),
        'rank':4,'steps':STEPS,'seed':SEED,'learning_rate':0.01,'maximum_tokens':3072,
        'projection_count':count} for arm,count in [('Q1',1),('Q4',4)]}
    return {'specifications':specs,'examples':[{k:v for k,v in r.items() if k not in ('messages','answer')}
        for r in examples()], 'epochs':STEPS//16,'rows_per_arm':16,
        'effective_training_tokens_per_arm':effective,
        'supervised_tokens_per_arm':sum(r['answer_tokens'] for r in rows)*(STEPS//16),
        'qualification':'TRAIN_ONLY_NOT_GENERALIZATION'}


CPU_CONTROL = r'''
import base64,hashlib,json,runpy
import torch
from transformers import Gemma4TextConfig,Gemma4ForCausalLM
torch.set_num_threads(1)
config=Gemma4TextConfig(vocab_size=128,vocab_size_per_layer_input=128,
 hidden_size=32,intermediate_size=64,num_hidden_layers=4,num_attention_heads=4,
 num_key_value_heads=2,head_dim=8,global_head_dim=8,hidden_size_per_layer_input=4,
 max_position_embeddings=128,sliding_window=32,num_kv_shared_layers=0,
 layer_types=['sliding_attention','full_attention']*2,dtype='float32')
config._attn_implementation='sdpa'
worker=runpy.run_path('/opt/backtrace/worker.py')
canonical=worker['canonical']
class Tokenizer:
 pad_token_id=0
 def apply_chat_template(self,*a,add_generation_prompt,**k):
  return {'input_ids':[2,3,4] if add_generation_prompt else [2,3,4,5,6,106]}
 def decode(self,ids,**k):return ''.join({5:'{',6:'}',106:'<end>'}[i] for i in ids)
tokenizer=Tokenizer();results={}
for arm,count in [('Q1',1),('Q4',4)]:
 torch.manual_seed(17);model=Gemma4ForCausalLM(config).eval()
 original={k:v.detach().clone() for k,v in model.state_dict().items()}
 spec={'schema':'trainability_adapter_v1','arm':arm,'rank':4,'steps':640,'seed':17,
  'learning_rate':0.01,'maximum_tokens':3072,'projection_count':count,'rows':[
   {'id':hashlib.sha256(str(i).encode()).hexdigest(),'messages':[{'role':'user','content':'CPU control'}],
    'answer':'{}','prompt_tokens':3,'answer_tokens':3,
    'sequence_sha256':hashlib.sha256(canonical([2,3,4,5,6,106])).hexdigest()} for i in range(16)]}
 result=worker['trainability_train'](model,tokenizer,spec)
 assert result['training_steps']==640 and len(result['target_modules'])==count
 assert len(result['changed_tensors'])==count*2
 assert result['after_fixed_loss']['token_mean_nll']<result['before_fixed_loss']['token_mean_nll']
 for key,value in original.items():assert torch.equal(value,model.state_dict()[key])
 restore={k:result[k] for k in ('arm','training_steps','training_input_sha256','adapter_bytes',
  'adapter_sha256','adapter_safetensors_base64','target_modules','projection_count',
  'probe_messages','probe_input_ids_sha256','trained_probe_logits_sha256')}
 restore['schema']='trainability_restore_v1'
 fresh=Gemma4ForCausalLM(config).eval();fresh.load_state_dict(original,strict=True)
 reloaded=worker['trainability_restore'](fresh,tokenizer,restore)
 assert reloaded['updates_in_worker']==0 and reloaded['observed_probe_logits_sha256']==result['trained_probe_logits_sha256']
 for changes in ({'adapter_sha256':'0'*64},{'projection_count':3},{'probe_input_ids_sha256':'0'*64}):
  bad=Gemma4ForCausalLM(config).eval();bad.load_state_dict(original,strict=True)
  try:worker['trainability_restore'](bad,tokenizer,dict(restore,**changes))
  except ValueError:pass
  else:raise AssertionError('corrupt diagnostic restore accepted')
 raw=base64.b64decode(result.pop('adapter_safetensors_base64'),validate=True)
 assert hashlib.sha256(raw).hexdigest()==result['adapter_sha256']
 result.pop('probe_messages')
 results[arm]={'training':result,'fresh_model_reload':reloaded}
print(json.dumps({'status':'PASS_RANDOM_CPU_TRAINABILITY_CONTROL','pretrained':False,
 'actual_gpu':False,'arms':results,'boundary':'Random tiny CPU models; actual independent worker reload is required later.'}))
'''
