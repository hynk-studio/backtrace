"""Free loopback integration of the rebuilt transport; no provider access.

Only this CPU test temporarily binds the observed executable hashes. Paid code
must use separately reviewed fixed hashes. Listener paths/ports are disposable.
"""
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import ssh_bootstrap as ssh
from tools.runpod_job import check_owner_host, private_json
from tools.private_delivery import push, ssh_command


def qualify(binary, keygen):
    check_owner_host()
    observed = {'binary_sha256': ssh.sha(binary), 'keygen_sha256': ssh.sha(keygen)}
    with tempfile.TemporaryDirectory(prefix='backtrace-transport-cpu-', dir='/root') as td, \
            patch.dict(ssh.TRANSPORT, observed):
        root = Path(td); owner = root / 'owner'; target = root / 'pod'
        init = ssh.prepare(binary, keygen, owner)
        private_json(owner / 'initializer.json', init)
        ssh.validate_material(owner)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        source = ssh.START.replace("'/root/backtrace'", repr(str(target)))
        source = source.replace("('0.0.0.0',22)", repr(('127.0.0.1', port)))
        source = source.replace("'-p','22'", "'-p'," + repr('127.0.0.1:' + str(port)))
        with (root / 'daemon.log').open('w') as log:
            process = subprocess.Popen([sys.executable, '-I', '-c', source],
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
                     'RUNPOD_API_KEY': 'fixture-canary-no-credential', **init['env']},
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            try:
                ssh.deliver(owner, '127.0.0.1', port, 20)
                known = ssh.known_hosts(owner, '127.0.0.1', port)
                command = ssh_command('127.0.0.1', port, owner / 'owner-key', known,
                                      str(target / 'input'), '0' * 64)[:-1]
                program = "import os,json;assert os.getuid()==0;assert not any(k.startswith('BT_') or k=='RUNPOD_API_KEY' for k in os.environ);print('clean-root-ssh')"
                for attempt in range(20):
                    result = subprocess.run(command + [shlex.join(['python3', '-I', '-c', program])],
                        stdin=subprocess.DEVNULL, capture_output=True, timeout=10,
                        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
                    if result.returncode == 0:
                        break
                    if process.poll() is not None:
                        raise RuntimeError('rebuilt daemon exited')
                    time.sleep(.1)
                if result.returncode or result.stdout.strip() != b'clean-root-ssh':
                    raise RuntimeError('rebuilt strict SSH or environment qualification failed')
                wrong = owner / 'wrong-hosts'
                wrong.write_text(f'[127.0.0.1]:{port} ' + (owner / 'owner-key.pub').read_text())
                wrong.chmod(0o600)
                denied = ssh_command('127.0.0.1', port, owner / 'owner-key', wrong,
                                     str(target / 'unused'), '0' * 64)[:-1]
                result = subprocess.run(denied + ["printf should-never-execute"],
                    stdin=subprocess.DEVNULL, capture_output=True, timeout=10,
                    env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
                if result.returncode == 0 or result.stdout:
                    raise RuntimeError('wrong host identity was not rejected')
                import hashlib
                data = b'backtrace private transport fixture\n' * 4096
                source_dir = root / 'source'; source_dir.mkdir(mode=0o700)
                (source_dir / 'fixture.bin').write_bytes(data)
                manifest = json.dumps({'schema_version': 1, 'phase': 'bootstrap', 'files': [
                    {'path': 'fixture.bin', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}]}).encode()
                command = ssh_command('127.0.0.1', port, owner / 'owner-key', known,
                                      str(target / 'input'), hashlib.sha256(manifest).hexdigest())
                manifest_path = root / 'manifest.json'; manifest_path.write_bytes(manifest)
                push(source_dir, manifest_path, command, 20)
                if (target / 'input/fixture.bin').read_bytes() != data:
                    raise RuntimeError('actual SSH byte transfer mismatch')
                return dict(observed, mutual_tls='PASS', strict_ssh='PASS', wrong_host='REJECTED',
                            clean_child_environment='PASS', private_transfer_bytes=len(data),
                            network='LOOPBACK ONLY', paid_operations=0)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)


if __name__ == '__main__':
    os.umask(0o077)
    if len(sys.argv) != 3:
        raise ValueError('exact rebuilt binary and keygen required')
    print(json.dumps(qualify(Path(sys.argv[1]), Path(sys.argv[2])), sort_keys=True))
