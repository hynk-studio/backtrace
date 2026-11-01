from pathlib import Path
import hashlib,json,sys
from tools import small_model_lifecycle as life, small_model_onecase_scope as scope

root=Path(sys.argv[1]);repo=Path.cwd()
read=lambda p:json.loads(Path(p).read_bytes())
run=read(root/'run.json');jobs=read(root/'jobs.json')['jobs']
assert run['head_sha']=='08148b7245b772830319d3bdc90be3ad2c74ca51'
assert run['run_attempt']==1 and run['event']=='push' and run['path']==scope.WORKFLOW
assert run['status']=='completed' and run['conclusion']=='success'
assert {r['name'] for r in jobs}=={'owner','watch','prepare','container'}
assert all(r['conclusion']=='success' for r in jobs)
git_source=read(root/'source-binding-git.json')
assert git_source['source_sha']==run['head_sha']
for path,sha in git_source['files'].items():
 raw=(repo/path).read_bytes()
 assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==sha,path
assert len(git_source['files'])==110
assert git_source['files']['tools/runpod_control.py']=='cf2dfe38b54b20a611d78c18c3a3e73d1b23644b'
assert b'Ran 32 tests' in (root/'focused-tests.log').read_bytes() and b'\nOK\n' in (root/'focused-tests.log').read_bytes()

members=0;bindings=[]
def walk(value):
 if isinstance(value,dict):
  for k,v in value.items():
   if k=='source_hashes':
    for path,digest in v.items():
     assert life.digest((repo/path).read_bytes())==digest,(path,digest)
     bindings.append((path,digest))
   else:walk(v)
 elif isinstance(value,list):
  for v in value:walk(v)
for role in ('owner','watch','prepare','container'):
 provenance=read(root/role/'archive-provenance.json')
 assert hashlib.sha256((root/(role+'-job.log')).read_bytes()).hexdigest()==provenance['job_log_sha256']
 for item in provenance['members']:
  raw=(root/role/item['path']).read_bytes()
  assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
  if item['path'].endswith('.json'):walk(json.loads(raw))
  members+=1
test=(root/'container/tests.log').read_text()
assert 'Ran 775 tests' in test and '\nOK\n' in test and '\nFAILED' not in test
cpu=read(root/'container/container-trainability-cpu-control.json')
assert cpu['status']=='PASS_RANDOM_CPU_TRAINABILITY_CONTROL'
assert cpu['pretrained'] is False and cpu['actual_gpu'] is False and set(cpu['arms'])=={'Q4'}
training=cpu['arms']['Q4']['training'];reload=cpu['arms']['Q4']['fresh_model_reload']
assert training['training_steps']==640 and len(training['losses'])==640
assert training['after_fixed_loss']['token_mean_nll']<training['before_fixed_loss']['token_mean_nll']
assert reload['updates_in_worker']==0 and reload['observed_probe_logits_sha256']==training['trained_probe_logits_sha256']
inputs=read(root/'prepare/input-verification.json')
assert inputs['assigned']==2 and inputs['per_arm']==1 and inputs['planned_updates_per_trained_arm']==640
assert inputs['training']['effective_training_tokens_per_arm']==906880
assert inputs['training']['supervised_tokens_per_arm']==38400
assert inputs['training']['examples'][0]['id']==scope.onecase.data.SELECTED_ID
assert read(root/'owner/minimum-owner.json')['status']=='PASS_FREE_REMOTE_CLEANUP'
assert read(root/'container/container.json')['status']=='PASS_FREE_MINIMUM_ENTRY'
assert read(root/'watch/minimum-watch.json')['status']=='DELETED'
result={'status':'PASS_INDEPENDENT_QUALIFICATION_VERIFICATION','source_sha':run['head_sha'],
 'qualification_run_id':run['id'],'native_tests':775,'source_git_blobs_verified':110,'focused_tests':32,'original_members_verified':members,
 'source_binding_occurrences':len(bindings),'distinct_bound_paths':len(set(p for p,_ in bindings)),
 'cpu_before_nll':training['before_fixed_loss']['token_mean_nll'],
 'cpu_after_nll':training['after_fixed_loss']['token_mean_nll'],
 'training_specification_sha256':inputs['specification_sha256'],
 'boundary':'Free input and implementation qualification; actual pretrained GPU result is separate.'}
(root/'verification.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print(json.dumps(result,sort_keys=True))
