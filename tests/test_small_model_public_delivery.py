import base64
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock,patch

from tools import small_model_public_delivery as public,small_model_public_scope as scope
from tools import small_model_delivery as delivery,small_model_minimum as minimum


class Response(io.BytesIO):
    status=200
    def __init__(self,content,length=None):
        super().__init__(content);self.headers={'Content-Length':str(len(content) if length is None else length)}


class PublicDeliveryTests(unittest.TestCase):
    def fixture(self,root,body=b'public bytes'):
        stage=root/'stage';stage.mkdir();(stage/'owner.json').write_bytes(b'private owner bytes')
        rows=[{'path':'owner.json','bytes':19,'sha256':public.sha(b'private owner bytes')},
              {'path':'wheels/public.whl','bytes':len(body),'sha256':public.sha(body)}]
        raw=json.dumps({'schema_version':1,'phase':'bootstrap','files':rows},sort_keys=True,separators=(',',':')).encode()+b'\n'
        local_raw=json.dumps({'schema_version':1,'phase':'bootstrap','files':rows[:1]},sort_keys=True,separators=(',',':')).encode()+b'\n'
        (stage/public.MANIFEST_NAME).write_bytes(local_raw)
        return stage,root/'installed',raw,{'manifest_b64':base64.b64encode(raw).decode(),
            'public_urls':{'wheels/public.whl':'https://files.pythonhosted.org/public.whl'}}

    def test_complete_mixed_readback_matches_existing_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            stage,dest,raw,bundle=self.fixture(Path(td));opener=Mock();opener.open.return_value=Response(b'public bytes')
            result=public.hydrate(stage,dest,bundle,public.sha(raw),30,opener=opener)
            self.assertEqual(result['receipt'],delivery.verify(dest,raw,exact=True))
            self.assertEqual((dest/'owner.json').read_bytes(),b'private owner bytes')
            self.assertFalse(stage.exists());self.assertEqual(len(result['public_files']),1)
            request=opener.open.call_args.args[0]
            self.assertEqual(request.headers,{'Accept-encoding':'identity'})

    def test_bad_content_never_becomes_installed(self):
        for body,length in [(b'wrong bytes!',None),(b'short',12),(b'longer than pinned bytes',12),(b'public bytes',999)]:
            with self.subTest(body=body),tempfile.TemporaryDirectory() as td:
                stage,dest,raw,bundle=self.fixture(Path(td));opener=Mock();opener.open.return_value=Response(body,length)
                with self.assertRaises(ValueError):public.hydrate(stage,dest,bundle,public.sha(raw),30,opener=opener)
                self.assertFalse(dest.exists());self.assertFalse(stage.exists())

    def test_local_tampering_is_detected_by_independent_readback(self):
        with tempfile.TemporaryDirectory() as td:
            stage,dest,raw,bundle=self.fixture(Path(td));(stage/'owner.json').write_bytes(b'tampered')
            opener=Mock();opener.open.return_value=Response(b'public bytes')
            with self.assertRaisesRegex(ValueError,'readback'):public.hydrate(stage,dest,bundle,public.sha(raw),30,opener=opener)
            self.assertFalse(dest.exists())

    def test_no_unlisted_or_symlink_stage_content(self):
        for kind in ('extra','link','destination'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
                stage,dest,raw,bundle=self.fixture(Path(td));opener=Mock()
                if kind=='extra':(stage/'extra').write_bytes(b'extra')
                elif kind=='link':(stage/'outside').symlink_to('/etc/passwd')
                else:dest.mkdir()
                with self.assertRaises(ValueError):public.hydrate(stage,dest,bundle,public.sha(raw),30,opener=opener)
                opener.open.assert_not_called()

    def test_manifest_rejects_identity_traversal_duplicates_and_size(self):
        with tempfile.TemporaryDirectory() as td:
            stage,dest,raw,bundle=self.fixture(Path(td));original=json.loads(raw)
            with self.assertRaises(ValueError):public.manifest_rows(raw,'0'*64)
            for value in ('../escape','/absolute','wheels/./public.whl',''):
                changed=json.loads(raw);changed['files'][1]['path']=value;b=json.dumps(changed).encode()
                with self.subTest(value=value),self.assertRaises(ValueError):public.manifest_rows(b,public.sha(b))
            for change in ('duplicate','oversize','negative','bool'):
                changed=json.loads(raw)
                if change=='duplicate':changed['files'].append(changed['files'][0])
                else:changed['files'][0]['bytes']={'oversize':public.MAX_TOTAL+1,'negative':-1,'bool':True}[change]
                b=json.dumps(changed).encode()
                with self.subTest(change=change),self.assertRaises(ValueError):public.manifest_rows(b,public.sha(b))

    def test_public_origin_and_redirects_never_accept_credentials_or_private_hosts(self):
        for url in ('http://files.pythonhosted.org/a','https://user:secret@huggingface.co/a',
                'https://127.0.0.1/a','https://example.com/a','https://files.pythonhosted.org.attacker/a',
                'https://huggingface.co:444/a','https://huggingface.co/a#fragment'):
            for redirect in (True,False):
                with self.subTest(url=url,redirect=redirect),self.assertRaises(ValueError):public.public_url(url,redirect=redirect)
        self.assertEqual(public.public_url('https://cas-bridge.xethub.hf.co/public?X=1',redirect=True),
            'https://cas-bridge.xethub.hf.co/public?X=1')
        with self.assertRaises(ValueError):public.public_url('https://cas-bridge.xethub.hf.co/public')

    def test_only_frozen_hash_catalog_is_selected_and_local_payload_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            _,_,raw,_=self.fixture(Path(td));manifest=public.manifest_rows(raw,public.sha(raw))
            catalog={('bootstrap','wheels/public.whl'):(public.sha(b'public bytes'),'https://files.pythonhosted.org/public.whl')}
            self.assertEqual(set(public.select_public(manifest,catalog)),{'wheels/public.whl'})
            with self.assertRaises(ValueError):public.select_public(manifest,{('bootstrap','wheels/public.whl'):('0'*64,'https://files.pythonhosted.org/public.whl')})
            manifest['files'][0]['bytes']=public.MAX_LOCAL+1
            with self.assertRaises(ValueError):public.select_public(manifest,catalog)
        catalog=public.public_catalog();self.assertEqual(sum(k[0]=='bootstrap' for k in catalog),56)
        self.assertIn(('model','models/E2B/model.safetensors'),catalog)

    def test_scope_restores_controller_and_transport_on_failure(self):
        before=(minimum.State,minimum.CONTRACT,minimum.REMOTE_MODULE,delivery.push)
        with self.assertRaisesRegex(RuntimeError,'fixture'):
            with scope.configured():
                self.assertNotEqual(delivery.push,before[-1]);self.assertEqual(minimum.REMOTE_MODULE,'tools.small_model_public_scope')
                self.assertEqual(minimum.State('fixture','a'*40,True).namespace,'e2b-public-route-paid-20261031')
                self.assertEqual(minimum.CONTRACT['public_asset_delivery'],'PINNED_HTTPS_PREPARATION_ONLY_V1')
                raise RuntimeError('fixture')
        self.assertEqual((minimum.State,minimum.CONTRACT,minimum.REMOTE_MODULE,delivery.push),before)

    def test_public_scope_permit_cannot_reuse_consumed_scope_or_exceed_wallet(self):
        now=time.time();source='a'*40
        value={'source_sha':source,'contract_sha256':minimum.life.digest(scope.CONTRACT),'namespace':scope.NAMESPACE,
            'instruction':scope.INSTRUCTION,'mode':'OWNER_APPROVED_E2B_PUBLIC_ASSETS','additional_cap_usd':'0.47',
            'allocation_inclusive_seconds':2020,'single_use':True,'automatic_retry':False,'top_up_allowed':False,
            'weight_bytes':10246621918,'pretrained_requests':3,'training_steps':4,'qualification_run_id':'123',
            'approved_at':now-1,'expires_at':now+3600,'continuation_observed_spend_usd':'0.95','maximum_projection_usd':'0.47'}
        self.assertIs(scope.validate_permit(value,source,now),value)
        for key,val in [('namespace','e2b-completion-paid-20261031'),('namespace','e2b-direct-paid-20261031'),('mode','OWNER_APPROVED_E2B_ADAPTER_FEASIBILITY'),
                ('maximum_projection_usd','0.48'),('continuation_observed_spend_usd','1'),('pretrained_requests',4)]:
            with self.subTest(key=key),self.assertRaises(ValueError):scope.validate_permit(dict(value,**{key:val}),source,now)

    def test_receiver_compressed_command_remains_within_dropbear_bound(self):
        command=delivery.remote_python(Path(public.__file__).read_text())
        self.assertLess(len(__import__('shlex').join(command+['receive','/root/backtrace/stage','/root/backtrace/runtime','a'*64,'600']).encode()),9000)

    def test_changed_public_transport_can_select_a40_without_relaxing_cost_or_create_exclusion(self):
        a40={'gpu':'NVIDIA A40','region':'EU-SE-1'}
        excluded={'gpu':'NVIDIA RTX A6000','region':'US-TX-1'}
        snapshot={'offers':[a40,excluded],'account':{'credit_balance_usd':'1.9441643765'}}
        with patch.object(scope,'original_choose',return_value={'costs':{'maximum_projection':'0.34'}}) as choose:
            self.assertEqual(scope.choose(snapshot,1)['costs']['additional_cap'],'0.47')
            self.assertEqual(choose.call_args.args[0]['offers'],[a40])
        for balance,projection in [('1.9441643765','0.48'),('1.79','0.34')]:
            with self.subTest(balance=balance,projection=projection),patch.object(scope,'original_choose',return_value={'costs':{'maximum_projection':projection}}),self.assertRaises(ValueError):
                scope.choose(dict(snapshot,account={'credit_balance_usd':balance}),1)


if __name__=='__main__':unittest.main()
