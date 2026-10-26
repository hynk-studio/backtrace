"""Score all assigned benchmark cases; report descriptive evidence, never promotion."""
import argparse
from collections import defaultdict
from fractions import Fraction
import json
import math
from pathlib import Path
import re
import sys

from tools import abductive_benchmark as bench
from tools import exact_teacher as exact


def probability(value):
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError('nonfinite prediction')
        value = Fraction(str(value))
    elif type(value) is int:
        value = Fraction(value)
    elif isinstance(value, str) and re.fullmatch(r'-?\d{1,128}(?:/[1-9]\d{0,127}|\.\d{1,128})?', value):
        value = Fraction(value)
    else:
        raise ValueError('numeric probability required')
    if not 0 <= value <= 1:
        raise ValueError('probability outside [0,1]')
    return value


def assignment_key(assignment):
    return tuple(sorted(assignment.items()))


def best_action(values):
    return min(values, key=lambda key: (-Fraction(values[key]), key))


def optimal_response(payload, ref=None):
    """Evaluator/control target, never a model result or evaluation model input."""
    ref = ref if ref is not None else bench.reference(payload)
    if payload['task'] == 'abduction':
        return {'status': ref['status'], 'explanations': ref['explanations']}
    response = {'status': ref['status'], 'posterior': ref['posterior'], 'decision': None}
    if payload['task'] == 'revision':
        response['active_evidence_ids'] = ref['active_evidence_ids']
    if ref['status'] != 'OK':
        return response
    action = best_action(ref['action_values'])
    value = Fraction(ref['action_values'][action])
    decision = {'mode': 'STOP', 'action': action}
    for event, inspection in sorted(ref['inspections'].items()):
        after = -Fraction(inspection['cost'])
        choices = {}
        for outcome, branch in inspection['branches'].items():
            choices[outcome] = best_action(branch['action_values']) if branch['action_values'] else action
            if branch['action_values']:
                after += Fraction(branch['probability']) * Fraction(branch['action_values'][choices[outcome]])
        if after > value:  # Stop wins exact zero-value inspection ties.
            value = after
            decision = {'mode': 'INSPECT', 'event': event, 'outcome_actions': choices}
    response['decision'] = decision
    return response


def validate_response(payload, response):
    if isinstance(response, str):
        if len(response) > 100_000:
            raise ValueError('response too large')
        response = bench.strict_json(response)
    task = payload['task']
    keys = {'status', 'explanations'} if task == 'abduction' else {'status', 'posterior', 'decision'}
    if task == 'revision':
        keys.add('active_evidence_ids')
    exact._keys(response, keys)
    if not isinstance(response['status'], str) or response['status'] not in bench.STATUSES:
        raise ValueError('unknown status')
    question = bench.input_question(payload)
    if task == 'revision':
        ids = exact._list(response['active_evidence_ids'], 0, 32)
        if any(not isinstance(x, str) for x in ids) or len(ids) != len(set(ids)):
            raise ValueError('unique evidence IDs required')
    if task == 'abduction':
        explanations = exact._list(response['explanations'], 0, payload['max_explanations'])
        if response['status'] != 'OK':
            if explanations:
                raise ValueError('undefined distribution must be empty')
            return response
        if not explanations:
            raise ValueError('OK requires at least one explanation')
        total, seen = Fraction(0), set()
        for item in explanations:
            exact._keys(item, {'assignment', 'probability', 'predictions'})
            exact._keys(item['assignment'], payload['cause_variables'])
            if any(type(value) is not bool for value in item['assignment'].values()):
                raise ValueError('Boolean assignment required')
            key = assignment_key(item['assignment'])
            if key in seen:
                raise ValueError('duplicate semantic explanation')
            seen.add(key)
            p = probability(item['probability'])
            if p == 0:
                raise ValueError('zero-mass assignments must be omitted')
            total += p
            exact._keys(item['predictions'], payload['prediction_events'])
            for value in item['predictions'].values():
                probability(value)
        if abs(total - 1) > Fraction(bench.protocol()['numeric_prediction_tolerance']):
            raise ValueError('exclusive root-assignment distribution must sum to one')
        return response
    if response['status'] != 'OK':
        if response['posterior'] is not None or response['decision'] is not None:
            raise ValueError('undefined posterior/decision must be null')
        return response
    exact._keys(response['posterior'], {h['id'] for h in question['hypotheses']})
    for value in response['posterior'].values():
        probability(value)
    decision = response['decision']
    if not isinstance(decision, dict):
        raise ValueError('decision object required')
    actions = {a['id'] for a in question['actions']}
    if decision.get('mode') == 'STOP':
        exact._keys(decision, {'mode', 'action'})
        if decision['action'] not in actions:
            raise ValueError('unknown stop action')
    elif decision.get('mode') == 'INSPECT':
        exact._keys(decision, {'mode', 'event', 'outcome_actions'})
        if decision['event'] not in {i['event'] for i in question['inspections']}:
            raise ValueError('unknown inspection')
        exact._keys(decision['outcome_actions'], {'false', 'true'})
        if any(action not in actions for action in decision['outcome_actions'].values()):
            raise ValueError('unknown outcome action')
    else:
        raise ValueError('unknown decision mode')
    return response


def decision_value(decision, ref):
    if decision['mode'] == 'STOP':
        return Fraction(ref['action_values'][decision['action']])
    inspection = ref['inspections'][decision['event']]
    value = -Fraction(inspection['cost'])
    for outcome, branch in inspection['branches'].items():
        if Fraction(branch['probability']):
            value += Fraction(branch['probability']) * Fraction(branch['action_values'][decision['outcome_actions'][outcome]])
    return value


def score_case(payload, response, *, missing=False, ref=None):
    ref = ref if ref is not None else bench.reference(payload)
    task = payload['task']
    losses = {'status_error': 1.0}
    if ref['status'] == 'OK':
        losses['posterior_mae'] = 1.0
        if task == 'abduction':
            losses.update(hypothesis_precision_error=1.0, hypothesis_recall_error=1.0,
                          forward_prediction_mae=1.0)
        else:
            losses['normalized_decision_regret'] = 1.0
    if task == 'revision':
        losses['evidence_selection_error'] = 1.0
    result = {'response_status': 'MISSING' if missing else 'INVALID', 'losses': losses}
    if missing:
        return result
    try:
        response = validate_response(payload, response)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return result
    result['response_status'] = 'VALID'
    losses['status_error'] = float(response['status'] != ref['status'])
    if task == 'revision':
        losses['evidence_selection_error'] = float(sorted(response['active_evidence_ids']) != ref['active_evidence_ids'])
    if response['status'] != ref['status'] or ref['status'] != 'OK':
        return result
    if task == 'abduction':
        expected = {assignment_key(e['assignment']): e for e in ref['explanations']}
        observed = {assignment_key(e['assignment']): e for e in response['explanations']}
        keys = expected.keys() | observed.keys()
        # All 2^root-count assignments, including omitted zero probabilities.
        error = sum(abs((probability(observed[k]['probability']) if k in observed else 0)
                        - (Fraction(expected[k]['probability']) if k in expected else 0)) for k in keys)
        losses['posterior_mae'] = float(error / (2 ** len(payload['cause_variables'])))
        common = expected.keys() & observed.keys()
        losses['hypothesis_precision_error'] = 1 - len(common) / len(observed)
        losses['hypothesis_recall_error'] = 1 - len(common) / len(expected)
        errors = []
        for key, item in expected.items():
            for event, p in item['predictions'].items():
                errors.append(abs(probability(observed[key]['predictions'][event]) - Fraction(p)) if key in observed else Fraction(1))
        losses['forward_prediction_mae'] = float(sum(errors) / len(errors)) if errors else 0.0
    else:
        losses['posterior_mae'] = float(sum(abs(probability(response['posterior'][key]) - Fraction(value))
                                          for key, value in ref['posterior'].items()) / len(ref['posterior']))
        optimum = decision_value(optimal_response(payload, ref)['decision'], ref)
        gap = optimum - decision_value(response['decision'], ref)
        normalizer = Fraction(ref['normalizer'])
        if gap < 0 or (normalizer == 0 and gap != 0):
            raise AssertionError('inconsistent decision oracle')
        losses['normalized_decision_regret'] = float(gap / normalizer) if normalizer else 0.0
    return result


def score_records(agents, labels, predictions):
    if len(agents) != len(labels) or not agents:
        raise ValueError('aligned nonempty assignments required')
    expected_ids = {a['id'] for a in agents}
    if len(expected_ids) != len(agents):
        raise ValueError('duplicate assigned ID')
    supplied = {}
    for row in predictions:
        exact._keys(row, {'id', 'response'})
        if not isinstance(row['id'], str) or row['id'] not in expected_ids or row['id'] in supplied:
            raise ValueError('duplicate or unassigned prediction')
        supplied[row['id']] = row['response']
    cases, paired = [], defaultdict(dict)
    for agent, label in zip(agents, labels):
        if agent['id'] != label['id']:
            raise ValueError('reference identity mismatch')
        result = score_case(agent['input'], supplied.get(agent['id']), missing=agent['id'] not in supplied,
                            ref=label['reference'])
        cases.append(dict(result, id=agent['id'], task=agent['input']['task'], family=label['family'], episode=label['episode']))
        if agent['input']['task'] == 'revision':
            paired[label['episode']][agent['input']['as_of']] = (agent, label, result)
    groups = {}
    for task in bench.TASKS:
        selected = [c for c in cases if c['task'] == task]
        if not selected:
            continue
        names = sorted({name for c in selected for name in c['losses']})
        metrics = {}
        for name in names:
            values = defaultdict(list)
            for c in selected:
                if name in c['losses']:
                    values[c['family']].append(c['losses'][name])
            means = {key: sum(v) / len(v) for key, v in values.items()}
            flat = [v for vs in values.values() for v in vs]
            metrics[name] = {'case_mean': sum(flat) / len(flat), 'family_mean': sum(means.values()) / len(means),
                             'cases': len(flat), 'families': len(means), 'by_family': means}
        groups[task] = {'assigned': len(selected), 'responses': dict(bench.Counter(c['response_status'] for c in selected)),
                        'metrics': metrics}
    invariant_errors, update_errors = [], []
    tolerance = Fraction(bench.protocol()['numeric_prediction_tolerance'])
    for snapshots in paired.values():
        if set(snapshots) != {1, 2, 3}:
            raise ValueError('incomplete revision episode assignment')
        first, second, third = [snapshots[i] for i in (1, 2, 3)]
        def usable(item):
            return item[2]['response_status'] == 'VALID' and item[1]['reference']['status'] == 'OK' and item[2]['losses']['status_error'] == 0
        invariant_errors.append(1.0)
        if usable(first) and usable(second):
            p, q = [validate_response(item[0]['input'], supplied[item[0]['id']])['posterior'] for item in (first, second)]
            invariant_errors[-1] = float(any(abs(probability(p[k]) - probability(q[k])) > tolerance for k in p))
        elif (first[1]['reference']['status'] == second[1]['reference']['status'] != 'OK'
              and all(item[2]['response_status'] == 'VALID' and item[2]['losses']['status_error'] == 0
                      for item in (first, second))):
            # An undefined posterior stays undefined under duplicated evidence.
            invariant_errors[-1] = 0.0
        # Exact posterior change, including magnitude, is already scored per case.
        if first[1]['reference']['status'] == third[1]['reference']['status'] == 'OK':
            expected_delta = {k: Fraction(third[1]['reference']['posterior'][k]) - Fraction(v)
                              for k, v in first[1]['reference']['posterior'].items()}
            if any(expected_delta.values()):
                error = 1.0
                if usable(first) and usable(third):
                    p, q = [validate_response(item[0]['input'], supplied[item[0]['id']])['posterior'] for item in (first, third)]
                    sign = lambda x: (x > tolerance) - (x < -tolerance)
                    error = float(any(sign(probability(q[k]) - probability(p[k])) != sign(v) for k, v in expected_delta.items()))
                update_errors.append(error)
    return {'status': 'DESCRIPTIVE_ONLY', 'assigned': len(agents), 'provided': len(supplied), 'tasks': groups,
            'revision_pairs': {name: {'episodes': len(values), 'error_rate': sum(values) / len(values) if values else None}
                               for name, values in [('duplicate_invariance', invariant_errors), ('revision_direction', update_errors)]},
            'capability_claim': 'NOT_ESTABLISHED', 'confidence_intervals': 'NOT_COMPUTED',
            'cases': cases}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('predictions', type=Path)
    parser.add_argument('--split', choices=bench.SPLITS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        bench.audit_dataset(args.dataset)
        destination, manifest = bench.read_manifest(args.dataset)
        if args.predictions.is_symlink() or args.predictions.stat().st_size > bench.MAX_FILE_BYTES:
            raise ValueError('unsafe predictions file')
        predictions = [bench.strict_json(line) for line in args.predictions.read_bytes().splitlines()]
        agents, labels = [bench.read_rows(destination, f'{args.split}/{kind}.jsonl', manifest)
                          for kind in ('agent', 'evaluator')]
        report = score_records(agents, labels, predictions)
        report['source_manifest_sha256'] = exact.sha(exact.canonical(manifest))
        report['prediction_sha256'] = exact.sha(args.predictions.read_bytes())
        report['split'] = args.split
        output = exact._local_path(args.output)
        bench.private_write(output, exact.canonical(report))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print('abductive scoring failed: ' + type(error).__name__, file=sys.stderr)
        return 2
    print(json.dumps({key: report[key] for key in ('status', 'assigned', 'provided', 'capability_claim')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
