"""Read root/UID test logs as root; export only owner-encrypted bytes."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def collect(root, output, *, early=False):
    from tools import cloud_seal
    if os.getuid() != 0:
        raise PermissionError('private qualification evidence requires root collection')
    root, output = Path(root), Path(output)
    owner = root.stat()
    names = ('evidence-permissions.log', 'actual-api-http.log', 'official-cloud-driver.log', 'actual-cpu-prerequisites.log',
             'connected-task.log') if early else (
        'evidence-permissions.log', 'retained-source.ipynb', 'offline-runtime.log', 'official-cloud-driver.log', 'cpu-task-layout.log',
        'actual-cpu-prerequisites.log', 'cuda-runtime.log', 'transport-loopback.log', 'transport/build.log',
        'pinned-image.log', 'concurrent-controller.log', 'actual-api-http.log', 'image-result/api-http.log',
        'image-result/image.json', 'connected-task.log', 'full-setup-process.log',
        'full-setup-result.json', 'full-setup/image.log', 'full-setup/ssh.log', 'full-setup/container.log')
    files = {name: root / name for name in names if (root / name).is_file()}
    trees = ('connected-task',) if early else ('connected-task', 'image-result/connected-task')
    for tree in trees:
        for path in sorted((root / tree).rglob('*')):
            if path.is_file() and (not early or path.name in ('execution.log', 'connected-summary.json',
                    'evaluation.json', 'evaluator.log', 'test-output.txt', 'test-results.xml',
                    'scripted-model-summary.json')):
                files[path.relative_to(root).as_posix()] = path
    if not files:
        return None
    result = cloud_seal.seal(files, output, limit=460 * 1024 if early else 16 * 1024**2)
    os.chown(output, owner.st_uid, owner.st_gid)
    return result


def privileged(root, output, *, early=False):
    import pyrage
    output = Path(output)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    sites = str(Path(pyrage.__file__).resolve().parent.parent)
    program = ('import sys,json;sys.path[:0]=' + repr([str(ROOT), sites])
               + ';from tools.qualification_evidence import collect;'
               + 'print(json.dumps(collect(sys.argv[1],sys.argv[2],early=sys.argv[3]=="early")))')
    result = subprocess.run(['sudo', sys.executable, '-I', '-c', program, str(root), str(output),
                             'early' if early else 'final'],
        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=120)
    return json.loads(result.stdout)
