"""Verify read-only account/audit reports against retained machine-readable stdout."""
from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_bytes())
checks=[]
for directory in sorted(root.glob('onecase-account-run-*')):
    run=read(directory/'run.json')
    assert run['status']=='completed' and run['conclusion']=='success' and run['run_attempt']==1
    raw=(directory/'quote-job.log').read_bytes()
    proof=read(next(directory.glob('*provenance.json')))
    assert hashlib.sha256(raw).hexdigest()==proof.get('job_log_sha256',proof.get('log_sha256'))
    stdout=[]
    for line in raw.decode('utf-8-sig').splitlines():
        line=re.sub(r'^\d{4}-\d\d-\d\dT\S+\s+','',line)
        if line.startswith('{'):
            try:stdout.append(json.loads(line))
            except ValueError:pass
    account=read(directory/'account-quotes.json')
    assert stdout.count(account)==1
    assert account['source_sha']==run['head_sha'] and str(account['run_id'])==str(run['id'])
    assert account['resource_mutations']==account['allocation_requests']==0
    obs=account['observation']
    assert obs['inventory']['pod_count']==0 and obs['inventory']['complete_paginated_list']
    assert obs['account']['credit_balance_usd']=='1.1925423895'
    assert obs['account']['spend_per_hour_usd']=='0' and obs['account']['auto_pay'] is False
    audit_queries=0
    if (directory/'audit-lookup.json').exists():
        audit=read(directory/'audit-lookup.json')
        assert stdout.count(audit)==1 and audit['method']=='GET'
        assert audit['source_sha']==run['head_sha'] and str(audit['run_id'])==str(run['id'])
        assert audit['resource_mutations']==audit['allocation_requests']==0
        assert len(audit['queries'])==2
        for query in audit['queries']:
            assert query['parameters']['startTime']=='2026-11-01T10:00:00Z'
            assert query['parameters']['endTime']=='2026-11-01T10:02:00Z'
            assert len(query['pages'])==1
            page=query['pages'][0]
            assert page['http_status']==200 and page['returned_entries']==0
            assert page['has_next_page'] is False and page['pod_entries']==[]
        audit_queries=2
    checks.append({'run_id':run['id'],'source_sha':run['head_sha'],
        'account_observed_at':obs['account']['observed_at'],
        'inventory_observed_at':obs['inventory']['observed_at'],
        'empty_audit_queries':audit_queries})
assert len(checks)==4
summary={'status':'PASS_READ_ONLY_STDOUT_VERIFICATION','runs':checks,
         'allocation_requests':0,'resource_mutations':0,
         'limit':'Empty audit queries do not identify the HTTP400 rejection cause.'}
(root/'onecase-account-verification.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
print(json.dumps(summary,sort_keys=True))
