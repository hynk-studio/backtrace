import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools import private_delivery as delivery


class PrivateDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'nested').mkdir()
        self.content = b'private fixture, not competition data\n' * 50
        (self.source / 'nested/input.bin').write_bytes(self.content)
        self.manifest = {'schema_version': 1, 'phase': 'task', 'files': [
            {'path': 'nested/input.bin', 'bytes': len(self.content),
             'sha256': hashlib.sha256(self.content).hexdigest()}]}
        self.data = json.dumps(self.manifest).encode()
        self.sha = hashlib.sha256(self.data).hexdigest()
        self.manifest_path = self.root / 'manifest.json'
        self.manifest_path.write_bytes(self.data)
        self.dest = self.root / 'received'

    def archive(self):
        stream = io.BytesIO()
        delivery.emit(self.source, self.data, stream)
        return stream.getvalue()

    def test_separate_receiver_process_and_exact_readback(self):
        command = [sys.executable, '-I', delivery.__file__, 'receive', str(self.dest), self.sha]
        receipt = delivery.push(self.source, self.manifest_path, command, 10)
        self.assertEqual(receipt, delivery.verify(self.dest, self.data, exact=True))
        self.assertEqual((self.dest / 'nested/input.bin').read_bytes(), self.content)
        self.assertEqual(self.dest.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.dest / 'nested/input.bin').stat().st_mode & 0o777, 0o600)

    def test_wrong_manifest_never_commits(self):
        with self.assertRaises(ValueError):
            delivery.receive(self.dest, '0' * 64, io.BytesIO(self.archive()))
        self.assertFalse(self.dest.exists())

    def test_mutated_bytes_never_commit(self):
        raw = self.archive().replace(self.content, b'X' * len(self.content))
        with self.assertRaises(ValueError):
            delivery.receive(self.dest, self.sha, io.BytesIO(raw))
        self.assertFalse(self.dest.exists())
        self.assertFalse(list(self.root.glob('.delivery-*')))

    def test_truncation_never_commits(self):
        raw = self.archive()
        index = raw.index(self.content)
        with self.assertRaises((ValueError, tarfile.TarError)):
            delivery.receive(self.dest, self.sha, io.BytesIO(raw[:index + 20]))
        self.assertFalse(self.dest.exists())

    def test_extra_member_rejected(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            for name, content in [(delivery.MANIFEST_NAME, self.data), ('nested/input.bin', self.content), ('answers.json', b'private evaluator')]:
                entry = tarfile.TarInfo(name); entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
        with self.assertRaises(ValueError):
            delivery.receive(self.dest, self.sha, io.BytesIO(stream.getvalue()))
        self.assertFalse(self.dest.exists())

    def test_symlink_and_hardlink_members_rejected(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            with self.subTest(kind=kind):
                stream = io.BytesIO()
                with tarfile.open(fileobj=stream, mode='w') as archive:
                    entry = tarfile.TarInfo(delivery.MANIFEST_NAME); entry.size = len(self.data)
                    archive.addfile(entry, io.BytesIO(self.data))
                    entry = tarfile.TarInfo('nested/input.bin'); entry.type = kind
                    entry.linkname = '/etc/passwd'; archive.addfile(entry)
                with self.assertRaises(ValueError):
                    delivery.receive(self.dest, self.sha, io.BytesIO(stream.getvalue()))

    def test_traversal_duplicate_and_prefix_collisions_rejected(self):
        for name in ('../escape', '/absolute', 'a/../b', 'a//b', './b', 'a\\b', delivery.MANIFEST_NAME):
            with self.subTest(name=name):
                value = json.loads(self.data)
                value['files'][0]['path'] = name
                with self.assertRaises(ValueError):
                    delivery.parse_manifest(json.dumps(value).encode())
        for name in ('nested/input.bin', 'nested'):
            value = json.loads(self.data)
            value['files'].append(dict(value['files'][0], path=name))
            with self.assertRaises(ValueError):
                delivery.parse_manifest(json.dumps(value).encode())

    def test_source_symlink_rejected(self):
        path = self.source / 'nested/input.bin'
        path.unlink(); path.symlink_to(self.manifest_path)
        with self.assertRaises(ValueError):
            delivery.emit(self.source, self.data, io.BytesIO())

    def test_no_overwrite_or_parallel_delivery(self):
        self.dest.mkdir()
        (self.dest / 'keep').write_text('unrelated')
        with self.assertRaises(ValueError):
            delivery.receive(self.dest, self.sha, io.BytesIO(self.archive()))
        self.assertEqual((self.dest / 'keep').read_text(), 'unrelated')
        other = self.root / 'other'
        (self.root / '.other.delivery-lock').touch()
        with self.assertRaises(FileExistsError):
            delivery.receive(other, self.sha, io.BytesIO(self.archive()))

    def test_receiver_requires_private_parent_and_capacity(self):
        self.root.chmod(0o755)
        with self.assertRaises(ValueError):
            delivery.receive(self.dest, self.sha, io.BytesIO(self.archive()))
        self.root.chmod(0o700)
        with patch.object(delivery.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 0})()):
            with self.assertRaises(ValueError):
                delivery.receive(self.dest, self.sha, io.BytesIO(self.archive()))

    def test_reader_rehash_detects_post_stream_corruption(self):
        original = delivery.verify
        def corrupt(root, data, exact=False):
            if exact:
                (root / 'nested/input.bin').write_bytes(b'corrupt')
            return original(root, data, exact)
        with patch.object(delivery, 'verify', side_effect=corrupt):
            with self.assertRaises(ValueError):
                delivery.receive(self.dest, self.sha, io.BytesIO(self.archive()))
        self.assertFalse(self.dest.exists())

    def test_receiver_hang_is_bounded_and_readback_mismatch_rejected(self):
        hanging = [sys.executable, '-I', '-c', 'import time; time.sleep(30)']
        with self.assertRaises(subprocess.TimeoutExpired):
            delivery.push(self.source, self.manifest_path, hanging, .1)
        wrong = [sys.executable, '-I', '-c', 'import sys; sys.stdin.buffer.read(); print("{}")']
        with self.assertRaises(ValueError):
            delivery.push(self.source, self.manifest_path, wrong, 10)

    def test_ssh_pins_host_and_disables_ambient_configuration(self):
        key, hosts = self.root / 'key', self.root / 'known_hosts'
        key.touch(); hosts.touch()
        command = delivery.ssh_command('host.example', 2222, key, hosts, '/root/private/attempt', self.sha)
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertIn('ForwardAgent=no', command)
        self.assertEqual(command[1:3], ['-F', '/dev/null'])
        for host in ('-oProxyCommand=evil', 'example;bad', 'root@example'):
            with self.assertRaises(ValueError):
                delivery.ssh_command(host, 22, key, hosts, '/root/private/attempt', self.sha)


if __name__ == '__main__':
    unittest.main()
