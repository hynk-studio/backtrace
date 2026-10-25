import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from tools import research_entry as entry, research_entry_contract as c
from tools.research_entry_state import StateError
from tests.research_entry_replica import Replica, clients, authorization, offer, limits

SOURCE='a'*40


def fake_worker(directory,configuration,claim,endpoint):
    # Controller-only fixture; never represented as a real serving/slot result.
    code="""import hashlib,json,sys,time
from pathlib import Path
p=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=True)
data=b'CPU controller fixture; not model or encrypted qualification'
(out/'results.age').write_bytes(data)
v={'status':'PASS','kind':'CONTROLLER_FIXTURE_ONLY','export':{'ciphertext_sha256':hashlib.sha256(data).hexdigest(),'completed_at':time.time()}}
(p/'worker-result.json').write_text(json.dumps(v))
"""
    return subprocess.Popen([sys.executable,'-I','-c',code,str(directory),configuration['output']],start_new_session=True)


class ContractTests(unittest.TestCase):
    def test_absent_or_cpu_permit_never_enters_paid(self):
        for value in (None,{},authorization(SOURCE)):
            with self.subTest(value=bool(value)),self.assertRaises(ValueError):c.permit(value,SOURCE,time.time())

    def test_expiry_source_and_caps(self):
        value=authorization(SOURCE);c.permit(value,SOURCE,time.time(),replica=True)
        for key,bad in [('source_sha','b'*40),('single_use',False),('expires_at',0),('additional_cap','NaN'),('cumulative_cap','13')]:
            v=dict(value);v[key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):c.permit(v,SOURCE,time.time(),replica=True)

    def test_allocation_inclusive_cost_and_reserve(self):
        a=authorization(SOURCE);o=offer();value=c.costs(o,a,time.time())
        self.assertEqual(value['maximum_all_in'],'2.442')
        for key,bad in [('credit_balance','2.9'),('other_total','.1'),('compute_per_hour','2.1'),('auto_pay',True)]:
            with self.subTest(key=key),self.assertRaises(ValueError):c.costs(dict(o,**{key:bad}),a,time.time())
        with self.assertRaises(ValueError):c.costs(o,dict(a,cumulative_cap='5'),time.time())

    def test_endpoint_mapping_must_match_ssh(self):
        pod={'ssh':{'direct':{'host':'127.0.0.1','port':22001,'username':'root'}},'runtime':{'ports':[
            {'private':22,'public':22001,'ip':'127.0.0.1','type':'tcp'},
            {'private':8443,'public':22002,'ip':'127.0.0.1','type':'tcp'}]}}
        self.assertEqual(c.endpoints(pod)['tls']['port'],22002)
        for mutated in ([],[pod['runtime']['ports'][0]]*2):
            with self.assertRaises(ValueError):c.endpoints(dict(pod,runtime={'ports':mutated}))
        wrong=copy.deepcopy(pod);wrong['runtime']['ports'][1]['ip']='127.0.0.2'
        with self.assertRaises(ValueError):c.endpoints(wrong)


class WireLifecycleTests(unittest.TestCase):
    def run_case(self,faults=()):
        with tempfile.TemporaryDirectory() as temporary,Replica(SOURCE,faults=faults) as replica:
            root=Path(temporary);namespace='free-test-'+str(time.time_ns())
            store,api=clients(replica.port,namespace);lim=limits()
            config={'port':replica.port,'namespace':namespace,'source':SOURCE,'limits':lim,'output':str(root/'watch.json')}
            (root/'watch-config.json').write_text(json.dumps(config))
            watcher=subprocess.Popen([sys.executable,'-I','-B',str(c.ROOT/'tests/research_entry_replica.py'),str(root/'watch-config.json')],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            try:
                end=time.monotonic()+5
                while not store.read('watcher'):
                    if time.monotonic()>end:raise AssertionError('watcher start failed')
                    time.sleep(.02)
                result=entry.execute(store,api,authorization(SOURCE),offer(),None,
                    {'output':str(root/'out'),'authored_cpu':True},root,SOURCE,'11',replica=True,
                    limits=lim,spawn_worker=fake_worker)
                watcher.wait(timeout=15)
                watch=json.loads((root/'watch.json').read_bytes())
                self.assertLessEqual(replica.create_count,1)
                self.assertFalse(replica.pods)
                self.assertIn(watch['status'],('DELETED','NO_RESOURCE_OBSERVED'))
                if result['cleanup']:
                    self.assertIn(result['cleanup']['status'],('DELETED','NO_RESOURCE_OBSERVED'))
                    self.assertEqual(result['cleanup']['absence_reads'],2)
                self.assertEqual(watch['absence_reads'],2)
                return result,watch,replica.create_count,replica.delete_count
            finally:
                if watcher.poll() is None:watcher.kill();watcher.wait(timeout=5)

    def test_normal_export_precedes_both_cleanup_loops(self):
        result,watch,creates,_=self.run_case()
        self.assertEqual(result['status'],'PASS');self.assertEqual(creates,1)
        exported=result['worker']['export']['completed_at']
        self.assertLessEqual(exported,result['cleanup']['started_at'])
        self.assertLessEqual(exported,watch['started_at'])

    def test_ambiguous_create_never_retries_and_finds_exact_name(self):
        for fault in ('create_ack_lost','create_500'):
            with self.subTest(fault=fault):
                result,watch,creates,_=self.run_case((fault,))
                self.assertEqual(creates,1);self.assertEqual(result['status'],'INCOMPLETE')
                self.assertIn(watch['status'],('DELETED','NO_RESOURCE_OBSERVED'))

    def test_false_and_lost_delete_acknowledgements(self):
        for fault in ('delete_false_ack','delete_ack_lost'):
            with self.subTest(fault=fault):self.run_case((fault,))

    def test_state_loss_after_create_retains_cleanup_identity(self):
        result,watch,creates,_=self.run_case(('state_unavailable',))
        self.assertEqual(creates,1);self.assertEqual(result['status'],'INCOMPLETE')
        self.assertIn(watch['status'],('DELETED','NO_RESOURCE_OBSERVED'))

    def test_delayed_ambiguous_create_stays_under_cleanup_observation(self):
        result,watch,creates,_=self.run_case(('create_ack_lost','delayed_create_visibility'))
        self.assertEqual(creates,1)
        self.assertGreaterEqual(result['cleanup']['completed_at']-result['claim']['requested_at'],.3)

    def test_claim_lost_ack_consumes_scope_without_create(self):
        result,watch,creates,_=self.run_case(('claim_ack_lost',))
        self.assertEqual(creates,0);self.assertEqual(result['status'],'INCOMPLETE')

    def test_mutable_ack_and_concurrent_branch_conflict(self):
        for fault in ('heartbeat_ack_lost','state_conflict'):
            with self.subTest(fault=fault):
                result,_,creates,_=self.run_case((fault,))
                self.assertEqual(result['status'],'PASS');self.assertEqual(creates,1)

    def test_state_claim_is_create_only(self):
        with Replica(SOURCE) as replica:
            store,_=clients(replica.port,'free-immutable')
            store.write('claim',{'id':'one'})
            with self.assertRaises(StateError):store.write('claim',{'id':'two'})
            self.assertEqual(store.read('claim')[0],{'id':'one'})
            with self.assertRaises(ValueError):store.write('authorization',{'mode':'paid'})


if __name__=='__main__':unittest.main()
