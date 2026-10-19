"""Real loopback TLS tests; fixture executable never starts a shell/server."""
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import runpod_control as control
from tools import runpod_job as job
from tools import ssh_bootstrap as ssh


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.marker = self.root / 'executed.json'
        self.binary = self.root / 'fixture-executable'
        self.binary.write_text('#!/usr/bin/python3\nimport os,json\nfrom pathlib import Path\n'
                               + 'Path(' + repr(str(self.marker)) + ').write_text(json.dumps(dict(os.environ)))\n')
        self.keygen = self.root / 'fixture-keygen'
        self.keygen.write_text('#!/usr/bin/python3\nimport sys\nfrom pathlib import Path\n'
                              + "p=Path(sys.argv[sys.argv.index('-f')+1])\n"
                              + "if '-y' in sys.argv:print('ssh-ed25519 Zml4dHVyZQ==')\n"
                              + "else:p.write_bytes(b'fixture host key')\n")
        self.keygen.chmod(0o700)
        self.addCleanup(patch.stopall)
        patch.dict(ssh.TRANSPORT, {'binary_sha256': ssh.sha(self.binary),
                                  'keygen_sha256': ssh.sha(self.keygen)}).start()
        self.owner = self.root / 'owner'
        self.init = ssh.prepare(self.binary, self.keygen, self.owner)
        job.private_json(self.owner / 'initializer.json', self.init)
        self.processes = []
        self.addCleanup(self.stop)

    def stop(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)

    def server(self, init=None):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        target = self.root / ('pod-' + str(port))
        program = ssh.START.replace("'/root/backtrace'", repr(str(target)))
        program = program.replace("('0.0.0.0',22)", "('127.0.0.1'," + str(port) + ")")
        # Only filesystem root/bind port differ from the literal production code.
        process = subprocess.Popen([sys.executable, '-I', '-c', program],
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'RUNPOD_API_KEY': 'fixture-canary',
                 **(init or self.init)['env']}, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.processes.append(process)
        deadline = time.monotonic() + 10
        while True:
            if process.poll() is not None:
                self.fail('receiver exited before readiness')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1):
                    break
            except ConnectionRefusedError:
                if time.monotonic() >= deadline:
                    self.fail('receiver did not listen')
                time.sleep(.01)
        return process, target, port

    def test_complete_wire_size_and_private_material_then_exact_delivery(self):
        receipt = ssh.validate_material(self.owner)
        body = control.encode_create_request(control.make_request('a' * 32, 0, self.init))
        self.assertLess(len(body), 16384)
        self.assertNotIn(b'BT_SSH_PART_', body)
        self.assertNotIn(base64.b64encode((self.owner / 'client.key').read_bytes()), body)
        process, target, port = self.server()
        self.assertEqual(ssh.deliver(self.owner, '127.0.0.1', port, 10)['bytes'], receipt['binary_bytes'])
        self.assertEqual(process.wait(timeout=10), 0)
        self.assertEqual((target / 'dropbear').read_bytes(), self.binary.read_bytes())
        self.assertEqual((target / 'dropbear').stat().st_mode & 0o777, 0o700)
        self.assertFalse((target / 'tls-key').exists())
        env = json.loads(self.marker.read_text())
        self.assertNotIn('RUNPOD_API_KEY', env)
        self.assertFalse(any(k.startswith('BT_') for k in env))
        self.assertNotIn('client.key', {p.name for p in target.iterdir()})

    def test_wrong_server_identity_is_rejected_before_upload(self):
        other = self.root / 'other'
        init = ssh.prepare(self.binary, self.keygen, other)
        process, target, port = self.server(init)
        with self.assertRaises(ssl.SSLCertVerificationError):
            ssh.deliver(self.owner, '127.0.0.1', port, 10)
        self.assertFalse((target / 'dropbear').exists())
        self.assertFalse(self.marker.exists())
        self.assertIsNone(process.poll())

    def test_missing_client_certificate_cannot_upload_then_owner_succeeds(self):
        process, target, port = self.server()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.load_verify_locations(cafile=self.owner / 'server.crt')
        with socket.create_connection(('127.0.0.1', port), timeout=5) as raw:
            with self.assertRaises(ssl.SSLError):
                with ctx.wrap_socket(raw, server_hostname='backtrace-bootstrap') as conn:
                    conn.sendall(b'not an authorized executable'); conn.recv(1)
        self.assertFalse((target / 'dropbear').exists())
        ssh.deliver(self.owner, '127.0.0.1', port, 10)
        self.assertEqual(process.wait(timeout=10), 0)

    def test_corruption_truncation_and_wrong_length_never_execute(self):
        data = self.binary.read_bytes()
        for label, header, content in (
                ('corrupt', len(data), b'x' * len(data)),
                ('truncated', len(data), data[:-5]),
                ('oversized', len(data) + 1, b'')):
            with self.subTest(label=label):
                process, target, port = self.server()
                with socket.create_connection(('127.0.0.1', port), timeout=5) as raw:
                    with ssh.context(self.owner).wrap_socket(raw, server_hostname='backtrace-bootstrap') as conn:
                        conn.sendall(header.to_bytes(8, 'big') + content)
                self.assertNotEqual(process.wait(timeout=10), 0)
                self.assertFalse((target / 'dropbear').exists())
                self.assertFalse((target / 'dropbear.partial').exists())
                self.assertFalse(self.marker.exists())

    def test_local_changed_binary_and_key_material_block_before_connection(self):
        (self.owner / 'transport').write_bytes(b'changed')
        with patch.object(socket, 'create_connection') as connect:
            with self.assertRaisesRegex(ValueError, 'executable changed'):
                ssh.deliver(self.owner, '127.0.0.1', 1234, 10)
            connect.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'executable changed'):
            ssh.validate_material(self.owner)
        (self.owner / 'transport').write_bytes(self.binary.read_bytes())
        (self.owner / 'client.key').chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'private transport file'):
            ssh.validate_material(self.owner)

    def test_expired_certificate_blocks_preparation_before_provider_or_hashing(self):
        expired = self.owner / 'expired.crt'
        subprocess.run(['openssl', 'x509', '-in', str(self.owner / 'client.crt'),
                        '-signkey', str(self.owner / 'client.key'), '-days', '-1', '-out', str(expired)],
                       check=True, capture_output=True, timeout=10)
        expired.replace(self.owner / 'client.crt'); (self.owner / 'client.crt').chmod(0o600)
        self.init['env']['BT_TLS_CLIENT'] = base64.b64encode((self.owner / 'client.crt').read_bytes()).decode()
        job.private_json(self.owner / 'initializer.json', self.init)
        config = dict.fromkeys(('driver', 'wheels', 'task', 'model'), str(self.root))
        config.update(ssh_directory=str(self.owner), controller_host='existing-linux-host',
                      state_directory=str(self.root / 'state'), files_persist=True)
        with patch.object(job, 'check_owner_host'), patch.object(job, 'verify') as verify, \
                patch.object(control, 'RunpodAPI') as api:
            with self.assertRaises(subprocess.CalledProcessError):
                job.prepare(config, self.root / 'plan')
            verify.assert_not_called(); api.assert_not_called()
        self.assertFalse((self.root / 'plan').exists())

    def test_retry_is_only_tcp_readiness_and_deadline_is_bounded(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        t0 = time.monotonic()
        with self.assertRaises(TimeoutError):
            ssh.deliver(self.owner, '127.0.0.1', port, .1)
        self.assertLess(time.monotonic() - t0, 2)

    def test_transfer_failure_marks_worker_failed_before_streams_or_task(self):
        plan, state = self.root / 'plan', self.root / 'state'
        plan.mkdir(); state.mkdir()
        job.private_json(plan / 'plan.json', {'configuration': {'ssh_directory': str(self.owner)}})
        job.private_json(state / 'a100-attempt.json',
                         {'attempt': 'a' * 32, 'pod_id': 'fixture', 'requested_at': time.time()})
        key = self.root / 'key'; key.write_text('fixture-no-provider'); key.chmod(0o600)
        with patch.object(control, 'RunpodAPI') as api, patch.object(control, 'resource_matches', return_value=True), \
                patch.object(ssh, 'deliver', side_effect=TimeoutError('fixture timeout')), \
                patch.object(job, 'push') as push, patch.object(job, 'remote') as remote:
            api.return_value.get.return_value = {'status': 'RUNNING', 'ssh': {
                'direct': {'username': 'root', 'host': '127.0.0.1', 'port': 1234}}}
            with self.assertRaises(TimeoutError):
                job.worker(plan, key, state)
            push.assert_not_called(); remote.assert_not_called()
        self.assertEqual(json.loads((state / 'job-status.json').read_text())['state'], 'failed')


if __name__ == '__main__':
    unittest.main()
