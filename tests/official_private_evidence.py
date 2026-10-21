"""Actual cross-UID encrypted evidence handoff, on free Linux only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if len(sys.argv) != 2:
    raise ValueError('qualified controller SDK site directory required')
sys.path.insert(0, sys.argv[1])
from tools.qualification_evidence import collect


def main():
    if sys.platform != 'linux' or os.getuid() != 0:
        raise ValueError('actual root Linux file/UID operations required')
    with tempfile.TemporaryDirectory(prefix='backtrace-evidence-permissions-') as directory:
        outer = Path(directory); outer.chmod(0o755)
        stage = outer / 'stage'; stage.mkdir(mode=0o700); os.chown(stage, 65533, 65533)
        private = stage / 'connected-task/success'; private.mkdir(mode=0o700, parents=True)
        (stage / 'connected-task').chmod(0o700)
        log = private / 'execution.log'; log.write_text('private evidence canary'); log.chmod(0o600)
        cipher = stage / 'result.age'
        before = log.stat()
        receipt = collect(stage, cipher)
        assert receipt['files'] == 1 and cipher.stat().st_uid == 65533
        assert log.stat().st_uid == before.st_uid == 0 and log.stat().st_mode == before.st_mode
        code = ('import os,sys;from pathlib import Path;'
                'assert not os.access(sys.argv[1],os.R_OK);'
                'assert Path(sys.argv[2]).read_bytes().startswith(b"age-encryption.org/v1");'
                'assert b"private evidence canary" not in Path(sys.argv[2]).read_bytes()')
        subprocess.run(['setpriv', '--no-new-privs', '--bounding-set=-all', '--reuid=65533',
            '--regid=65533', '--clear-groups', sys.executable, '-I', '-c', code, str(log), str(cipher)],
            env={'PATH': '/usr/bin:/bin'}, check=True, timeout=15)
        return {'status': 'PASS', 'plaintext_reader_uid': 0, 'ciphertext_reader_uid': 65533,
                'plaintext_access_from_controller': 'DENIED', 'ciphertext_read': 'PASS',
                'plaintext_permissions': 'UNCHANGED', 'gpu_allocations': 0}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
