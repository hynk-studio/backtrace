"""Real UID/file-access regression for the observed pre-inference failure."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import cloud_worker as worker


FIXTURE = r'''import json,os,shutil,subprocess,sys
from pathlib import Path
root=Path.cwd()
if sys.argv[1:]==['--probe']:
 assert os.getuid()==65534 and os.getgid()==65534 and os.getgroups()==[]
 assert 'NoNewPrivs:\t1' in Path('/proc/self/status').read_text()
 assert not os.access(root/'control/canary',os.R_OK)
 assert not os.access(root/'code/one_task.py',os.W_OK)
 assert not os.access(root/'input/pinned',os.W_OK)
 assert (root/'input/pinned').read_text()=='frozen-input'
 assert not any(k in os.environ for k in ('RUNPOD_API_KEY','GITHUB_TOKEN','KAGGLE_API_TOKEN'))
 (root/'worker/result').write_text('workload-output')
 print(json.dumps({'uid':os.getuid(),'requested_at':os.environ['BACKTRACE_ALLOCATION_REQUESTED_AT'],
                   'canary_readable':False,'code_writable':False,'input_writable':False}))
else:
 assert sys.argv[1:]==['--authorized-run'] and os.getuid()==0
 for name,mode in [('code',0o755),('worker',0o700),('control',0o700),('input',0o755)]:
  (root/name).mkdir(mode=mode)
 os.chown(root/'worker',65534,65534)
 (root/'control/canary').write_text('control-boundary')
 (root/'control/canary').chmod(0o600)
 (root/'input/pinned').write_text('frozen-input')
 (root/'input/pinned').chmod(0o444)
 shutil.copyfile(__file__,root/'code/one_task.py')
 subprocess.run([sys.executable,'-m','venv','--without-pip',str(root/'task-venv')],check=True,timeout=30)
 command=['setpriv','--no-new-privs','--bounding-set=-all','--reuid=65534','--regid=65534',
          '--clear-groups',str(root/'task-venv/bin/python'),'-I',str(root/'code/one_task.py'),'--probe']
 result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15)
 print(result.stdout,end='');print(result.stderr,end='',file=sys.stderr)
 raise SystemExit(result.returncode)
'''


def mapped_workload_ids():
    try:
        for kind in ('uid', 'gid'):
            rows = [tuple(map(int, line.split()))
                    for line in Path('/proc/self/' + kind + '_map').read_text().splitlines()]
            if not any(start <= 65534 < start + size for start, outside, size in rows):
                return False
        return True
    except (OSError, ValueError):
        return False


@unittest.skipUnless(os.getuid() == 0 and shutil.which('setpriv') and mapped_workload_ids(),
                     'real root Linux with mapped workload UID/GID required')
class WorkloadPermissionsTests(unittest.TestCase):
    def test_private_ssh_mask_reproduces_failure_and_workload_exec_restores_read_access(self):
        with tempfile.TemporaryDirectory(prefix='backtrace-worker-permissions-') as directory:
            root = Path(directory); root.chmod(0o755)
            private = root / 'private'; private.mkdir(mode=0o700)
            driver = private / 'driver.py'; driver.write_text(FIXTURE); driver.chmod(0o600)
            for fixed in (False, True):
                with self.subTest(fixed=fixed):
                    run = root / ('fixed' if fixed else 'old'); run.mkdir(mode=0o755)
                    with patch.object(worker, 'WORKLOAD_PYTHON', sys.executable), \
                            patch.object(worker, 'WORKLOAD_DRIVER', str(driver)):
                        command = worker.workload_command(1792477237)
                    if not fixed:
                        command = ['env', 'BACKTRACE_ALLOCATION_REQUESTED_AT=1792477237',
                                   sys.executable, '-I', str(driver), '--authorized-run']
                    result = subprocess.run(command, cwd=run, env=worker.CLEAN, umask=0o077,
                                            capture_output=True, text=True, timeout=60)
                    if not fixed:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('Permission denied', result.stderr)
                        self.assertFalse(result.stdout)
                        continue
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), {'uid':65534, 'requested_at':'1792477237',
                        'canary_readable':False, 'code_writable':False, 'input_writable':False})
                    self.assertEqual((run / 'code/one_task.py').stat().st_mode & 0o777, 0o644)
                    self.assertEqual((run / 'control').stat().st_mode & 0o777, 0o700)
                    self.assertEqual((run / 'control/canary').stat().st_mode & 0o777, 0o600)
                    self.assertEqual((run / 'worker/result').stat().st_uid, 65534)


if __name__ == '__main__': unittest.main()
