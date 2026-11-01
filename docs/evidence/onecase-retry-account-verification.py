"""Check read-only retry stock observations without rewriting prior evidence."""
from pathlib import Path
from decimal import Decimal
import hashlib,json,re
from tools import small_model_onecase_scope as scope

root=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_bytes())
checks=[]
for directory in sorted(root.glob('onecase-retry-account-run-*')):
    run=read(directory/'run.json');account=read(directory/'account-quotes.json')
    assert run['status']=='completed' and run['conclusion']=='success' and run['run_attempt']==1
    assert str(account['run_id'])==str(run['id']) and account['source_sha']==run['head_sha']
    assert account['status']=='PASS' and account['allocation_requests']==account['resource_mutations']==0
    raw=(directory/'quote-job.log').read_bytes();proof=read(directory/'provenance.json')
    assert hashlib.sha256(raw).hexdigest()==proof['job_log_sha256']
    stdout=[]
    for line in raw.decode('utf-8-sig').splitlines():
        line=re.sub(r'^\d{4}-\d\d-\d\dT\S+\s+','',line)
        if line.startswith('{'):
            try:stdout.append(json.loads(line))
            except ValueError:pass
    assert stdout.count(account)==1
    obs=account['observation']
    assert obs['status']=='PASS_READ_ONLY' and obs['inventory']['complete_paginated_list']
    assert obs['inventory']['pod_count']==0 and obs['account']['spend_per_hour_usd']=='0'
    assert obs['account']['auto_pay'] is False
    # Reproduce admission at this historical observation's own completed time;
    # this is not a claim that an old quote remains fresh at verification time.
    observed_at=scope.previous.minimum.control.timestamp(obs['inventory']['observed_at'])
    try:
        with scope.configured():offer=scope.previous.minimum.choose(obs,observed_at)
        admission={'status':'ADMISSIBLE_AT_OBSERVATION','gpu':offer['gpu'],
                   'region':offer['region'],'maximum_projection_usd':offer['costs']['maximum_projection']}
    except ValueError as error:
        admission={'status':'NO_ADMISSIBLE_OFFER','reason':str(error)}
    if (directory/'admission.json').exists():
        previous=read(directory/'admission.json')
        assert previous.get('status','ADMISSIBLE_AT_OBSERVATION')==admission['status']
    checks.append({'run_id':run['id'],'source_sha':run['head_sha'],
        'account_observed_at':obs['account']['observed_at'],
        'inventory_observed_at':obs['inventory']['observed_at'],
        'credit_balance_usd':obs['account']['credit_balance_usd'],
        'remaining_continuation_budget_usd':str(Decimal('2.30')-(Decimal('2.9060441339')-Decimal(obs['account']['credit_balance_usd']))),
        'large_available_offers':[{'gpu':x['gpu'],'region':x['region'],
            'maximum_projection_usd':x['proposed_3000s_compute_and_storage_usd']}
            for x in obs['offers'] if x['reported_gpu_gb']>=40 and x['stock_eligible']],
        'admission':admission})
assert len(checks)>=2
summary={'status':'PASS_RETRY_READ_ONLY_EVIDENCE','observations':checks,
         'resource_mutations':0,'allocation_requests':0,
         'limit':'Historical observations of queried routes; stock is not reserved and can change.'}
(root/'onecase-retry-account-verification.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
print(json.dumps({'status':summary['status'],'observations':len(checks),
                 'latest':checks[-1]},sort_keys=True))
