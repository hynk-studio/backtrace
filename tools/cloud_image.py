"""Run CPU prerequisites inside the exact digest-pinned deployment image."""
import json
from pathlib import Path
import subprocess

from tools import a100_delivery as frozen, runpod_control as control


def qualify(root, log):
    root = Path(root)
    output = root / 'image-result'; output.mkdir(mode=0o700)
    subprocess.run(['docker', 'pull', control.BASE], stdin=subprocess.DEVNULL,
                   stdout=log, stderr=log, check=True, timeout=900)
    result = subprocess.run(['docker', 'image', 'inspect', control.BASE],
        stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=30)
    image = json.loads(result.stdout)
    if (len(image) != 1 or image[0]['Architecture'] != 'amd64' or image[0]['Os'] != 'linux'
            or not any(d.endswith('@' + control.BASE.split('@')[1]) for d in image[0]['RepoDigests'])):
        raise ValueError('pulled image identity differs from the deployment digest')
    name = 'backtrace-free-image-qualification'
    command = ['docker', 'run', '--rm', '--name', name, '--network', 'none',
               '--security-opt', 'no-new-privileges', '--entrypoint', '/usr/bin/python3.12']
    for source, target, readonly in (
            *((frozen.ROOT / p, '/work/' + p, True) for p in ('tools', 'docs', 'tests')),
            (root / 'driver', '/inputs/driver', True),
            (root / 'system', '/inputs/system', True),
            (root / 'wheels', '/root/backtrace/wheels', True),
            (root / 'api-negative', '/inputs/api-negative', True),
            (root / 'task', '/inputs/task', True), (output, '/result', False)):
        command += ['--mount', 'type=bind,source=' + str(source.resolve()) + ',target=' + target
                    + (',readonly' if readonly else '')]
    command += [control.BASE, '-I', '/work/tests/official_cloud_image.py']
    try:
        subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                       check=True, timeout=1800)
    finally:
        subprocess.run(['docker', 'rm', '-f', name], stdin=subprocess.DEVNULL,
                       stdout=log, stderr=log, timeout=30)
    report = json.loads((output / 'image.json').read_text())
    if report.get('status') != 'PASS':
        raise ValueError('pinned image CPU prerequisites did not pass')
    return dict(report, image=control.BASE, image_id=image[0]['Id'])
