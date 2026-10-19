"""Read-only fresh account, regional stock and hardware-price qualification.

Fields and inputs are from https://graphql-spec.runpod.io/ (2026-10-19).
No introspection, account setting changes, payment or resource creation.
"""
import time

from tools.cloud_inventory import response_json
from tools.cloud_probe import secret
from tools import runpod_control as control, cloud_state as state


def query(source, variables=None):
    import requests
    value = response_json(requests.post('https://api.runpod.io/graphql',
        headers={'Authorization': 'Bearer ' + secret('RUNPOD_API_KEY')},
        json={'query': source, 'variables': variables or {}}, timeout=30,
        stream=True, allow_redirects=False))
    if value.get('errors') or not isinstance(value.get('data'), dict):
        raise ValueError('documented provider read rejected')
    return value['data']


def inspect_offer(*, read=query, now=time.time):
    value = read('''query {
      myself { clientBalance currentSpendPerHr isAutoPayEnabled }
      dataCenters { id gpuAvailability { gpuTypeId available stockStatus } }
    }''')
    account = value['myself']
    report = {'observed_at': control.utc(now()), 'account': {
        'credit_balance': str(account['clientBalance']),
        'current_spend_per_hour': str(account['currentSpendPerHr']),
        'auto_pay': account['isAutoPayEnabled']}, 'regions': [], 'settings_changed': False,
        'allocation_requests': 0, 'offer': None}
    if (type(account['isAutoPayEnabled']) is not bool
            or account['isAutoPayEnabled'] is not False
            or control.money(str(account['currentSpendPerHr'])) != 0):
        report['status'] = 'ACCOUNT_NOT_QUALIFIED'
        return report
    candidates = []
    for center in value['dataCenters']:
        for row in center.get('gpuAvailability') or []:
            if row['gpuTypeId'] == control.GPU:
                control.validate_region(center['id'])
                entry = {'id': center['id'], 'available': row['available'], 'stock': row['stockStatus']}
                report['regions'].append(entry)
                # Also inspect exact hardware quotes for unavailable regions.
                # This validates the complete read path before a paid claim and
                # preserves discrepancies instead of treating a broad stock
                # summary as proof of an allocatable machine.
                candidates.append(center['id'])
    if len(candidates) > 32 or len(candidates) != len(set(candidates)):
        raise ValueError('ambiguous regional inventory')
    # The previous region has no cost/performance preference; a current matching
    # offer anywhere is allowed by the owner's equivalent-region instruction.
    for region in sorted(candidates):
        result = read('''query($gpu: GpuTypeFilter, $price: GpuLowestPriceInput) {
          gpuTypes(input: $gpu) { id memoryInGb secureCloud
            lowestPrice(input: $price) {
              uninterruptablePrice minMemory minVcpu stockStatus supportPublicIp availableGpuCounts
            }
          }
        }''', {'gpu': {'id': control.GPU}, 'price': {'gpuCount': 1, 'dataCenterId': region,
              'secureCloud': True, 'minMemoryInGb': 117, 'minVcpuCount': 8, 'minDisk': 100,
              'minCudaVersion': '12.8', 'supportPublicIp': True}})['gpuTypes']
        if len(result) != 1 or result[0]['id'] != control.GPU or result[0]['memoryInGb'] != 80:
            raise ValueError('GPU quote identity mismatch')
        gpu = result[0]; price = gpu['lowestPrice']
        regional = next(r for r in report['regions'] if r['id'] == region)
        regional['exact_quote'] = price
        if (gpu['secureCloud'] is not True or not price
                or regional['available'] is not True
                or str(price['stockStatus']).lower() not in ('low', 'medium', 'high')
                or price['supportPublicIp'] is not True or 1 not in (price['availableGpuCounts'] or [])):
            continue
        offer = {'observed_at': report['observed_at'], 'region': region, 'region_policy': control.REGION_POLICY,
            'gpu': control.GPU, 'gpu_count': 1, 'cloud': 'SECURE', 'image': control.BASE,
            'container_disk_gb': 100, 'volume_gb': 0, 'network_volume': None, 'interruptible': False,
            'stock_available': True, 'auto_pay': False, 'authenticated': True,
            'vcpus': price['minVcpu'], 'ram_gb': price['minMemory'],
            'compute_per_hour': str(price['uninterruptablePrice']), 'storage_per_hour': '0.014',
            'tax_rate': '0', 'other_total': '0', 'credit_balance': str(account['clientBalance'])}
        # Storage bound retains the observed USD 0.014/h for 100GB temporary
        # disk; every live Pod's total cost must still pass resource_matches.
        report['costs'] = state.cloud_costs(offer, now())
        report.update(status='QUALIFIED', offer=offer)
        return report
    report['status'] = 'NO_QUALIFIED_REGION'
    return report
