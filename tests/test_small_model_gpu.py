"""Contract controls, not evidence of a physical GPU or driver."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
from unittest import mock

from tools import exact_teacher as exact
from tools import small_model_gpu as gpu
from tools import small_model_runner as runner
from tools import small_model_worker as worker
from tests.test_small_model_runner import FakeChannel,Tokenizer,request,frame

UUID='GPU-12345678-1234-1234-1234-123456789abc'
XML=f'''<nvidia_smi_log><driver_version>560.35.05</driver_version><gpu>
<uuid>{UUID}</uuid><product_name>Authored fixture</product_name><minor_number>3</minor_number>
<fb_memory_usage><total>40960 MiB</total></fb_memory_usage>
<mig_mode><current_mig>Disabled</current_mig></mig_mode><processes></processes>
</gpu></nvidia_smi_log>'''.encode()


class InventoryTests(unittest.TestCase):
    def test_uuid_device_minor_and_memory_are_not_enumeration_index(self):
        value=gpu.parse_inventory(XML,UUID)
        self.assertEqual(value['device_basename'],'nvidia3')
        self.assertEqual(value['reported_total_bytes'],40*gpu.GIB)
        self.assertEqual(value['nvidia_smi_xml_sha256'],exact.sha(XML))

    def test_driver_mig_busy_memory_and_identity_rejections(self):
        changes=[(b'560.35.05',b'550.90.07'),(b'40960 MiB',b'12288 MiB'),
                 (b'Disabled',b'Enabled'),(b'40960 MiB',b'40 GiB'),
                 (b'<processes></processes>',b'<processes><process_info/></processes>'),
                 (b'<minor_number>3',b'<minor_number>-1'),(UUID.encode(),b'GPU-wrong')]
        for before,after in changes:
            with self.subTest(after=after),self.assertRaises(ValueError):gpu.parse_inventory(XML.replace(before,after),UUID)
        with self.assertRaises(ValueError):gpu.parse_inventory(XML,'all')
        with self.assertRaises(ValueError):gpu.parse_inventory(XML.replace(b'</nvidia_smi_log>',XML[XML.index(b'<gpu>'):]),UUID)

    def test_no_nvidia_smi_fails_before_any_launch(self):
        with patch.object(gpu.shutil,'which',return_value=None),self.assertRaisesRegex(RuntimeError,'absent'):
            gpu.inventory(UUID)

    def test_no_cuda_device_never_falls_back_to_cpu(self):
        fake=types.SimpleNamespace(version=types.SimpleNamespace(cuda='12.6'),cuda=types.SimpleNamespace(is_available=lambda:False))
        with patch.dict('sys.modules',{'torch':fake}),self.assertRaisesRegex(RuntimeError,'fallback forbidden'):
            worker.cuda_check({'gpu':{'uuid':UUID}})

    def test_wrong_cuda_build_and_multiple_devices_are_rejected(self):
        fake=types.SimpleNamespace(version=types.SimpleNamespace(cuda='12.9'),cuda=types.SimpleNamespace(is_available=lambda:True,device_count=lambda:2))
        with patch.dict('sys.modules',{'torch':fake}),self.assertRaises(RuntimeError):worker.cuda_check({})
        fake.version.cuda='12.6'
        with patch.dict('sys.modules',{'torch':fake}),self.assertRaisesRegex(RuntimeError,'exactly one'):worker.cuda_check({})

    def cuda_identity_fixture(self,**changes):
        prop=types.SimpleNamespace(uuid=UUID.removeprefix('GPU-'),major=8,total_memory=48*gpu.GIB)
        for k,v in changes.items():setattr(prop,k,v)
        cuda=mock.Mock()
        cuda.is_available.return_value=True;cuda.device_count.return_value=1
        cuda.get_device_properties.return_value=prop;cuda.is_bf16_supported.return_value=True
        cuda.set_device.side_effect=RuntimeError('AUTHORED_KERNEL_BOUNDARY')
        fake=types.SimpleNamespace(version=types.SimpleNamespace(cuda='12.6'),cuda=cuda)
        job={'gpu':{'uuid':UUID,'minimum_total_bytes':24*gpu.GIB,'device_basename':'nvidia3'}}
        return fake,job

    def test_bare_pytorch_uuid_reaches_kernel_boundary_without_weakening_identity(self):
        for spelling in (UUID.removeprefix('GPU-'),UUID.removeprefix('GPU-').upper(),UUID):
            fake,job=self.cuda_identity_fixture(uuid=spelling)
            with patch.dict('sys.modules',{'torch':fake}),patch.object(worker.Path,'glob',return_value=[Path('/dev/nvidia3')]),\
                    self.assertRaisesRegex(RuntimeError,'AUTHORED_KERNEL_BOUNDARY'):
                worker.cuda_check(job)
            fake.cuda.is_bf16_supported.assert_called_once_with(including_emulation=False)
            fake.cuda.set_device.assert_called_once_with(0)
        for spelling in ('12345678','MIG-'+UUID[4:],UUID[:-1]+'d',UUID+'junk'):
            fake,job=self.cuda_identity_fixture(uuid=spelling)
            with patch.dict('sys.modules',{'torch':fake}),self.assertRaisesRegex(RuntimeError,'UUID'):
                worker.cuda_check(job)
            fake.cuda.set_device.assert_not_called()

    def test_correct_uuid_still_requires_capacity_memory_and_native_bf16(self):
        for changes,reason in [({'major':7},'capability'),({'total_memory':12*gpu.GIB},'memory'),({},'native BF16')]:
            fake,job=self.cuda_identity_fixture(**changes)
            if not changes:fake.cuda.is_bf16_supported.return_value=False
            with patch.dict('sys.modules',{'torch':fake}),self.assertRaisesRegex(RuntimeError,reason):
                worker.cuda_check(job)
            fake.cuda.set_device.assert_not_called()


class FilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=exact.ROOT/'.local');self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()

    def test_wheel_byte_identity_exact_closure_and_links(self):
        p=self.root/'one.whl';p.write_bytes(b'fixture')
        spec={'gpu_candidate':{'wheels':[{'url':'https://example.invalid/one.whl','sha256':exact.sha(b'fixture')}]}}
        with patch.object(gpu.ready,'lock',return_value=spec):
            self.assertEqual(gpu.verify_wheels(self.root)['count'],1)
            p.write_bytes(b'changed')
            with self.assertRaises(ValueError):gpu.verify_wheels(self.root)
            p.write_bytes(b'fixture');(self.root/'extra').write_bytes(b'x')
            with self.assertRaises(ValueError):gpu.verify_wheels(self.root)
            (self.root/'extra').unlink();p.unlink();p.symlink_to('/dev/null')
            with self.assertRaises(ValueError):gpu.verify_wheels(self.root)

    def test_device_mount_rejects_regular_file_or_changed_major_minor(self):
        stage=self.root/'stage';stage.mkdir()
        p=self.root/'not-device';p.write_text('x')
        command=runner.JailCommand(['bwrap','--chdir','/tmp','python'],stage)
        with self.assertRaises(ValueError):gpu.attach_devices(command,[{'path':str(p),'major':1,'minor':3}],{},UUID)
        runner.shutil.rmtree(stage);stage.mkdir()
        with self.assertRaises(ValueError):gpu.attach_devices(command,[{'path':'/dev/null','major':195,'minor':0}],{},UUID)

    def test_mount_builder_keeps_explicit_device_and_readonly_driver_only(self):
        stage=self.root/'stage';stage.mkdir();s=Path('/dev/null').stat()
        command=runner.JailCommand(['bwrap','--unshare-net','--dev','/dev','--chdir','/tmp','python'],stage)
        gpu.attach_devices(command,[{'path':'/dev/null','major':os.major(s.st_rdev),'minor':os.minor(s.st_rdev)}],{},UUID)
        self.assertIn('--unshare-net',command);self.assertEqual(command.count('--dev-bind'),1)
        self.assertNotIn('--bind',command);self.assertNotIn('--share-net',command)
        self.assertEqual(command[command.index('--dev-bind')+1:command.index('--dev-bind')+3],['/dev/null','/dev/null'])
        self.assertIn('LD_LIBRARY_PATH',command)

    def test_driver_library_hash_change_is_rejected_before_mount(self):
        stage=self.root/'stage';stage.mkdir();lib=self.root/'libcuda';lib.write_text('fixture')
        command=runner.JailCommand(['bwrap','--chdir','/tmp','python'],stage)
        with self.assertRaises(ValueError):gpu.attach_devices(command,[],{'libcuda.so.1':{'path':str(lib),'bytes':7,'sha256':'0'*64}},UUID)

    def test_preparation_preserves_schedule_and_does_not_grant_paid_permit(self):
        plan={'scope':'smoke','models':{'E2B':{},'E4B':{}},'generation':{},'model_loading':{}}
        schedule=[request(i) for i in range(36)]
        with patch.object(runner,'load_scope',return_value=(plan,schedule,'0'*64)):
            result=gpu.prepare(None,None,None,self.root/'plan.json')
        self.assertEqual(len(result['assignments']),36);self.assertFalse(result['paid_authorization'])
        self.assertEqual(result['additional_diagnostics']['random_cuda_requests'],36)
        self.assertEqual(result['limits']['allocation_inclusive_seconds'],3000)
        self.assertTrue(all('messages' not in r for r in result['assignments']))
        self.assertGreater(result['resource_candidate']['source_plus_disposable_model_copy_bytes'],48*gpu.GIB)
        plan['scope']='screening'
        with patch.object(runner,'load_scope',return_value=(plan,schedule,'0'*64)),self.assertRaises(ValueError):
            gpu.prepare(None,None,None,self.root/'screening.json')

    def test_cuda_handshake_and_metrics_required(self):
        channel=FakeChannel();channel.mode='pretrained_cuda'
        result=runner.collect([request()],self.root/'bad',lambda *a:channel,{'E2B':Tokenizer()},
            mode='pretrained_cuda',max_new_tokens=2,total_seconds=2,startup_seconds=1,request_seconds=1)
        self.assertEqual(result['coverage'],{'NOT_RUN':1})
        self.assertFalse(result['gpu_run']);self.assertTrue(result['gpu_requested'])
        class CudaChannel(FakeChannel):
            def read(self,deadline):return super().read(deadline)|{'cuda':{'uuid':UUID,'no_cpu_fallback':True}}
        channel=CudaChannel();channel.mode='pretrained_cuda'
        factory=lambda *a:channel;factory.gpu_uuid=UUID
        result=runner.collect([request()],self.root/'metrics-missing',factory,{'E2B':Tokenizer()},
            mode='pretrained_cuda',max_new_tokens=2,total_seconds=2,startup_seconds=1,request_seconds=1)
        self.assertEqual(result['coverage'],{'WORKER_ERROR':1})
        self.assertTrue(result['gpu_run'])

    def test_gpu_metrics_are_retained_with_raw_outputs_and_validated(self):
        f=frame(request());f['cuda_metrics']={'peak_allocated_bytes':100,'peak_reserved_bytes':200,'post_free_bytes':500,'total_bytes':1000}
        result=runner.response_record(f,request(),Tokenizer(),2)
        self.assertEqual(result['cuda_metrics'],f['cuda_metrics']);self.assertEqual(result['raw_output_ids'],[10,106])
        for key,value in [('peak_allocated_bytes',True),('peak_reserved_bytes',99),('post_free_bytes',1001),('total_bytes',-1)]:
            changed=deepcopy(f);changed['cuda_metrics'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):runner.response_record(changed,request(),Tokenizer(),2)


if __name__=='__main__':unittest.main()
