"""Descriptive temporal scores, including late evidence and state-change estimates."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import json
from pathlib import Path
import sys

from tools import abductive_benchmark as base
from tools import abductive_scoring as score
from tools import exact_teacher as exact
from tools import temporal_benchmark as bench


def score_case(payload, response, *, missing=False, ref=None):
    translated = bench.as_revision(payload)
    ref = ref if ref is not None else bench.reference(payload)
    result = score.score_case(translated, response, missing=missing, ref=ref)
    if ref['status'] == 'OK':
        usable = result['response_status'] == 'VALID' and result['losses']['status_error'] == 0
        answer = score.validate_response(translated, response) if usable else None
        for target, metric in [('past', 'past_posterior_mae'), ('current', 'current_posterior_mae'),
                               ('changed', 'change_posterior_mae')]:
            result['losses'][metric] = (float(abs(score.probability(answer['posterior'][target])
                                                 - Fraction(ref['posterior'][target]))) if usable else 1.0)
    return result


def aggregate(rows):
    metrics = {}
    for name in sorted({k for row in rows for k in row['losses']}):
        groups = defaultdict(list)
        for row in rows:
            if name in row['losses']:
                groups[row['family']].append(row['losses'][name])
        means = {family: sum(values) / len(values) for family, values in groups.items()}
        values = [v for values in groups.values() for v in values]
        metrics[name] = {'case_mean': sum(values) / len(values), 'cases': len(values),
                         'family_mean': sum(means.values()) / len(means), 'families': len(means),
                         'by_family': means}
    return metrics


def score_records(agents, labels, predictions):
    if not agents or len(agents) != len(labels):
        raise ValueError('aligned nonempty assignments required')
    expected = {a['id'] for a in agents}
    if len(expected) != len(agents):
        raise ValueError('duplicate assigned ID')
    supplied = {}
    for row in predictions:
        exact._keys(row, {'id', 'response'})
        if not isinstance(row['id'], str) or row['id'] not in expected or row['id'] in supplied:
            raise ValueError('duplicate or unassigned prediction')
        supplied[row['id']] = row['response']
    cases, episodes = [], defaultdict(dict)
    for agent, label in zip(agents, labels):
        if agent['id'] != label['id']:
            raise ValueError('unaligned reference')
        result = score_case(agent['input'], supplied.get(agent['id']), missing=agent['id'] not in supplied,
                            ref=label['reference'])
        cases.append(dict(result, id=agent['id'], family=label['family'], episode=label['episode']))
        cutoff = agent['input']['as_of']
        if cutoff in episodes[label['episode']]:
            raise ValueError('duplicate episode snapshot')
        episodes[label['episode']][cutoff] = (agent, label, result)
    pairs = []
    tolerance = Fraction(base.protocol()['numeric_prediction_tolerance'])
    sign = lambda x: (x > tolerance) - (x < -tolerance)
    def usable(item):
        return item[2]['response_status'] == 'VALID' and item[2]['losses']['status_error'] == 0
    def posterior(item):
        answer = score.validate_response(bench.as_revision(item[0]['input']), supplied[item[0]['id']])
        return {k: score.probability(v) for k, v in answer['posterior'].items()}
    for episode, snapshots in episodes.items():
        if set(snapshots) != set(bench.CUTOFFS):
            raise ValueError('incomplete temporal episode')
        first, duplicate, update, correction = [snapshots[t] for t in bench.CUTOFFS]
        if len({item[1]['family'] for item in snapshots.values()}) != 1:
            raise ValueError('episode crosses families')
        losses = {'duplicate_invariance_error': 1.0}
        if first[1]['reference']['status'] != duplicate[1]['reference']['status']:
            raise ValueError('duplicate reference changes status')
        if usable(first) and usable(duplicate):
            if first[1]['reference']['status'] != 'OK':
                losses['duplicate_invariance_error'] = 0.0
            else:
                p, q = posterior(first), posterior(duplicate)
                losses['duplicate_invariance_error'] = float(any(abs(q[k] - p[k]) > tolerance for k in p))
        for name, before, after in [('update_direction_error', duplicate, update),
                                     ('correction_direction_error', update, correction)]:
            if before[1]['reference']['status'] == after[1]['reference']['status'] == 'OK':
                losses[name] = 1.0
                if usable(before) and usable(after):
                    p, q = posterior(before), posterior(after)
                    expected_delta = {k: Fraction(after[1]['reference']['posterior'][k])
                                         - Fraction(before[1]['reference']['posterior'][k]) for k in p}
                    # Includes zero-change targets: needless reversal is also an error.
                    losses[name] = float(any(sign(q[k] - p[k]) != sign(v) for k, v in expected_delta.items()))
        pairs.append({'episode': episode, 'family': first[1]['family'], 'losses': losses})
    return {'status': 'DESCRIPTIVE_ONLY', 'assigned': len(agents), 'provided': len(supplied),
            'responses': dict(Counter(c['response_status'] for c in cases)), 'metrics': aggregate(cases),
            'paired_metrics': aggregate(pairs), 'cases': cases, 'pairs': pairs,
            'confidence_intervals': 'NOT_COMPUTED', 'capability_claim': 'NOT_ESTABLISHED'}


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
        if args.predictions.is_symlink() or args.predictions.stat().st_size > base.MAX_FILE_BYTES:
            raise ValueError('unsafe predictions file')
        raw = args.predictions.read_bytes()
        predictions = [base.strict_json(line) for line in raw.splitlines()]
        agents, labels = [base.read_rows(destination, f'{args.split}/{kind}.jsonl', manifest)
                          for kind in ('agent', 'evaluator')]
        report = score_records(agents, labels, predictions)
        report.update(source_manifest_sha256=exact.sha(exact.canonical(manifest)),
                      prediction_sha256=exact.sha(raw), split=args.split)
        base.private_write(exact._local_path(args.output), exact.canonical(report))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print('temporal scoring failed: ' + type(error).__name__, file=sys.stderr)
        return 2
    print(json.dumps({key: report[key] for key in ('status', 'assigned', 'provided', 'capability_claim')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
