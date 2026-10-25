"""Read the frozen v25 serving wheel on free CPU; never acquire a model."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

from tools import research_comparison as c, cloud_resolver as resolver
from tools.direct_delivery import pull
from tools.linux_runtime import supplied_records
from tools.cloud_seal import seal


def acquire(output):
    from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest
    output = Path(output); output.mkdir(mode=0o700, parents=True)
    row, = [r for r in supplied_records() if r['path'].startswith('vllm-')]
    with tempfile.TemporaryDirectory(prefix='split-cache-') as temporary:
        root = Path(temporary)
        with resolver.kaggle_client() as client:
            request = ApiDownloadDatasetRequest()
            request.owner_slug = 'metric'; request.dataset_slug = 'gemma-4-developer-agent-wheelhouse'
            request.dataset_version_number = 25; request.file_name = row['path']
            response = resolver.retry_read(lambda: client.datasets.dataset_api_client.download_dataset(request))
            source = resolver.source_from_response(response, row)
        manifest = c.encoded({'schema_version': 1, 'phase': 'bootstrap', 'files': [
            {k: row[k] for k in ('path', 'bytes', 'sha256')}]})
        pull(root/'wheel', manifest, {row['path']: source}, c.digest(manifest), 300)
        files = {}
        with zipfile.ZipFile(root/'wheel'/row['path']) as archive:
            for name in ('vllm/engine/arg_utils.py', 'vllm/config/cache.py',
                         'vllm/utils/argparse_utils.py', 'vllm/entrypoints/openai/cli_args.py'):
                target = root / Path(name).name
                target.write_bytes(archive.read(name)); files[name] = target
        report = {'status': 'SOURCE_ACQUIRED', 'wheel': row, 'model_files': 0,
                  'sources': {n: hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()},
                  'cache_runtime_execution': 'NOT_RUN'}
        report['encrypted_sources'] = seal(files, output/'cache-sources.age')
    c._new_output(output/'cache.json', c.encoded(report))
    return report


if __name__ == '__main__':
    print(json.dumps(acquire(sys.argv[1])))
