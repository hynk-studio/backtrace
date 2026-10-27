import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

from tools import small_model_container as container
from tools import small_model_container_install as installer


class ContainerTests(unittest.TestCase):
    def test_runtime_archive_rejects_path_traversal_links_duplicates(self):
        for kind in ('path','link','duplicate'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as td:
                root=Path(td);archive=root/'runtime.tar.gz'
                with tarfile.open(archive,'w:gz') as t:
                    i=tarfile.TarInfo('../escape' if kind=='path' else 'bin/python3.12');i.size=1
                    if kind=='link':i.type=tarfile.SYMTYPE;i.linkname='/etc/passwd';i.size=0
                    t.addfile(i,io.BytesIO(b'x'))
                    if kind=='duplicate':t.addfile(i,io.BytesIO(b'x'))
                with self.assertRaises(ValueError):installer.unpack(archive,root/'python')
                self.assertFalse((root/'escape').exists())

    def test_unpacked_executable_has_fixed_owner_controlled_mode(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);archive=root/'runtime.tar.gz'
            with tarfile.open(archive,'w:gz') as t:
                i=tarfile.TarInfo('bin/python3.12');i.size=1;i.mode=0o6777;t.addfile(i,io.BytesIO(b'x'))
            r=installer.unpack(archive,root/'python')
            self.assertEqual(r,{'files':1,'bytes':1})
            self.assertEqual((root/'python/bin/python3.12').stat().st_mode&0o7777,0o555)

    def test_paid_modes_are_not_an_adapter_option(self):
        for mode in ('pretrained_cuda','pretrained_cpu','random_cuda_fixture','cuda_probe'):
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                container.command(['ssh'],'E2B',mode)
        self.assertFalse(container.launch_gates()['paid_launch_enabled'])
        self.assertEqual(container.launch_gates()['hidden_cgroup_ancestor_admission'],'BLOCKED_REQUIRES_HOST_EVIDENCE')

    def test_remote_command_has_fixed_identity_and_bounds(self):
        command=container.command(['ssh','-T'],'E2B','random_fixture')
        self.assertEqual(command[:2],['ssh','-T'])
        self.assertIn('/opt/backtrace/venv/bin/python -I',command[-1])
        for invalid in (0,3001):
            with self.assertRaises(ValueError):container.command(['ssh'],'E2B','random_fixture',seconds=invalid)
        with self.assertRaises(ValueError):container.command(['ssh'],'../../root','random_fixture')

    def test_actual_filter_denies_sockets_processes_and_allows_threads(self):
        program="""import errno,json,os,socket,threading
from tools.small_model_container_worker import restrict_syscalls
restrict_syscalls();r={}
for name,fn in [('socket',socket.socket),('fork',os.fork),('exec',lambda:os.execve('/usr/bin/true',['true'],{}))]:
 try:fn()
 except OSError as e:r[name]=e.errno==errno.EPERM
 else:r[name]=False
t=threading.Thread(target=lambda:r.update(thread=True));t.start();t.join(3)
print(json.dumps(r))
"""
        p=subprocess.run([sys.executable,'-c',program],capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout),{'socket':True,'fork':True,'exec':True,'thread':True})

    def test_manifest_excludes_unlisted_stream_injection(self):
        from tools.private_delivery import verify
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'worker.py').write_text('trusted')
            raw=container.manifest(root);(root/'delivery-manifest.json').write_bytes(raw)
            (root/'labels.json').write_text('must not enter')
            with self.assertRaises(ValueError):verify(root,raw,exact=True)

    def test_transport_close_preserves_exit_after_remote_grace_period(self):
        with tempfile.TemporaryDirectory() as td:
            channel=container.ContainerChannel([sys.executable,'-I','-c',
                'import sys,time;sys.stdin.buffer.read();time.sleep(1.15)'],Path(td)/'stderr.log')
            self.assertEqual(channel.close(),0)


if __name__=='__main__':unittest.main()
