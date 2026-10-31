import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from tools import small_model_minimum as m, small_model_minimum_worker as w
from tools import small_model_minimum_remote as remote, small_model_lifecycle as life
from tools import research_entry as cleanup

SOURCE='a'*40


def snapshot():
    return {'status':'PASS_READ_ONLY','account_idle':True,'inventory':{'pod_count':0},
        'account':{'credit_balance_usd':'3.07'},'offers':[{'stock_eligible':True,'pricing_status':'OBSERVED',
        'reported_gpu_gb':48,'compute_usd_per_hour':'.44','observed_at':m.control.utc(time.time()),
        'gpu':'NVIDIA RTX A6000','region':'EU-RO-1'}]}


class MinimumTests(unittest.TestCase):
    def test_current_permit_rejects_old_scope_wrong_source_expiry_and_larger_cap(self):
        now=time.time();p={'source_sha':SOURCE,'contract_sha256':life.digest(m.CONTRACT),
            'mode':'OWNER_APPROVED_HARDWARE_MINIMUM','single_use':True,'additional_cap_usd':'1.00',
            'allocation_inclusive_seconds':3000,'instruction':'최소검증 진행하자','qualification_run_id':'123',
            'approved_at':now-1,'expires_at':now+3600}
        m.validate_permit(p,SOURCE,now)
        for key,value in [('source_sha','b'*40),('additional_cap_usd','2.00'),('mode','CPU_REPLICA'),
                ('expires_at',now-1),('allocation_inclusive_seconds',3001),('single_use',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):m.validate_permit(dict(p,**{key:value}),SOURCE,now)

    def test_offer_covers_allocation_clock_and_preserves_credit(self):
        s=snapshot();r=m.choose(s,time.time());self.assertLess(float(r['costs']['maximum_projection']),1)
        for update in ('credit','price','age','stock','marketed24','pods'):
            s=snapshot()
            if update=='credit':s['account']['credit_balance_usd']='.6'
            if update=='price':s['offers'][0]['compute_usd_per_hour']='1.1'
            if update=='age':s['offers'][0]['observed_at']=m.control.utc(time.time()-301)
            if update=='stock':s['offers'][0]['stock_eligible']=False
            if update=='marketed24':s['offers'][0]['reported_gpu_gb']=24
            if update=='pods':s['inventory']['pod_count']=1
            with self.subTest(update=update),self.assertRaises(ValueError):m.choose(s,time.time())

    def test_hardware_entry_has_no_pretrained_or_training_command(self):
        for mode in ('pretrained_cuda','random_cuda_fixture','train','worker'):
            with self.subTest(mode=mode),self.assertRaises(ValueError):remote.command(['ssh'],mode,60,True)
        for seconds in (0,181):
            with self.assertRaises(ValueError):remote.command(['ssh'],'kernels',seconds,True)
        self.assertIn('minimum-gpu.json',remote.command(['ssh'],'kernels',60,True)[-1])

    def test_source_and_resource_claim_binding_rejects_same_runner(self):
        state=mock.Mock(source=SOURCE,namespace='minimum-paid-20261027',actual=True)
        c={'source_sha':SOURCE,'contract_sha256':life.digest(m.CONTRACT),'namespace':state.namespace,
            'run_id':'123','actual':True,'owner_boot':'a'*64,'watch_boot':'b'*64,
            'name':'backtrace-small-minimum-'+'c'*32,'total_seconds':3000,'cleanup_seconds':300,
            'poll_seconds':90,'unknown_create_seconds':90,'requested_at':time.time()}
        m.check_claim(c,state,'123')
        for key,value in [('source_sha','d'*40),('watch_boot','a'*64),('name','old-resource'),('total_seconds',3001)]:
            with self.subTest(key=key),self.assertRaises(m.StateError):m.check_claim(dict(c,**{key:value}),state,'123')

    def test_freshness_uses_source_bound_claim_and_rejects_future_heartbeat(self):
        c={'x':1};row=({'claim_sha256':life.digest(c),'at':10},'sha')
        self.assertTrue(m.fresh(row,c,11,15));self.assertFalse(m.fresh(row,c,9,15))
        self.assertFalse(m.fresh(row,{'x':2},11,15));self.assertFalse(m.fresh(row,c,26,15))

    def test_real_touched_resident_pages_and_invalid_allocations(self):
        r=w.resident_probe(4*1024**2)
        self.assertEqual(r['resident_bytes'],4*1024**2);self.assertEqual(r['swap_bytes'],0)
        self.assertEqual(r['full_model_memory_admission'],'NOT_ESTABLISHED')
        for size in (0,1,-4096,9*1024**3,True):
            with self.assertRaises(ValueError):w.resident_probe(size)

    def test_wrong_resource_or_price_never_qualifies(self):
        c={'name':'backtrace-small-minimum-'+'c'*32,'gpu':'NVIDIA RTX A6000','region':'EU-RO-1',
            'costs':{'compute_per_hour':'.44'}}
        p={'name':c['name'],'image':m.control.BASE,'cloud':'SECURE','disk':100,'mounts':{},'ports':['22/tcp'],
            'locked':False,'status':'RUNNING','dataCenterId':'EU-RO-1','cost':'.45',
            'gpu':{'id':c['gpu'],'count':1,'memory':32,'vcpuCount':8}}
        self.assertTrue(m.resource_matches(p,c))
        for key,value in [('name','unrelated'),('cost','.9'),('mounts',{'other':'disk'}),('ports',['22/tcp','80/http'])]:
            self.assertFalse(m.resource_matches(dict(p,**{key:value}),c))

    def test_exact_id_name_cleanup_never_deletes_unrelated_resource(self):
        api=mock.Mock();api.list.return_value=[{'id':'other','name':'unrelated'}];api.get.return_value={'id':'owned','name':'wrong'}
        c={'name':'backtrace-small-minimum-'+'a'*32,'requested_at':time.time(),'total_seconds':1,
            'cleanup_seconds':.03,'unknown_create_seconds':.01,'poll_seconds':.005}
        r=cleanup.reconcile(api,c,'owned');self.assertEqual(r['status'],'UNRESOLVED');api.delete.assert_not_called()

    def test_new_state_does_not_reuse_prior_permits_or_allow_worker_authorization(self):
        state=m.State('fixture',SOURCE,True)
        self.assertIn('minimum-paid-20261027',state.path('authorization'))
        with self.assertRaises(ValueError):state.write('authorization',{})
        with self.assertRaises(ValueError):state.path('../../research-state')
        with self.assertRaises(ValueError):state.write('claim',{},'b'*40)

    def test_real_owner_deadline_interrupts_blocking_work_and_is_removed_before_cleanup(self):
        import signal
        old=signal.getsignal(signal.SIGALRM)
        close=m.work_alarm(.04)
        try:
            with self.assertRaisesRegex(TimeoutError,'allocation-inclusive'):
                time.sleep(1)
        finally:close()
        self.assertEqual(signal.getsignal(signal.SIGALRM),old)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))

    def test_no_actual_provider_client_or_preparation_without_current_permit(self):
        import os
        environment={'GITHUB_REF_NAME':m.START,'GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':SOURCE,
            'GITHUB_RUN_ID':'123','GITHUB_TOKEN':'fixture'}
        previous=os.umask(0o077)
        try:
            with mock.patch.dict(os.environ,environment),mock.patch.object(m,'State') as state,\
                    mock.patch.object(m,'require_run'),mock.patch.object(m.control,'RunpodAPI') as api,\
                    mock.patch.object(remote,'prepare') as prepare:
                state.return_value.read.return_value=None
                with self.assertRaises((ValueError,TypeError)):m.main('owner',True)
                api.assert_not_called();prepare.assert_not_called()
        finally:os.umask(previous)

    def test_owner_retains_observed_cleanup_when_a_later_state_read_would_be_stale(self):
        records={};observations=[]
        state=mock.Mock(source=SOURCE,namespace='minimum-free-'+SOURCE,actual=False)
        peer={'run_id':'123','role':'watch','boot_sha256':'b'*64}
        def write(name,value,previous=None):
            records[name]=dict(value,source_sha=SOURCE);return 'c'*40
        def read(name):
            if name=='watch':return peer,'d'*40
            if name in ('armed','watch-heartbeat'):
                return {'claim_sha256':life.digest(records['claim']),'watch_boot':'b'*64,'at':time.time()},'d'*40
            if name=='watch-cleanup':
                observations.append(name)
                if len(observations)>1:return None
                return {'reason':'OWNER_HEARTBEAT_LOST','status':'DELETED','pod_id':'free-resource'},'d'*40
            return (records[name],'d'*40) if name in records else None
        state.read.side_effect=read;state.write.side_effect=write
        api=mock.Mock();api.create.side_effect=lambda r:{'id':'free-resource','name':r['name']}
        with tempfile.TemporaryDirectory() as td,mock.patch.object(m,'ROOT',Path(td)),\
                mock.patch.object(m,'sources',return_value={}),mock.patch.object(m,'require_run'),\
                mock.patch.object(cleanup,'reconcile',return_value={'status':'DELETED','absence_reads':2}):
            result=m.owner(state,api,'123',{'boot_sha256':'a'*64})
        self.assertEqual(result['status'],'PASS_FREE_REMOTE_CLEANUP')
        self.assertEqual(len(observations),1)
        self.assertEqual(api.create.call_count,1)

    def run_paid_owner_fixture(self,metadata,*,running=False,create_error=None):
        """Execute the owner state machine with delayed provider snapshots, no I/O."""
        start=time.time();clock=[start];records={};spawn_times=[]
        state=mock.Mock(source=SOURCE,namespace='minimum-paid-20261027',actual=True)
        peer={'run_id':'123','role':'watch','boot_sha256':'b'*64}
        permit={'source_sha':SOURCE,'contract_sha256':life.digest(m.CONTRACT),
            'mode':'OWNER_APPROVED_HARDWARE_MINIMUM','single_use':True,'additional_cap_usd':'1.00',
            'allocation_inclusive_seconds':3000,'instruction':'최소검증 진행하자','qualification_run_id':'123',
            'approved_at':start-1,'expires_at':start+3600}
        def write(name,value,previous=None):
            records[name]=dict(value,source_sha=SOURCE);return 'c'*40
        def read(name):
            if name=='watch':return peer,'d'*40
            if name=='authorization':return permit,'d'*40
            if name in ('armed','watch-heartbeat'):
                return {'claim_sha256':life.digest(records['claim']),'watch_boot':'b'*64,'at':clock[0]},'d'*40
            return (records[name],'d'*40) if name in records else None
        state.read.side_effect=read;state.write.side_effect=write
        api=mock.Mock();api.list.return_value=[]
        api.create.side_effect=create_error or (lambda r:{'id':'owned','name':r['name']})
        samples=iter(metadata);last=[None]
        def get(pod_id):
            last[0]=next(samples,last[0]);c=records['claim']
            return dict({'id':pod_id,'name':c['name'],'image':m.control.BASE,'cloud':'SECURE',
                'disk':100,'mounts':{},'ports':['22/tcp'],'locked':False,'status':'RUNNING',
                'dataCenterId':c['region'],'cost':'.45',
                'gpu':{'id':c['gpu'],'count':1,'memory':32,'vcpuCount':8}},**last[0])
        api.get.side_effect=get
        def sleep(seconds):clock[0]+=seconds
        process=mock.Mock(returncode=0);process.poll.return_value=None if running else 0
        def reconcile_result(*args,**kwargs):
            if create_error:
                self.assertIsNone(args[2])
                self.assertTrue(kwargs['possible_create'])
                self.assertEqual(records['done']['provider_create_requests'],1)
                self.assertEqual(records['done']['failure'],
                    {'type':'ProviderError','http_status':400})
                self.assertNotIn('private-body-fixture',json.dumps(records['done']))
                self.assertEqual(records['done']['claim_sha256'],life.digest(records['claim']))
            return {'status':'DELETED','absence_reads':2}
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'keys').mkdir();(root/'keys/initializer.json').write_text('{}')
            def launch(argv,**kwargs):
                spawn_times.append(clock[0]-start);out=Path(argv[-1]);out.mkdir()
                (out/'connected-receipt.json').write_text(json.dumps({'status':'PASS_ACTUAL_HARDWARE_ONLY'}))
                return process
            with mock.patch.object(m,'ROOT',root),mock.patch.object(m,'sources',return_value={}),\
                    mock.patch.object(m,'require_run'),mock.patch.object(m,'require_qualification'),\
                    mock.patch.object(m.provider,'ReadOnlyAPI'),mock.patch.object(m.provider,'inspect',side_effect=lambda **kw:snapshot()),\
                    mock.patch.object(m.prior_contract,'github_budget',return_value={}),\
                    mock.patch.object(m,'request_for',side_effect=lambda offer,init,attempt:{'name':'backtrace-small-minimum-'+attempt}),\
                    mock.patch.object(m,'work_alarm',return_value=lambda:None),\
                    mock.patch.object(m.time,'time',side_effect=lambda:clock[0]),\
                    mock.patch.object(m.time,'monotonic',side_effect=lambda:clock[0]-start),\
                    mock.patch.object(m.time,'sleep',side_effect=sleep),\
                    mock.patch.object(m.subprocess,'Popen',side_effect=launch) as spawn,\
                    mock.patch.object(cleanup,'stop'),\
                    mock.patch.object(cleanup,'reconcile',side_effect=reconcile_result) as reconcile:
                result=m.owner(state,api,'123',{'boot_sha256':'a'*64},root)
            reconcile.assert_called_once()
        self.assertEqual(api.create.call_count,1)
        self.assertEqual(result['cleanup']['status'],'DELETED')
        return result,spawn,spawn_times

    def test_create_error_metadata_precedes_full_unknown_create_cleanup_without_retry(self):
        result,spawn,times=self.run_paid_owner_fixture([],create_error=
            m.control.ProviderError('private-body-fixture',http_status=400))
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['failure'],{'type':'ProviderError','http_status':400})
        spawn.assert_not_called();self.assertEqual(times,[])

    @staticmethod
    def ready_metadata():
        return {'ssh':{'direct':{'host':'192.0.2.1','port':12222,'username':'root'}},
            'runtime':{'ports':[{'private':22,'type':'tcp','ip':'192.0.2.1','public':12222}]}}

    def test_running_before_ssh_and_runtime_metadata_waits_without_early_launch(self):
        ready=self.ready_metadata()
        cases=[{'ssh':None,'runtime':None},{'ssh':{'direct':None},'runtime':None},
            dict(ready,runtime=None),dict(ready,runtime={'ports':[]}),ready]
        result,spawn,times=self.run_paid_owner_fixture(cases)
        self.assertEqual(result['status'],'PASS_ACTUAL_HARDWARE_ONLY')
        self.assertEqual(times,[120]);spawn.assert_called_once()
        self.assertEqual([r['readiness'] for r in result['readiness_observations']],
            ['WAIT_DIRECT_ENDPOINT','WAIT_DIRECT_ENDPOINT','WAIT_RUNTIME_MAPPING','WAIT_RUNTIME_MAPPING','READY'])
        self.assertNotIn('192.0.2.1',json.dumps(result['readiness_observations']))

    def test_pending_endpoint_hits_original_startup_deadline_and_cleanup_without_retry(self):
        result,spawn,times=self.run_paid_owner_fixture([{'ssh':None,'runtime':None}])
        self.assertEqual(result['status'],'FAIL');self.assertEqual(result['error_type'],'TimeoutError')
        self.assertEqual(result['readiness_observations'][-1]['elapsed_seconds'],900)
        spawn.assert_not_called();self.assertEqual(times,[])

    def test_contradictory_complete_endpoint_never_launches(self):
        bad=self.ready_metadata();bad['runtime']['ports'][0]['public']=12223
        result,spawn,_=self.run_paid_owner_fixture([bad])
        self.assertEqual(result['status'],'FAIL');self.assertEqual(result['error_type'],'ValueError')
        self.assertEqual(result['readiness_observations'][-1]['readiness'],'INVALID_ENDPOINT_MAPPING')
        spawn.assert_not_called()
        for field,value in [('username','nobody'),('port',True),('host','bad host')]:
            p=self.ready_metadata();p['ssh']['direct'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):m.endpoint(p)
        p=self.ready_metadata();p['runtime']['ports']*=2
        with self.assertRaises(ValueError):m.endpoint(p)

    def test_endpoint_loss_after_launch_fails_instead_of_reconnecting(self):
        result,spawn,_=self.run_paid_owner_fixture([self.ready_metadata(),{'ssh':None,'runtime':None}],running=True)
        self.assertEqual(result['status'],'FAIL');self.assertEqual(result['error'],'provider endpoint disappeared')
        spawn.assert_called_once()

    def test_watcher_retains_owner_done_when_resource_is_already_absent(self):
        c={'source_sha':SOURCE,'contract_sha256':life.digest(m.CONTRACT),'namespace':'minimum-paid-20261027',
            'run_id':'123','actual':True,'owner_boot':'a'*64,'watch_boot':'b'*64,
            'name':'backtrace-small-minimum-'+'c'*32,'total_seconds':3000,'cleanup_seconds':300,
            'poll_seconds':90,'unknown_create_seconds':90,'requested_at':time.time()}
        records={'claim':c,'pod':{'claim_sha256':life.digest(c),'pod_id':'owned'},
            'done':{'claim_sha256':life.digest(c),'provider_create_requests':1}}
        state=mock.Mock(source=SOURCE,namespace=c['namespace'],actual=True)
        state.read.side_effect=lambda name:(records[name],'d'*40) if name in records else None
        api=mock.Mock();api.get.return_value=None
        with mock.patch.object(cleanup,'reconcile',return_value={'status':'DELETED','absence_reads':2}) as reconcile:
            result=m.watch(state,api,'123',{'boot_sha256':'b'*64})
        self.assertEqual(result['reason'],'OWNER_DONE');api.get.assert_not_called()
        reconcile.assert_called_once_with(api,c,'owned',possible_create=True)


if __name__=='__main__':unittest.main()
