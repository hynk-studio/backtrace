import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from unittest import mock

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


def slow_worker(directory,configuration,claim,endpoint):
    code="""import json,sys,time,os
from pathlib import Path
p=Path(sys.argv[1]);binding=sys.argv[2]
end=time.monotonic()+30
while time.monotonic()<end:
 q=p/'worker-status.partial';q.write_text(json.dumps({'claim_sha256':binding,'phase':'setup','at':time.time()}))
 os.replace(q,p/'worker-status.json');time.sleep(.05)
"""
    process=subprocess.Popen([sys.executable,'-I','-c',code,str(directory),entry.binding(claim)],start_new_session=True)
    (Path(directory)/'fixture-child.pid').write_text(str(process.pid))
    return process


class ContractTests(unittest.TestCase):
    def test_heartbeat_published_during_read_uses_post_read_clock(self):
        clock=[100.0];state=mock.Mock();state.namespace='free-read-race'
        def read(_):
            clock[0]=100.25
            return ({'source_sha':SOURCE,'namespace':state.namespace,'at':100.125,'run_id':'22'},'blob')
        state.read.side_effect=read
        state.run.return_value={'id':22,'head_sha':SOURCE,'head_branch':c.WATCH,'run_attempt':1,
            'status':'in_progress','event':'push','path':'.github/workflows/research-entry-watch.yml'}
        self.assertEqual(entry.require_watcher(state,SOURCE,lambda:clock[0],entry.defaults()),'22')
        with self.assertRaises(StateError):entry.require_watcher(state,SOURCE,lambda:99.0,entry.defaults())

    def test_paid_entry_missing_permit_never_constructs_provider_client(self):
        from tools import research_entry_main
        environment={'GITHUB_REPOSITORY':c.REPOSITORY,'GITHUB_REF_NAME':c.OWNER,
            'GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':SOURCE,'GITHUB_RUN_ID':'11','GITHUB_TOKEN':'fixture'}
        previous=os.umask(0o077)
        try:
            with mock.patch.dict(os.environ,environment),mock.patch.object(research_entry_main,'State') as state,\
                    mock.patch.object(research_entry_main,'RunpodAPI') as provider:
                state.return_value.read.return_value=None
                with self.assertRaises(ValueError):research_entry_main.main('owner')
                provider.assert_not_called()
        finally:os.umask(previous)

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
        self.assertEqual(value['maximum_all_in'],'1.7501')
        for key,bad in [('credit_balance','2.2'),('other_total','.1'),('compute_per_hour','2.1'),('auto_pay',True)]:
            with self.subTest(key=key),self.assertRaises(ValueError):c.costs(dict(o,**{key:bad}),a,time.time())
        with self.assertRaises(ValueError):c.costs(o,dict(a,cumulative_cap='4.7'),time.time())

    def test_endpoint_mapping_must_match_ssh(self):
        pod={'ssh':{'direct':{'host':'127.0.0.1','port':22001,'username':'root'}},'runtime':{'ports':[
            {'private':22,'public':22001,'ip':'127.0.0.1','type':'tcp'},
            {'private':8443,'public':22002,'ip':'127.0.0.1','type':'tcp'}]}}
        self.assertEqual(c.endpoints(pod)['tls']['port'],22002)
        for mutated in ([],[pod['runtime']['ports'][0]]*2):
            with self.assertRaises(ValueError):c.endpoints(dict(pod,runtime={'ports':mutated}))
        wrong=copy.deepcopy(pod);wrong['runtime']['ports'][1]['ip']='127.0.0.2'
        with self.assertRaises(ValueError):c.endpoints(wrong)

    def test_top_up_cannot_reduce_historical_spend(self):
        a=authorization(SOURCE);o=dict(offer(),credit_balance='8.5')
        with self.assertRaises(ValueError):c.costs(o,a,time.time())
        funded=dict(a,account_funded_total='11.5')
        with self.assertRaises(ValueError):c.costs(o,funded,time.time())
        with self.assertRaises(ValueError):c.permit(funded,SOURCE,time.time(),replica=True)

    @unittest.skipUnless(os.geteuid()==0 and sys.platform=='linux','actual dropped UID traversal')
    def test_private_umask_does_not_block_agent_workspace_or_expose_credentials(self):
        from tools.runpod_job import check_owner_host
        try:check_owner_host()
        except ValueError:self.skipTest('requires the production native PID/UID host')
        with tempfile.TemporaryDirectory(dir='/var/tmp') as temporary:
            outer=Path(temporary);outer.chmod(0o711);previous=os.umask(0o077)
            try:
                prepared=c.traversable_directory(outer/'prepared')
                execution=c.traversable_directory(prepared/'execution')
                work=c.traversable_directory(execution/'work')
                (prepared/'private').mkdir(mode=0o700)
                secret=prepared/'private/client.key';secret.write_text('permission fixture')
            finally:os.umask(previous)
            subprocess.run(['setpriv','--reuid=65532','--regid=65532','--clear-groups',
                '/bin/sh','-c','test -x "$1" && ! test -r "$2"','probe',str(work),str(secret)],check=True,timeout=5)


class WireLifecycleTests(unittest.TestCase):
    def run_case(self,faults=(),*,worker=fake_worker,watcher_failure=False):
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
                killer=None
                if watcher_failure:
                    def kill_watch():
                        until=time.monotonic()+5
                        while not replica.create_count and time.monotonic()<until:time.sleep(.01)
                        watcher.kill();replica.watcher_status='completed'
                    killer=threading.Thread(target=kill_watch);killer.start()
                result=entry.execute(store,api,authorization(SOURCE),offer(),None,
                    {'output':str(root/'out'),'authored_cpu':True},root,SOURCE,'11',replica=True,
                    limits=lim,spawn_worker=worker)
                watcher.wait(timeout=15)
                if killer:killer.join(timeout=5)
                if watcher_failure:
                    self.assertFalse(replica.pods);self.assertEqual(result['cleanup']['status'],'DELETED')
                    return result,None,replica.create_count,replica.delete_count
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

    def test_controller_failure_keeps_completed_worker_receipt(self):
        def finished_then_invalid(directory,configuration,claim,endpoint):
            p=fake_worker(directory,configuration,claim,endpoint);p.wait(timeout=5)
            (Path(directory)/'worker-status.json').write_text(json.dumps({
                'claim_sha256':entry.binding(claim),'phase':'invalid','at':time.time()}))
            return subprocess.Popen([sys.executable,'-I','-c','import time;time.sleep(30)'],start_new_session=True)
        result,watch,creates,_=self.run_case(worker=finished_then_invalid)
        self.assertEqual(result['status'],'INCOMPLETE');self.assertEqual(creates,1)
        self.assertEqual(result['failure']['detail'],'worker phase invalid')
        self.assertEqual(result['worker']['kind'],'CONTROLLER_FIXTURE_ONLY')
        self.assertLessEqual(result['worker']['export']['completed_at'],result['cleanup']['started_at'])

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

    def test_provider_delay_does_not_block_independent_state_service(self):
        with Replica(SOURCE) as replica:
            state,_=clients(replica.port,'free-independent-services')
            with replica.lock:
                state.write('probe-owner',{'mode':'FREE_GITHUB_HANDSHAKE'})
                self.assertEqual(state.read('probe-owner')[0],{'mode':'FREE_GITHUB_HANDSHAKE'})

    def test_watcher_process_death_stops_owner(self):
        result,_,count,_=self.run_case(worker=slow_worker,watcher_failure=True)
        self.assertEqual(count,1);self.assertEqual(result['status'],'INCOMPLETE')

    def test_readiness_setup_deadline_stops_child(self):
        result,watch,count,_=self.run_case(worker=slow_worker)
        self.assertEqual(count,1);self.assertEqual(result['status'],'INCOMPLETE')
        self.assertLess(result['cleanup']['completed_at']-result['claim']['requested_at'],10)

    def test_owner_process_kill_still_deletes(self):
        with tempfile.TemporaryDirectory() as temporary,Replica(SOURCE) as replica:
            root=Path(temporary);namespace='free-parent-'+str(time.time_ns());lim=limits()
            config={'port':replica.port,'namespace':namespace,'source':SOURCE,'limits':lim,'output':str(root/'watch.json')}
            (root/'watch-config.json').write_text(json.dumps(config))
            watcher=subprocess.Popen([sys.executable,'-I','-B',str(c.ROOT/'tests/research_entry_replica.py'),str(root/'watch-config.json')],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            store,api=clients(replica.port,namespace);owner=None
            try:
                until=time.monotonic()+5
                while not store.read('watcher'):
                    if time.monotonic()>until:raise AssertionError('watcher unavailable')
                    time.sleep(.02)
                code="""import sys,time,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from tools import research_entry as e
from tests.research_entry_replica import clients,authorization,offer,limits
from tests.test_research_entry import slow_worker
root=Path(sys.argv[2]);store,api=clients(int(sys.argv[3]),sys.argv[4]);source=sys.argv[5]
e.execute(store,api,authorization(source),offer(),None,{'output':str(root/'out'),'authored_cpu':True},root,source,'11',replica=True,limits=limits(),spawn_worker=slow_worker)
"""
                owner=subprocess.Popen([sys.executable,'-I','-c',code,str(c.ROOT),str(root),str(replica.port),namespace,SOURCE],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                while not replica.create_count:
                    if time.monotonic()>until:raise AssertionError('owner create unavailable')
                    time.sleep(.01)
                # Kill before workload spawn; no fixture subprocess is orphaned.
                owner.kill();owner.wait(timeout=5)
                watcher.wait(timeout=15)
                result=json.loads((root/'watch.json').read_bytes())
                self.assertEqual(result['status'],'DELETED');self.assertFalse(replica.pods)
                self.assertEqual(replica.create_count,1);self.assertEqual(owner.returncode,-9)
            finally:
                for process in (owner,watcher):
                    if process and process.poll() is None:process.kill();process.wait(timeout=5)
                child=root/'fixture-child.pid'
                if child.exists():
                    import contextlib,signal
                    with contextlib.suppress(ProcessLookupError):os.killpg(int(child.read_text()),signal.SIGKILL)

    def test_failed_provider_read_is_not_absence(self):
        result,watch,count,_=self.run_case(('get_error',))
        self.assertEqual(count,1);self.assertEqual(result['status'],'INCOMPLETE')

    def test_wrong_resource_name_cannot_be_deleted(self):
        with Replica(SOURCE) as replica:
            store,api=clients(replica.port,'free-foreign')
            claim={'name':'backtrace-a100-'+'a'*32,'requested_at':time.time(),
                'total_seconds':.3,'cleanup_seconds':.2,'unknown_create_seconds':.1,'poll_seconds':.02}
            replica.pods['foreign']={'id':'foreign','name':'unrelated-resource'}
            result=entry.reconcile(api,claim,'foreign')
            self.assertEqual(result['status'],'UNRESOLVED');self.assertEqual(result['absence_reads'],0)
            self.assertEqual(replica.delete_count,0);self.assertIn('foreign',replica.pods)


if __name__=='__main__':unittest.main()
