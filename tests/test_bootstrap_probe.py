import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import bootstrap_probe as probe, cloud_state as state, cloud_owner, runpod_control as control
from tests.test_cloud_state import MemoryStore, SOURCE
from tests.test_cloud_owner import Provider, Process
from tests.test_runpod_control import T0, offer


class ProbeTests(unittest.TestCase):
    def test_scope_is_fixed_separate_and_restores_legacy_identity(self):
        previous=(state.AUTHORIZATION,state.DIRECTORY,state.OWNER_BRANCH,state.TOTAL,control.RUN)
        with probe.scope():
            self.assertEqual(state.AUTHORIZATION,probe.AUTHORIZATION)
            self.assertEqual(state.TOTAL,1800)
            self.assertNotEqual(state.DIRECTORY,previous[1])
            self.assertEqual(state.OWNER_BRANCH,probe.START)
        self.assertEqual((state.AUTHORIZATION,state.DIRECTORY,state.OWNER_BRANCH,state.TOTAL,control.RUN),previous)

    def test_diagnostic_context_never_accepts_old_paid_branches_or_reruns(self):
        env={'GITHUB_REPOSITORY':state.REPOSITORY,'GITHUB_REF_NAME':probe.START,'GITHUB_RUN_ATTEMPT':'1'}
        probe.validate_context('paid',env)
        for changes in ({'GITHUB_REF_NAME':'bt-001-a100-start-connected-gpu'},
                        {'GITHUB_REF_NAME':probe.REVIEW},{'GITHUB_RUN_ATTEMPT':'2'}):
            with self.assertRaises(state.StateError):probe.validate_context('paid',dict(env,**changes))
        probe.validate_context('access',dict(env,GITHUB_REF_NAME=probe.REVIEW,GITHUB_RUN_ATTEMPT='2'))

    def test_probe_claim_has_thirty_minute_bound_and_cannot_be_recreated(self):
        with probe.scope():
            store=MemoryStore();api=Provider()
            store.write('watcher',{'run_id':'2','source_sha':SOURCE,'at':T0})
            with tempfile.TemporaryDirectory() as td:
                clock=[T0]
                def sleep(n):clock[0]+=n
                result=cloud_owner.execute(store,api,offer(),None,{},td,'1',SOURCE,
                    wall=lambda:clock[0],sleep=sleep,spawn=lambda *a:Process(0),
                    stop=lambda p:None,emit=lambda r:None,
                    before_cleanup=lambda pod_id:{'owned_before_delete':pod_id in api.pods})
                self.assertTrue(result['pre_cleanup_diagnostic']['owned_before_delete'])
                self.assertEqual(result['cleanup']['phase'],'deleted')
                claim=store.read('claim')[0]
                self.assertEqual(claim['authorization'],probe.AUTHORIZATION)
                self.assertEqual(claim['total_seconds'],1800)
                self.assertEqual(claim['setup_seconds'],1500)
                self.assertLess(control.money(claim['costs']['maximum_all_in']),control.money('1.00'))
                again=cloud_owner.execute(store,api,offer(),None,{},td,'1',SOURCE,
                    wall=lambda:clock[0],sleep=sleep,emit=lambda r:None)
                self.assertEqual(again['allocation_requests'],0)

    def test_pre_cleanup_diagnostic_error_does_not_mask_delete(self):
        with tempfile.TemporaryDirectory() as td:
            store=MemoryStore();api=Provider();clock=[T0]
            store.write('watcher',{'run_id':'2','source_sha':SOURCE,'at':T0})
            def bad(pod_id):raise RuntimeError('CANARY')
            result=cloud_owner.execute(store,api,offer(),None,{},td,'1',SOURCE,
                wall=lambda:clock[0],sleep=lambda n:clock.__setitem__(0,clock[0]+n),
                spawn=lambda *a:Process(0),stop=lambda p:None,emit=lambda r:None,before_cleanup=bad)
            self.assertEqual(result['cleanup']['phase'],'deleted')
            self.assertNotIn('CANARY',json.dumps(result))

    def test_observation_validation_is_scoped_and_rejects_extra_fields(self):
        value={'attempt':'a'*32,'at':T0,'provider_status':'STARTING',
            'readiness':'WAIT_PROVIDER_RUNNING','direct_endpoint_present':False,
            'direct_endpoint_valid':False,'log_status':'SAMPLED','log_events':0}
        with self.assertRaises(ValueError):state.validate_document('observation',value)
        with probe.scope():
            state.validate_document('observation',value)
            with self.assertRaises(ValueError):state.validate_document('observation',dict(value,secret='CANARY'))

    def test_remote_probe_has_no_model_or_input_transfer_and_requires_gpu_only_when_paid(self):
        cpu=probe.remote_program(False);gpu=probe.remote_program(True)
        self.assertNotIn('nvidia-smi',cpu)
        self.assertIn('nvidia-smi',gpu)
        for source in (cpu,gpu):
            self.assertNotIn('pip install',source)
            self.assertNotIn('from_pretrained',source)
            self.assertIn("'model_execution':'NOT RUN'",source)

    def test_qualification_binds_controller_and_distinct_workflows(self):
        files=probe.hashes()
        self.assertIn('tools/bootstrap_probe.py',files)
        self.assertIn('.github/workflows/bootstrap-probe-start.yml',files)
        self.assertIn('.github/workflows/bootstrap-probe-watch.yml',files)
        self.assertIn('tools/cloud_owner.py',files)

    def test_tls_and_remote_command_failures_keep_specific_stages_without_public_stderr(self):
        with patch.object(probe.ssh,'deliver',side_effect=TimeoutError('CANARY')):
            with self.assertRaises(probe.ProbeFailure) as error:
                probe.connect(Path('/fixture'),{'host':'127.0.0.1','port':1234},gpu_required=True)
            self.assertEqual(error.exception.diagnostic['stage'],'mutual_tls_transfer')
            self.assertNotIn('CANARY',json.dumps(error.exception.diagnostic))
        with patch.object(probe.ssh,'deliver',return_value={}), \
             patch.object(probe.ssh,'known_hosts',return_value=Path('/fixture/hosts')), \
             patch.object(probe,'ssh_command',return_value=['ssh','remote']), \
             patch.object(probe.subprocess,'run',return_value=SimpleNamespace(
                 returncode=1,stdout=b'',stderr=b'CANARY remote traceback')):
            with self.assertRaises(probe.ProbeFailure) as error:
                probe.connect(Path('/fixture'),{'host':'127.0.0.1','port':1234},gpu_required=True)
            self.assertEqual(error.exception.diagnostic['stage'],'ssh_remote_probe')
            self.assertEqual(error.exception.diagnostic['returncode'],1)
            self.assertIn(b'CANARY',error.exception.private_output)
            self.assertNotIn('CANARY',json.dumps(error.exception.diagnostic))


if __name__=='__main__':unittest.main()
