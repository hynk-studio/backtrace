"""Build exact private A100 delivery manifests without crawling private inputs.

Wheels, prepared driver, selected task and model are separate private streams.
This prepares/readbacks bytes only; no install, model execution or Pod creation.
"""
import argparse
import hashlib
import json
from pathlib import Path

from tools.a100_task import ROOT, POD_TOOLS, POD_DOCS, WHEEL_MANIFEST_SHA256
from tools.private_delivery import digest, parse_manifest, regular_file, verify

SOURCE_SHA256 = '873e9dc7cf372948c154fb6b9d1e24170f1eb74fea4426d32fc17702581a030a'
TASK_SHA256 = '3cf1409f7dd48366b194523bfa7ee42bd0dd5289be68f3c26cdf140fc98faab3'
DRIVER_SHA256 = '13b5150de9c3ae5f060a009c748428e7b2dbf40ef2ed28a3560422821ca1339f'


def pinned_document(name, expected):
    data = (ROOT / 'docs' / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('frozen delivery inventory changed: ' + name)
    return json.loads(data)


def manifest(kind, prepared=None):
    if kind == 'task':
        value = pinned_document('a100-task-delivery.json', TASK_SHA256)
    elif kind == 'model':
        source = pinned_document('source-manifest.json', SOURCE_SHA256)
        records = source['native_dtype_continuation']['mounted_model_files']['files']
        value = {'schema_version': 1, 'phase': 'model', 'files': [
            {'path': r['path'], 'bytes': r['size_bytes'], 'sha256': r['sha256']} for r in records]}
    elif kind == 'wheels':
        records = pinned_document('linux-wheel-manifest.json', WHEEL_MANIFEST_SHA256)
        value = {'schema_version': 1, 'phase': 'bootstrap', 'files': [
            {k: r[k] for k in ('path', 'bytes', 'sha256')} for r in records]}
    elif kind == 'driver':
        if prepared is None:
            raise ValueError('prepared private driver directory required')
        driver = regular_file(prepared, 'one_task.py')
        if digest(driver) != DRIVER_SHA256:
            raise ValueError('prepared driver changed')
        references = {'startup_guard.py': ROOT / 'tools/startup_guard.py'}
        references.update({'tools/' + n: ROOT / 'tools' / n for n in POD_TOOLS})
        references.update({'docs/' + n: ROOT / 'docs' / n for n in POD_DOCS})
        rows = [{'path': 'one_task.py', 'bytes': driver.stat().st_size, 'sha256': DRIVER_SHA256}]
        for name, reference in sorted(references.items()):
            # Hash from this reviewed source snapshot, not an arbitrary source
            # file added beside the driver. Receipt/diff/controller are excluded.
            rows.append({'path': name, 'bytes': reference.stat().st_size, 'sha256': digest(reference)})
        value = {'schema_version': 1, 'phase': 'bootstrap', 'files': rows}
        verify(prepared, json.dumps(value).encode())
    else:
        raise ValueError('unsupported delivery kind')
    data = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    parse_manifest(data)
    return data


def build(kind, root, output):
    data = manifest(kind, root if kind == 'driver' else None)
    receipt = verify(root, data)  # No manifest is written for changed/missing input bytes.
    with Path(output).open('xb') as stream:
        import os
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('wheels', 'driver', 'task', 'model'))
    parser.add_argument('root', type=Path)
    parser.add_argument('manifest_output', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.kind, args.root, args.manifest_output), sort_keys=True))
