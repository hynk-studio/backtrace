import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import small_model_provider as p, small_model_remote_watch as w
from tools import small_model_provider_probe as probe


class ProviderTests(unittest.TestCase):
    def test_read_only_adapter_rejects_mutations_before_network(self):
        api=p.ReadOnlyAPI('fixture',opener=lambda *a,**kw:self.fail('network reached'))
        for method in ('POST','PUT','PATCH','DELETE'):
            with self.subTest(method=method),self.assertRaises(ValueError):api.request(method,'/pods')

    def test_invalid_costs(self):
        for value in ('NaN','Infinity','-1',True,None,''):
            with self.subTest(value=value),self.assertRaises(ValueError):p.money(value)

    def test_quote_budget_and_null_filtered_summaries(self):
        gpu={'id':'NVIDIA A40','memoryInGb':48}
        price={'uninterruptablePrice':'.44','minMemory':48,'minVcpu':8,'stockStatus':'High',
               'supportPublicIp':None,'availableGpuCounts':None}
        def read(source,variables):
            self.assertEqual(variables['price']['minMemoryInGb'],32)
            self.assertTrue(variables['price']['supportPublicIp'])
            return {'gpuTypes':[dict(gpu,secureCloud=True,lowestPrice=price)]}
        result=p.quote(gpu,'EU-RO-1',read)
        self.assertTrue(result['stock_eligible']);self.assertTrue(result['compute_within_proposal'])
        price['uninterruptablePrice']='1.79'
        self.assertFalse(p.quote(gpu,'EU-RO-1',read)['compute_within_proposal'])
        for field,value in (('supportPublicIp',False),('availableGpuCounts',[2]),('stockStatus','None')):
            saved=price[field];price[field]=value
            self.assertFalse(p.quote(gpu,'EU-RO-1',read)['stock_eligible']);price[field]=saved

    def test_nullable_unavailable_price_is_not_zero_or_affordable_stock(self):
        gpu={'id':'NVIDIA A40','memoryInGb':48}
        price={'uninterruptablePrice':None,'minMemory':None,'minVcpu':None,'stockStatus':'None'}
        result=p.quote(gpu,'EU-RO-1',lambda *a:{'gpuTypes':[dict(gpu,secureCloud=True,lowestPrice=price)]})
        self.assertFalse(result['stock_eligible'])
        self.assertEqual(result['pricing_status'],'UNAVAILABLE_NULL_COMPUTE_PRICE')
        self.assertNotIn('compute_within_proposal',result)

    def test_partial_account_survives_later_read_failure(self):
        result={}
        def read(source):
            if 'myself' in source:return {'myself':{'clientBalance':3,'currentSpendPerHr':0,'isAutoPayEnabled':False}}
            raise RuntimeError('catalog unavailable')
        with self.assertRaises(RuntimeError):p.inspect(read=read,report=result)
        self.assertEqual(result['account']['credit_balance_usd'],'3')
        self.assertEqual(result['status'],'INCOMPLETE')
        self.assertEqual(result['stage'],'CATALOG_READ')

    def test_mismatched_quote_rejected(self):
        with self.assertRaises(ValueError):
            p.quote({'id':'NVIDIA A40','memoryInGb':48},'EU-RO-1',lambda *a:{'gpuTypes':[]})

    def test_inventory_does_not_export_other_pod_details(self):
        class API:
            def list(self):return [{'id':'private-id','name':'private-name','env':{'secret':'value'}}]
        result=p.inventory(API());self.assertEqual(result['pod_count'],1)
        self.assertNotIn('private',json.dumps(result));self.assertNotIn('secret',json.dumps(result))


class RemoteTests(unittest.TestCase):
    def test_stale_missing_future_foreign_beats(self):
        beat=({'source_sha':'a'*40,'run_id':'1','at':100},'sha')
        self.assertTrue(w.fresh(beat,'a'*40,'1',129.9))
        for now in (99,130,200):self.assertFalse(w.fresh(beat,'a'*40,'1',now))
        self.assertFalse(w.fresh(None,'a'*40,'1',100))
        self.assertFalse(w.fresh(beat,'b'*40,'1',100))
        self.assertFalse(w.fresh(beat,'a'*40,'2',100))

    def test_remote_workflow_identity(self):
        row={'run_id':'11','source_sha':'a'*40,'role':'watch','boot_sha256':'b'*64}
        run={'id':11,'head_sha':'a'*40,'run_attempt':1,'head_branch':w.BRANCH,'event':'push',
             'path':'.github/workflows/small-model-provider-watch.yml','status':'in_progress'}
        w.validate_run(run,row,'watch','a'*40)
        for key,value in (('run_attempt',2),('head_sha','c'*40),('head_branch','main'),
                          ('path','another.yml'),('status','completed'),('event','pull_request')):
            changed=dict(run,**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError):w.validate_run(changed,row,'watch','a'*40)

    def test_no_claim_or_permit_path_and_no_immutable_overwrite(self):
        state=w.State('fixture','a'*40)
        for name in ('claim','authorization','pod','../owner'):
            with self.subTest(name=name),self.assertRaises(ValueError):state.path(name)
        with self.assertRaises(ValueError):state.write('owner',{'source_sha':'a'*40},'b'*40)

    def test_real_blob_binding_and_corruption(self):
        state=w.State('fixture','a'*40);raw=w.encoded({'source_sha':'a'*40,'at':1})
        row={'type':'file','encoding':'base64','content':base64.b64encode(raw).decode(),
             'sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
        with patch.object(state,'request',return_value=row):self.assertEqual(state.read('owner')[0]['at'],1)
        row['content']=base64.b64encode(raw+b' ').decode()
        with patch.object(state,'request',return_value=row),self.assertRaises(w.StateError):state.read('owner')

    def test_payload_is_exact_previous_sources_and_plan(self):
        with tempfile.TemporaryDirectory() as td:
            raw=probe.payload(Path(td)/'payload');rows=json.loads(raw)['files']
            names={r['path'] for r in rows}
            self.assertEqual(names,set(probe.pre.sources())|{'docs/small-model-gpu-baseline-v1.json'})
            self.assertNotIn('tools/small_model_provider.py',names)
            for row in rows:self.assertEqual(hashlib.sha256((Path(td)/'payload'/row['path']).read_bytes()).hexdigest(),row['sha256'])


if __name__=='__main__':unittest.main()
