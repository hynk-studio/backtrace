from pathlib import Path
from collections import Counter
from decimal import Decimal
import base64,hashlib,json,math,struct
from tools import small_model_trainability_data as data, small_model_lifecycle as life
ROOT=Path.cwd();root=ROOT/'docs/evidence/trainability-paid-run-41284716992';remote=root/'owner/minimum-owner/remote'
read=lambda p:json.loads(Path(p).read_bytes())
source='ebe6fa37b44ad465c16fa36cd2823f55cf93a050';originals=[]
for role in ('owner','watch'):
 receipt=read(root/role/'archive-provenance.json')
 assert hashlib.sha256((root/(role+'-job.log')).read_bytes()).hexdigest()==receipt['job_log_sha256']
 for item in receipt['members']:
  raw=(root/role/item['path']).read_bytes()
  assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
 originals.append({'role':role,'members':len(receipt['members']),'archive_sha256':receipt['archive']['sha256']})
state={p.stem:read(p) for p in (root/'state').glob('*.json') if p.name!='git-provenance.json'}
claim=state['claim'];pod=state['pod']['pod_id']
assert all(v['source_sha']==source for v in state.values())
assert state['owner']['boot_sha256']!=state['watch']['boot_sha256']
for name in ('owner-cleanup','watch-cleanup'):
 x=state[name];assert x['status']=='DELETED' and x['absence_reads']==2 and x['pod_id']==pod and x['claim_sha256']==life.digest(claim)
owner=read(root/'owner/minimum-owner.json');assert owner['status']=='PASS_TRAINABILITY_COLLECTION' and owner['provider_create_requests']==1
account=read(root/'owner/account-after.json')['observation'];assert account['inventory']['pod_count']==0 and account['inventory']['complete_paginated_list'] and account['account']['spend_per_hour_usd']=='0' and account['account']['auto_pay'] is False
bindings=[]
def walk(value):
 if isinstance(value,dict):
  for k,v in value.items():
   if k=='source_hashes':
    for path,digest in v.items():
     assert life.digest((ROOT/path).read_bytes())==digest,(path,digest)
     bindings.append((path,digest))
   else:walk(v)
 elif isinstance(value,list):
  for v in value:walk(v)
for p in (root/'owner').rglob('*.json'):walk(read(p))
qualified=read(ROOT/'docs/evidence/trainability-qualified-run-41283861825/prepare/input-verification.json')
schedule=read(remote/'input-schedule.json')['requests'];assert len(schedule)==48 and life.digest(schedule)==qualified['schedule_sha256']
examples=data.examples();example_map={x['id']:x for x in examples}
all_records=read(remote/'all-assignment-outcomes.json')['records'];assert len(all_records)==48
records={(r['arm'],r['id']):r for r in all_records};assert len(records)==48
summary={'status':'PASS_INDEPENDENT_EVIDENCE_VERIFICATION','source_sha':source,'actual_run_id':41284716992,'original_archives':originals,'original_members_verified':sum(x['members'] for x in originals),'state_blobs_verified':len(state),'source_binding_occurrences':len(bindings),'distinct_source_paths':len(set(p for p,_ in bindings)),'arms':{},'training':{}}
verified_wires=0
for arm in data.ARMS:
 directory=remote/'collections'/arm;assignment=read(directory/'assignment.json');collection=read(directory/'collection.json')
 expected=[r for r in schedule if r['arm']==arm]
 assert assignment['requests']==[{k:v for k,v in r.items() if k!='messages'} for r in expected] and assignment['retries']==0 and collection['status']=='COMPLETED' and collection['assigned']==16 and collection['mode']=='pretrained_cuda'
 assert collection['error'] is None and collection['worker_exit_codes']=={'E2B':0}
 hello=collection['worker_handshakes']['E2B'];assert hello['uid']==65532 and hello['caps']==0 and hello['cuda']['no_cpu_fallback']
 events=[json.loads(line) for line in (directory/'ledger.jsonl').read_bytes().splitlines()];assert len(events)==32
 for i,request in enumerate(expected):
  record=records[arm,request['id']];assert collection['records'][i]==record
  assert events[i*2]=={'event':'STARTED','index':i,'model':'E2B','arm':arm,'id':request['id']}
  assert events[i*2+1]=={'event':'FINISHED','index':i,'record':record}
  wire=read(directory/f'wire-{i:04d}.json')
  assert all(wire[k]==request[k] for k in ('id','input_tokens','input_ids_sha256'))
  assert wire['output_ids']==record['raw_output_ids'] and wire['raw_text']==record['raw_text'] and wire['elapsed_seconds']==record['worker_seconds']
  assert record['generated_tokens']==len(wire['output_ids']) and record['finish_reason']=='END' and wire['output_ids'][-1]==106
  assert record['answer_text']==record['raw_text'].removesuffix('<turn|>')
  assert len(wire['output_ids'])<=768;verified_wires+=1
 teardown=read(remote/(arm+'-evaluation-teardown.json'))['worker'];assert not teardown['same_process_alive'] and teardown['exit_code']==0
 summary['arms'][arm]={'coverage':collection['coverage'],'wall_seconds':collection['wall_seconds'],'generation_seconds':sum(r['worker_seconds'] for r in collection['records']),'output_tokens':sum(r['generated_tokens'] for r in collection['records']),'evaluation_worker':teardown,'fresh_reload':hello.get('candidate_adapter')}
 if arm=='BASE':assert not collection['training'] and 'candidate_adapter' not in hello
for arm in ('Q1','Q4'):
 train=read(remote/(arm+'-training-ready.json'))['candidate_adapter'];reload=summary['arms'][arm]['fresh_reload'];count={'Q1':1,'Q4':4}[arm]
 assert train['status']=='PASS_TRAINABILITY_UPDATES' and train['training_steps']==train['updates_in_worker']==640
 assert train['training_input_sha256']==qualified['specification_sha256'][arm] and train['projection_count']==count and len(train['changed_tensors'])==count*2
 assert train['disabled_base_max_logit_difference']==train['save_reload_max_logit_difference']==0 and train['adapter_on_off_max_logit_difference']>0
 assert reload['status']=='PASS_FRESH_PROCESS_TRAINABILITY_RELOAD' and reload['updates_in_worker']==0 and reload['adapter_sha256']==train['adapter_sha256'] and reload['observed_probe_logits_sha256']==train['trained_probe_logits_sha256']
 raw=base64.b64decode(train['adapter_safetensors_base64'],validate=True);assert len(raw)==train['adapter_bytes'] and hashlib.sha256(raw).hexdigest()==train['adapter_sha256']
 header_length=struct.unpack('<Q',raw[:8])[0];header=json.loads(raw[8:8+header_length]);parameters=0
 for key,tensor in header.items():
  if key=='__metadata__':continue
  assert tensor['dtype']=='F32';parameters+=math.prod(tensor['shape'])
 assert parameters==train['trainable_parameters']
 (root/(arm+'-adapter.safetensors')).write_bytes(raw)
 events=[];fixed=[]
 for line in (remote/(arm+'-training-stderr.log')).read_text().splitlines():
  if line.startswith('{'):
   event=json.loads(line)
   if event.get('phase')=='TRAINABILITY_UPDATE_FINISHED':events.append(event)
   if event.get('phase')=='TRAINABILITY_FIXED_LOSS':fixed.append(event)
 assert len(events)==640 and len(fixed)==2
 for i,event in enumerate(events):
  assert event['step']==i+1 and event['epoch']==i//16+1 and event['id']==examples[i%16]['id'] and event['arm']==arm
  assert event['loss']==train['losses'][i] and event['gradient_norm']==train['gradient_norms'][i] and math.isfinite(event['loss']) and math.isfinite(event['gradient_norm'])
 for event in fixed:assert event['measurement']==train[event['stage']+'_fixed_loss']
 training_worker=read(remote/(arm+'-training-teardown.json'))['worker'];evaluation_worker=summary['arms'][arm]['evaluation_worker']
 assert not training_worker['same_process_alive'] and training_worker['exit_code']==0 and (training_worker['pid'],training_worker['start_ticks'])!=(evaluation_worker['pid'],evaluation_worker['start_ticks'])
 metrics={k:train[k] for k in ('training_steps','trainable_parameters','adapter_bytes','adapter_sha256','target_modules','seconds','peak_allocated_bytes','peak_reserved_bytes','adapter_on_off_max_logit_difference')}
 metrics['training_worker']=training_worker;metrics['fixed_loss']={}
 for stage in ('before','after'):
  measurements=train[stage+'_fixed_loss'];assert measurements['supervised_tokens']*40==61120
  rows=measurements['rows'];assert [r['id'] for r in rows]==[r['id'] for r in examples]
  metrics['fixed_loss'][stage]={'all_token_mean_nll':measurements['token_mean_nll'],'first_token_mean_nll':sum(r['first_token_nll'] for r in rows)/16,**{kind:sum(r['mean_nll']*r['supervised_tokens'] for r in rows if example_map[r['id']]['kind']==kind)/sum(r['supervised_tokens'] for r in rows if example_map[r['id']]['kind']==kind) for kind in ('reasoning','format')}}
 metrics['first_token_argmax_matches_generation']=sum(r['first_token_argmax']==records[arm,r['id']]['raw_output_ids'][0] for r in train['after_fixed_loss']['rows']);assert metrics['first_token_argmax_matches_generation']==16
 summary['training'][arm]=metrics
q1=read(remote/'Q1-training-ready.json')['candidate_adapter'];q4=read(remote/'Q4-training-ready.json')['candidate_adapter']
assert q1['before_fixed_loss']==q4['before_fixed_loss'] and q1['untrained_probe_logits_sha256']==q4['untrained_probe_logits_sha256']
summary['verified_wire_ledger_collection_assignments']=verified_wires
summary['identical_Q1_Q4_output_token_sequences']=sum(records['Q1',r['id']]['raw_output_ids']==records['Q4',r['id']]['raw_output_ids'] for r in examples)
summary['scoring']=read(root/'scoring.json')['arms'];summary['failures']=[]
reasoning={(r['episode'],r['task']):r for r in examples if r['kind']=='reasoning'}
for record in all_records:
 e=example_map[record['id']];error=None
 try:
  response=data.prior.base.strict_json(record['answer_text']);parent=reasoning[e['episode'],e['task']];converted,ref=data.prior.reference(json.loads(parent['messages'][1]['content']));data.prior.score.validate_response(converted,response)
 except (ValueError,TypeError,KeyError) as ex:error=str(ex)
 if error:summary['failures'].append({'arm':record['arm'],'id':record['id'],'task':e['task'],'kind':e['kind'],'error':error})
summary['cost']={'initial_balance_usd':claim['costs']['initial_balance'],'remaining_balance_usd':account['account']['credit_balance_usd'],'observed_run_debit_usd':str(Decimal(claim['costs']['initial_balance'])-Decimal(account['account']['credit_balance_usd'])),'cumulative_continuation_debit_usd':str(Decimal('2.9060441339')-Decimal(account['account']['credit_balance_usd'])),'account_observed_at':account['account']['observed_at'],'inventory_observed_at':account['inventory']['observed_at'],'pod_count':0,'hourly_spend_usd':'0','auto_pay':False,'billing':'Observed balance differences; settlement can lag.'}
summary['limits']=['One seed and sixteen selected training examples; no held-out inference.','Format inputs intentionally contain the answer values.','Both trained arms fail all eight reasoning schemas; learned posterior correctness is not established.','Q4 changes adapter placement and parameter count together.','The historical masked run is not a controlled causal comparator.']
(root/'verification.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ('status','original_members_verified','state_blobs_verified','source_binding_occurrences','distinct_source_paths','verified_wire_ledger_collection_assignments','identical_Q1_Q4_output_token_sequences','scoring','cost')},sort_keys=True))
