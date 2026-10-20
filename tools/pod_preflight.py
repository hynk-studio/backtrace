"""Small, credential-free checks before expensive input transfer; no model start."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


def base(minimum_free_bytes):
    if (os.getuid() != 0 or sys.version_info[:2] != (3, 12)
            or platform.system() != 'Linux' or platform.machine() != 'x86_64'
            or int(Path('/proc/self/stat').read_bytes().split(b' ', 1)[0]) != os.getpid()):
        raise ValueError('root Linux x86_64 CPython 3.12 with local procfs required')
    if type(minimum_free_bytes) is not int or minimum_free_bytes <= 0:
        raise ValueError('explicit positive disk requirement required')
    free = shutil.disk_usage('/root').free
    if free < minimum_free_bytes:
        raise ValueError('insufficient temporary disk before input transfer')
    if any(shutil.which(name) is None for name in ('setpriv', 'git', 'bash')):
        raise ValueError('required workload executable missing')
    # Exercise the actual UID transition and traversal rules under SSH's mask.
    with tempfile.TemporaryDirectory(prefix='backtrace-preflight-') as name:
        root = Path(name); root.chmod(0o755)
        (root / 'code').write_text('readable'); (root / 'code').chmod(0o444)
        (root / 'private').mkdir(mode=0o700)
        (root / 'private/key').write_text('permission-fixture')
        (root / 'output').mkdir(mode=0o700); os.chown(root / 'output', 65534, 65534)
        program = '''import os,sys
from pathlib import Path
p=Path(sys.argv[1])
assert os.getuid()==65534 and os.getgid()==65534 and os.getgroups()==[]
assert 'NoNewPrivs:\\t1' in Path('/proc/self/status').read_text()
assert (p/'code').read_text()=='readable' and not os.access(p/'code',os.W_OK)
assert not os.access(p/'private/key',os.R_OK)
(p/'output/probe').write_text('ok')
'''
        subprocess.run(['setpriv', '--no-new-privs', '--bounding-set=-all',
            '--reuid=65534', '--regid=65534', '--clear-groups',
            '/usr/bin/python3.12', '-I', '-c', program, name],
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
            stdin=subprocess.DEVNULL, check=True, timeout=15)
    return {'status': 'PASS', 'python': platform.python_version(),
            'free_disk_bytes': free, 'required_disk_bytes': minimum_free_bytes,
            'uid_boundary': 'PASS', 'workload_uid': 65534, 'model_execution': 'NOT RUN'}


def runtime(*, require_gpu=True):
    """Check the installed frozen runtime in a short-lived process before weights."""
    if type(require_gpu) is not bool:
        raise ValueError('explicit hardware check mode required')
    program = '''import json,sys
sys.path.insert(0,'/root/backtrace/driver')
from tools.a100_task import check_runtime,cuda_runtime_info,check_gpu
inventory=check_runtime()
result={'status':'PASS','distributions':len(inventory),'cuda_runtime':cuda_runtime_info(),
        'model_execution':'NOT RUN','hardware':'NOT RUN'}
'''
    if require_gpu:
        program += 'import torch\nresult["hardware"]=check_gpu(torch.cuda)\n'
    program += 'print(json.dumps(result,sort_keys=True))\n'
    result = subprocess.run(['/opt/backtrace-runtime/venv/bin/python', '-I', '-c', program],
        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/root',
             'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
             'PYTHON_DOTENV_DISABLED': '1', 'OTEL_SDK_DISABLED': 'true'},
        stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    if result.returncode:
        sys.stderr.buffer.write(result.stderr); sys.stderr.flush()
        raise RuntimeError('installed runtime or assigned hardware check failed')
    return json.loads(result.stdout)
