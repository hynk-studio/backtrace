"""Post-deletion assembly around the repository's unchanged per-case scorers."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

REPOSITORY=Path('/workspace/scratch/565575038e73/backtrace-matched')
sys.path.insert(0,str(REPOSITORY))
from tools import small_model_matched_data as data
from tools import abductive_scoring as static, temporal_scoring as temporal
from tools import small_model_lifecycle as life


def scores(records,development):
    expected=[(arm,row['id']) for arm in ('B1','B2','S') for row in development]
    synthetic=[r for r in records if not r['id'].startswith('augnes-screen-')]
    if [(r['arm'],r['id']) for r in synthetic]!=expected:
        raise ValueError('all original ordered synthetic assignments required')
    by_id={r['id']:r for r in development};arms={}
    for arm in ('B1','B2','S'):
        cases=[]
        for row in (r for r in synthetic if r['arm']==arm):
            if row['status'] not in ('OK','INVALID_OUTPUT','TIMEOUT','WORKER_ERROR','INTERRUPTED','NOT_RUN'):
                raise ValueError('unknown collector status')
            original=by_id[row['id']];payload=original['input']
            scorer=temporal if payload['task']=='temporal_revision' else static
            received=row['status'] in ('OK','INVALID_OUTPUT')
            response=row['answer_text'] if row['status']=='OK' else None
            scored=scorer.score_case(payload,response,missing=not received)
            cases.append(dict(scored,id=row['id'],family=original['family'],episode=original['episode'],
                task=original['task'],collector_status=row['status']))
        tasks={}
        for task in data.TASKS:
            chosen=[r for r in cases if r['task']==task]
            tasks[task]={'assigned':len(chosen),'responses':dict(Counter(r['response_status'] for r in chosen)),
                'metrics':temporal.aggregate(chosen)}
        arms[arm]={'assigned':len(cases),'responses':dict(Counter(r['response_status'] for r in cases)),
            'tasks':tasks,'metrics':temporal.aggregate(cases),'cases':cases}
    comparisons={}
    for baseline in ('B1','B2'):
        group={}
        for task in data.TASKS:
            left=arms['S']['tasks'][task]['metrics'];right=arms[baseline]['tasks'][task]['metrics']
            if set(left)!=set(right):raise ValueError('mismatched assigned metric domains')
            group[task]={name:{'specialist_family_mean':left[name]['family_mean'],
                'baseline_family_mean':right[name]['family_mean'],
                'specialist_minus_baseline':left[name]['family_mean']-right[name]['family_mean'],
                'by_family_difference':{f:left[name]['by_family'][f]-right[name]['by_family'][f] for f in left[name]['by_family']}}
                for name in left}
        comparisons['S_minus_'+baseline]=group
    return {'schema':'matched_candidate_existing_case_scores_v1','arms':arms,'comparisons':comparisons,
        'interpretation':'Lower losses are better. Original invalid/missing penalties are retained. Compare S against B1 as well as B2.',
        'trajectory_metrics':'NOT_ASSIGNED: each revision episode contributes only its final snapshot; no duplicate-invariance or update-direction claim.',
        'confidence_intervals':'NOT_COMPUTED_ONE_SEED_EIGHT_DEVELOPMENT_FAMILIES',
        'capability_claim':'CANDIDATE_DESCRIPTIVE_ONLY'}


def controls():
    development=data.development_inputs();oracle=[];missing=[];invalid=[]
    for arm in ('B1','B2','S'):
        for row in development:
            translated,ref=data.reference(row['input']);answer=static.optimal_response(translated,ref)
            identity={'model':'E2B','arm':arm,'id':row['id']}
            oracle.append(dict(identity,status='OK',answer_text=json.dumps(answer)))
            missing.append(dict(identity,status='NOT_RUN'))
            invalid.append(dict(identity,status='INVALID_OUTPUT',answer_text='{}'))
    a,b,c=(scores(r,development) for r in (oracle,missing,invalid))
    assert all(v==0 for arm in a['arms'].values() for row in arm['cases'] for v in row['losses'].values())
    assert all(v==1 for result in (b,c) for arm in result['arms'].values() for row in arm['cases'] for v in row['losses'].values())
    assert b['arms']['B1']['responses']=={'MISSING':96} and c['arms']['B1']['responses']=={'INVALID':96}
    return {'status':'PASS_EXISTING_CASE_SCORER_ASSEMBLY_CONTROLS','actual_model':False,
        'cases_per_arm':96,'oracle_loss':0,'invalid_and_missing_loss':1,
        'trajectory_metrics':'NOT_ASSIGNED','reserved_family_references':'NOT_GENERATED'}


def evaluate(directory):
    directory=Path(directory)
    claim=(directory/'state/claim.json').read_bytes();claim_hash=life.digest(claim)
    for role in ('owner-cleanup','watch-cleanup'):
        proof=json.loads((directory/'state'/(role+'.json')).read_bytes())
        if proof['status']!='DELETED' or proof['absence_reads']!=2 or proof['claim_sha256']!=claim_hash:
            raise ValueError('both independent exact-claim deletion proofs required before scoring')
    remote=directory/'owner/minimum-owner/remote'
    collection=json.loads((remote/'all-assignment-outcomes.json').read_bytes())
    schedule=json.loads((remote/'input-schedule.json').read_bytes())['requests']
    development=data.development_inputs()
    expected={r['id']:r for r in development}
    for row in schedule:
        if row['id'] in expected and row['messages']!=expected[row['id']]['messages']:
            raise ValueError('development message identity changed')
    if collection['assigned']!=348 or len(collection['records'])!=348 or len(schedule)!=348:
        raise ValueError('full348 assignment denominator required')
    if [(r['model'],r['arm'],r['id']) for r in collection['records']]!=[(r['model'],r['arm'],r['id']) for r in schedule]:
        raise ValueError('original assignment identity changed')
    result=scores(collection['records'],development)
    result['input_sha256']={'collection':life.digest((remote/'all-assignment-outcomes.json').read_bytes()),
        'schedule':life.digest((remote/'input-schedule.json').read_bytes())}
    destination=directory/'synthetic-existing-scorer-results.json'
    with destination.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    return {'status':result['capability_claim'],'responses':{a:r['responses'] for a,r in result['arms'].items()}}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',nargs='?');args=parser.parse_args()
    print(json.dumps(evaluate(args.directory) if args.directory else controls()))
