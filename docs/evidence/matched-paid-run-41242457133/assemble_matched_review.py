"""Retain unblinded notes without editing any response, rubric or original score."""
import argparse,hashlib,json,sys
from collections import Counter
from pathlib import Path

def load(p):return json.loads(p.read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,v):
    with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')

p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('notes',type=Path);a=p.parse_args()
directory=a.directory.resolve();repository=directory.parents[2]
packet_path=repository/'docs/augnes-screening-packets-20261031.json'
rubric_path=repository/'docs/augnes-screening-rubric-20261031.json'
packet=load(packet_path);rubric=load(rubric_path)
raw_path=directory/'owner/minimum-owner/remote/all-assignment-outcomes.json';all_rows=load(raw_path)['records']
raw={(r['arm'],r['id']):r for r in all_rows}
previous_root=repository/'docs/evidence/public-route-paid-run-41236271328'
previous_path=previous_root/'combined-twenty-screening.json';previous=load(previous_path)
previous_review_path=previous_root/'manual-screening-review.json';previous_review=load(previous_review_path)
old={r['id']:r for r in previous['records']};old_reviews={r['id']:r for r in previous_review['rows']}
notes=load(a.notes);ids={r['id'].removeprefix('augnes-screen-') for r in packet['cases']}
if set(notes)!={'B2','S'} or any(set(notes[arm])!=ids for arm in notes):raise ValueError('all40 new notes required')
records=[];repeat=[]
for arm in ('B1','B2','S'):
    for case in packet['cases']:
        row=raw[(arm,case['id'])];answer_sha=sha(row['answer_text'].encode())
        if arm=='B1':
            past=old[case['id']]
            if (row['raw_text']!=past['raw_text'] or row['raw_output_ids']!=past['raw_output_ids']
                    or answer_sha!=old_reviews[row['id']]['answer_sha256']):
                raise ValueError('B1 prior review requires byte-identical original output')
            entry=dict(old_reviews[row['id']],arm=arm,
                review_reuse='Previous unblinded review retained after exact raw-text/token equality; not an independent quality observation.')
            repeat.append({'id':row['id'],'raw_text_and_tokens_identical':True,'answer_sha256':answer_sha})
        else:
            assessments,note,flags=notes[arm][row['id'].removeprefix('augnes-screen-')]
            if len(assessments)!=len(rubric['cases'][row['id']]['criteria']) or any(x not in ('PASS','PARTIAL','FAIL') for x in assessments):
                raise ValueError('three original criterion notes required')
            entry={'arm':arm,'id':row['id'],'criterion_assessments':assessments,'note':note,
                'flags':flags,'collector_status':row['status'],'answer_sha256':answer_sha}
        entry.update(family=case['family'],source=case['source'],frozen_criteria=rubric['cases'][case['id']]['criteria'])
        records.append(entry)
report={'schema':'matched_source_grounded_retrospective_review_v1','reviewer':'assistant, unblinded',
    'reference':'Three frozen rubric criteria in original order. PASS/PARTIAL/FAIL are descriptive judgments, never an aggregate accuracy or adoption score.',
    'assigned':60,'cases_per_arm':20,'author_defined_families':len({r['family'] for r in packet['cases']}),
    'input_sha256':{'packet':sha(packet_path.read_bytes()),'rubric':sha(rubric_path.read_bytes()),
        'collection':sha(raw_path.read_bytes()),'notes':sha(a.notes.read_bytes()),
        'prior_collection':sha(previous_path.read_bytes()),'prior_review':sha(previous_review_path.read_bytes())},
    'rows':records,'B1_exact_prior_response_repetitions':repeat,
    'limitations':['Retrospective authored packets, unblinded review and17author-defined families do not establish independent prospective workflow benefit.',
        'The historical main-model flow and a new additional main-model review were not run.',
        'No output was repaired; malformed visible text can be discussed without turning it into a valid answer.',
        'No hypothetical check was executed; no counterfactual task resolution or measured human-time saving is claimed.',
        'Specialist1448 contains a local useful content change, but this does not override failed synthetic scores or establish a learning/product effect.']}
write(directory/'manual-screening-review.json',report)
comparisons={}
for other in ('B1','B2'):
    same=[]
    for row in (r for r in all_rows if r['arm']=='S'):
        baseline=raw[(other,row['id'])]
        same.append({'id':row['id'],'screening':row['id'].startswith('augnes-screen-'),
            'identical_raw_text_and_tokens':row['raw_text']==baseline['raw_text'] and row['raw_output_ids']==baseline['raw_output_ids']})
    comparisons['S_vs_'+other]={'assigned':116,'identical':sum(r['identical_raw_text_and_tokens'] for r in same),
        'screening_identical':sum(r['identical_raw_text_and_tokens'] for r in same if r['screening']),'rows':same}
write(directory/'paired-response-identities.json',{'B1_vs_prior_twenty':repeat,'comparisons':comparisons,
    'interpretation':'Exact repetition is a provenance observation, not independent quality replication or a statistical effect estimate.'})
print(json.dumps({'reviewed':len(records),'B1_reused_after_exact_match':len(repeat),
    'paired_identities':{k:{a:b for a,b in v.items() if a!='rows'} for k,v in comparisons.items()}},indent=2))
