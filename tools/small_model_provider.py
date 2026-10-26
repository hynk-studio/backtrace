"""Authenticated read-only provider inventory for the new small-model scope.

No allocation, deletion, account changes, secret export or live model operation.
Inventory/price observations never establish Pod capabilities or reserve stock.
"""
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import time

from tools.cloud_offer import query
from tools import runpod_control as control


class ReadOnlyAPI(control.RunpodAPI):
    def request(self, method, path, body=None, missing=False):
        if method != 'GET' or body is not None:
            raise ValueError('this deployment permits provider reads only')
        return super().request(method, path, missing=missing)


def money(value):
    if isinstance(value, bool):
        raise ValueError('money must be a finite nonnegative number')
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError('money must be a finite nonnegative number')
    return result


def account_snapshot(read=query, now=time.time):
    value = read('query { myself { clientBalance currentSpendPerHr isAutoPayEnabled } }')['myself']
    if type(value['isAutoPayEnabled']) is not bool:
        raise ValueError('account setting unknown')
    return {'observed_at': control.utc(now()), 'credit_balance_usd': str(money(value['clientBalance'])),
            'spend_per_hour_usd': str(money(value['currentSpendPerHr'])),
            'auto_pay': value['isAutoPayEnabled']}


def inventory(api):
    rows = api.list()
    # IDs/names/environments of unrelated resources need not be published.
    return {'observed_at': control.utc(time.time()), 'pod_count': len(rows),
            'complete_paginated_list': True, 'resource_mutations': 0}


def quote(gpu, region, read=query):
    control.validate_region(region)
    result = read('''query($gpu: GpuTypeFilter, $price: GpuLowestPriceInput) {
      gpuTypes(input:$gpu) { id memoryInGb secureCloud lowestPrice(input:$price) {
        uninterruptablePrice minMemory minVcpu stockStatus supportPublicIp availableGpuCounts
      } } }''', {'gpu': {'id': gpu['id']}, 'price': {'gpuCount': 1, 'dataCenterId': region,
          'secureCloud': True, 'minMemoryInGb': 32, 'minVcpuCount': 8, 'minDisk': 100,
          'minCudaVersion': '12.8', 'supportPublicIp': True}})['gpuTypes']
    if len(result) != 1 or result[0]['id'] != gpu['id'] or result[0]['memoryInGb'] != gpu['memoryInGb']:
        raise ValueError('filtered quote identity changed')
    p = result[0]['lowestPrice']
    row = {'observed_at': control.utc(time.time()), 'gpu': gpu['id'], 'region': region,
           'reported_gpu_gb': gpu['memoryInGb'], 'exact_quote': p, 'stock_eligible': False}
    if not p:
        return row
    hourly = money(p['uninterruptablePrice'])
    counts, ip = p.get('availableGpuCounts'), p.get('supportPublicIp')
    row['stock_eligible'] = (result[0]['secureCloud'] is True
        and str(p['stockStatus']).lower() in ('low', 'medium', 'high')
        and p['minMemory'] >= 32 and p['minVcpu'] >= 8
        and (ip is None or ip is True)
        and (counts is None or isinstance(counts, list) and any(type(x) is int and x == 1 for x in counts)))
    row.update(compute_usd_per_hour=str(hourly),
        proposed_3000s_compute_usd=str(hourly*Decimal(3000)/3600),
        compute_within_proposal=hourly*Decimal(3000)/3600 <= Decimal('.90'),
        storage_projection_usd_per_hour='0.015',
        proposed_3000s_compute_and_storage_usd=str((hourly+Decimal('.015'))*Decimal(3000)/3600))
    return row


def inspect(read=query, api=None):
    result = {'schema': 'small-model-provider-read-v1', 'status': 'INCOMPLETE',
              'account': account_snapshot(read), 'allocation_requests': 0, 'settings_changed': False,
              'quote_constraints': {'gpu_count': 1, 'secure_cloud': True, 'minimum_gpu_gb': 24,
                  'minimum_ram_gb': 32, 'minimum_vcpu': 8, 'container_disk_gb': 100,
                  'volume_gb': 0, 'minimum_cuda': '12.8', 'public_ip': True},
              'storage_basis': 'Published USD0.10/GB/month; USD0.015/hour for 100GB rounds up a 28-day month. Projection, not a provider quote; taxes/other charges not established.',
              'maximum_pairs': 32, 'offers': [], 'excluded_or_unqueried_pairs': 0,
              'hardware_capabilities': 'NOT_OBSERVED', 'launch_enabled': False}
    catalog = read('query { gpuTypes { id memoryInGb secureCloud securePrice } }')['gpuTypes']
    centers = read('query { dataCenters { id gpuAvailability { gpuTypeId available stockStatus } } }')['dataCenters']
    if len(catalog) > 256 or len(centers) > 128:
        raise ValueError('unbounded provider catalog')
    choices = [g for g in catalog if g['secureCloud'] is True and 24 <= g['memoryInGb'] <= 80
               and re.search(r'(RTX 3090|RTX 4090|RTX A5000|RTX A6000|A40|L4|L40|A100)', g['id'])]
    choices.sort(key=lambda g: (money(g['securePrice']) if g.get('securePrice') is not None else Decimal('999'), g['id']))
    choices = choices[:8]
    pairs = [(g, c, r) for g in choices for c in centers for r in c.get('gpuAvailability') or []
             if r['gpuTypeId'] == g['id']]
    pairs.sort(key=lambda p: (not p[1]['id'].startswith('EU-'), not p[2]['available'],
                            money(p[0]['securePrice']) if p[0].get('securePrice') is not None else Decimal('999'),
                            p[0]['id'], p[1]['id']))
    if len({(g['id'], c['id']) for g,c,r in pairs}) != len(pairs):
        raise ValueError('duplicate regional quote identity')
    result['candidate_gpus'] = choices
    result['excluded_or_unqueried_pairs'] = max(0, len(pairs)-32)
    for g, c, r in pairs[:32]:
        row = quote(g, c['id'], read)
        row['broad_stock'] = {'available': r['available'], 'status': r['stockStatus']}
        row['stock_eligible'] = row['stock_eligible'] and r['available'] is True
        result['offers'].append(row)
    if api is not None:
        result['inventory'] = inventory(api)
    a = result['account']
    result['proposal_funded'] = money(a['credit_balance_usd']) >= Decimal('1.50')
    result['account_idle'] = money(a['spend_per_hour_usd']) == 0 and a['auto_pay'] is False
    result['status'] = 'PASS_READ_ONLY'
    return result


if __name__ == '__main__':
    import sys
    out = Path(sys.argv[1]); out.parent.mkdir(parents=True, exist_ok=True)
    result = {'source_sha': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID'),
              'allocation_requests': 0, 'resource_mutations': 0}
    try:
        result['observation'] = inspect(api=ReadOnlyAPI(os.environ['RUNPOD_API_KEY'].strip()))
        result['status'] = 'PASS'
    except Exception as error:
        result.update(status='FAIL', error_type=type(error).__name__)
    out.write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
