"""Post-deletion descriptive screening checks; never repairs or judges causality."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def strict(text):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('duplicate JSON key')
            d[k]=v
        return d
    def constant(value):raise ValueError('nonfinite JSON number')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=constant)


def inspect(record,case,rubric):
    result={'id':case['id'],'family':case['family'],'collector_status':record['status'],
            'strict_json_object':False,'explicit_contract_checks_pass':False,
            'semantic_quality':'REQUIRES_SOURCE_GROUNDED_REVIEW','issues':[]}
    if record['status']!='OK':result['issues'].append('collector_'+record['status'])
    try:answer=strict(record.get('answer_text',''))
    except (ValueError,TypeError):
        result['issues'].append('not_strict_json');return result
    if not isinstance(answer,dict):
        result['issues'].append('not_an_object');return result
    result['strict_json_object']=True
    fields={'decision','cause_status','evidence','next_action','avoid','candidates'}
    if set(answer)!=fields:result['issues'].append('contract_fields')
    if answer.get('decision') not in {'DIAGNOSE','LOCAL_FIX','PROCEED','NO_CHANGE','STOP_AND_RETAIN','ESCALATE'}:
        result['issues'].append('decision_enum')
    if answer.get('cause_status') not in {'ESTABLISHED','HYPOTHESIS','UNKNOWN','NOT_APPLICABLE'}:
        result['issues'].append('cause_status_enum')
    ids={r['id'] for r in case['facts']}
    def references(value):
        return isinstance(value,list) and all(isinstance(x,str) and x in ids for x in value)
    if not references(answer.get('evidence')):result['issues'].append('evidence_references')
    if not isinstance(answer.get('next_action'),str) or not answer['next_action'].strip():
        result['issues'].append('next_action')
    if not isinstance(answer.get('avoid'),list) or not all(isinstance(x,str) for x in answer['avoid']):
        result['issues'].append('avoid_list')
    candidates=answer.get('candidates')
    if not isinstance(candidates,list) or len(candidates)>3:result['issues'].append('candidate_bound')
    else:
        required={'hypothesis','support_fact_ids','conflicting_fact_ids','missing_assumptions','disconfirming_check'}
        for i,c in enumerate(candidates):
            if not isinstance(c,dict) or set(c)!=required:
                result['issues'].append(f'candidate_{i}_fields');continue
            if not references(c['support_fact_ids']) or not references(c['conflicting_fact_ids']):
                result['issues'].append(f'candidate_{i}_references')
            if not isinstance(c['hypothesis'],str) or not c['hypothesis'].strip():
                result['issues'].append(f'candidate_{i}_hypothesis')
            # The frozen prose contract did not fix the last two value types.
            # Their meaning must be reviewed, not retroactively constrained.
    result.update(explicit_contract_checks_pass=not result['issues'],decision=answer.get('decision'),
        cause_status=answer.get('cause_status'),candidate_count=len(candidates) if isinstance(candidates,list) else None,
        decision_in_retrospective_acceptable_set=answer.get('decision') in rubric['acceptable_decisions'])
    return result


def review(packet,rubric,collection):
    expected=[c['id'] for c in packet['cases']]
    if (len(expected)!=20 or len(set(expected))!=20
            or [r['id'] for r in collection['records']]!=expected
            or any(r['model']!='E2B' or r['arm']!='B1' for r in collection['records'])
            or collection.get('training') is not False):
        raise ValueError('original twenty untrained assignments required, including missing outputs')
    rows=[inspect(r,c,rubric['cases'][c['id']]) for r,c in zip(collection['records'],packet['cases'])]
    return {'schema':'augnes_screening_descriptive_checks_v1','assigned':20,
        'author_defined_families':len({c['family'] for c in packet['cases']}),
        'collector_coverage':dict(Counter(r['collector_status'] for r in rows)),
        'strict_json_objects':sum(r['strict_json_object'] for r in rows),
        'explicit_contract_checks_pass':sum(r['explicit_contract_checks_pass'] for r in rows),
        'rows':rows,'limitations':packet['limitations']+[
            'Reference IDs verify existence only, not whether the cited fact supports the claim.',
            'An acceptable decision enum alone is not correct reasoning or useful added value.',
            'This report does not repair fences, omitted fields or malformed responses.',
            'No aggregate semantic accuracy, effect size or workflow benefit is inferred.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('packet','rubric','collection','output'):p.add_argument(name,type=Path)
    a=p.parse_args();inputs={k:getattr(a,k).read_bytes() for k in ('packet','rubric','collection')}
    result=review(*(strict(inputs[k]) for k in ('packet','rubric','collection')))
    result['input_sha256']={k:hashlib.sha256(v).hexdigest() for k,v in inputs.items()}
    with a.output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')


if __name__=='__main__':main()
