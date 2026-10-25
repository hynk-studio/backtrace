"""Fresh read-only account/stock report, separate from any old paid policy."""
from decimal import Decimal
import json
import os
from pathlib import Path
import time

from tools.cloud_offer import query
from tools import runpod_control as control


def inspect(*,read=query,now=time.time):
    value=read('query { myself { clientBalance currentSpendPerHr isAutoPayEnabled } '
               'dataCenters { id gpuAvailability { gpuTypeId available stockStatus } } }')
    account=value['myself'];balance=control.money(str(account['clientBalance']))
    report={'observed_at':control.utc(now()),'account':{'credit_balance':str(balance),
        'current_spend_per_hour':str(account['currentSpendPerHr']),'auto_pay':account['isAutoPayEnabled']},
        'regions':[],'offers':[],'allocation_requests':0,'settings_changed':False}
    centers=[(center,row) for center in value['dataCenters'] for row in center.get('gpuAvailability') or []
             if row['gpuTypeId']==control.GPU]
    if len(centers)>32 or len({center['id'] for center,row in centers})!=len(centers):raise ValueError('ambiguous regions')
    for center,row in sorted(centers,key=lambda pair:(not pair[0]['id'].startswith('EU-'),pair[0]['id'])):
        region=control.validate_region(center['id'])
        response=read('''query($gpu: GpuTypeFilter, $price: GpuLowestPriceInput) {
          gpuTypes(input:$gpu) { id memoryInGb secureCloud lowestPrice(input:$price) {
            uninterruptablePrice minMemory minVcpu stockStatus supportPublicIp availableGpuCounts
          } } }''',{'gpu':{'id':control.GPU},'price':{'gpuCount':1,'dataCenterId':region,
            'secureCloud':True,'minMemoryInGb':117,'minVcpuCount':8,'minDisk':100,
            'minCudaVersion':'12.8','supportPublicIp':True}})['gpuTypes']
        if len(response)!=1 or response[0]['id']!=control.GPU or response[0]['memoryInGb']!=80:
            raise ValueError('quote identity changed')
        gpu=response[0];price=gpu['lowestPrice']
        report['regions'].append({'id':region,'available':row['available'],'summary_stock':row['stockStatus'],'exact_quote':price})
        if (not price or gpu['secureCloud'] is not True or row['available'] is not True
                or str(price['stockStatus']).lower() not in ('low','medium','high')
                or price.get('supportPublicIp') is False
                or (price.get('availableGpuCounts') is not None and 1 not in price['availableGpuCounts'])):continue
        offer={'observed_at':report['observed_at'],'region':region,'gpu':control.GPU,
            'gpu_count':1,'cloud':'SECURE','image':control.BASE,'container_disk_gb':100,
            'volume_gb':0,'network_volume':None,'interruptible':False,'stock_available':True,
            'auto_pay':account['isAutoPayEnabled'],'authenticated':True,'vcpus':price['minVcpu'],
            'ram_gb':price['minMemory'],'compute_per_hour':str(price['uninterruptablePrice']),
            'storage_per_hour':'0.014','tax_rate':'0','other_total':'0','credit_balance':str(balance)}
        hourly=control.money(offer['compute_per_hour'])+Decimal('.014')
        report['offers'].append({'offer':offer,'projected_three_hour_spend':str(hourly*3),
            'historical_usd8_headroom':str(balance-Decimal(2)),
            'credit_after_three_hours':str(balance-hourly*3),
            'pricing_basis':'fresh compute quote + retained observed 100GB disk ceiling USD0.014/h; live Pod cost must not exceed this bound'})
    report['status']='READ_ONLY_COMPLETE'
    report['account_idle']=control.money(report['account']['current_spend_per_hour'])==0 and account['isAutoPayEnabled'] is False
    return report


if __name__=='__main__':
    import sys
    destination=Path(sys.argv[1]);destination.parent.mkdir(parents=True,exist_ok=True)
    result={'source_sha':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],
            'allocation_requests':0,'settings_changed':False}
    try:
        result['availability']=inspect()
        result['pods']=[{k:p.get(k) for k in ('id','name','status')} for p in control.RunpodAPI(os.environ['RUNPOD_API_KEY'].strip()).list()]
        result['status']='PASS'
    except Exception as error:result.update(status='UNAVAILABLE',error_type=type(error).__name__)
    destination.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))
