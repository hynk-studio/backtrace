"""CPU-only acquisition and conservative ZIP inspection; never execute artifacts."""
import argparse
import hashlib
import json
import re
import stat
import sys
import urllib.request
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'docs' / 'source-manifest.json'
# Local safety ceilings, NOT Kaggle limits. Binary adapters intentionally unsupported.
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_MEMBER = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_ENTRIES = 1000
TEXT_SUFFIXES = {'.md', '.txt', '.yaml', '.yml', '.json', '.py', '.sh'}
BAD_NAME = re.compile(
    r'(^|[/_.-])(credentials?|secrets?|tokens?|cookies?|passwords?|kaggle|'
    r'answers?|labels?|hidden|ground_truth|evaluator|eval_only|'
    r'__pycache__|node_modules|cache|caches|weights|checkpoints?)([/_.-]|$)', re.I)
BAD_CONTENT = re.compile(
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----|'
    r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|'
    r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})|'
    r'["\']?(?:api[_-]?key|access[_-]?token|secret|password|authorization|cookie)["\']?\s*[:=]\s*\S+|'
    r'\b(?:hidden_labels?|ground_truth|reference_answers?|latent_causes?|future_observations?|test_patch)\b',
    re.I)
BLOCKED = ('Official baseline NOT RUN: acquire the competition sample_submission/ and '
           'HARNESS_README.md through authorized Kaggle access; pin their bytes and the '
           'swegemma/adk_submission wheel versions; verify redistribution terms, agent.yaml '
           'schema and official validation before implementing packaging. See '
           'docs/competition-contract.md. No archive was created.')


class InspectionError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    """Conservative portable paths, rejecting aliases rather than normalizing them."""
    if not name or not re.fullmatch(r'[A-Za-z0-9_./-]+', name):
        raise InspectionError('unsafe or nonportable archive path')
    parts = name.rstrip('/').split('/')
    if any(p in ('', '.', '..') or p.startswith('.') for p in parts):
        raise InspectionError('unsafe or hidden archive path')
    if BAD_NAME.search(name):
        raise InspectionError('restricted archive path')
    return '/'.join(parts).casefold()


def inspect_archive(path, allowed):
    """Read only; exact caller allowlist plus local safety checks, never extraction."""
    path = Path(path)
    allowed = set(allowed)
    if not allowed:
        raise InspectionError('provide an explicit --allow path for every expected file')
    for name in allowed:
        safe_name(name)
        if name.endswith('/'):
            raise InspectionError('allowlist must contain files, not directories')
    if path.stat().st_size > MAX_ARCHIVE:
        raise InspectionError('archive exceeds local compressed size ceiling')
    # Read a bounded snapshot so the hash and inspected content identify the same bytes.
    import io
    with path.open('rb') as stream:
        raw = stream.read(MAX_ARCHIVE + 1)
    if len(raw) > MAX_ARCHIVE:
        raise InspectionError('archive exceeds local compressed size ceiling')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.comment:
            raise InspectionError('archive comments require separate review')
        infos = archive.infolist()
        if not infos or len(infos) > MAX_ENTRIES:
            raise InspectionError('empty archive or local entry ceiling exceeded')
        if sum(i.file_size for i in infos) > MAX_TOTAL:
            raise InspectionError('local expanded size ceiling exceeded')
        seen, files, directories, records = set(), set(), set(), []
        for index, info in enumerate(infos):
            if info.comment or info.extra:
                raise InspectionError('member metadata requires separate review')
            name = info.filename
            if info.orig_filename != name:
                raise InspectionError('truncated archive path')
            key = safe_name(name)
            if key in seen:
                raise InspectionError('duplicate or case-alias archive path')
            seen.add(key)
            kind = stat.S_IFMT(info.external_attr >> 16)
            if kind not in (0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG):
                raise InspectionError('symlink or special archive member')
            if info.flag_bits & 1:
                raise InspectionError('encrypted archive member')
            if info.is_dir():
                if info.file_size or not any(a.startswith(name) for a in allowed):
                    raise InspectionError('unexpected directory entry')
                directories.add(key)
                continue
            if name not in allowed:
                raise InspectionError('file absent from explicit allowlist')
            if Path(name).suffix.lower() not in TEXT_SUFFIXES:
                raise InspectionError('binary, nested archive or unsupported file type')
            if info.file_size > MAX_MEMBER:
                raise InspectionError('local member size ceiling exceeded')
            if info.file_size > max(info.compress_size, 1) * 200:
                raise InspectionError('suspicious compression ratio')
            files.add(key)
            with archive.open(info) as member:
                data = member.read(MAX_MEMBER + 1)
            if len(data) != info.file_size or len(data) > MAX_MEMBER:
                raise InspectionError('member length mismatch or ceiling exceeded')
            try:
                content = data.decode('utf-8')
            except UnicodeDecodeError:
                raise InspectionError('non-UTF-8 member') from None
            if any(ord(c) < 32 and c not in '\n\r\t' for c in content):
                raise InspectionError('binary control character in text member')
            if BAD_CONTENT.search(content):
                raise InspectionError('possible credential or evaluator-only content')
            records.append({'member_index': index, 'bytes': len(data), 'sha256': digest(data)})
        if files != {safe_name(a) for a in allowed}:
            raise InspectionError('allowlisted file missing from archive')
        for key in files | directories:
            if any('/'.join(key.split('/')[:i]) in files for i in range(1, len(key.split('/')))):
                raise InspectionError('file/directory path collision')
    return {'level': 'local inspection only', 'sha256': digest(raw), 'members': records,
            'official_validator': 'NOT RUN', 'semantic_review': 'REQUIRED'}


def acquire_notebook(destination):
    """Download only public notebook source; pin decoded UTF-8 bytes, never execute."""
    spec = json.loads(MANIFEST.read_text())['notebook']
    request = urllib.request.Request(spec['acquisition_url'], headers={'User-Agent': 'Backtrace/0.1'})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise InspectionError('notebook response exceeds local size ceiling')
    payload = json.loads(raw)
    if payload['metadata']['currentVersionNumber'] != spec['version']:
        raise InspectionError('notebook version changed; review and repin primary source')
    source = payload['blob'].get('source') or payload['blob']['sourceNullable']
    data = source.encode('utf-8')
    if digest(data) != spec['sha256']:
        raise InspectionError('notebook source hash changed; review and repin primary source')
    if json.loads(source).get('nbformat') != 4:
        raise InspectionError('unexpected notebook format')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as output:
        output.write(data)
    return {'source_url': spec['acquisition_url'], 'version': spec['version'],
            'accessed_at': datetime.now(timezone.utc).isoformat(), 'sha256': digest(data),
            'evidence_level': 'primary text', 'execution': 'NOT RUN'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('preflight', help='check local CPU tooling only')
    inspect = commands.add_parser('inspect', help='inspect an untrusted ZIP without extracting')
    inspect.add_argument('archive', type=Path)
    inspect.add_argument('--allow', action='append', required=True, help='exact expected member path; repeat')
    acquire = commands.add_parser('acquire-notebook', help='acquire pinned public source without execution')
    acquire.add_argument('destination', type=Path)
    commands.add_parser('baseline', help='fail clearly until the official contract is complete')
    args = parser.parse_args(argv)
    try:
        if args.command == 'baseline':
            print(BLOCKED, file=sys.stderr)
            return 2
        if args.command == 'preflight':
            if sys.version_info < (3, 9):
                raise InspectionError('Python 3.9 or newer required')
            result = {'local_tooling': 'READY', 'python': sys.version.split()[0],
                      'dependencies': 'standard library only', 'official_baseline': 'BLOCKED',
                      'official_validator': 'NOT RUN'}
        elif args.command == 'inspect':
            result = inspect_archive(args.archive, args.allow)
        else:
            result = acquire_notebook(args.destination)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except InspectionError as error:
        # InspectionError messages are authored constants, never artifact content.
        print('FAILED: ' + str(error), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile,
            RuntimeError, NotImplementedError, EOFError, zlib.error):
        # No raw errors, paths, response bodies or matched secret values in output.
        print('FAILED: unsafe/unreadable artifact, pin mismatch, or acquisition unavailable. '
              'Review local input and docs/competition-contract.md; no artifact was executed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
