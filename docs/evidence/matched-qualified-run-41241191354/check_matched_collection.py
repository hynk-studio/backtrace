import json,sys,tempfile,types
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,'/workspace/scratch/565575038e73/backtrace-matched')
from tools import small_model_matched as entry
from tests.test_small_model_runner import FakeChannel,Tokenizer,request
from tests.test_small_model_matched import MatchedEntryTests
base=entry.ROOT;calls=[];pid=100
rows=[dict(request(i),model='E2B',arm=arm) for arm in entry.ARMS for i in range(116)]
class Channel(FakeChannel):
 def __init__(self,arm,train):super().__init__();self.arm=arm;self.train=train
 def read(self,deadline):
  value=dict(super().read(deadline),mode='pretrained_cuda',cuda={'uuid':'fixture','no_cpu_fallback':True})
  if self.train:
   value['candidate_adapter']=dict(MatchedEntryTests().receipt(),arm=self.arm)
  elif self.arm!='B1':
   value['candidate_adapter']={'status':'PASS_FRESH_PROCESS_CANDIDATE_RELOAD','arm':self.arm,'training_steps':320,'updates_in_worker':0,'adapter_sha256':MatchedEntryTests().receipt()['adapter_sha256']}
  return value
 def exchange(self,req,deadline):
  value=super().exchange(req,deadline);value['cuda_metrics']={'peak_allocated_bytes':1,'peak_reserved_bytes':2,'post_free_bytes':2,'total_bytes':4};self.partial=entry.runner.exact.canonical(value);return value

def channel(command,log):
 arg=command[-1];job=next(j for j in entry.JOBS if j in arg);calls.append(job)
 return Channel(job.split('-')[1],job.endswith('-train'))
def stopped(*a):
 global pid
 pid+=1
 return {'worker':{'pid':pid,'start_ticks':str(pid),'same_process_alive':False},'gpu':{'idle':True}}
module=types.ModuleType('transformers');module.AutoTokenizer=Mock();module.AutoTokenizer.from_pretrained.return_value=Tokenizer()
with tempfile.TemporaryDirectory(dir=base/'.local') as td:
 root=Path(td);(root/'.local/e2b/matched').mkdir(parents=True);out=root/'evidence';out.mkdir()
 (root/'.local/e2b/matched/schedule.json').write_text(json.dumps({'requests':rows}))
 spec=root/'input.json';spec.write_text(json.dumps({'prefix':['fixture'],'gpu_uuid':'fixture','training_spec_sha256':{'B2':'a'*64,'S':'a'*64}}))
 with patch.object(entry,'ROOT',root),patch.dict(sys.modules,{'transformers':module}),patch.object(entry,'schedule',return_value=rows),patch.object(entry.container,'ContainerChannel',side_effect=channel),patch.object(entry,'check_stopped',side_effect=stopped),patch.object(entry,'deliver_restore') as deliver:
  result=entry.collect(spec,out)
  assert result['assigned']==348 and result['coverage']=={'OK':348} and deliver.call_count==2
  evidence=json.loads((out/'all-assignment-outcomes.json').read_text())
  assert evidence['collections']['B1']['training'] is False
  assert all(evidence['collections'][a]['training'] is True for a in ('B2','S'))
  assert calls==list(entry.JOBS)
  assert len(list((out/'collections').rglob('wire-*.json')))==348
  print(json.dumps({'status':'PASS_AUTHORED_COORDINATOR_CONTROL','real_model':False,'assigned':348,'calls':calls,'training_metadata':{a:evidence['collections'][a]['training'] for a in entry.ARMS},'limitations':'Authored fake channels; validates real collector sequencing/retention only, not transport or learning.'}))
