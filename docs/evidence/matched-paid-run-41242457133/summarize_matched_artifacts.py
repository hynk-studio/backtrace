"""Post-deletion descriptive assembly; keeps every original arm and response."""
import argparse,base64,hashlib,json,math,statistics,sys
from collections import Counter
from pathlib import Path
REPOSITORY=Path('/workspace/scratch/565575038e73/backtrace-matched');sys.path.insert(0,str(REPOSITORY))
from tools import small_model_lifecycle as life
from tools.augnes_screening_review import inspect


def load(p):return json.loads(p.read_bytes())
def write(p,value):
    with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def summarize(directory):
    directory=Path(directory);remote=directory/'owner/minimum-owner/remote'
    claim_hash=life.digest((directory/'state/claim.json').read_bytes())
    for name in ('owner-cleanup','watch-cleanup'):
        proof=load(directory/'state'/(name+'.json'))
        if proof['status']!='DELETED' or proof['absence_reads']!=2 or proof['claim_sha256']!=claim_hash:
            raise ValueError('both independent deletion proofs required')
    collection=load(remote/'all-assignment-outcomes.json');schedule=load(remote/'input-schedule.json')['requests']
    if len(schedule)!=348 or len(collection['records'])!=348:raise ValueError('full denominator required')
    inputs=load(REPOSITORY/'docs/evidence/matched-qualified-run-41241191354/inputs/input-verification.json')
    if life.digest(schedule)!=inputs['schedule_sha256']:raise ValueError('qualified full input schedule changed')
    packet=load(REPOSITORY/'docs/augnes-screening-packets-20261031.json');rubric=load(REPOSITORY/'docs/augnes-screening-rubric-20261031.json')
    reports={};adaptations={};wires=0
    for arm in ('B1','B2','S'):
        rows=[r for r in collection['records'] if r['arm']==arm]
        requests=[r for r in schedule if r['arm']==arm]
        if len(rows)!=116 or [r['id'] for r in rows]!=[r['id'] for r in requests]:raise ValueError('arm denominator or order changed')
        p=remote/'collections'/arm;local=load(p/'collection.json')
        if local['records']!=rows:raise ValueError('aggregate differs from raw arm collection')
        finished=[json.loads(line)['record'] for line in (p/'ledger.jsonl').read_text().splitlines() if json.loads(line)['event']=='FINISHED']
        if finished!=rows:raise ValueError('complete FINISHED ledger differs')
        for i,(row,request) in enumerate(zip(rows,requests)):
            raw=load(p/f'wire-{i:04d}.json');wires+=1
            for k in ('id','input_tokens','input_ids_sha256'):
                if raw[k]!=request[k]:raise ValueError('response input identity changed')
            for a,b in [('id','id'),('output_ids','raw_output_ids'),('raw_text','raw_text'),('elapsed_seconds','worker_seconds'),('cuda_metrics','cuda_metrics')]:
                if raw[a]!=row[b]:raise ValueError('response wire differs from collection')
        screening=[r for r in rows if r['id'].startswith('augnes-screen-')]
        if [r['id'] for r in screening]!=[r['id'] for r in packet['cases']]:raise ValueError('original screening order changed')
        descriptive=[inspect(r,c,rubric['cases'][c['id']]) for r,c in zip(screening,packet['cases'])]
        trained=local['worker_handshakes']['E2B'].get('candidate_adapter')
        if arm=='B1':
            if local['training'] or trained:raise ValueError('untrained baseline has adapter metadata')
        else:
            t=load(remote/(arm+'-training-ready.json'))['candidate_adapter']
            if t['training_input_sha256']!=inputs['specification_sha256'][arm] or t['training_steps']!=320:
                raise ValueError('qualified training identity differs')
            for key in ('losses','gradient_norms','sequence_tokens','padded_tokens','supervised_tokens'):
                if len(t[key])!=320 or any(not math.isfinite(v) for v in t[key]):raise ValueError('incomplete training array')
            for key,expected in [('sequence_tokens','effective_sequence_tokens'),('padded_tokens','padded_tokens'),('supervised_tokens','supervised_tokens')]:
                if sum(t[key])!=inputs['training']['totals'][arm][expected]:raise ValueError('training budget differs')
            lines=[]
            for line in (remote/(arm+'-training-stderr.log')).read_text().splitlines():
                try:item=json.loads(line)
                except ValueError:continue
                if isinstance(item,dict) and item.get('phase')=='CANDIDATE_UPDATE_FINISHED':lines.append(item)
            if len(lines)!=320:raise ValueError('finished update count differs')
            for i,(line,pair) in enumerate(zip(lines,inputs['training']['pairs'])):
                if (line['step']!=i+1 or line['arm']!=arm or line['id']!=pair['id']
                        or line['loss']!=t['losses'][i] or line['gradient_norm']!=t['gradient_norms'][i]
                        or line['supervised_tokens']!=pair['supervised_tokens']):raise ValueError('raw training update differs')
            if (trained['training_steps']!=320 or trained['updates_in_worker']!=0
                    or trained['adapter_sha256']!=t['adapter_sha256']
                    or trained['observed_probe_logits_sha256']!=t['trained_probe_logits_sha256']):
                raise ValueError('fresh reload does not reproduce trained probe')
            train_state=load(remote/(arm+'-training-teardown.json'))['worker']
            eval_state=load(remote/(arm+'-evaluation-teardown.json'))['worker']
            if (train_state['same_process_alive'] or eval_state['same_process_alive']
                    or (train_state['pid'],train_state['start_ticks'])==(eval_state['pid'],eval_state['start_ticks'])):
                raise ValueError('fresh worker identity/teardown absent')
            raw=base64.b64decode(t['adapter_safetensors_base64'],validate=True)
            if len(raw)!=t['adapter_bytes'] or hashlib.sha256(raw).hexdigest()!=t['adapter_sha256']:raise ValueError('adapter bytes differ')
            n=int.from_bytes(raw[:8],'little');header=json.loads(raw[8:8+n]);payload=raw[8+n:]
            if set(header)!={'a','b'} or any(v['dtype']!='F32' for v in header.values()):raise ValueError('unexpected adapter format')
            if header['a']['shape']!=[4,1536] or header['b']['shape']!=[4096,4] or len(payload)!=4*22528:
                raise ValueError('unexpected E2B candidate shapes')
            destination=directory/(arm+'-adapter.safetensors');destination.write_bytes(raw)
            adaptations[arm]={k:v for k,v in t.items() if k not in ('adapter_safetensors_base64','probe_messages')}
            adaptations[arm]['fresh_worker_reload']=trained
            adaptations[arm]['train_process']=train_state;adaptations[arm]['evaluation_process']=eval_state
            adaptations[arm]['safetensors_header']=header
        times=[r['worker_seconds'] for r in rows]
        reports[arm]={'assigned':116,'coverage':dict(Counter(r['status'] for r in rows)),
            'generated_tokens':sum(r['generated_tokens'] for r in rows),'generation_seconds':sum(times),
            'median_generation_seconds':statistics.median(times),'maximum_generation_seconds':max(times),
            'peak_allocated_bytes':max(r['cuda_metrics']['peak_allocated_bytes'] for r in rows),
            'peak_reserved_bytes':max(r['cuda_metrics']['peak_reserved_bytes'] for r in rows),
            'screening':{'assigned':20,'strict_json':sum(r['strict_json_object'] for r in descriptive),
                'explicit_structure_pass':sum(r['explicit_contract_checks_pass'] for r in descriptive),'rows':descriptive},
            'worker_load':{k:v for k,v in local['worker_handshakes']['E2B'].items() if k!='candidate_adapter'}}
    result={'status':'PASS_COMPLETE_RESPONSE_AND_TRAINING_PROVENANCE','verified_wires':wires,
        'arms':reports,'adaptations':adaptations,'limitations':['Timing order is fixed and not a controlled latency comparison.',
        'Structure/label counts are not semantic accuracy or Augnes value.','Different-row training losses are not a learning curve.']}
    write(directory/'actual-candidate-metrics.json',result)
    return {a:{k:v for k,v in r.items() if k not in ('screening','worker_load')} for a,r in reports.items()}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory');a=parser.parse_args()
    print(json.dumps(summarize(a.directory),indent=2))
