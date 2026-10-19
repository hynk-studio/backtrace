"""Free CPU loopback qualification of the exact private Dropbear transport.

Usage: python -m tools.qualify_ssh_transport BUILD DRIVER OUTPUT_JSON
No provider API, account key, inference, GPU or task execution is involved.
Only the literal receiver's private root and TCP port change for this fixture.
The pinned binary itself is never published with this tool.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

from tools import ssh_bootstrap as ssh
from tools import runpod_control as control
from tools.a100_delivery import manifest
from tools.private_delivery import digest, push, ssh_command, verify
from tools.runpod_job import check_owner_host, private_json


def qualify(build, driver, output):
    check_owner_host()
    if list(Path('/dev').glob('nvidia[0-9]*')):
        raise ValueError('free CPU fixture required')
    build, driver, output = Path(build).absolute(), Path(driver).absolute(), Path(output).absolute()
    if output.exists():
        raise FileExistsError('preserve prior qualification evidence')
    root = Path(tempfile.mkdtemp(prefix='backtrace-tls-ssh-', dir='/root'))
    state, remote = root / 'keys', root / 'remote'
    process = None
    started = time.monotonic()
    receipt = {'network': 'LOOPBACK ONLY', 'provider_api_calls': 0, 'gpu': 'NOT RUN',
               'server_starts': 0, 'task_executions': 0, 'status': 'FAIL'}
    try:
        init = ssh.prepare(build / 'dropbear', build / 'dropbearkey', state)
        private_json(state / 'initializer.json', init)
        receipt['transport'] = ssh.validate_material(state)
        receipt['create_request_bytes'] = len(control.encode_create_request(control.make_request('0' * 32, 0, init)))
        receipt['create_limit_bytes'] = control.MAX_CREATE_BYTES
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        program = ssh.START.replace("'/root/backtrace'", repr(str(remote)))
        program = program.replace("('0.0.0.0',22)", "('127.0.0.1'," + str(port) + ")")
        program = program.replace("'-p','22'", "'-p'," + repr(str(port)))
        receipt['literal_program_sha256'] = hashlib.sha256(ssh.START.encode()).hexdigest()
        receipt['fixture_overrides'] = ['private root', 'loopback TCP port']
        with (root / 'receiver.log').open('w') as log:
            process = subprocess.Popen([sys.executable, '-I', '-c', program],
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
                     'RUNPOD_API_KEY': 'fixture-canary-not-a-credential', **init['env']},
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            receipt['binary_transfer'] = ssh.deliver(state, '127.0.0.1', port, 30)
            known = ssh.known_hosts(state, '127.0.0.1', port)
            data = manifest('driver', driver)
            m = root / 'driver-manifest.json'; m.write_bytes(data); m.chmod(0o600)
            command = ssh_command('127.0.0.1', port, state / 'owner-key', known,
                                  str(remote / 'driver'), digest(m))
            prefix = command[:-1]
            deadline = time.monotonic() + 10
            while True:
                probe = subprocess.run(prefix + ['true'], capture_output=True, timeout=5,
                                       env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
                if probe.returncode == 0:
                    break
                if time.monotonic() >= deadline or process.poll() is not None:
                    raise RuntimeError('TLS-to-SSH handoff failed')
                time.sleep(.05)
            receipt['driver_transfer'] = push(driver, m, command, 60)
            verify(remote / 'driver', data, exact=True)
            code = "import os;assert 'RUNPOD_API_KEY' not in os.environ;assert not any(k.startswith('BT_') for k in os.environ);print('CREDENTIAL_ENV_ABSENT')"
            result = subprocess.check_output(prefix + [shlex.join(['python3', '-I', '-c', code])],
                                              env={'PATH': '/usr/bin:/bin'}, text=True, timeout=10)
            assert result.strip() == 'CREDENTIAL_ENV_ABSENT'
            wrong = root / 'wrong-known-hosts'
            wrong.write_text('[127.0.0.1]:' + str(port) + ' ' + (state / 'owner-key.pub').read_text())
            wrong.chmod(0o600)
            bad = ssh_command('127.0.0.1', port, state / 'owner-key', wrong,
                              str(remote / 'unused'), digest(m))[:-1]
            refused = subprocess.run(bad + ['true'], env={'PATH': '/usr/bin:/bin'}, capture_output=True, timeout=10)
            assert refused.returncode != 0 and b'Host key verification failed' in refused.stderr
            assert ssh.sha(remote / 'dropbear') == ssh.TRANSPORT['binary_sha256']
            assert not (remote / 'tls-key').exists()
            receipt.update(status='PASS', credential_environment='ABSENT', wrong_host_key='REFUSED',
                           tls_to_ssh_same_port='PASS', exact_driver_hashes='PASS')
    except Exception as error:
        receipt['error_type'] = type(error).__name__
        raise
    finally:
        if process is not None:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
            receipt['owned_daemon_exited'] = process.poll() is not None
        shutil.rmtree(root)
        receipt['temporary_keys_removed'] = not root.exists()
        receipt['seconds'] = round(time.monotonic() - started, 3)
        private_json(output, receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build'); parser.add_argument('driver'); parser.add_argument('output')
    args = parser.parse_args()
    print(json.dumps(qualify(args.build, args.driver, args.output), sort_keys=True))
