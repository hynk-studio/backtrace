"""Seal explicitly selected private evidence to the owner's offline age key.

Only the public recipient is present on Actions. Plaintext and secret keys are
never uploaded; this module has no decryption or credential API.
"""
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile

from tools.a100_delivery import ROOT

RECIPIENT = 'age1gpeg76pfvjyx04njsclt3tfka20a5lxwj4h5zrt55udg6gdch34ssc96uq'
LIMIT = 1024**3


def seal(files, output, *, limit=LIMIT):
    import pyrage
    if not 0 < limit <= LIMIT or not 0 < len(files) <= 1024:
        raise ValueError('private evidence bounds')
    if (ROOT / 'docs/a100-result-recipient.txt').read_text().strip() != RECIPIENT:
        raise ValueError('owner result recipient changed')
    rows, total = [], 0
    for name, value in files.items():
        rel, path = PurePosixPath(name), Path(value)
        if rel.is_absolute() or '..' in rel.parts or str(rel) != name or not name:
            raise ValueError('invalid evidence path')
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('evidence must be a regular file')
        total += info.st_size
        if total > limit:
            raise ValueError('private evidence size limit')
        rows.append((name, path, info))
    output = Path(output)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    plain = output.with_suffix('.private.tar')
    if output.exists() or plain.exists():
        raise FileExistsError('create-only evidence')
    try:
        with plain.open('xb') as stream:
            os.chmod(plain, 0o600)
            with tarfile.open(fileobj=stream, mode='w') as archive:
                for name, path, previous in rows:
                    with path.open('rb') as source:
                        current = os.fstat(source.fileno())
                        if ((current.st_ino, current.st_dev, current.st_size)
                                != (previous.st_ino, previous.st_dev, previous.st_size)):
                            raise ValueError('evidence changed during collection')
                        info = tarfile.TarInfo(name)
                        info.size = current.st_size; info.mode = 0o600
                        archive.addfile(info, source)
        pyrage.encrypt_file(str(plain), str(output), [pyrage.x25519.Recipient.from_str(RECIPIENT)])
        os.chmod(output, 0o600)
        with output.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        return {'format': 'age-v1', 'files': len(rows), 'plaintext_bytes': total,
                'ciphertext_bytes': output.stat().st_size, 'ciphertext_sha256': digest}
    finally:
        plain.unlink(missing_ok=True)
