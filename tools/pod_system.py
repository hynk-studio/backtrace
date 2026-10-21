"""Hash-pinned Ubuntu system utilities, installed offline before Python inputs."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

IMAGE = ('pytorch/pytorch:2.10.0-cuda12.8-cudnn9-runtime@sha256:'
         'b85566342b86d13a67712e9315d40cdc2dad7f8d86df1aff3831f80835edbcca')


def validate(value):
    if (set(value) != {'schema_version', 'image', 'requested', 'files'}
            or value['schema_version'] != 1 or value['image'] != IMAGE
            or value['requested'] != ['git', 'patch'] or not 1 <= len(value['files']) <= 24):
        raise ValueError('exact pinned system package manifest required')
    names = set(); packages = set()
    for row in value['files']:
        url = urllib.parse.urlsplit(row['url'])
        if (set(row) != {'path', 'package', 'version', 'architecture', 'bytes', 'sha256', 'url'}
                or not re.fullmatch(r'[A-Za-z0-9.+%:_-]+\.deb', row['path'])
                or row['path'] in names or row['package'] in packages
                or not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*', row['package'])
                or not re.fullmatch(r'[A-Za-z0-9.+:~_-]+', row['version'])
                or row['architecture'] not in ('amd64', 'all')
                or type(row['bytes']) is not int or not 0 < row['bytes'] <= 64 * 1024**2
                or not re.fullmatch(r'[a-f0-9]{64}', row['sha256'])
                or url.scheme != 'https' or url.hostname not in ('archive.ubuntu.com', 'security.ubuntu.com')
                or url.username or url.password or url.port or url.query or url.fragment
                or not url.path.startswith('/ubuntu/pool/') or '..' in url.path.split('/')):
            raise ValueError('invalid pinned Ubuntu package')
        names.add(row['path']); packages.add(row['package'])
    if not {'git', 'patch'}.issubset(packages) or sum(r['bytes'] for r in value['files']) > 64 * 1024**2:
        raise ValueError('system package scope differs')
    return value


def verify(value, directory):
    value = validate(value); directory = Path(directory)
    for row in value['files']:
        path = directory / row['path']
        if (path.is_symlink() or not path.is_file() or path.stat().st_size != row['bytes']
                or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']):
            raise ValueError('system package identity mismatch')


def download(value, directory, *, deadline):
    value = validate(value); directory = Path(directory); directory.mkdir(mode=0o700)
    for row in value['files']:
        remaining = deadline - time.time()
        if remaining <= 0: raise TimeoutError('system input deadline')
        with urllib.request.urlopen(row['url'], timeout=min(60, remaining)) as response:
            if response.geturl() != row['url']:
                raise ValueError('unexpected system package redirect')
            data = response.read(row['bytes'] + 1)
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('system package download identity mismatch')
        with (directory / row['path']).open('xb') as stream:
            stream.write(data)
    verify(value, directory)
    return {'status': 'PASS', 'files': len(value['files']), 'bytes': sum(r['bytes'] for r in value['files'])}


def smoke():
    """Use the real isolated UID to check the harness's git/patch operations."""
    with tempfile.TemporaryDirectory(prefix='backtrace-system-') as name:
        root = Path(name); root.chmod(0o700); os.chown(root, 65534, 65534)
        program = '''import subprocess
from pathlib import Path
def git(*args,**kwargs):
 return subprocess.run(['git',*args],check=True,capture_output=True,**kwargs)
git('init','-q')
Path('fixture.txt').write_text('before\\n')
git('add','fixture.txt')
git('-c','user.name=CPU fixture','-c','user.email=fixture@example.invalid','commit','-qm','baseline')
Path('fixture.txt').write_text('after\\n')
diff=git('diff','--binary','HEAD').stdout
assert b'+after' in diff
git('checkout','--','fixture.txt')
git('apply','--check',input=diff)
subprocess.run(['patch','--dry-run','-p1'],input=diff,check=True,capture_output=True)
git('apply',input=diff)
assert Path('fixture.txt').read_text()=='after\\n'
'''
        subprocess.run(['setpriv', '--no-new-privs', '--bounding-set=-all', '--reuid=65534',
            '--regid=65534', '--clear-groups', '/usr/bin/python3.12', '-I', '-c', program],
            cwd=root, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': str(root)},
            stdin=subprocess.DEVNULL, check=True, timeout=30)
    return 'PASS'


def install(value, requested_at, *, local_packages=None):
    value = validate(value)
    if os.getuid() != 0 or not 0 <= time.time() - requested_at < 5400:
        raise ValueError('root and fresh setup clock required')
    directory = Path(local_packages) if local_packages is not None else Path('/root/backtrace/system')
    if local_packages is None:
        download(value, directory, deadline=min(requested_at + 5400, time.time() + 180))
    verify(value, directory)
    subprocess.run(['dpkg', '--install', *[str(directory / row['path']) for row in value['files']]],
        env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'HOME': '/root',
             'DEBIAN_FRONTEND': 'noninteractive'}, stdin=subprocess.DEVNULL, check=True,
        timeout=min(180, max(.001, requested_at + 5400 - time.time())))
    for row in value['files']:
        observed = subprocess.check_output(['dpkg-query', '-W', '-f=${Version}', row['package']], text=True)
        if observed != row['version']: raise ValueError('installed system package version mismatch')
    return {'status': 'PASS', 'files': len(value['files']), 'installation_network': 'NOT USED',
            'git_version': subprocess.check_output(['git', '--version'], text=True).strip(),
            'isolated_git_patch_smoke': smoke()}
