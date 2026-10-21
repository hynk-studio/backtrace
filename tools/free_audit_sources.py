"""Acquire five pinned harness wheels for private source audit, with no execution.

This is a free read-only input acquisition, not runtime qualification. The only
published output is encrypted to the existing owner result recipient.
"""
import hashlib
import json
from pathlib import Path
import time

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
    data = json.dumps({'schema_version': 1, 'phase': 'bootstrap', 'files': [
        {k: row[k] for k in ('path', 'bytes', 'sha256')} for row in rows]}).encode()
    pull(root / 'wheels', data, sources, hashlib.sha256(data).hexdigest(), 120)
    files = {'wheels/' + row['path']: root / 'wheels' / row['path'] for row in rows}
    receipt = cloud_seal.seal(files, ROOT / 'evidence/audit-sources.age', limit=16 * 1024**2)
    print(json.dumps({'status': 'PASS', 'purpose': 'private primary-source audit only',
                      'wheels_verified': len(rows), 'package_code_executed': False,
                      'gpu_allocations': 0, 'private_evidence': receipt}, sort_keys=True))


if __name__ == '__main__':
    main()
