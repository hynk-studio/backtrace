"""Prospective one-seed curriculum screening using the existing finite teacher.

B2 is specifically a forward-probability/bookkeeping control, not a claim to
represent all general-reasoning SFT. Both arms receive identical train facts and
common format practice. Matching concerns supervised tokens, updates and padded
lengths; unpadded prompt/target lengths are measured and reported separately.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json

from tools import abductive_benchmark as base, abductive_baseline as prompts
from tools import abductive_scoring as score, temporal_benchmark as temporal

ARMS = ('B2', 'S')
TASKS = ('inference', 'abduction', 'revision', 'temporal_revision')
SEED = 17
MAXIMUM_TOKENS = 3072
MAXIMUM_EFFECTIVE_TOKENS = 1_000_000
FORWARD = '''
This is a forward-probability control exercise. The supplied facts and output fields are unchanged, but use the following objective instead of conditioning beliefs on observations. Perform the usual consistency and active-record bookkeeping checks; preserve any non-OK status and its required null/empty fields. Otherwise compute unconditional hypothesis marginals from the supplied model, without conditioning on the observed evidence. For abduction, enumerate positive-prior complete cause assignments and predict the requested events conditional on each assignment alone. For other tasks choose STOP with the action of highest unconditional expected utility; do not select an inspection. Revision outputs still list the correctly active observation IDs. Return only the applicable JSON object.'''
FORMAT = ('Convert the supplied ordered field/value pairs into one JSON object. '
          'Preserve every value, nested object and list exactly. Return no markdown '
          'or additional fields. This is formatting practice, not a diagnostic task.')


def digest(value):
    return base.exact.sha(base.exact.canonical(value))


def four_payloads(family, variant):
    ordinary = list(base.episode_inputs(base.make_question(family, variant)))
    return [ordinary[0], ordinary[1], ordinary[-1],
            list(temporal.episode_inputs(family, variant))[-1]]


def reference(payload):
    converted = temporal.as_revision(payload) if payload['task']=='temporal_revision' else payload
    ref = temporal.reference(payload) if payload['task']=='temporal_revision' else base.reference(payload)
    return converted, ref


def forward_answer(payload):
    """Change the probability objective, never fabricate labels for the original task."""
    converted, original = reference(payload)
    if original['status'] != 'OK':
        return score.optimal_response(converted, original)
    if payload['task']=='abduction':
        forward = deepcopy(payload)
        forward['evidence'] = []
    else:
        question = deepcopy(base.input_question(converted))
        question['evidence'] = []
        question['inspections'] = []
        forward = {'task':'inference', 'question':question}
    answer = score.optimal_response(forward, base.reference(forward))
    if payload['task'] in ('revision','temporal_revision'):
        answer['active_evidence_ids'] = original['active_evidence_ids']
    score.validate_response(converted, answer)
    return answer


def train_episodes():
    families = sorted(f for f,(split,_) in base.catalog().items() if split=='train')
    if len(families)!=12:
        raise ValueError('frozen twelve-family training partition required')
    selected=[]
    for scenario in range(8):
        for position in range(8):
            family=families[(scenario*5+position)%12]
            variants=[scenario+8*scale for scale in range(4)]
            variant=min(variants,key=lambda v:digest(['candidate-train-v1',family,v]))
            selected.append((family,variant))
    if len(selected)!=64 or len(set(selected))!=64:
        raise AssertionError('sixty-four distinct training episodes required')
    return selected


def training_pairs():
    result=[]
    for index,(family,variant) in enumerate(train_episodes()):
        payloads=four_payloads(family,variant)
        episode=digest(['episode',family,variant])
        episode_rows=[]
        for payload in payloads:
            converted, ref=reference(payload)
            specialist=score.optimal_response(converted,ref)
            score.validate_response(converted,specialist)
            ordinary=forward_answer(payload)
            identifier=digest(payload)
            common=prompts.messages(payload,'B1','json')
            control=deepcopy(common)
            control[0]['content']+=FORWARD
            pair={'id':identifier,'episode':episode,'family':family,'variant':variant,
                  'task':payload['task'],'kind':'reasoning','split':'train','arms':{
                'S':{'id':identifier,'messages':common,'answer':base.exact.canonical(specialist).decode().strip()},
                'B2':{'id':identifier,'messages':control,'answer':base.exact.canonical(ordinary).decode().strip()}}}
            result.append(pair);episode_rows.append(pair)
        # The same train-only formatting example is presented in both arms.
        parent=episode_rows[index%4]
        answer=parent['arms']['S']['answer']
        identifier=digest(['common-format-v1',parent['id']])
        messages=[{'role':'system','content':FORMAT},{'role':'user','content':
            base.exact.canonical({'fields':list(json.loads(answer).items())}).decode().strip()}]
        row={'id':identifier,'messages':messages,'answer':answer}
        result.append({'id':identifier,'episode':episode,'family':family,'variant':variant,
            'task':parent['task'],'kind':'common_format','split':'train',
            'arms':{'B2':deepcopy(row),'S':deepcopy(row)}})
    if len(result)!=320 or len({p['id'] for p in result})!=320:
        raise AssertionError('fixed320 distinct row pairs required')
    return sorted(result,key=lambda p:digest(['candidate-order-v1',SEED,p['id']]))


def exposed_development_episodes():
    """Exclude the entire historical episode, not only its already-seen views."""
    path=base.ROOT/'docs/evidence/e2b-run-41206950960/input-schedule.json'
    requests=json.loads(path.read_bytes())['requests']
    ids={r['id'] for r in requests if not r['id'].startswith('augnes-')}
    excluded=set()
    for family,(split,_) in base.catalog().items():
        if split!='development':continue
        for variant in range(32):
            views=list(base.episode_inputs(base.make_question(family,variant)))
            views+=list(temporal.episode_inputs(family,variant))
            if any(digest(p) in ids for p in views):excluded.add((family,variant))
    if not excluded:raise ValueError('historical development episode not identified')
    return excluded


def development_inputs():
    excluded=exposed_development_episodes()
    families=sorted(f for f,(split,_) in base.catalog().items() if split=='development')
    if len(families)!=8:raise ValueError('frozen eight-family development partition required')
    rows=[]
    for fi,family in enumerate(families):
        scenarios=list(range(8))+[(fi*3+j)%8 for j in range(4)]
        selected=set()
        for position,scenario in enumerate(scenarios):
            eligible=[v for v in range(scenario,32,8) if v not in selected and (family,v) not in excluded]
            if not eligible:raise ValueError('fresh episode supply exhausted')
            variant=min(eligible,key=lambda v:digest(['candidate-development-v1',family,v]))
            selected.add(variant)
            payload=four_payloads(family,variant)[(position+fi)%4]
            rows.append({'id':digest(payload),'episode':digest(['episode',family,variant]),
                'family':family,'variant':variant,'task':payload['task'],'split':'development',
                'input':payload,'messages':prompts.messages(payload,'B1','json')})
    if len(rows)!=96 or len({r['episode'] for r in rows})!=96:
        raise AssertionError('ninety-six distinct fresh development episodes required')
    return sorted(rows,key=lambda r:digest(['candidate-eval-order-v1',r['id']]))


def mask_positions(identifier,length,quota):
    if not 1<=quota<=length:raise ValueError('bounded label quota required')
    # Always supervise the terminal token; other positions are selected uniformly
    # by a fixed hash ranking, independent of target values and model responses.
    positions=sorted(range(length-1),key=lambda i:digest(['label-mask-v1',SEED,identifier,i]))[:quota-1]
    return sorted(positions+[length-1])


def materialize(tokenizer):
    specs={arm:{'schema':'matched_candidate_adapter_v1','arm':arm,'rows':[],
        'rank':4,'steps':320,'seed':SEED,'learning_rate':0.01,
        'maximum_tokens':MAXIMUM_TOKENS} for arm in ARMS}
    totals={arm:Counter() for arm in ARMS};pairs=[]
    for pair in training_pairs():
        encoded={}
        for arm in ARMS:
            row=pair['arms'][arm]
            prompt=tokenizer.apply_chat_template(row['messages'],tokenize=True,return_dict=True,
                add_generation_prompt=True,enable_thinking=False,truncation=False,padding=False)['input_ids']
            answer=tokenizer.encode(row['answer'],add_special_tokens=False)+[106]
            encoded[arm]=(prompt,answer)
        padded=max(len(p)+len(a) for p,a in encoded.values())
        quota=min(len(a) for p,a in encoded.values())
        if padded>MAXIMUM_TOKENS:raise ValueError('matched training sequence overflow')
        metadata={k:pair[k] for k in ('id','episode','family','variant','task','kind','split')}
        metadata.update(padded_tokens=padded,supervised_tokens=quota,arms={})
        for arm in ARMS:
            prompt,answer=encoded[arm];positions=mask_positions(pair['id'],len(answer),quota)
            row=dict(pair['arms'][arm],padded_tokens=padded,supervised_positions=positions,
                prompt_tokens=len(prompt),answer_tokens=len(answer),
                sequence_sha256=digest(prompt+answer))
            specs[arm]['rows'].append(row)
            totals[arm].update(prompt_tokens=len(prompt),answer_tokens=len(answer),
                effective_sequence_tokens=len(prompt)+len(answer),padded_tokens=padded,
                supervised_tokens=quota,steps=1)
            metadata['arms'][arm]={k:row[k] for k in ('prompt_tokens','answer_tokens','sequence_sha256')}
        pairs.append(metadata)
    for arm in ARMS:
        if totals[arm]['effective_sequence_tokens']>MAXIMUM_EFFECTIVE_TOKENS:
            raise ValueError('per-arm effective token ceiling exceeded')
    for key in ('steps','padded_tokens','supervised_tokens'):
        if totals['B2'][key]!=totals['S'][key]:raise AssertionError('matching invariant failed')
    return {'specifications':specs,'pairs':pairs,'totals':{k:dict(v) for k,v in totals.items()},
        'training_episodes':64,'reasoning_rows':256,'common_format_rows':64,
        'limitations':['B2 is a specified forward-probability/bookkeeping control, not all general reasoning.',
        'Updates, loss-bearing tokens and padded lengths match exactly; unpadded lengths are reported separately.',
        'This is one-seed candidate screening, not confirmation or an Augnes benefit estimate.']}


# Executed only in the existing free pinned runtime. This exercises numerical
# updates and a newly constructed model reload, not pretrained capability.
CPU_CONTROL = r'''
import base64,hashlib,json,runpy
import torch
from transformers import Gemma4TextConfig,Gemma4ForCausalLM
torch.set_num_threads(1);torch.manual_seed(17)
config=Gemma4TextConfig(vocab_size=128,vocab_size_per_layer_input=128,
 hidden_size=32,intermediate_size=64,num_hidden_layers=2,num_attention_heads=4,
 num_key_value_heads=2,head_dim=8,global_head_dim=8,hidden_size_per_layer_input=4,
 max_position_embeddings=128,sliding_window=32,num_kv_shared_layers=0,
 layer_types=['sliding_attention','full_attention'],dtype='float32')
config._attn_implementation='sdpa'
worker=runpy.run_path('/opt/backtrace/worker.py')
canonical=worker['canonical']
class Tokenizer:
 def apply_chat_template(self,*a,**k):return {'input_ids':[2,3,4]}
 def encode(self,*a,**k):return [5,6]
tokenizer=Tokenizer();results={}
for arm in ('B2','S'):
 torch.manual_seed(17)
 model=Gemma4ForCausalLM(config).eval()
 base_state={k:v.detach().clone() for k,v in model.state_dict().items()}
 spec={'schema':'matched_candidate_adapter_v1','arm':arm,'rank':4,'steps':320,
  'seed':17,'learning_rate':0.01,'maximum_tokens':3072,'rows':[
   {'id':hashlib.sha256(str(i).encode()).hexdigest(),'messages':[{'role':'user','content':'CPU control'}],
    'answer':'{}','padded_tokens':8,'supervised_positions':[0,2],
    'prompt_tokens':3,'answer_tokens':3,
    'sequence_sha256':hashlib.sha256(canonical([2,3,4,5,6,106])).hexdigest()}
   for i in range(320)]}
 result=worker['candidate_train'](model,tokenizer,spec)
 raw=base64.b64decode(result['adapter_safetensors_base64'],validate=True)
 assert hashlib.sha256(raw).hexdigest()==result['adapter_sha256']
 restore={k:result[k] for k in ('arm','training_steps','training_input_sha256',
  'adapter_bytes','adapter_sha256','adapter_safetensors_base64','target_module',
  'probe_messages','probe_input_ids_sha256','trained_probe_logits_sha256')}
 restore['schema']='matched_candidate_restore_v1'
 fresh=Gemma4ForCausalLM(config).eval();fresh.load_state_dict(base_state,strict=True)
 reloaded=worker['candidate_restore'](fresh,tokenizer,restore)
 assert reloaded['status']=='PASS_FRESH_PROCESS_CANDIDATE_RELOAD'
 assert reloaded['updates_in_worker']==0
 assert result['training_steps']==320 and set(result['changed_tensors'])=={'a','b'}
 assert result['adapter_on_off_max_logit_difference']>0
 assert result['save_reload_max_logit_difference']==result['disabled_base_max_logit_difference']==0
 rejected={}
 for name,changes in [('bad_hash',{'adapter_sha256':'0'*64}),
                      ('bad_probe',{'probe_input_ids_sha256':'0'*64})]:
  try:worker['candidate_restore'](Gemma4ForCausalLM(config).eval(),tokenizer,dict(restore,**changes))
  except ValueError:rejected[name]=True
  else:raise AssertionError(name+' was accepted')
 bad=Gemma4ForCausalLM(config).eval()
 try:worker['candidate_restore'](bad,tokenizer,restore)
 except ValueError:rejected['wrong_base']=True
 else:raise AssertionError('wrong base accepted')
 for key in ('adapter_safetensors_base64','probe_messages'):result.pop(key)
 results[arm]={'training':result,'fresh_model_reload':reloaded,'rejections':rejected}
print(json.dumps({'status':'PASS_RANDOM_CPU_MATCHED_CONTROL','actual_gpu':False,
 'pretrained':False,'arms':results,'boundary':'Fresh model instance in this control process; actual independent worker reload is a later GPU measurement.'}))
'''
