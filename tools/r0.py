"""Build only the authorized six-file R0-clean derivative of the pinned starter."""
import io
import json
import os
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path

try:
    from .artifacts import verify_artifacts
    from .backtrace import InspectionError, MANIFEST, MAX_ARCHIVE, ROOT, digest, inspect_archive
except ImportError:
    from artifacts import verify_artifacts
    from backtrace import InspectionError, MANIFEST, MAX_ARCHIVE, ROOT, digest, inspect_archive

RETAINED = ('agent.yaml', 'configs/sampling.yaml', 'eval_config.yaml',
            'prompts/analyzer.md', 'prompts/system.md', 'sub_agents/code_analyzer.yaml')
REMOVED_LINES = {'agent.yaml': b'adapter: main_lora\n',
                 'sub_agents/code_analyzer.yaml': b'adapter: tool_lora\n'}
EXCLUDED = tuple('adapters/' + name + '/' + file
                 for name in ('main_lora', 'tool_lora')
                 for file in ('adapter_config.json', 'adapter_model.safetensors'))


def expected_candidate(root, records=None):
    """Pin all inputs, then remove exact complete root-level lines without YAML rewriting."""
    root = Path(root)
    if records is None:
        records = json.loads(MANIFEST.read_text())['official_artifacts']
    verify_artifacts(root, records)
    sample_records = {r['local_path'].removeprefix('sample_submission/'): r for r in records
                      if r['local_path'].startswith('sample_submission/')}
    if set(sample_records) != set(RETAINED + EXCLUDED):
        raise InspectionError('R0-clean requires the pinned ten-file reference closure')
    files = {}
    for name in RETAINED:
        record = sample_records[name]
        with (root / 'sample_submission' / name).open('rb') as source:
            data = source.read(record['size_bytes'] + 1)
        if len(data) != record['size_bytes'] or digest(data) != record['sha256']:
            raise InspectionError('starter bytes changed after pin verification')
        if name in REMOVED_LINES:
            lines = data.splitlines(keepends=True)
            if lines.count(REMOVED_LINES[name]) != 1:
                raise InspectionError('expected root-level adapter declaration missing or ambiguous')
            data = b''.join(line for line in lines if line != REMOVED_LINES[name])
        files[name] = data
    return files


def inspect_candidate(archive, expected):
    """Inspect archive membership/content and bind the exact delta to archived bytes."""
    report = inspect_archive(archive, RETAINED)
    with Path(archive).open('rb') as source:
        raw = source.read(MAX_ARCHIVE + 1)
    if len(raw) > MAX_ARCHIVE or digest(raw) != report['sha256']:
        raise InspectionError('candidate changed during inspection')
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        if len(package.infolist()) != len(RETAINED):
            raise InspectionError('candidate must contain exactly six files and no directory entries')
        files = {name: package.read(name) for name in RETAINED}
    if files != expected:
        raise InspectionError('candidate differs from the authorized R0-clean byte delta')
    report.update(variant='R0-clean', exact_delta='PASS', membership='PASS')
    return report, files


def run_official_check(artifacts, archive, python, sha256):
    """No server/evaluator; execute the inspected CPU checks in their isolated venv."""
    environment = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'TMPDIR')}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    # absolute() retains the venv entrypoint; resolve() would bypass its venv symlink.
    command = [str(Path(python).absolute()), str(ROOT / 'tools/official_check.py'),
               str(Path(artifacts).resolve()), '--candidate', str(archive)]
    try:
        result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        raise InspectionError('official CPU check unavailable; use the pinned venv in docs/r0.md') from None
    if result.returncode != 0:
        raise InspectionError('candidate official CPU checks failed; verify the pinned CPU '
                              'environment using docs/r0.md. No archive was published')
    try:
        report = json.loads(result.stdout)
        if (report['official_cpu_checks'] != 'PASS' or report['subject'] != 'R0-clean candidate archive'
                or report['candidate_sha256'] != sha256):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise InspectionError('official CPU receipt does not identify the checked candidate') from None
    return report


def build_candidate(artifacts, destination, official_python, records=None):
    """Check staged bytes before atomically publishing a new, never-overwritten ZIP."""
    artifacts = Path(artifacts)
    destination = Path(destination)
    root, target = artifacts.resolve(), destination.resolve()
    if root == target or root in target.parents or target in root.parents:
        raise InspectionError('output must be separate from the original artifact directory')
    if os.path.lexists(destination):
        raise InspectionError('output already exists; choose a new ZIP path (no overwrite)')
    if not target.parent.is_dir() or target.suffix != '.zip':
        raise InspectionError('output requires an existing separate directory and a .zip filename')
    expected = expected_candidate(artifacts, records)
    # ZIP_STORED avoids zlib/version variability; names/order, epoch and modes are fixed.
    with tempfile.TemporaryDirectory(prefix='.r0-', dir=target.parent) as temporary:
        staged = Path(temporary) / 'candidate.zip'
        with zipfile.ZipFile(staged, 'x', compression=zipfile.ZIP_STORED) as package:
            for name in RETAINED:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = zipfile.ZIP_STORED
                package.writestr(info, expected[name])
        local, _ = inspect_candidate(staged, expected)
        official = run_official_check(artifacts, staged, official_python, local['sha256'])
        # Recheck after the subprocess, before publishing the exact checked bytes.
        final, _ = inspect_candidate(staged, expected)
        if final['sha256'] != local['sha256']:
            raise InspectionError('candidate changed during official CPU checks')
        # Same filesystem, atomic exclusive creation; unlike replace(), never clobbers.
        os.link(staged, target)
    return {'variant': 'R0-clean', 'sha256': local['sha256'], 'files': list(RETAINED),
            'local_inspection': local, 'official_cpu_validation': official,
            'model_execution': 'NOT RUN', 'submission': 'NOT RUN', 'hosted_scoring': 'NOT RUN'}
