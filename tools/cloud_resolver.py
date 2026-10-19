"""Owner-only resolution of frozen inputs. Service credentials never enter maps.

Kaggle v2/v25/v1 and PyPI/PyTorch exact wheel identities are fixed. This module
does not choose package versions, run notebook cells, or create compute.
"""
import contextlib
import functools
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

from tools import a100_delivery as frozen
from tools.cloud_inventory import response_json
from tools.cloud_probe import secret, retained_literal, notebook_output_url
from tools.direct_delivery import validate_url, sources_for
from tools.linux_runtime import supplied_records

NOTEBOOK_SHA256 = '1541b75bcff02705539b85d29ee810df0ee25ae01cbb9fd01ec36a10f11b8dc6'


class ResolutionError(ValueError):
    def __init__(self, row, error):
        super().__init__('frozen input source resolution failed')
        self.input_path = row['path']
        self.error_type = type(error).__name__
        self.http_status = getattr(getattr(error, 'response', None), 'status_code', None)


@contextlib.contextmanager
def kaggle_client():
    from kagglesdk.kaggle_client import KaggleClient
    from kagglesdk.kaggle_env import KaggleEnv
    with KaggleClient(env=KaggleEnv.PROD, api_token=secret('KAGGLE_API_TOKEN'), verbose=False) as client:
        # This SDK version otherwise has an unbounded requests.Session.send.
        session = client.http_client()._session
        session.headers['Accept-Encoding'] = 'identity'
        session.send = functools.partial(session.send, timeout=30)
        yield client


def get_source(client):
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
    request = ApiGetKernelRequest()
    request.user_name = 'hynk1240'
    request.kernel_slug = 'backtrace-pr7-cpu-qualification'
    request.version_label = 'v3'
    response = client.kernels.kernels_api_client.get_kernel(request)
    source = response.blob.source.encode()
    if response.metadata.is_private is not True or hashlib.sha256(source).hexdigest() != NOTEBOOK_SHA256:
        raise ValueError('saved private notebook identity changed')
    return source


def restore_cpu_inputs(source, repository, wheels, task, official):
    """Write only pinned reference inputs, never notebook code or shell scripts."""
    from tools.artifacts import verify_artifacts
    from tools.r0 import expected_candidate, inspect_candidate
    from tools.compile_probe import FROZEN_SHA256
    repository, wheels = Path(repository), Path(wheels)
    task, official = Path(task), Path(official)
    records = json.loads((repository / 'docs/source-manifest.json').read_text())['official_artifacts']
    root = repository / '.local/official'
    root.mkdir(mode=0o700, parents=True)
    for row in records:
        rel = row['local_path']
        if rel.startswith('wheels/'):
            data = (wheels / Path(rel).name).read_bytes()
        else:
            data = (official / rel).read_bytes()
        if len(data) != row['size_bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('official input differs from frozen manifest')
        target = root / rel
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
    verify_artifacts(root)
    candidate = repository / '.local/r0-clean/build-a.zip'
    candidate.parent.mkdir(mode=0o700, parents=True)
    data = (task / 'r0-clean.zip').read_bytes()
    if hashlib.sha256(data).hexdigest() != FROZEN_SHA256:
        raise ValueError('frozen candidate changed')
    with candidate.open('xb') as stream:
        stream.write(data)
    inspect_candidate(candidate, expected_candidate(root))
    retained = repository / '.local/smoke/no-custom-ar/one_task.py'
    retained.parent.mkdir(mode=0o700, parents=True)
    with retained.open('xb') as stream:
        stream.write(retained_literal(source))
    return {'official_artifacts': len(records), 'candidate_sha256': FROZEN_SHA256,
            'notebook_cells_executed': 0}


def source_from_response(response, row):
    """Inspect wire shape only. Activation still requires every body hash."""
    with response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError('final download response required')
        url = validate_url(response.url)
        wire = int(response.headers['Content-Length'])
        if response.headers.get('Content-Encoding', 'identity') != 'identity':
            raise ValueError('unexpected wire encoding')
        result = {'url': url, 'wire_bytes': wire,
                  'encoding': 'raw' if wire == row['bytes'] else 'single-file-zip'}
        sources_for({'files': [row]}, {row['path']: result})
        return result


def public_source(url, row):
    import requests
    validate_url(url)
    return source_from_response(requests.get(url, stream=True, timeout=30,
        allow_redirects=False, headers={'Accept-Encoding': 'identity'}), row)


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(value for name, value in attrs if name == 'href' and value)


def pypi_source(row):
    import requests
    if row['name'] == 'torch':
        if row['version'] != '2.10.0+cu128':
            raise ValueError('unexpected torch version')
        index = 'https://download.pytorch.org/whl/cu128/torch/'
        with requests.get(index, stream=True, timeout=30, allow_redirects=False) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 1024**2:
                    raise ValueError('torch index size limit')
        parser = Links(); parser.feed(body.decode())
        urls = []
        for href in parser.links:
            parsed = urlsplit(urljoin(index, href))
            if (Path(unquote(parsed.path)).name == row['path']
                    and parsed.fragment == 'sha256=' + row['sha256']):
                urls.append(urlunsplit(parsed._replace(fragment='')))
        if len(urls) != 1:
            raise ValueError('exact torch wheel unavailable')
        return public_source(urls[0], row)
    url = 'https://pypi.org/pypi/' + quote(row['name'], safe='') + '/' + quote(row['version'], safe='') + '/json'
    release = response_json(requests.get(url, timeout=30, stream=True, allow_redirects=False))
    matches = [item for item in release['urls'] if item['filename'] == row['path']
               and item['size'] == row['bytes'] and item['digests']['sha256'] == row['sha256']]
    if len(matches) != 1:
        raise ValueError('exact PyPI wheel unavailable')
    return public_source(matches[0]['url'], row)


def resolve_wheels(client, *, progress=lambda *_: None):
    from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest
    records = json.loads((frozen.ROOT / 'docs/linux-wheel-manifest.json').read_text())
    originals = {row['sha256']: row for row in supplied_records()}
    result = {}
    for index, row in enumerate(records):
        try:
            if row['sha256'] in originals:
                request = ApiDownloadDatasetRequest()
                request.owner_slug = 'metric'
                request.dataset_slug = 'gemma-4-developer-agent-wheelhouse'
                request.dataset_version_number = 25
                request.file_name = originals[row['sha256']]['path']
                response = client.datasets.dataset_api_client.download_dataset(request)
                result[row['path']] = source_from_response(response, row)
            else:
                result[row['path']] = pypi_source(row)
        except Exception as error:
            raise ResolutionError(row, error) from None
        if (index + 1) % 25 == 0:
            progress('resolved_wheels', index + 1)
    sources_for(json.loads(frozen.manifest('wheels')), result)
    return result


def resolve_task(client):
    result = {}
    for row in json.loads(frozen.manifest('task'))['files']:
        url = notebook_output_url(client, 'backtrace-r0-selected-inputs', 'v1', row['path'])
        result[row['path']] = public_source(url, row)
    return result


def resolve_model(client):
    from kagglesdk.models.types.model_api_service import ApiDownloadModelInstanceVersionRequest, ModelFramework
    result = {}
    for row in json.loads(frozen.manifest('model'))['files']:
        request = ApiDownloadModelInstanceVersionRequest()
        request.owner_slug = 'google'; request.model_slug = 'gemma-4'
        request.framework = ModelFramework.MODEL_FRAMEWORK_OTHER
        request.instance_slug = 'gemma-4-31b-it-qat-w4a16-ct'
        request.version_number = 2; request.path = row['path']
        response = client.models.model_api_client.download_model_instance_version(request)
        result[row['path']] = source_from_response(response, row)
    return result


def official_manifest():
    records = json.loads((frozen.ROOT / 'docs/source-manifest.json').read_text())['official_artifacts']
    return (json.dumps({'schema_version': 1, 'phase': 'bootstrap', 'files': [
        {'path': row['local_path'], 'bytes': row['size_bytes'], 'sha256': row['sha256']}
        for row in records if not row['local_path'].startswith('wheels/')]}, sort_keys=True) + '\n').encode()


def resolve_official(client):
    from kagglesdk.competitions.types.competition_api_service import ApiDownloadDataFileRequest
    result = {}
    for row in json.loads(official_manifest())['files']:
        try:
            request = ApiDownloadDataFileRequest()
            request.competition_name = 'gemma-4-developer-agent'
            request.file_name = row['path']
            response = client.competitions.competition_api_client.download_data_file(request)
            # The competition API returns an HttpRedirect JSON object, unlike
            # the model/dataset FileDownload response. Only its signed URL travels.
            result[row['path']] = public_source(response.url, row)
        except Exception as error:
            raise ResolutionError(row, error) from None
    return result
