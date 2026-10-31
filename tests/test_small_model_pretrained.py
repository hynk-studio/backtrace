import json
from pathlib import Path
import select
import socket
import tempfile
import subprocess
import sys
import time
import types
import unittest
from unittest import mock

from tools import small_model_pretrained as entry, small_model_pretrained_scope as scope
from tools import small_model_minimum as minimum


class PretrainedTests(unittest.TestCase):
    def test_real_collector_uses_allowed_local_path_and_preserves_raw_checkpoints(self):
        from tests.test_small_model_runner import FakeChannel,Tokenizer,request
        class ModelFixture(FakeChannel):
            def read(self,deadline):
                return dict(super().read(deadline),mode='pretrained_cuda',cuda={'uuid':'fixture','no_cpu_fallback':True})
            def exchange(self,req,deadline):
                result=super().exchange(req,deadline)
                result['cuda_metrics']={'peak_allocated_bytes':1,'peak_reserved_bytes':2,'post_free_bytes':2,'total_bytes':4}
                self.partial=entry.runner.exact.canonical(result);return result
        module=types.ModuleType('transformers')
        module.AutoTokenizer=mock.Mock();module.AutoTokenizer.from_pretrained.return_value=Tokenizer()
        with tempfile.TemporaryDirectory(dir=minimum.ROOT/'.local') as td:
            root=Path(td);(root/'.local').mkdir();output=root/'evidence';output.mkdir()
            spec=root/'collector.json';spec.write_text(json.dumps({'prefix':['fixture'],'gpu_uuid':'fixture'}))
            with mock.patch.object(entry,'ROOT',root),mock.patch.dict(sys.modules,{'transformers':module}),\
                    mock.patch.object(entry.runner,'load_scope',return_value=({},[request()],None)),\
                    mock.patch.object(entry,'replay_schedule',return_value=[]),\
                    mock.patch.object(entry.container,'ContainerChannel',return_value=ModelFixture()):
                result=entry.collect(spec,output)
                self.assertEqual(result['status'],'COMPLETED');self.assertEqual(result['assigned'],1)
                self.assertFalse((output/'collection').exists())
                saved=entry.preserve_collection(output)
                self.assertGreater(saved['files'],3)
                self.assertEqual((root/'.local/e2b-collection/ledger.jsonl').read_bytes(),
                                 (output/'collection/ledger.jsonl').read_bytes())
                self.assertTrue((output/'collection/wire-0000.json').exists())

    def test_passive_driver_listener_cannot_accept_or_read_a_queued_peer(self):
        code="""import ctypes,errno,json,socket,os,sys
from tools.small_model_container_worker import restrict_syscalls
restrict_syscalls();s=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET|socket.SOCK_CLOEXEC,0);r={}
s.bind('\\0backtrace-cuda-'+str(os.getpid()));s.listen(128)
print(json.dumps({'address':s.getsockname()}),flush=True)
if sys.stdin.readline()!='continue\\n':raise RuntimeError('test peer not ready')
lib=ctypes.CDLL(None,use_errno=True)
def bare_socket():
 fd=lib.syscall(41,1,5,0)
 if fd<0:raise OSError(ctypes.get_errno(),'raw socket')
 os.close(fd)
def accept(nr):
 fd=lib.syscall(nr,s.fileno(),0,0,0)
 if fd<0:raise OSError(ctypes.get_errno(),'accept')
 os.close(fd)
for name,fn in [('connect',lambda:s.connect('/tmp/backtrace-not-a-server')),
 ('accept',lambda:accept(43)),('accept4',lambda:accept(288)),
 ('sendmsg',lambda:s.sendmsg([b'x'])),('sendto',lambda:s.sendto(b'x','/tmp/backtrace-not-a-server')),
 ('inet',lambda:socket.socket()),('unix_stream',lambda:socket.socket(socket.AF_UNIX)),
 ('unix_no_cloexec',bare_socket),
 ('socketpair',socket.socketpair)]:
 try:fn()
 except OSError as e:r[name]=e.errno==errno.EPERM
 else:r[name]=False
try:os.read(s.fileno(),1)
except OSError as e:r['listener_cannot_receive']=e.errno in (errno.EINVAL,errno.ENOTCONN)
else:r['listener_cannot_receive']=False
s.close();print(json.dumps(r))
"""
        p=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertTrue(select.select([p.stdout],[],[],10)[0],'listener startup timed out')
            first=p.stdout.readline()
            if not first:
                _,err=p.communicate(timeout=5);self.fail(err)
            address=json.loads(first)['address']
            with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET|socket.SOCK_CLOEXEC,0) as peer:
                peer.settimeout(3);peer.connect(address);peer.sendall(b'queued-peer-data')
                out,err=p.communicate('continue\n',timeout=10)
            self.assertEqual(p.returncode,0,err)
            self.assertEqual(len(json.loads(out)),10);self.assertTrue(all(json.loads(out).values()))
        finally:
            if p.poll() is None:p.kill()
            p.communicate(timeout=5)

    def test_no_failed_partial_or_cpu_hardware_record_authorizes_a_job(self):
        good={'status':'PASS_ACTUAL_HARDWARE_ONLY','actual_gpu':True,
              'checks':{'boundary':True,'deadline':True},'initial_gpu':{'uuid':'fixture'}}
        for row in ({},dict(good,status='DIAGNOSTIC_RECORDED'),dict(good,actual_gpu=False),
                    dict(good,checks={}),dict(good,checks={'boundary':False})):
            with self.subTest(row=row),self.assertRaises(ValueError):entry.qualified_job(row,{})
        job=entry.qualified_job(good,{'vision_tower.weight':{},'language_model.weight':{}})
        self.assertEqual(job['mode'],'pretrained_cuda');self.assertEqual(job['container_model'],'E2B')
        self.assertEqual(job['hardware_receipt_sha256'],minimum.life.digest(good))

    def test_replay_arms_have_same_facts_and_no_rubric_or_later_outcomes(self):
        with mock.patch.object(entry.ready,'encode',return_value={'overflow':False,'input_tokens':100,'token_ids_sha256':'a'*64}):
            rows=entry.replay_schedule(mock.Mock())
        self.assertEqual(len(rows),6);self.assertEqual(len({r['id'] for r in rows}),3)
        for b0,b1 in zip(rows[::2],rows[1::2]):
            self.assertEqual(b0['messages'][1],b1['messages'][1])
            self.assertNotEqual(b0['messages'][0],b1['messages'][0])
            payload=json.loads(b0['messages'][1]['content'])
            self.assertEqual(set(payload),{'id','cutoff','facts','question','goal','constraints','prior_claims','allowed_checks','output_contract'})
            self.assertEqual(payload['facts'][0]['id'],'F1')
            self.assertNotIn('historical_action',b0['messages'][1]['content'])
            self.assertNotIn('expected_decision',b0['messages'][1]['content'])

    def test_paid_permit_keeps_denominators_no_training_and_cumulative_cap(self):
        now=time.time();source='a'*40
        p={'source_sha':source,'contract_sha256':minimum.life.digest(scope.CONTRACT),
            'namespace':scope.NAMESPACE,'instruction':scope.INSTRUCTION,'mode':'OWNER_APPROVED_E2B_DEVELOPMENT',
            'additional_cap_usd':'1.00','allocation_inclusive_seconds':3000,'single_use':True,
            'automatic_retry':False,'top_up_allowed':False,'weight_bytes':10246621918,
            'pretrained_requests':24,'training_steps':0,'qualification_run_id':'123',
            'approved_at':now-1,'expires_at':now+3600,'continuation_observed_spend_usd':'0.10',
            'maximum_projection_usd':'0.505'}
        self.assertIs(scope.validate_permit(p,source,now),p)
        for key,value in [('source_sha','b'*40),('pretrained_requests',25),('training_steps',1),
                ('automatic_retry',True),('single_use',1),('namespace','cuda-trace-paid-20261031'),
                ('continuation_observed_spend_usd','0.60')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                scope.validate_permit(dict(p,**{key:value}),source,now)

    def test_scope_restores_original_owner_and_cleanup_entry(self):
        original=(minimum.State,minimum.prepare_runtime,minimum.CONTRACT,minimum.choose)
        with scope.configured():
            self.assertIs(minimum.prepare_runtime,entry.prepare_runtime)
            self.assertEqual(minimum.REMOTE_MODULE,'tools.small_model_pretrained_scope')
            self.assertEqual(minimum.State('fixture','a'*40,True).namespace,scope.NAMESPACE)
        self.assertEqual((minimum.State,minimum.prepare_runtime,minimum.CONTRACT,minimum.choose),original)


if __name__=='__main__':unittest.main()
