"""Acquire five pinned harness wheels for private source audit, with no execution.

This is a free read-only input acquisition, not runtime qualification. The only
published output is encrypted to the existing owner result recipient.
"""
import hashlib
import json
from pathlib import Path

from tools import cloud_resolver as resolver, cloud_seal
from tools.a100_delivery import ROOT
from tools.direct_delivery import pull


def main():
    from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest
    root = ROOT / '.local/audit-sources'
    root.mkdir(mode=0o700, parents=True)
    wanted = {'swegemma', 'adk-submission', 'adk-eval-core', 'google-adk', 'google-genai'}
    rows = [r for r in json.loads((ROOT / 'docs/linux-wheel-manifest.json').read_text())
            if r['name'] in wanted]
    if len(rows) != len(wanted):
        raise ValueError('exact five pinned harness wheels required')
    sources = {}
    with resolver.kaggle_client() as client:
        for row in rows:
            request = ApiDownloadDatasetRequest()
            request.owner_slug = 'metric'
            request.dataset_slug = 'gemma-4-developer-agent-wheelhouse'
            request.dataset_version_number = 25
            request.file_name = row['path']
            sources[row['path']] = resolver.source_from_response(
                client.datasets.dataset_api_client.download_dataset(request), row)
        # Retain the original public evaluation record only in private CPU
        # evidence. It is never added to the agent's selected input stream.
        from kagglesdk.competitions.types.competition_api_service import ApiDownloadDataFileRequest
        spec = next(r for r in json.loads((ROOT / 'docs/source-manifest.json').read_text())[
            'smoke_preallocation']['artifacts'] if r.get('source_path') == 'tasks.jsonl')
        task_row = {'path': 'tasks.jsonl', 'bytes': spec['size_bytes'], 'sha256': spec['sha256']}
        request = ApiDownloadDataFileRequest()
        request.competition_name = 'gemma-4-developer-agent'
        request.file_name = 'tasks.jsonl'
        response = client.competitions.competition_api_client.download_data_file(request)
        evaluator_source = resolver.public_source(response.url, task_row)
    data = json.dumps({'schema_version': 1, 'phase': 'bootstrap', 'files': [
        {k: row[k] for k in ('path', 'bytes', 'sha256')} for row in rows]}).encode()
    pull(root / 'wheels', data, sources, hashlib.sha256(data).hexdigest(), 120)
    files = {'wheels/' + row['path']: root / 'wheels' / row['path'] for row in rows}
    evaluator_manifest = json.dumps({'schema_version': 1, 'phase': 'bootstrap', 'files': [task_row]}).encode()
    pull(root / 'evaluator', evaluator_manifest, {'tasks.jsonl': evaluator_source},
         hashlib.sha256(evaluator_manifest).hexdigest(), 60)
    files['evaluator/tasks.jsonl'] = root / 'evaluator/tasks.jsonl'
    receipt = cloud_seal.seal(files, ROOT / 'evidence/audit-sources.age', limit=16 * 1024**2)
    print(json.dumps({'status': 'PASS', 'purpose': 'private primary-source audit only',
                      'wheels_verified': len(rows), 'package_code_executed': False,
                      'gpu_allocations': 0, 'private_evidence': receipt}, sort_keys=True))


if __name__ == '__main__':
    main()
