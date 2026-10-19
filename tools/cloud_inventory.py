"""Read-only launch inventory discovery. No create, mutation or model execution."""
import contextlib
import io
import json
import logging
import re
import time
from urllib.parse import quote
from pathlib import PurePosixPath

from tools.a100_delivery import manifest
from tools.cloud_probe import failure, secret
from tools.direct_delivery import validate_url
from tools.runpod_control import GPU


def response_json(response):
    with response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > 1024**2:
                raise ValueError('bounded JSON response required')
        return json.loads(data)


def provider_inventory():
    import requests
    headers = {'Authorization': 'Bearer ' + secret('RUNPOD_API_KEY')}
    url = 'https://api.runpod.io/v2/catalog/gpus/' + quote(GPU, safe='')
    gpu = response_json(requests.get(url, headers=headers, timeout=30, stream=True,
        allow_redirects=False, params={'include': 'AVAILABILITY', 'product': 'POD',
                                      'count': 1, 'cloud': 'SECURE', 'minCudaVersion': '12.8'}))
    if gpu['id'] != GPU or gpu['memory'] != 80 or gpu['secure'] is not True:
        raise ValueError('catalog GPU identity mismatch')
    result = {k: gpu.get(k) for k in ('id', 'memory', 'availability', 'price', 'cudaVersions')}
    result['data_centers'] = [{'id': row['id'], 'availability': row['availability']}
                              for row in gpu.get('dataCenters', [])]
    yield 'catalog', result
    centers = response_json(requests.get('https://api.runpod.io/v2/catalog/datacenters',
        headers=headers, timeout=30, stream=True, allow_redirects=False,
        params={'include': 'GPU_AVAILABILITY'}))
    yield 'regional_catalog', {'gpu': GPU, 'data_centers': [
        {'id': center['id'], 'availability': row['availability']}
        for center in centers['dataCenters'] for row in center.get('gpuAvailability', [])
        if row['id'] == GPU]}

    def query(source, variables=None):
        value = response_json(requests.post('https://api.runpod.io/graphql', headers=headers,
            json={'query': source, 'variables': variables or {}}, timeout=30, stream=True,
            allow_redirects=False))
        if value.get('errors'):
            raise ValueError('provider GraphQL read rejected')
        return value['data']

    # These read fields come from runpodctl's official GetUser implementation.
    account = query('query { myself { __typename clientBalance currentSpendPerHr } }')['myself']
    yield 'wallet', {k: str(account[k]) for k in ('clientBalance', 'currentSpendPerHr')}
    # Schema discovery returned HTTP 400. Do not retry it or infer auto-pay.
    yield 'billing_settings', {'auto_pay': 'NOT VERIFIED BY API', 'settings_changed': False}


def saved_inventory():
    from kagglesdk.kaggle_client import KaggleClient
    from kagglesdk.kaggle_env import KaggleEnv
    from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest
    wheels = json.loads(manifest('wheels'))['files']
    expected = {'prepay-20261018/wheels/' + row['path']: 'wheels' for row in wheels}
    expected.update({'prepay-20261018/transport/dropbear-DROPBEAR_2026.94/' + name: 'transport'
                     for name in ('dropbear', 'dropbearkey')})
    found, seen, token, listed, archives = {}, set(), '', 0, []
    with KaggleClient(env=KaggleEnv.PROD, api_token=secret('KAGGLE_API_TOKEN'), verbose=False) as client:
        for page in range(100):
            request = ApiListKernelSessionOutputRequest()
            request.user_name = 'hynk1240'
            request.kernel_slug = 'backtrace-pr7-cpu-qualification'
            request.version_label = 'v3'
            request.page_size = 100
            request.page_token = token
            response = client.kernels.kernels_api_client.list_kernel_session_output(request)
            for row in response.files:
                listed += 1
                name = PurePosixPath(row.file_name).name
                if name.endswith(('.zip', '.tar.gz', '.tgz')) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', name):
                    archives.append(name)
                if row.file_name in expected:
                    if row.file_name in found:
                        raise ValueError('duplicate expected saved output')
                    validate_url(row.url)
                    found[row.file_name] = row.url
            token = response.next_page_token
            if not token or set(found) == set(expected):
                break
            if token in seen:
                raise ValueError('saved output pagination cycle')
            seen.add(token)
        else:
            raise ValueError('saved output pagination limit')
    return {'version': 3, 'listed_count': listed, 'complete_listing': not bool(token),
            'expected_wheels': len(wheels),
            'saved_wheels': sum(expected[n] == 'wheels' for n in found),
            'expected_transport_binaries': 2,
            'saved_transport_binaries': sum(expected[n] == 'transport' for n in found),
            'available_archive_names': sorted(set(archives)),
            'downloaded_bytes': 0, 'saved_output_urls': 'NOT PUBLISHED'}


def main():
    logging.disable(logging.CRITICAL)
    report = {'observed_at_epoch': int(time.time()), 'gpu_allocations': 0, 'checks': {}}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            for name, result in provider_inventory():
                report['checks'][name] = {'status': 'PASS', **result}
        except Exception as error:
            report['checks']['provider_inventory'] = failure(error)
        try:
            report['checks']['saved_assets'] = {'status': 'PASS', **saved_inventory()}
        except Exception as error:
            report['checks']['saved_assets'] = failure(error)
    print(json.dumps(report, sort_keys=True))
    return 0 if all(r['status'] == 'PASS' for r in report['checks'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
