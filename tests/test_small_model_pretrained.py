import json
from pathlib import Path
import tempfile
import subprocess
import sys
import time
import unittest
from unittest import mock

from tools import small_model_pretrained as entry, small_model_pretrained_scope as scope
from tools import small_model_minimum as minimum


class PretrainedTests(unittest.TestCase):
    def test_only_observed_socket_shape_is_created_and_cannot_communicate(self):
        code="""import ctypes,errno,json,socket,os
from tools.small_model_container_worker import restrict_syscalls
restrict_syscalls();s=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET|socket.SOCK_CLOEXEC,0);r={}
lib=ctypes.CDLL(None,use_errno=True)
def bare_socket():
 fd=lib.syscall(41,1,5,0)
 if fd<0:raise OSError(ctypes.get_errno(),'raw socket')
 os.close(fd)
for name,fn in [('connect',lambda:s.connect('/tmp/backtrace-not-a-server')),
 ('bind',lambda:s.bind('/tmp/backtrace-must-not-bind')),('listen',lambda:s.listen(1)),
 ('sendmsg',lambda:s.sendmsg([b'x'])),('sendto',lambda:s.sendto(b'x','/tmp/backtrace-not-a-server')),
 ('inet',lambda:socket.socket()),('unix_stream',lambda:socket.socket(socket.AF_UNIX)),
 ('unix_no_cloexec',bare_socket),
 ('socketpair',socket.socketpair)]:
 try:fn()
 except OSError as e:r[name]=e.errno==errno.EPERM
 else:r[name]=False
s.close();print(json.dumps(r))
"""
        p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(len(json.loads(p.stdout)),9);self.assertTrue(all(json.loads(p.stdout).values()))

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
