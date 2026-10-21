"""Rebuild the already reviewed SSH source on a free owner-side CPU runner."""
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile

from tools.ssh_bootstrap import TRANSPORT

OPTIONS = '''#define DROPBEAR_SVR_PASSWORD_AUTH 0
#define DROPBEAR_SVR_PAM_AUTH 0
#define DROPBEAR_SFTPSERVER 0
#define DROPBEAR_SVR_AGENTFWD 0
#define DROPBEAR_SVR_LOCALTCPFWD 0
#define DROPBEAR_SVR_REMOTETCPFWD 0
#define DROPBEAR_X11FWD 0
'''


def build(directory):
    import requests
    directory = Path(directory)
    directory.mkdir(mode=0o700)
    with requests.get(TRANSPORT['source_url'], timeout=30, stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > TRANSPORT['source_bytes']:
                raise ValueError('transport source size limit')
    if len(data) != TRANSPORT['source_bytes'] or hashlib.sha256(data).hexdigest() != TRANSPORT['source_sha256']:
        raise ValueError('pinned transport source changed')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        members = archive.getmembers()
        if (len(members) > 5000 or sum(m.size for m in members) > 32 * 1024**2
                or any(not (m.isfile() or m.isdir()) for m in members)):
            raise ValueError('transport source archive shape changed')
        archive.extractall(directory, filter='data')
    source = directory / 'dropbear-DROPBEAR_2026.94'
    (source / 'localoptions.h').write_text(OPTIONS)
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(directory), 'LANG': 'C.UTF-8'}
    with (directory / 'build.log').open('xb') as log:
        os.fchmod(log.fileno(), 0o600)
        for command in (
            ['./configure', '--enable-static', '--disable-zlib', '--disable-syslog',
             '--disable-lastlog', '--disable-utmp', '--disable-wtmp'],
            ['make', '-j4', 'PROGRAMS=dropbear dropbearkey'],
            ['strip', 'dropbear', 'dropbearkey'],
        ):
            subprocess.run(command, cwd=source, env=env, stdout=log, stderr=log, check=True, timeout=300)
    files = {name: {'bytes': (source / name).stat().st_size,
                    'sha256': hashlib.sha256((source / name).read_bytes()).hexdigest()}
             for name in ('dropbear', 'dropbearkey')}
    exact = (files['dropbear']['sha256'] == TRANSPORT['binary_sha256']
             and files['dropbearkey']['sha256'] == TRANSPORT['keygen_sha256'])
    return {'source_sha256': TRANSPORT['source_sha256'], 'binaries': files,
            'matches_prior_transport': exact, 'paid_transport': 'NOT STARTED'}
