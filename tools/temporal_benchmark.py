"""Exact changing-state extension; retains the original family split and teacher."""
import argparse
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import shutil
import sys

from tools import abductive_benchmark as base
from tools import exact_teacher as exact


PROTOCOL = exact.ROOT / 'docs/temporal-evaluation-protocol-v1.json'
SPLITS = base.SPLITS
CUTOFFS = (2, 3, 4, 5)


def protocol():
    return base.strict_json(PROTOCOL.read_bytes())


def source_hashes():
    return dict(base.source_hashes(), **{name: exact.sha((exact.ROOT / name).read_bytes()) for name in (
        'tools/temporal_benchmark.py', 'tools/temporal_scoring.py',
        'docs/temporal-evaluation-protocol-v1.json')})


def episode_inputs(family, variant):
    original = base.make_question(family, variant)
    question = deepcopy(original)
    nodes = question['model']['nodes']
    old = next(n['id'] for n in nodes if not n['parents'])
    old_signal = nodes[-1]['id']
    middle, current, signal = old + '_t1', old + '_t2', 'signal_t2'
    # Stay, uncertain change, independence, forced change, and asymmetric drift.
    transition = (
        (('0', '1'), ('0', '1')),
        (('1/10', '9/10'), ('1/5', '4/5')),
        (('1/2', '1/2'), ('1/2', '1/2')),
        (('1', '0'), ('0', '1')),
        (('1/4', '9/10'), ('1/3', '4/5')),
    )[variant % 5]
    for name, parent, probabilities in zip((middle, current), (old, middle), transition):
        nodes.append({'id': name, 'parents': [parent], 'p_true': dict(zip(('0', '1'), probabilities))})
    nodes.append({'id': signal, 'parents': [current], 'p_true': {'0': '1/4', '1': '3/4'}})
    question['evidence'] = []
    question['hypotheses'] = [
        {'id': 'past', 'condition': [{old: True}]},
        {'id': 'current', 'condition': [{current: True}]},
        {'id': 'changed', 'condition': [{old: False, current: True}, {old: True, current: False}]},
    ]
    question['queries'] = deepcopy(question['hypotheses'])
    question['actions'] = [
        {'id': 'yes', 'condition': [{current: True}], 'if_true': '1', 'if_false': '0'},
        {'id': 'no', 'condition': [{current: False}], 'if_true': '1', 'if_false': '0'},
    ]
    question['inspections'] = [{'event': current, 'cost': '1/3'}, {'event': signal, 'cost': '1/20'}]
    times = {n['id']: 0 for n in original['model']['nodes']}
    times.update({middle: 1, current: 2, signal: 2})
    def observe(identifier, event, value, available):
        return {'id': identifier, 'kind': 'observation', 'event': event, 'value': value,
                'observed_at': times[event], 'available_at': available}
    stream = [observe('old_signal', old_signal, True, 2),
              observe('old_copy', old_signal, True, 3),
              observe('delayed_old_cause', old, variant % 2 == 0, 4),
              observe('current_signal', signal, True, 4),
              {'id': 'withdraw_current', 'kind': 'retraction', 'target': 'current_signal', 'available_at': 5},
              observe('corrected_current', signal, False, 5),
              observe('future_unavailable', current, True, 6)]
    for cutoff in CUTOFFS:
        yield {'task': 'temporal_revision', 'question': question, 'event_times': times,
               'as_of': cutoff, 'records': [r for r in stream if r['available_at'] <= cutoff]}


def as_revision(payload):
    exact._keys(payload, {'task', 'question', 'event_times', 'as_of', 'records'})
    if payload['task'] != 'temporal_revision':
        raise ValueError('temporal task required')
    nodes = exact.validate(payload['question'])
    names = {node['id'] for node in nodes}
    exact._keys(payload['event_times'], names)
    cutoff = payload['as_of']
    if type(cutoff) is not int or cutoff not in CUTOFFS:
        raise ValueError('unsupported temporal cutoff')
    times = payload['event_times']
    if any(type(t) is not int or not 0 <= t <= 2 for t in times.values()):
        raise ValueError('event time outside declared horizon')
    if any(times[parent] > times[node['id']] for node in nodes for parent in node['parents']):
        raise ValueError('edge goes backwards in time')
    # base validation establishes record kinds, uniqueness, retractions and cutoff.
    translated = {key: payload[key] for key in ('question', 'as_of', 'records')}
    translated['task'] = 'revision'
    base.input_question(translated)
    for record in payload['records']:
        if record['kind'] == 'observation' and record['observed_at'] != times[record['event']]:
            raise ValueError('observation time must match the time-indexed event')
    hypotheses = {h['id']: h['condition'] for h in payload['question']['hypotheses']}
    if set(hypotheses) != {'past', 'current', 'changed'}:
        raise ValueError('temporal hypotheses required')
    for name, time in [('past', 0), ('current', 2)]:
        condition = hypotheses[name]
        if (len(condition) != 1 or len(condition[0]) != 1 or
                next(iter(condition[0].values())) is not True or
                times[next(iter(condition[0]))] != time):
            raise ValueError('past/current must name a true state variable at its declared time')
    past, current = [next(iter(hypotheses[name][0])) for name in ('past', 'current')]
    expected_change = [{past: True, current: False}, {past: False, current: True}]
    if (len(hypotheses['changed']) != 2 or
            any(clause not in hypotheses['changed'] for clause in expected_change)):
        raise ValueError('changed must mean different past and current states')
    if any(times[i['event']] != 2 for i in payload['question']['inspections']):
        raise ValueError('only current-state inspections allowed')
    return translated


@lru_cache(maxsize=6000)
def _reference(raw):
    return base.reference(as_revision(base.strict_json(raw)))


def reference(payload):
    return deepcopy(_reference(exact.canonical(payload)))


def generate_split(split, variants=20):
    if split not in SPLITS or type(variants) is not int or not 1 <= variants <= 32:
        raise ValueError('invalid split or variants')
    data = {'agent': [], 'evaluator': []}
    for family, (assigned, _) in base.catalog().items():
        if assigned != split:
            continue
        for variant in range(variants):
            # Same episode identity as the existing static views, not a new independent case.
            episode = exact.sha(exact.canonical(base.make_question(family, variant)))
            for payload in episode_inputs(family, variant):
                identifier = exact.sha(exact.canonical(payload))
                data['agent'].append({'id': identifier, 'input': payload})
                data['evaluator'].append({'id': identifier, 'family': family, 'episode': episode,
                                          'reference': reference(payload)})
    return data


def audit_records(data, variants):
    exact._keys(data, SPLITS)
    seen, episodes, families, counts, coverage = set(), {}, {}, {}, {}
    for split in SPLITS:
        if data[split] != generate_split(split, variants):
            raise ValueError('temporal data differs from deterministic generator')
        counts[split] = len(data[split]['agent'])
        coverage[split] = dict(Counter(l['reference']['status'] for l in data[split]['evaluator']))
        for agent, label in zip(data[split]['agent'], data[split]['evaluator']):
            identifier = agent['id']
            if identifier in seen or label['id'] != identifier:
                raise ValueError('duplicate or unaligned input')
            seen.add(identifier)
            if label['episode'] in episodes and episodes[label['episode']] != split:
                raise ValueError('episode crosses partitions')
            if base.catalog()[label['family']][0] != split:
                raise ValueError('static/temporal family split mismatch')
            episodes[label['episode']], families[label['family']] = split, split
    return {'status': 'PASS', 'counts': counts, 'coverage': coverage,
            'family_counts': dict(Counter(families.values())), 'episode_counts': dict(Counter(episodes.values())),
            'model_evaluation': 'NOT_RUN', 'confirmatory_ready': False}


def write_dataset(destination, variants=20):
    data = {s: generate_split(s, variants) for s in SPLITS}
    audit = audit_records(data, variants)
    destination = exact._local_path(destination)
    destination.mkdir(mode=0o700, exist_ok=False)
    try:
        files = {}
        for split in SPLITS:
            (destination / split).mkdir(mode=0o700)
            for kind in ('agent', 'evaluator'):
                name = f'{split}/{kind}.jsonl'
                content = b''.join(exact.canonical(row) for row in data[split][kind])
                base.private_write(destination / name, content)
                files[name] = base.file_info(content)
        manifest = {'version': protocol()['version'], 'source_hashes': source_hashes(), 'variants': variants,
                    'files': files, 'audit': audit, 'status': 'CPU_PREPARATION_NOT_CONFIRMATORY'}
        base.private_write(destination / 'manifest.json', exact.canonical(manifest))
        return manifest
    except BaseException:
        shutil.rmtree(destination)
        raise


def read_manifest(destination):
    destination = exact._local_path(destination)
    path = destination / 'manifest.json'
    if path.is_symlink() or path.stat().st_size > 1_000_000:
        raise ValueError('unsafe manifest')
    manifest = base.strict_json(path.read_bytes())
    exact._keys(manifest, {'version', 'source_hashes', 'variants', 'files', 'audit', 'status'})
    if (manifest['version'] != protocol()['version'] or manifest['source_hashes'] != source_hashes()
            or manifest['status'] != 'CPU_PREPARATION_NOT_CONFIRMATORY'
            or type(manifest['variants']) is not int or not 1 <= manifest['variants'] <= 32):
        raise ValueError('source-bound manifest mismatch')
    exact._keys(manifest['files'], {f'{s}/{k}.jsonl' for s in SPLITS for k in ('agent', 'evaluator')})
    return destination, manifest


def audit_dataset(destination):
    destination, manifest = read_manifest(destination)
    if any(p.is_symlink() for p in destination.rglob('*')):
        raise ValueError('symlink member')
    expected = {'manifest.json', *manifest['files']}
    if {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()} != expected:
        raise ValueError('unexpected dataset member')
    data = {s: {k: base.read_rows(destination, f'{s}/{k}.jsonl', manifest)
                for k in ('agent', 'evaluator')} for s in SPLITS}
    audit = audit_records(data, manifest['variants'])
    if audit != manifest['audit']:
        raise ValueError('audit mismatch')
    return audit


def export_view(destination, output, *, split='train', training=False):
    if split not in SPLITS or (training and split != 'train'):
        raise ValueError('training export is train-only')
    destination, manifest = read_manifest(destination)
    agents = base.read_rows(destination, f'{split}/agent.jsonl', manifest)
    for row in agents:
        exact._keys(row, {'id', 'input'})
        as_revision(row['input'])
        if row['id'] != exact.sha(exact.canonical(row['input'])):
            raise ValueError('input identity mismatch')
    rows = agents
    if training:
        from tools.abductive_scoring import optimal_response
        labels = base.read_rows(destination, 'train/evaluator.jsonl', manifest)
        expected = generate_split('train', manifest['variants'])
        if agents != expected['agent'] or labels != expected['evaluator']:
            raise ValueError('training data mismatch')
        rows = [{'id': a['id'], 'messages': [
            {'role': 'user', 'content': exact.canonical(a['input']).decode().strip()},
            {'role': 'assistant', 'content': exact.canonical(optimal_response(as_revision(a['input']), l['reference'])).decode().strip()}]}
            for a, l in zip(agents, labels)]
    output = exact._local_path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    try:
        content = b''.join(exact.canonical(row) for row in rows)
        base.private_write(output / 'records.jsonl', content)
        receipt = {'kind': 'training' if training else 'inputs_only', 'split': split,
                   'source_manifest_sha256': exact.sha(exact.canonical(manifest)),
                   'file': base.file_info(content), 'runtime_isolation': 'NOT_PROVEN_BY_FILE_EXPORT'}
        base.private_write(output / 'receipt.json', exact.canonical(receipt))
        return receipt
    except BaseException:
        shutil.rmtree(output)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('generate', 'audit', 'export-inputs', 'export-training'):
        sub = commands.add_parser(command)
        sub.add_argument('dataset', type=Path)
        if command == 'generate':
            sub.add_argument('--variants', type=int, default=20)
        if command.startswith('export'):
            sub.add_argument('output', type=Path)
        if command == 'export-inputs':
            sub.add_argument('--split', choices=SPLITS, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'generate':
            result = write_dataset(args.dataset, args.variants)
        elif args.command == 'audit':
            result = audit_dataset(args.dataset)
        else:
            result = export_view(args.dataset, args.output, split=getattr(args, 'split', 'train'),
                                 training=args.command == 'export-training')
    except (OSError, ValueError, TypeError, KeyError) as error:
        print('temporal benchmark failed: ' + type(error).__name__, file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
