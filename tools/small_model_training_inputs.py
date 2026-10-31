"""Fixed train-partition inputs for an implementation-only four-update probe."""
import json
from tools import abductive_benchmark as base, abductive_baseline as prompts
from tools import abductive_scoring as score, temporal_benchmark as temporal


def specification():
    family=min(f for f,(split,_) in base.catalog().items() if split=='train')
    original=list(base.episode_inputs(base.make_question(family,1)))
    payloads=[original[0],original[1],original[-1],list(temporal.episode_inputs(family,1))[-1]]
    rows=[]
    for payload in payloads:
        temporal_task=payload['task']=='temporal_revision'
        ref=temporal.reference(payload) if temporal_task else base.reference(payload)
        converted=temporal.as_revision(payload) if temporal_task else payload
        answer=score.optimal_response(converted,ref)
        score.validate_response(converted,answer)
        rows.append({'id':base.exact.sha(base.exact.canonical(payload)),
            'messages':prompts.messages(payload,'B1','json'),
            'answer':base.exact.canonical(answer).decode().strip()})
    return {'schema':'tiny_lora_feasibility_v1','rows':rows,'rank':4,'steps':4,
            'seed':17,'learning_rate':0.01,'maximum_tokens':2048}


def verify_tokens(tokenizer):
    spec=specification(); lengths=[]
    for row in spec['rows']:
        prompt=tokenizer.apply_chat_template(row['messages'],tokenize=True,return_dict=True,
            add_generation_prompt=True,enable_thinking=False,truncation=False,padding=False)['input_ids']
        answer=tokenizer.encode(row['answer'],add_special_tokens=False)+[106]
        if len(prompt)+len(answer)>2048:raise ValueError('training token overflow')
        lengths.append({'id':row['id'],'prompt_tokens':len(prompt),'supervised_tokens':len(answer),
            'sequence_sha256':base.exact.sha(base.exact.canonical(prompt+answer))})
    return {'training_specification_sha256':base.exact.sha(base.exact.canonical(spec)),
            'rows':lengths,'partition':'train','training_steps':4,'capability_claim':'NOT_ESTABLISHED'}


# Executed only in the free pinned runtime. Real Torch autograd and safetensors,
# random small Gemma, synthetic token IDs; no pretrained or hardware result.
CPU_CONTROL = r'''
import json,hashlib,base64,runpy
import torch
from transformers import Gemma4TextConfig,Gemma4ForCausalLM
torch.set_num_threads(1);torch.manual_seed(17)
config=Gemma4TextConfig(vocab_size=128,vocab_size_per_layer_input=128,
 hidden_size=32,intermediate_size=64,num_hidden_layers=2,num_attention_heads=4,
 num_key_value_heads=2,head_dim=8,global_head_dim=8,hidden_size_per_layer_input=4,
 max_position_embeddings=128,sliding_window=32,num_kv_shared_layers=0,
 layer_types=['sliding_attention','full_attention'],dtype='float32')
config._attn_implementation='sdpa'
model=Gemma4ForCausalLM(config).eval()
class Tokenizer:
 def apply_chat_template(self,*a,**k):return {'input_ids':[2,3,4]}
 def encode(self,*a,**k):return [5,6]
spec={'schema':'tiny_lora_feasibility_v1','rank':4,'steps':4,'seed':17,
 'learning_rate':0.01,'maximum_tokens':2048,'rows':[
 {'id':hashlib.sha256(str(i).encode()).hexdigest(),'messages':[{'role':'user','content':'CPU fixture'}],
 'answer':'{}'} for i in range(4)]}
function=runpy.run_path('/opt/backtrace/worker.py')['adapter_feasibility']
r=function(model,Tokenizer(),spec)
raw=base64.b64decode(r.pop('adapter_safetensors_base64'))
assert hashlib.sha256(raw).hexdigest()==r['adapter_sha256']
assert r['training_steps']==4 and r['changed_tensors'] and r['adapter_on_off_max_logit_difference']>0
assert r['disabled_base_max_logit_difference']==r['save_reload_max_logit_difference']==0
r.update(status='PASS_RANDOM_CPU_ADAPTER_CONTROL',pretrained=False,actual_gpu=False)
print(json.dumps(r))
'''
