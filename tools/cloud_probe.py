"""Read-only checks of Actions credentials and two frozen private input files.

No Pod mutation, notebook execution, terms acceptance or raw artifact publication.
Only explicit result fields reach stdout; SDK diagnostics and exception text do not.
"""
import contextlib
import ast
import base64
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
import zipfile
import zlib

from tools.a100_delivery import manifest
from tools.runpod_control import RunpodAPI


class CredentialFormatError(ValueError):
    """A missing or malformed value, before any network request."""


class InputCheckError(ValueError):
    """Only locally fixed labels may be included in the public result."""


def secret(name):
    # GitHub's multiline editor can retain the final clipboard newline.
    value = os.environ.get(name, '').strip()
    if len(value) < 16 or any(c.isspace() for c in value):
        raise CredentialFormatError('missing or malformed credential')
    return value


def verify_small_response(response, row):
    """Bound the wire body, decode a single expected ZIP member, then hash it."""
    with response:
        response.raise_for_status()
        url = urlsplit(response.url)
        if (url.scheme != 'https' or url.hostname != 'storage.googleapis.com'
                or url.username or url.password or url.fragment or url.port not in (None, 443)):
            raise InputCheckError('unqualified storage host')
        wire = int(response.headers['Content-Length'])
        if response.headers.get('Content-Encoding', 'identity') != 'identity':
            raise InputCheckError('unexpected HTTP encoding')
        if not 0 < wire <= row['bytes'] + 65536 or row['bytes'] > 1024**2:
            raise InputCheckError('probe size limit')
        # The SDK pre-reads application/json bodies. iter_content handles both
        # buffered and streaming responses; raw.read would see an empty body.
        data = bytearray()
        for chunk in response.iter_content(chunk_size=min(wire + 1, 32768)):
            data.extend(chunk)
            if len(data) > wire:
                break
        data = bytes(data)
        if len(data) != wire:
            raise InputCheckError('incomplete or oversized response')
        encoding = 'raw'
        if data.startswith(b'PK\x03\x04'):
            encoding = 'zip'
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = archive.infolist()
                if (len(members) != 1 or members[0].filename != Path(row['path']).name
                        or members[0].file_size != row['bytes'] or members[0].flag_bits & 1):
                    raise InputCheckError('unexpected archive members')
                data = archive.read(members[0])
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise InputCheckError('frozen input mismatch')
        return {'bytes': len(data), 'sha256': row['sha256'], 'encoding': encoding,
                'wire_bytes': wire, 'storage_host': url.hostname}


def retained_literal(source):
    """Find only the exact retained driver bytes; never run notebook cells."""
    from tools.a100_task import DRIVER_SHA256
    if len(source) > 8 * 1024**2:
        raise ValueError('notebook source size limit')
    notebook = json.loads(source)
    if not isinstance(notebook.get('cells'), list) or len(notebook['cells']) > 200:
        raise ValueError('notebook cell count limit')
    for cell in notebook['cells']:
        if cell.get('cell_type') != 'code':
            continue
        try:
            tree = ast.parse(''.join(cell['source']))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                data = node.value.encode()
                if len(data) == 33461 and hashlib.sha256(data).hexdigest() == DRIVER_SHA256:
                    return data
                if (len(data) == 837896 and hashlib.sha256(data).hexdigest()
                        == 'ebd011f3e9acc7890b94b7fb1ed8acc03a19f62435de866eb70cda52152e09e8'):
                    decoder = zlib.decompressobj()
                    raw = decoder.decompress(base64.b64decode(data, validate=True), 2 * 1024**2)
                    if (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
                            or hashlib.sha256(raw).hexdigest()
                            != 'f35ec577d4657cb0ce45dbca58fea9a7361418b097db64e3568a26afb7c9ee7d'):
                        raise ValueError('retained packed archive mismatch')
                    data = base64.b64decode(json.loads(raw)['.local/smoke/no-custom-ar/one_task.py'],
                                            validate=True)
                    if len(data) == 33461 and hashlib.sha256(data).hexdigest() == DRIVER_SHA256:
                        return data
    raise InputCheckError('retained literal unavailable')


def notebook_output_url(client, slug, version, path):
    from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest
    seen, matches = set(), []
    token = ''
    for _ in range(10):
        request = ApiListKernelSessionOutputRequest()
        request.user_name = 'hynk1240'
        request.kernel_slug = slug
        request.version_label = version
        request.page_size = 100
        request.page_token = token
        result = client.kernels.kernels_api_client.list_kernel_session_output(request)
        matches.extend(item.url for item in result.files
                       if item.file_name == path or item.file_name.endswith('/' + path))
        token = result.next_page_token
        if not token:
            if len(matches) != 1:
                raise InputCheckError('expected output missing or ambiguous')
            from tools.direct_delivery import validate_url
            validate_url(matches[0])
            return matches[0]
        if token in seen:
            break
        seen.add(token)
    raise InputCheckError('output listing limit')


def runpod_read():
    pods = RunpodAPI(secret('RUNPOD_API_KEY')).list()
    return {'authenticated': True, 'pod_count': len(pods),
            'backtrace_pod_count': sum(str(p.get('name', '')).startswith('backtrace-a100-') for p in pods),
            'write_permission': 'NOT TESTED; no resource mutation'}


def kaggle_checks():
    from kagglesdk.kaggle_client import KaggleClient
    from kagglesdk.kaggle_env import KaggleEnv
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
    from kagglesdk.models.types.model_api_service import ApiDownloadModelInstanceVersionRequest, ModelFramework

    with KaggleClient(env=KaggleEnv.PROD, api_token=secret('KAGGLE_API_TOKEN'), verbose=False) as client:
        row = next(r for r in json.loads(manifest('model'))['files'] if r['path'] == 'config.json')
        request = ApiDownloadModelInstanceVersionRequest()
        request.owner_slug = 'google'
        request.model_slug = 'gemma-4'
        request.framework = ModelFramework.MODEL_FRAMEWORK_OTHER
        request.instance_slug = 'gemma-4-31b-it-qat-w4a16-ct'
        request.version_number = 2
        request.path = row['path']
        try:
            model = verify_small_response(client.models.model_api_client.download_model_instance_version(request), row)
            yield 'kaggle_model_v2', model
        except Exception as error:
            yield 'kaggle_model_v2', failure(error)

        row = next(r for r in json.loads(manifest('task'))['files'] if r['path'] == 'agent-task.json')
        try:
            import requests
            url = notebook_output_url(client, 'backtrace-r0-selected-inputs', 'v1', row['path'])
            # Signed object URL only: no service credential is sent here.
            response = requests.get(url, stream=True, timeout=30, allow_redirects=False,
                                    headers={'Accept-Encoding': 'identity'})
            task = verify_small_response(response, row)
            yield 'kaggle_private_task_v1', task
        except Exception as error:
            yield 'kaggle_private_task_v1', failure(error)

        request = ApiGetKernelRequest()
        request.user_name = 'hynk1240'
        request.kernel_slug = 'backtrace-pr7-cpu-qualification'
        # The official CLI formats numeric labels as v<N>; bare 3 returns 404.
        request.version_label = 'v3'
        try:
            kernel = client.kernels.kernels_api_client.get_kernel(request)
            source = kernel.blob.source.encode()
            driver = retained_literal(source)
            yield 'kaggle_retained_notebook_v3', {
                'source_bytes': len(source), 'source_sha256': hashlib.sha256(source).hexdigest(),
                'is_private': kernel.metadata.is_private, 'execution': 'NOT RUN',
                'retained_driver_bytes': len(driver), 'retained_driver_sha256': hashlib.sha256(driver).hexdigest()}
        except Exception as error:
            yield 'kaggle_retained_notebook_v3', failure(error)


def failure(error):
    response = getattr(error, 'response', None)
    status = getattr(response, 'status_code', getattr(error, 'http_status', None))
    result = {'status': 'FAIL', 'error_type': type(error).__name__,
              'http_status': status if type(status) is int else None}
    reasons = {'unqualified storage host', 'unexpected HTTP encoding', 'probe size limit',
               'incomplete or oversized response', 'unexpected archive members', 'frozen input mismatch',
               'retained literal unavailable', 'expected output missing or ambiguous', 'output listing limit'}
    if isinstance(error, InputCheckError) and str(error) in reasons:
        result['reason'] = str(error)
    return result


def main():
    logging.disable(logging.CRITICAL)
    report = {'schema_version': 1, 'observed_at_epoch': int(time.time()),
              'gpu_allocations': 0, 'checks': {}}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            report['checks']['runpod_read'] = {'status': 'PASS', **runpod_read()}
        except Exception as error:
            report['checks']['runpod_read'] = failure(error)
        try:
            for name, result in kaggle_checks():
                report['checks'][name] = {'status': 'PASS', **result}
        except Exception as error:
            report['checks']['kaggle_access'] = failure(error)
    print(json.dumps(report, sort_keys=True))
    return 0 if len(report['checks']) == 4 and all(r['status'] == 'PASS' for r in report['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
