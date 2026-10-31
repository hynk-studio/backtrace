import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from tools import small_model_minimum as minimum
from tools import small_model_minimum_diagnostic as diagnostic

SOURCE='a'*40


def permit():
    now=time.time()
    return {'source_sha':SOURCE,'contract_sha256':minimum.life.digest(diagnostic.CONTRACT),
        'authorization_id':diagnostic.AUTHORIZATION_ID,'namespace':diagnostic.PAID_NAMESPACE,
        'instruction':diagnostic.INSTRUCTION,'mode':'OWNER_APPROVED_CUDA_COMPARISON',
        'single_use':True,'automatic_retry':False,'top_up_allowed':False,
        'additional_cap_usd':'1.00','allocation_inclusive_seconds':3000,
        'weight_download_bytes':0,'pretrained_requests':0,'training_steps':0,
        'qualification_run_id':'123','approved_at':now-1,'expires_at':now+3600}


class DiagnosticScopeTests(unittest.TestCase):
    def test_prior_permits_and_widened_paid_scopes_are_rejected(self):
        p=permit();self.assertIs(diagnostic.validate_permit(p,SOURCE,time.time()),p)
        for k,v in [('mode','OWNER_APPROVED_HARDWARE_MINIMUM'),('source_sha','b'*40),
                ('namespace','minimum-retry-paid-20261027'),('automatic_retry',True),
                ('single_use',1),('training_steps',False),('pretrained_requests',1),
                ('weight_download_bytes',1),('additional_cap_usd','2.00'),
                ('allocation_inclusive_seconds',3001),('top_up_allowed',True),
                ('approved_at',float('nan')),('expires_at',time.time()-1)]:
            with self.subTest(key=k),self.assertRaises(ValueError):
                diagnostic.validate_permit(dict(p,**{k:v}),SOURCE,time.time())

    def test_new_state_never_reads_or_writes_a_consumed_scope(self):
        original=(minimum.STATE_BRANCH,minimum.CONTRACT,minimum.REMOTE_MODULE,minimum.SUCCESS_STATUS)
        with diagnostic.configured():
            state=minimum.State('fixture',SOURCE,True)
            with mock.patch.object(state,'request',return_value=None) as request:
                state.initialize();state.read('authorization')
            self.assertEqual(request.call_args_list[0].args[1],'/git/ref/heads/'+diagnostic.STATE_BRANCH)
            self.assertIn('/minimum/'+diagnostic.PAID_NAMESPACE+'/',request.call_args_list[2].args[1])
            self.assertEqual(minimum.REMOTE_MODULE,'tools.small_model_minimum_diagnostic')
            self.assertEqual(minimum.SUCCESS_STATUS,'DIAGNOSTIC_RECORDED')
            with self.assertRaises(ValueError):state.write('authorization',{})
            with self.assertRaises(ValueError):state.write('claim',{},'b'*40)
        self.assertEqual((minimum.STATE_BRANCH,minimum.CONTRACT,minimum.REMOTE_MODULE,minimum.SUCCESS_STATUS),original)

    def test_only_the_matching_successful_free_source_qualifies(self):
        state=mock.Mock(source=SOURCE,actual=True)
        row={'head_sha':SOURCE,'head_branch':diagnostic.REVIEW,'run_attempt':1,
            'event':'push','status':'completed','conclusion':'success','path':diagnostic.WORKFLOW}
        state.run.return_value=row;diagnostic.require_qualification(state,permit())
        for k,v in [('head_sha','b'*40),('run_attempt',2),('head_branch',diagnostic.START),
                ('conclusion','failure'),('path','.github/workflows/small-model-minimum-retry-cpu.yml')]:
            state.run.return_value=dict(row,**{k:v})
            with self.subTest(key=k),self.assertRaises(ValueError):diagnostic.require_qualification(state,permit())
        live=dict(row,head_branch=diagnostic.START,status='in_progress')
        state.run.return_value=live;diagnostic.require_run(state,'123')
        state.run.return_value=dict(live,run_attempt=2)
        with self.assertRaises(ValueError):diagnostic.require_run(state,'123')

    def test_absent_current_authorization_stops_before_provider_or_preparation(self):
        p=permit();p['authorization_id']='hardware-minimum-retry-20261027-one'
        env={'GITHUB_REF_NAME':diagnostic.START,'GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':SOURCE,
             'GITHUB_RUN_ID':'123','GITHUB_TOKEN':'fixture'}
        previous=os.umask(0o077)
        try:
            with mock.patch.dict(os.environ,env),mock.patch.object(diagnostic.State,'initialize'),\
                    mock.patch.object(diagnostic.State,'read',return_value=(p,'b'*40)),\
                    mock.patch.object(diagnostic,'require_run'),\
                    mock.patch.object(minimum.control,'RunpodAPI') as api,\
                    mock.patch.object(diagnostic.remote,'prepare') as prepare:
                with self.assertRaises(ValueError):diagnostic.main('owner',True)
                api.assert_not_called();prepare.assert_not_called()
        finally:os.umask(previous)

    def test_consumed_claim_cannot_create_another_gpu(self):
        state=mock.Mock(source=SOURCE,actual=True);state.read.return_value=({'existing':True},'b'*40)
        api=mock.Mock()
        with tempfile.TemporaryDirectory() as td,diagnostic.configured(),\
                mock.patch.object(minimum,'ROOT',Path(td)),mock.patch.object(minimum,'sources',return_value={}):
            result=minimum.owner(state,api,'123',{'boot_sha256':'a'*64})
        self.assertEqual(result['status'],'FAIL');api.create.assert_not_called()

    def test_recorded_gpu_failure_is_not_relabelled_as_hardware_success(self):
        for decision in ('ALL_PRIMARY_PROBES_FAILED_CAUSE_UNRESOLVED_STOP','INCONCLUSIVE_STOP_SAME_ROUTE',
                'ADDED_FILTER_IMPLICATED_SYSCALL_UNRESOLVED','CUDA_PATH_WORKS_FAILURE_NOT_REPRODUCED'):
            with self.subTest(decision=decision),tempfile.TemporaryDirectory() as td:
                root=Path(td);ep=root/'endpoint.json';ep.write_text('{}')
                result={'status':'DIAGNOSTIC_RECORDED','diagnostics':{'cuda_comparison':{'decision':decision}}}
                def connected_result(*args,**kwargs):
                    # Real connected() creates this exclusively before returning.
                    minimum.life.write(root/'connected-receipt.json',result)
                    return result
                with mock.patch.object(diagnostic.remote,'connected',side_effect=connected_result) as connected:
                    recorded=diagnostic.measure(root,ep,root)
                self.assertEqual(connected.call_args.kwargs,{'actual':True,'comparison_only':True})
                self.assertEqual(recorded['status'],'DIAGNOSTIC_RECORDED')
                self.assertEqual(recorded['measurement_decision'],decision)
                self.assertIs(recorded['hardware_qualified'],False)
                self.assertIs(recorded['model_baseline_run'],False)
                self.assertEqual((root/'connected-receipt.json').read_bytes(),minimum.life.encoded(result))
                summary=json.loads((root/'diagnostic-summary.json').read_text())
                self.assertEqual(summary['connected_receipt_sha256'],minimum.life.digest(result))
                self.assertEqual(summary['measurement_decision'],decision)
                self.assertFalse(summary['hardware_qualified'])
                with self.assertRaises(FileExistsError):minimum.life.write(root/'diagnostic-summary.json',summary)


if __name__=='__main__':unittest.main()
