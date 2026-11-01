"""Fixed-window, read-only audit lookup after the rejected one-case create."""
from pathlib import Path
import hashlib,json,os,re,urllib.error,urllib.parse,urllib.request
from tools.runpod_control import NoRedirect
NAME='backtrace-small-minimum-f39b93e3220c4b66b095dc97e588209d'
key=os.environ['RUNPOD_API_KEY'].strip()
opener=urllib.request.build_opener(NoRedirect())
result={'source_sha':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],
 'allocation_requests':0,'resource_mutations':0,'method':'GET','queries':[]}
for search in (NAME,'pod'):
 params={'startTime':'2026-11-01T10:00:00Z','endTime':'2026-11-01T10:02:00Z','search':search,'limit':100}
 query={'parameters':params,'pages':[]};result['queries'].append(query)
 seen=set()
 for page in range(3):
  request=urllib.request.Request('https://api.runpod.io/v2/audit-logs?'+urllib.parse.urlencode(params),
   headers={'Authorization':'Bearer '+key,'Accept':'application/json'},method='GET')
  try:
   with opener.open(request,timeout=20) as response:status=response.status;raw=response.read(1024**2+1)
  except urllib.error.HTTPError as error:
   query['pages'].append({'http_status':error.code});break
  if len(raw)>1024**2:raise ValueError('audit response exceeds bound')
  value=json.loads(raw);logs=value['auditLogs'];rows=[]
  for row in logs:
   if row.get('resourceType')!='pod':continue
   text=str(row.get('value',''));lower=text.lower()
   try:payload=json.loads(text)
   except (ValueError,TypeError):payload=None
   categories=[name for name,pattern in [
    ('CAPACITY_TEXT',r'no (?:available )?(?:gpu|instance|capacity)|out of stock|insufficient capacity|could not find.*(?:gpu|machine)'),
    ('CREDIT_TEXT',r'insufficient (?:credit|balance|fund)|billing|payment'),
    ('CUDA_TEXT',r'cuda'),('ACCESS_TEXT',r'permission|forbidden|access denied'),
    ('VALIDATION_TEXT',r'invalid|validation|unsupported')]
    if re.search(pattern,lower)]
   safe={k:v for k,v in (payload.items() if isinstance(payload,dict) else [])
    if k in ('status','code','errorCode') and
      (type(v) is int or isinstance(v,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',v))}
   rows.append({k:row.get(k) for k in ('resourceType','resourceId','action','timestamp')}|{
    'exact_attempt_name_present':NAME in text,'value_bytes':len(text.encode()),
    'value_sha256':hashlib.sha256(text.encode()).hexdigest(),
    'value_top_level_keys':sorted(payload) if isinstance(payload,dict) else [],
    'safe_fields':safe,'text_categories_not_diagnosis':categories})
  pagination=value['pagination']
  query['pages'].append({'http_status':status,'response_bytes':len(raw),
   'response_sha256':hashlib.sha256(raw).hexdigest(),'returned_entries':len(logs),
   'pod_entries':rows,'has_next_page':pagination['hasNextPage']})
  if not pagination['hasNextPage']:break
  cursor=pagination.get('nextCursor')
  if not isinstance(cursor,str) or not cursor or cursor in seen:raise ValueError('invalid audit cursor')
  seen.add(cursor);params=dict(params,cursor=cursor)
result['status']='READ_ONLY_AUDIT_LOOKUP_COMPLETE'
path=Path('evidence/onecase-audit.json');path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
print(json.dumps(result,sort_keys=True))
