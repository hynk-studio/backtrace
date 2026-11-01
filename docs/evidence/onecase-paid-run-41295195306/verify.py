"""Verify a rejected create and zero model execution, not a learning result."""
from pathlib import Path
from decimal import Decimal
import hashlib,json,sys
from tools import small_model_lifecycle as life, small_model_onecase as onecase
ROOT=Path.cwd()
root=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'docs/evidence/onecase-paid-run-41295195306'
qualified=ROOT/'docs/evidence/onecase-qualified-run-41294192731'
read=lambda p:json.loads(Path(p).read_bytes())
run=read(root/'run.json');source=run['head_sha']
assert source=='ca6d2ce07c19eef01f465a0c59fe85f4cbd487a2'
assert run['status']=='completed' and run['conclusion']=='failure' and run['run_attempt']==1
assert run['event']=='push' and run['path']=='.github/workflows/small-model-onecase.yml'
originals=[];bindings=[]
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
for role in ('owner','watch'):
 receipt=read(root/role/'archive-provenance.json')
 assert hashlib.sha256((root/(role+'-job.log')).read_bytes()).hexdigest()==receipt['job_log_sha256']
 for item in receipt['members']:
  raw=(root/role/item['path']).read_bytes()
  assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
  if item['path'].endswith('.json'):walk(json.loads(raw))
 originals.append({'role':role,'members':len(receipt['members']),'archive_sha256':receipt['archive']['sha256']})
state={p.stem:read(p) for p in (root/'state').glob('*.json') if p.name!='git-provenance.json'}
provenance=read(root/'state/git-provenance.json')
assert {x['filename'][:-5] for x in provenance['files']}==set(state)
assert len(provenance['files'])==len(state)
for item in provenance['files']:
 raw=(root/'state'/item['filename']).read_bytes()
 assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['sha']
assert all(v['source_sha']==source for v in state.values())
assert 'pod' not in state and state['owner']['boot_sha256']!=state['watch']['boot_sha256']
claim=state['claim'];done=state['done']
assert done['failure']=={'type':'ProviderError','http_status':400}
assert done['provider_create_requests']==1 and done['claim_sha256']==life.digest(claim)
cleanups={}
for name in ('owner-cleanup','watch-cleanup'):
 x=state[name]
 assert x['status']=='NO_RESOURCE_OBSERVED' and x['absence_reads']==2 and x['pod_id'] is None
 assert x['claim_sha256']==life.digest(claim)
 assert x['completed_at']>=claim['requested_at']+claim['total_seconds']-claim['cleanup_seconds']
 assert x['completed_at']<=claim['requested_at']+claim['total_seconds']
 assert [r['state'] for r in x['history'][-2:]]==['ABSENT','ABSENT']
 assert x['history'][-2]['at']>=claim['requested_at']+claim['total_seconds']-claim['cleanup_seconds']
 assert x['history'][-1]['at']-x['history'][-2]['at']>=claim['poll_seconds']
 cleanups[name]=x
owner=read(root/'owner/minimum-owner.json');watch=read(root/'watch/minimum-watch.json')
assert owner['status']=='FAIL' and owner['failure']==done['failure']
assert owner['error']=='provider HTTP 400' and owner['provider_create_requests']==1
assert owner['cleanup']=={k:v for k,v in state['owner-cleanup'].items() if k!='source_sha'}
assert watch['status']=='NO_RESOURCE_OBSERVED'
assert all(watch[k]==v for k,v in state['watch-cleanup'].items() if k!='source_sha')
assert watch['provider_create_requests']==0 and watch['claim_sha256']==life.digest(claim)
account=read(root/'owner/account-after.json')['observation']
assert account['inventory']['pod_count']==0 and account['inventory']['complete_paginated_list']
assert account['account']['spend_per_hour_usd']=='0' and account['account']['auto_pay'] is False
inputs=read(root/'owner/assignment-before-allocation.json')
prior_inputs=read(qualified/'prepare/input-verification.json')
for key in ('schedule_sha256','specification_sha256','training','assigned_before_allocation'):
 assert inputs[key]==prior_inputs[key],key
assert inputs['assigned']==2 and inputs['pretrained_requests']==inputs['training_steps']==0
remote=root/'owner/minimum-owner/remote'
outcomes=read(remote/'all-assignment-outcomes.json')
assert outcomes['assigned']==2 and outcomes['coverage']=={'NOT_RUN':2}
assert {(r['arm'],r['id']) for r in outcomes['records']}=={(a,onecase.data.SELECTED_ID) for a in onecase.data.ARMS}
assert all(r['status']=='NOT_RUN' and 'answer_text' not in r for r in outcomes['records'])
assert not (remote/'Q4-training-ready.json').exists() and not (remote/'connected-receipt.json').exists()
with onecase.configured():scored=onecase.entry.evaluate(remote)
assert scored==read(root/'scoring.json')
assert all(r['collection_status']=='NOT_RUN' for r in scored['rows'])
balance=Decimal(account['account']['credit_balance_usd'])
summary={'status':'PASS_REJECTED_CREATE_EVIDENCE_VERIFICATION','source_sha':source,
 'actual_run_id':run['id'],'outcome':'PROVIDER_CREATE_HTTP_400_MODEL_VERIFICATION_NOT_RUN',
 'original_archives':originals,'original_members_verified':sum(r['members'] for r in originals),
 'state_blobs_verified':len(state),'source_binding_occurrences':len(bindings),
 'distinct_source_paths':len(set(p for p,_ in bindings)),
 'provider_create_requests':1,'observed_pods':0,'actual_training_updates':0,
 'actual_generations':0,'original_assignments':2,'coverage':outcomes['coverage'],
 'cleanup':cleanups,'cost':{'initial_balance_usd':claim['costs']['initial_balance'],
  'remaining_balance_usd':str(balance),
  'observed_run_debit_usd':str(Decimal(claim['costs']['initial_balance'])-balance),
  'cumulative_continuation_debit_usd':str(Decimal('2.9060441339')-balance),
  'account_observed_at':account['account']['observed_at'],
  'inventory_observed_at':account['inventory']['observed_at'],
  'hourly_spend_usd':'0','auto_pay':False,'billing':'Observed balance; settlement can lag.'},
 'limitation':'No pretrained GPU result or train-fit conclusion; both original assignments were NOT_RUN.'}
(root/'verification.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='cleanup'},sort_keys=True))
