"""Verify retained offline regression evidence, including the superseded failure."""
from pathlib import Path
import hashlib,json,re

root=Path(__file__).resolve().parent
repo=Path.cwd()
read=lambda p:json.loads(Path(p).read_bytes())
verified=[]
for run_id,conclusion,count,source in (
    (41297302373,'failure',757,'cf95cd117ffe364618be7750e8eeb8faef24f22e'),
    (41298060217,'success',775,'ea463b6e332d95639b59118ab21e95e4ebb234b9')):
    directory=root.parent/('provider-error-run-'+str(run_id))
    run=read(directory/'run.json');jobs=read(directory/'jobs.json')['jobs']
    assert run['id']==run_id and run['head_sha']==source and run['run_attempt']==1
    assert run['status']=='completed' and run['conclusion']==conclusion
    assert run['path']=='.github/workflows/provider-error-evidence.yml'
    assert len(jobs)==1 and jobs[0]['conclusion']==conclusion
    receipt=read(directory/'archive/archive-provenance.json')
    assert hashlib.sha256((directory/'offline-job.log').read_bytes()).hexdigest()==receipt['job_log_sha256']
    for member in receipt['members']:
        raw=(directory/'archive'/member['path']).read_bytes()
        assert len(raw)==member['bytes'] and hashlib.sha256(raw).hexdigest()==member['sha256']
    tests=(directory/'archive/tests.log').read_text()
    assert re.search(r'^Ran '+str(count)+r' tests in [\d.]+s$',tests,re.M)
    if conclusion=='success':
        assert '\nOK\n' in tests and '\nFAILED ' not in tests
        preflight=read(directory/'archive/preflight.json')
        assert preflight['local_tooling']=='READY' and preflight['python']=='3.12.14'
        assert preflight['official_validator']=='NOT RUN'
    else:
        assert '\nFAILED (errors=25)\n' in tests
        assert not (directory/'archive/preflight.json').exists()
    verified.append({'run_id':run_id,'conclusion':conclusion,'tests':count,
                     'source_sha':source,'archive_members':len(receipt['members'])})

provenance=read(root/'source-provenance.json')
assert provenance['source_sha']==verified[-1]['source_sha']
for path,sha in provenance['files'].items():
    raw=(root/'source'/path).read_bytes()
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==sha
    if not path.startswith('docs/'):
        assert (repo/path).read_bytes()==raw,path
assert provenance['files']['tools/runpod_control.py']=='cf2dfe38b54b20a611d78c18c3a3e73d1b23644b'
assert 'secrets.' not in (root/'source/.github/workflows/provider-error-evidence.yml').read_text()
focused=(root/'focused-tests.log').read_bytes()
assert b'Ran 64 tests in ' in focused and b'\nOK\n' in focused
summary={'status':'PASS_OFFLINE_PROVIDER_EVIDENCE_FIX','source_sha':provenance['source_sha'],
         'runs':verified,'source_files_verified':len(provenance['files']),
         'focused_tests':64,'focused_log_sha256':hashlib.sha256(focused).hexdigest(),
         'actual_provider_requests':0,'actual_model_result':'NOT_RUN',
         'limitation':'Offline tests do not recover the discarded HTTP400 body or establish reasoning fit.'}
(root/'verification.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
print(json.dumps(summary,sort_keys=True))
