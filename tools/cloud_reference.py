"""Ephemeral encrypted handoff of the previously frozen CPU reference files.

Only a public age recipient and ciphertext enter Git. The identity remains on
the disposable free runner. This separate namespace cannot write paid claims.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
import zipfile

from tools import cloud_state
from tools.cloud_resolver import official_manifest


def transfer_path(run_id, source_sha):
    if not re.fullmatch(r'[1-9][0-9]{0,19}', str(run_id)) or not cloud_state.SHA.fullmatch(source_sha):
        raise ValueError('exact free workflow identity required')
    return 'a100-transfer/' + str(run_id) + '-' + source_sha


def open_receiver(store, run_id, source_sha):
    import pyrage
    prefix = transfer_path(run_id, source_sha)
    identity = pyrage.x25519.Identity.generate()
    recipient = str(identity.to_public())
    value = {'format': 'age-x25519', 'run_id': str(run_id), 'source_sha': source_sha,
             'recipient': recipient, 'purpose': 'frozen-cpu-references-only'}
    body = {'branch': cloud_state.BRANCH, 'message': 'Open ephemeral CPU reference receiver',
            'content': base64.b64encode(cloud_state.encoded(value)).decode()}
    # Create only. Unknown completion is not retried with another identity.
    store.request('PUT', '/contents/' + prefix + '/receiver.json', body)
    return identity, prefix


def restore_zip(data, root):
    """Validate every original byte before writing explicit fixed destinations."""
    root = Path(root)
    if len(data) > 1024**2:
        raise ValueError('reference archive size limit')
    rows = json.loads(official_manifest())['files']
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if (len(infos) != len(rows) or {i.filename for i in infos} != {r['path'] for r in rows}
                or any(i.is_dir() or (i.external_attr >> 16) & 0o170000 == 0o120000 for i in infos)):
            raise ValueError('unexpected reference archive members')
        verified = {}
        for row in rows:
            info = archive.getinfo(row['path'])
            if info.file_size != row['bytes'] or info.file_size > 1024**2:
                raise ValueError('reference size changed')
            body = archive.read(info)
            if hashlib.sha256(body).hexdigest() != row['sha256']:
                raise ValueError('reference hash changed')
            verified[row['path']] = body
    root.mkdir(mode=0o700)
    for name, body in verified.items():
        target = root / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with target.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(body)
    return {'verified_files': len(rows), 'bytes': sum(map(len, verified.values())),
            'source': 'retained-original-manifest', 'transport': 'ephemeral-age', 'plaintext_published': False}


def receive(store, identity, prefix, root, *, timeout=600, wall=time.monotonic, sleep=time.sleep):
    import pyrage
    deadline = wall() + timeout
    while wall() < deadline:
        result = store.request('GET', '/contents/' + prefix + '/references.age.b64?ref=' + cloud_state.BRANCH,
                               missing=True)
        if result is None:
            sleep(min(5, max(0, deadline - wall())))
            continue
        if result.get('type') != 'file' or result.get('encoding') != 'base64':
            raise ValueError('invalid encrypted reference object')
        encoded = base64.b64decode(result['content'])
        if len(encoded) > 2 * 1024**2:
            raise ValueError('encrypted reference size limit')
        ciphertext = base64.b64decode(encoded, validate=True)
        data = pyrage.decrypt(ciphertext, [identity])
        return restore_zip(data, root)
    raise TimeoutError('ephemeral reference handoff deadline')
