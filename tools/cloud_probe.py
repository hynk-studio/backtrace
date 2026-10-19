"""Read-only checks of Actions credentials and two frozen private input files.

No Pod mutation, notebook execution, terms acceptance or raw artifact publication.
Only explicit result fields reach stdout; SDK diagnostics and exception text do not.
"""
import contextlib
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
import zipfile

from tools.a100_delivery import manifest
from tools.runpod_control import RunpodAPI


class CredentialFormatError(ValueError):
    """A missing or malformed value, before any network request."""


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
            raise ValueError('unqualified storage host')
        wire = int(response.headers['Content-Length'])
        if response.headers.get('Content-Encoding', 'identity') != 'identity':
            raise ValueError('unexpected HTTP encoding')
        if not 0 < wire <= row['bytes'] + 65536 or row['bytes'] > 1024**2:
            raise ValueError('probe size limit')
        data = response.raw.read(wire + 1)
        if len(data) != wire:
            raise ValueError('incomplete or oversized response')
        encoding = 'raw'
        if data.startswith(b'PK\x03\x04'):
            encoding = 'zip'
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = archive.infolist()
                if (len(members) != 1 or members[0].filename != Path(row['path']).name
                        or members[0].file_size != row['bytes'] or members[0].flag_bits & 1):
                    raise ValueError('unexpected archive members')
                data = archive.read(members[0])
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('frozen input mismatch')
        return {'bytes': len(data), 'sha256': row['sha256'], 'encoding': encoding,
                'wire_bytes': wire, 'storage_host': url.hostname}


def runpod_read():
    pods = RunpodAPI(secret('RUNPOD_API_KEY')).list()
    return {'authenticated': True, 'pod_count': len(pods),
            'backtrace_pod_count': sum(str(p.get('name', '')).startswith('backtrace-a100-') for p in pods),
            'write_permission': 'NOT TESTED; no resource mutation'}


def kaggle_checks():
    from kagglesdk.kaggle_client import KaggleClient
    from kagglesdk.kaggle_env import KaggleEnv
    from kagglesdk.kernels.types.kernels_api_service import ApiDownloadKernelOutputRequest, ApiGetKernelRequest
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
        model = verify_small_response(client.models.model_api_client.download_model_instance_version(request), row)
        yield 'kaggle_model_v2', model

        row = next(r for r in json.loads(manifest('task'))['files'] if r['path'] == 'agent-task.json')
        request = ApiDownloadKernelOutputRequest()
        request.owner_slug = 'hynk1240'
        request.kernel_slug = 'backtrace-r0-selected-inputs'
        request.version_number = 1
        request.file_path = row['path']
        task = verify_small_response(client.kernels.kernels_api_client.download_kernel_output(request), row)
        yield 'kaggle_private_task_v1', task

        request = ApiGetKernelRequest()
        request.user_name = 'hynk1240'
        request.kernel_slug = 'backtrace-pr7-cpu-qualification'
        request.version_label = '3'
        kernel = client.kernels.kernels_api_client.get_kernel(request)
        source = kernel.blob.source.encode()
        yield 'kaggle_retained_notebook_v3', {
            'source_bytes': len(source), 'source_sha256': hashlib.sha256(source).hexdigest(),
            'is_private': kernel.metadata.is_private, 'execution': 'NOT RUN'}


def failure(error):
    response = getattr(error, 'response', None)
    status = getattr(response, 'status_code', getattr(error, 'http_status', None))
    return {'status': 'FAIL', 'error_type': type(error).__name__,
            'http_status': status if type(status) is int else None}


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
