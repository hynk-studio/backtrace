"""Read-only acquisition for the frozen pilot; no task or model execution.

First acquisition records exact bytes, never invents an upstream revision. Agent
projections contain only the five official task inputs. Raw sources and errors
are kept private and only encrypted evidence leaves the disposable CPU host.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import logging
from pathlib import Path
import tempfile
import time
import zipfile

from tools import research_comparison as c, research_cpu, cloud_resolver as resolver
from tools.direct_delivery import NoRedirect, validate_url
import urllib.request

ROOT = c.ROOT
FIELDS = ('instance_id', 'repo', 'base_commit', 'problem_statement', 'hints_text')
MAX_ASSET = 128 * 1024**2


def projections(data, selection, protocol):
    actual = c.select_tasks(data, protocol)
    if actual != selection:
        raise ValueError('source does not reproduce committed selection')
    records = {r['instance_id']: r for r in (c.parse(line) for line in data.splitlines() if line.strip())}
    result = {}
    for selected in selection['primary']:
        record = records[selected['instance_id']]
        task = {key: record.get(key, '') for key in FIELDS}
        if task['hints_text'] is None:
            task['hints_text'] = ''
        if any(not isinstance(value, str) for value in task.values()):
            raise ValueError('invalid agent task input')
        if any(task[k] != selected[k] for k in ('instance_id', 'repo', 'base_commit')):
            raise ValueError('task identity changed')
        result[task['instance_id']] = task
    return result


def asset_paths(task):
    if (not c.ID.fullmatch(task['instance_id']) or not c.REPO.fullmatch(task['repo'])
            or not c.SHA1.fullmatch(task['base_commit'])):
        raise ValueError('invalid selected identity')
    stem = task['repo'].split('/')[1] + '_' + task['base_commit']
    return ('snapshots/' + task['instance_id'] + '.tgz',
            'graphs/' + stem + '.json', 'embeddings/' + stem + '.npz')


def download_new(client, name, destination):
    """Bounded first acquisition. Hashes become a lock, not a prior hash check."""
    from kagglesdk.competitions.types.competition_api_service import ApiDownloadDataFileRequest
    request = ApiDownloadDataFileRequest()
    request.competition_name = 'gemma-4-developer-agent'
    request.file_name = name
    response = resolver.retry_read(lambda: client.competitions.competition_api_client.download_data_file(request))
    url = validate_url(response.url)
    opener = urllib.request.build_opener(NoRedirect())
    deadline = time.monotonic() + 120
    with opener.open(urllib.request.Request(url, headers={'Accept-Encoding': 'identity'}), timeout=30) as stream:
        if stream.status != 200 or stream.headers.get('Content-Encoding', 'identity') != 'identity':
            raise ValueError('unexpected asset response')
        size = int(stream.headers['Content-Length'])
        if not 0 < size <= MAX_ASSET:
            raise ValueError('asset size bound exceeded')
        wire = bytearray()
        while len(wire) < size:
            if time.monotonic() >= deadline:
                raise TimeoutError('asset download deadline')
            chunk = stream.read(min(1024**2, size - len(wire)))
            if not chunk:
                raise ValueError('truncated asset')
            wire.extend(chunk)
        if stream.read(1):
            raise ValueError('asset size changed')
    data = bytes(wire)
    # NPZ is itself a ZIP. Only unwrap a one-file transport bearing the
    # requested path, never a content archive such as a numpy node dictionary.
    if data.startswith(b'PK\x03\x04'):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) == 1 and members[0].filename in (name, Path(name).name):
                entry = members[0]
                if entry.is_dir() or entry.file_size > MAX_ASSET or entry.flag_bits & 1:
                    raise ValueError('invalid transport archive')
                data = archive.read(entry)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    c._new_output(destination, data)
    return {'path': name, 'bytes': len(data), 'sha256': c.digest(data),
            'source': 'https://www.kaggle.com/competitions/gemma-4-developer-agent/data',
            'acquired_at_utc': datetime.now(timezone.utc).isoformat(),
            'upstream_version': 'UNSPECIFIED; exact acquired bytes pinned'}


def official_wheels(client, root):
    from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest
    from tools.linux_runtime import supplied_records
    from tools.direct_delivery import pull
    wanted = {r['sha256'] for r in c.parse((ROOT / 'docs/source-manifest.json').read_bytes())['official_artifacts']
              if r['local_path'].startswith('wheels/')}
    rows = [r for r in supplied_records() if r['sha256'] in wanted]
    if len(rows) != 5:
        raise ValueError('five pinned official wheels required')
    sources = {}
    manifest = c.encoded({'schema_version': 1, 'phase': 'bootstrap', 'files': [
        {k: row[k] for k in ('path', 'bytes', 'sha256')} for row in rows]})
    for row in rows:
        request = ApiDownloadDatasetRequest()
        request.owner_slug = 'metric'; request.dataset_slug = 'gemma-4-developer-agent-wheelhouse'
        request.dataset_version_number = 25; request.file_name = row['path']
        response = resolver.retry_read(lambda: client.datasets.dataset_api_client.download_dataset(request))
        sources[row['path']] = resolver.source_from_response(response, row)
    return pull(root, manifest, sources, c.digest(manifest), 180)


def prepare(output):
    from tools.cloud_seal import seal
    output = Path(output).absolute(); output.mkdir(mode=0o700)
    protocol = c.load_protocol()
    selection = c.parse((ROOT / 'docs/research-selection-20261024.json').read_bytes())
    c.validate_selection(selection, protocol)
    report = {'schema_version': 1, 'kind': 'MATCHED_PILOT_ASSET_ACQUISITION',
              'protocol_sha256': c.digest(c.encoded(protocol)), 'stages': {}, 'tasks': [],
              'model_execution': 'NOT RUN', 'provider_operations': 0, 'compute_authorization': 'NONE'}
    import os
    report.update(source_sha=os.environ.get('GITHUB_SHA'), run_id=os.environ.get('GITHUB_RUN_ID'))
    previous = logging.root.manager.disable
    try:
        with tempfile.TemporaryDirectory(prefix='research-assets-', dir=ROOT / '.local') as temp:
            root = Path(temp)
            logging.disable(logging.CRITICAL)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with resolver.kaggle_client() as client:
                    for kind in ('metadata', 'baseline'):
                        report['stages'][kind] = research_cpu.acquire(kind, client, root / kind)
                    report['phase'] = 'agent_projection'
                    tasks = projections((root / 'metadata/tasks.jsonl').read_bytes(), selection, protocol)
                    report['phase'] = 'candidate_assembly'
                    report['assembly'] = c.build(root / 'baseline/r0-clean.zip', root / 'candidates', protocol)
                    report['phase'] = 'official_wheels'
                    report['stages']['official_wheels'] = official_wheels(client, root / 'wheels')
                    report['phase'] = 'retained_driver'
                    c._new_output(root / 'retained-driver.py', resolver.retained_literal(resolver.get_source(client)))
                    report['phase'] = 'task_assets'
                    for identifier, task in tasks.items():
                        path = root / 'agents' / identifier / 'agent-task.json'
                        path.parent.mkdir(mode=0o700, parents=True)
                        c._new_output(path, c.encoded(task))
                        row = {k: task[k] for k in ('instance_id', 'repo', 'base_commit')}
                        row.update(agent_task_sha256=c.digest(path.read_bytes()), assets=[], failures=[])
                        report['tasks'].append(row)
                        for name in asset_paths(task):
                            try:
                                row['assets'].append(download_new(client, name, root / 'assets' / name))
                            except Exception as error:
                                row['failures'].append({'path': name, 'error_type': type(error).__name__,
                                                        'http_status': getattr(error, 'code', None)})
                        row['status'] = 'ACQUIRED' if not row['failures'] else 'INCOMPLETE'
            report['status'] = 'PASS' if all(t['status'] == 'ACQUIRED' for t in report['tasks']) else 'INCOMPLETE'
            # Retain artifacts for owner-side exact-byte inspection/reuse, including
            # failures, without publishing raw tasks or signed download URLs.
            files = {str(p.relative_to(root)): p for p in root.rglob('*') if p.is_file()}
            report['sealed'] = seal(files, output / 'inputs.age')
    except Exception as error:
        report['status'] = 'FAILED'; report['error_type'] = type(error).__name__
        if str(error) in ('source does not reproduce committed selection', 'invalid agent task input',
                          'task identity changed', 'five pinned official wheels required'):
            report['reason'] = str(error)
    finally:
        logging.disable(previous)
    report['temporary_inputs_removed'] = not any((ROOT / '.local').glob('research-assets-*'))
    c._new_output(output / 'assets.json', c.encoded(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = prepare(args.output)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
