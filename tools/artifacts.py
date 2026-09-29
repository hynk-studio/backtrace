"""Read-only verification of the exact locally acquired competition inputs."""
import json
import stat
from pathlib import Path

try:
    from .backtrace import InspectionError, MANIFEST, digest, safe_name
except ImportError:
    from backtrace import InspectionError, MANIFEST, digest, safe_name


def verify_artifacts(root, records=None):
    """Verify byte pins before any official code is imported or a package built."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise InspectionError('missing artifact directory; follow docs/r0.md acquisition steps')
    root = root.resolve()
    if records is None:
        records = json.loads(MANIFEST.read_text())['official_artifacts']
    paths, keys = set(), set()
    for record in records:
        rel = record['local_path']
        key = safe_name(rel)
        if key in keys:
            raise InspectionError('ambiguous artifact manifest path')
        keys.add(key)
        paths.add(rel)
        path = root / rel
        if any(p.is_symlink() for p in (path, *path.parents) if p != root):
            raise InspectionError('artifact path contains a symlink')
        if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise InspectionError('missing pinned artifact; follow docs/r0.md acquisition steps')
        size = record['size_bytes']
        if path.stat().st_size != size:
            raise InspectionError('artifact size mismatch; preserve originals and reacquire exact pins')
        with path.open('rb') as stream:
            data = stream.read(size + 1)
        if len(data) != size or digest(data) != record['sha256']:
            raise InspectionError('artifact hash mismatch; preserve originals and reacquire exact pins')
    # A pinned starter must have its exact closure, including no additional files.
    sample = root / 'sample_submission'
    expected = {p for p in paths if p.startswith('sample_submission/')}
    actual = set()
    for path in sample.rglob('*'):
        if path.is_symlink():
            raise InspectionError('starter contains a symlink')
        if not path.is_dir():
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise InspectionError('starter file set differs from pinned reference closure')
    return {'artifact_pins': 'PASS', 'artifacts': len(records),
            'starter_files': len(expected), 'model_execution': 'NOT RUN'}
