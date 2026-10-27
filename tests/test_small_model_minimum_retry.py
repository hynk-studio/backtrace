import json
import os
import time
import unittest
from unittest import mock

from tools import small_model_minimum as m, small_model_minimum_retry as retry
from tools import small_model_minimum_remote as remote

SOURCE='a'*40


def permit():
    now=time.time()
    return {'source_sha':SOURCE,'contract_sha256':m.life.digest(m.CONTRACT),
        'authorization_id':retry.AUTHORIZATION_ID,'namespace':retry.PAID_NAMESPACE,
        'instruction':retry.INSTRUCTION,'single_use':True,'mode':'OWNER_APPROVED_HARDWARE_MINIMUM',
        'additional_cap_usd':'1.00','allocation_inclusive_seconds':3000,
        'automatic_retry':False,'top_up_allowed':False,'weight_download_bytes':0,
        'pretrained_requests':0,'training_steps':0,'qualification_run_id':'123',
        'approved_at':now-1,'expires_at':now+3600}


class RetryTests(unittest.TestCase):
    def test_only_new_owner_instruction_identity_and_unchanged_limits_are_accepted(self):
        p=permit();self.assertIs(retry.validate_permit(p,SOURCE,time.time()),p)
        for key,value in [('instruction','최소검증 진행하자'),('authorization_id','hardware-minimum-20261027-one'),
                ('namespace','minimum-paid-20261027'),('source_sha','b'*40),('single_use',False),
                ('additional_cap_usd','2.00'),('allocation_inclusive_seconds',3001),('automatic_retry',True),
                ('top_up_allowed',True),('weight_download_bytes',1),('training_steps',1),
                ('expires_at',time.time()-1),('approved_at',float('nan'))]:
            with self.subTest(key=key),self.assertRaises(ValueError):retry.validate_permit(dict(p,**{key:value}),SOURCE,time.time())

    def test_state_reads_and_initialization_never_target_old_paid_branch_or_namespace(self):
        original=(m.REVIEW,m.START,m.STATE_BRANCH,m.State)
        with retry.configured():
            state=m.State('fixture',SOURCE,True)
            with mock.patch.object(state,'request',return_value=None) as request:
                state.initialize();state.read('authorization')
            calls=request.call_args_list
            self.assertEqual(calls[0].args[1],'/git/ref/heads/'+retry.STATE_BRANCH)
            self.assertEqual(calls[1].args[2],{'ref':'refs/heads/'+retry.STATE_BRANCH,'sha':SOURCE})
            self.assertEqual(calls[2].args[1],'/contents/minimum/'+retry.PAID_NAMESPACE+'/authorization.json?ref='+retry.STATE_BRANCH)
            with self.assertRaises(ValueError):state.write('authorization',{})
            with self.assertRaises(ValueError):state.write('claim',{},'b'*40)
        self.assertEqual((m.REVIEW,m.START,m.STATE_BRANCH,m.State),original)

    def test_prior_workflow_and_rerun_cannot_satisfy_new_source_gates(self):
        state=mock.Mock(source=SOURCE,actual=True)
        live={'head_sha':SOURCE,'head_branch':retry.START,'run_attempt':1,'status':'in_progress',
            'event':'push','path':retry.LIVE_WORKFLOW}
        state.run.return_value=live;retry.require_run(state,'123')
        for key,value in [('head_branch',m.START),('path','.github/workflows/small-model-minimum-live.yml'),('run_attempt',2)]:
            state.run.return_value=dict(live,**{key:value})
            with self.assertRaises(ValueError):retry.require_run(state,'123')
        free=dict(live,head_branch=retry.REVIEW,path=retry.CPU_WORKFLOW,status='completed',conclusion='success')
        state.run.return_value=free;retry.require_qualification(state,permit())
        for key,value in [('head_branch',m.REVIEW),('path','.github/workflows/small-model-minimum-cpu.yml'),('conclusion','failure'),('head_sha','b'*40)]:
            state.run.return_value=dict(free,**{key:value})
            with self.assertRaises(ValueError):retry.require_qualification(state,permit())

    def test_old_authorization_blocks_before_provider_client_or_preparation(self):
        p=permit();p['authorization_id']='hardware-minimum-20261027-one'
        env={'GITHUB_REF_NAME':retry.START,'GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':SOURCE,
            'GITHUB_RUN_ID':'123','GITHUB_TOKEN':'fixture'}
        previous=os.umask(0o077)
        try:
            with mock.patch.dict(os.environ,env),mock.patch.object(retry.State,'initialize'),\
                    mock.patch.object(retry.State,'read',return_value=(p,'b'*40)),\
                    mock.patch.object(retry,'require_run'),mock.patch.object(m.control,'RunpodAPI') as api,\
                    mock.patch.object(remote,'prepare') as prepare:
                with self.assertRaises(ValueError):retry.main('owner',True)
                api.assert_not_called();prepare.assert_not_called()
        finally:os.umask(previous)

    def test_consumed_retry_claim_cannot_send_another_provider_create(self):
        import tempfile
        from pathlib import Path
        state=mock.Mock(source=SOURCE,actual=True);state.read.return_value=({'existing':True},'b'*40)
        api=mock.Mock()
        with tempfile.TemporaryDirectory() as td,retry.configured(),mock.patch.object(m,'ROOT',Path(td)),\
                mock.patch.object(m,'sources',return_value={}):
            result=m.owner(state,api,'123',{'boot_sha256':'a'*64})
        self.assertEqual(result['status'],'FAIL');self.assertIn('already consumed',result['error'])
        api.create.assert_not_called()


if __name__=='__main__':unittest.main()
