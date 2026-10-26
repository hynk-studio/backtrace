"""Prepare matched development prompts only; no model/runtime/network invocation."""
import argparse
import json
from pathlib import Path
import shutil
import sys

from tools import abductive_benchmark as base
from tools import exact_teacher as exact
from tools import temporal_benchmark as temporal


PROTOCOL = exact.ROOT / 'docs/abductive-baseline-protocol-v1.json'
COMMON = '''Solve the supplied finite-model task and return only one JSON object, with no markdown or extra fields.
Boolean nodes form a Bayesian network. A CPT gives P(node=true | ordered parents); false has complementary probability. Different time-indexed nodes are different variables. Hypothesis conditions are an OR of AND clauses; an empty clause is true and an empty clause list false. Hypotheses may overlap.
Evidence observes the named variable exactly. Repeated observations of the same variable are not independent measurements. Conflicting active values of that variable give INCONSISTENT_EVIDENCE. Consistent evidence with zero model probability gives MODEL_MISMATCH. Otherwise status is OK. Low probability alone is not model mismatch.
For revision tasks use only records available by as_of, remove explicitly retracted observations, and list all active observation IDs, including duplicates. observed_at identifies the state observed; available_at identifies when it became available. A late observation of an old event does not become an observation of a current event.
For inference/revision/temporal_revision, return {"status":...,"posterior":{hypothesis_id:probability,...},"decision":...}. Revision and temporal_revision additionally require "active_evidence_ids":[...]. Non-OK requires null posterior and decision. Use marginal posteriors without normalizing overlapping hypotheses. Decision is {"mode":"STOP","action":action_id} or {"mode":"INSPECT","event":event_id,"outcome_actions":{"false":action_id,"true":action_id}}. Maximize expected action utility minus the chosen inspection cost over one observation then one action. Pick STOP on an exact zero-benefit check tie. Inspections reveal a Boolean variable without intervention; already observed variables reveal no new information. Either declared action is acceptable on an impossible outcome branch.
For abduction, return {"status":...,"explanations":[{"assignment":{cause_variable:boolean,...},"probability":...,"predictions":{prediction_event:probability,...}},...]}. Construct complete assignments to all named causes. Include all and only positive-posterior assignments up to max_explanations; exclusive assignment masses sum to one. Predictions are conditional on that assignment and the evidence. Non-OK requires an empty explanations list. Equivalent assignment/dictionary ordering is irrelevant.
Probabilities may be finite JSON numbers or rational/decimal strings. Never add a confidence field or a free-form explanation.'''

GUIDANCE = '''
Before answering, track evidence identity and availability, distinguish a correction about one state from an actual transition between states, and retain multiple compatible explanations. Account for the joint model and dependencies instead of multiplying duplicate observations. Check both the hypotheses' forward implications and the evidence likelihood. Compare the expected value of each permitted check including its actual outcome-contingent actions and cost, then verify the final JSON, numerical range and applicable normalization. Return only the required object. Don't output your working.'''


def protocol():
    return base.strict_json(PROTOCOL.read_bytes())


def validate_input(payload):
    if payload.get('task') == 'temporal_revision':
        temporal.as_revision(payload)
    else:
        base.input_question(payload)


def condition_text(clauses):
    if not clauses:
        return 'false'
    return ' OR '.join('(' + (' AND '.join(f'{name}={str(value).lower()}' for name, value in sorted(c.items()))
                              if c else 'true') + ')' for c in clauses)


def render_text(payload):
    """Deterministic controlled English; every model and evidence fact is retained."""
    validate_input(payload)
    task = payload['task']
    q = payload if task == 'abduction' else payload['question']
    lines = [f'Task: {task}.', 'The supplied probability model is:']
    for node in q['model']['nodes']:
        time = f" at state time {payload['event_times'][node['id']]}" if 'event_times' in payload else ''
        lines.append(f"Variable {node['id']}{time}.")
        for bits, p in sorted(node['p_true'].items()):
            given = ' AND '.join(f'{name}={str(bit == "1").lower()}' for name, bit in zip(node['parents'], bits))
            lines.append(f"P({node['id']}=true" + (f' | {given}' if given else '') + f') = {p}.')
    if task in ('revision', 'temporal_revision'):
        lines.append(f"Information cutoff as_of={payload['as_of']}. No base observations. Records, in availability order:")
        for record in payload['records']:
            if record['kind'] == 'observation':
                lines.append(f"Record {record['id']}: observed {record['event']}={str(record['value']).lower()} "
                             f"at observed_at={record['observed_at']}; available_at={record['available_at']}.")
            else:
                lines.append(f"Record {record['id']}: retract record {record['target']}; available_at={record['available_at']}.")
    else:
        lines.append('Evidence:')
        for record in q['evidence']:
            lines.append(f"Record {record['id']}: {record['event']}={str(record['value']).lower()}.")
        if not q['evidence']:
            lines.append('No observations.')
    if task == 'abduction':
        lines += ['Construct complete assignments to: ' + ', '.join(payload['cause_variables']) + '.',
                  'Predict these events for each assignment: ' + ', '.join(payload['prediction_events']) + '.',
                  f"At most {payload['max_explanations']} explanations."]
    else:
        for field in ('hypotheses', 'queries'):
            for item in q[field]:
                lines.append(f"{field} {item['id']}: {condition_text(item['condition'])}.")
        for action in q['actions']:
            lines.append(f"Action {action['id']}: utility {action['if_true']} when {condition_text(action['condition'])}; "
                         f"utility {action['if_false']} otherwise.")
        for inspection in q['inspections']:
            lines.append(f"Allowed inspection: {inspection['event']}, cost {inspection['cost']}.")
        if not q['inspections']:
            lines.append('No inspections allowed.')
    return '\n'.join(lines)


def messages(payload, arm, rendering):
    if arm not in ('B0', 'B1') or rendering not in ('json', 'controlled_text'):
        raise ValueError('unsupported matched arm or rendering')
    validate_input(payload)
    return [{'role': 'system', 'content': COMMON + (GUIDANCE if arm == 'B1' else '')},
            {'role': 'user', 'content': exact.canonical(payload).decode().strip() if rendering == 'json' else render_text(payload)}]


def read_view(directory):
    directory = exact._local_path(directory)
    if {p.name for p in directory.iterdir()} != {'receipt.json', 'records.jsonl'}:
        raise ValueError('only an isolated exported input view is accepted')
    for name, bound in [('receipt.json', 1_000_000), ('records.jsonl', base.MAX_FILE_BYTES)]:
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > bound:
            raise ValueError('unsafe input view')
    receipt = base.strict_json((directory / 'receipt.json').read_bytes())
    exact._keys(receipt, {'kind', 'split', 'source_manifest_sha256', 'file', 'runtime_isolation'})
    if receipt['kind'] != 'inputs_only' or receipt['split'] != 'development':
        raise ValueError('baseline preparation accepts development inputs only')
    raw = (directory / 'records.jsonl').read_bytes()
    if base.file_info(raw) != receipt['file']:
        raise ValueError('input view hash/count mismatch')
    rows = [base.strict_json(line) for line in raw.splitlines()]
    if not rows:
        raise ValueError('empty input view')
    for row in rows:
        exact._keys(row, {'id', 'input'})
        validate_input(row['input'])
        if row['id'] != exact.sha(exact.canonical(row['input'])):
            raise ValueError('input identity mismatch')
    return rows, receipt


def prepare(views, output):
    rows, receipts = [], []
    for view in views:
        data, receipt = read_view(view)
        rows.extend(data)
        receipts.append(receipt)
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('empty or duplicate assignment')
    rows.sort(key=lambda row: row['id'])
    output = exact._local_path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    try:
        files = {}
        for arm in protocol()['arms']:
            for rendering in protocol()['renderings']:
                name = f'{arm}-{rendering}.jsonl'
                content = b''.join(exact.canonical({'id': row['id'], 'messages': messages(row['input'], arm, rendering)})
                                   for row in rows)
                base.private_write(output / name, content)
                files[name] = dict(base.file_info(content), arm=arm, rendering=rendering)
        manifest = {'protocol': protocol(), 'status': 'PREPARED_NOT_EXECUTABLE', 'files': files,
                    'input_receipts': receipts, 'assigned_cases_per_packet': len(rows),
                    'requests_per_backbone_if_all_packets_run': len(rows) * len(files),
                    'model_evaluation': 'NOT_RUN', 'tokenization': 'NOT_RUN',
                    'model_pins': {name: None for name in protocol()['backbones']},
                    'prompt_hashes': {arm: exact.sha((COMMON + (GUIDANCE if arm == 'B1' else '')).encode())
                                      for arm in protocol()['arms']},
                    'source_hashes': dict(temporal.source_hashes(), **{name: exact.sha((exact.ROOT / name).read_bytes())
                                          for name in ('tools/abductive_baseline.py', 'docs/abductive-baseline-protocol-v1.json')})}
        base.private_write(output / 'manifest.json', exact.canonical(manifest))
        return manifest
    except BaseException:
        shutil.rmtree(output)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--view', type=Path, action='append', required=True)
    args = parser.parse_args(argv)
    try:
        manifest = prepare(args.view, args.output)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print('baseline preparation failed: ' + type(error).__name__, file=sys.stderr)
        return 2
    print(json.dumps(manifest, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
