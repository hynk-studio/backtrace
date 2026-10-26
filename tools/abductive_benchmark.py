"""Bounded CPU abduction benchmark; no model, network or training invocation.

The historical exact teacher is imported unchanged. Reserved data is a candidate
test partition, not a powered or approved confirmatory experiment.
"""
import argparse
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
import itertools
import json
import os
from pathlib import Path
import shutil
import sys

from tools import exact_teacher as exact


ROOT = exact.ROOT
PROTOCOL_PATH = ROOT / 'docs/abductive-evaluation-protocol-v1.json'
SPLITS = ('train', 'development', 'reserved')
TASKS = ('inference', 'abduction', 'revision')
STATUSES = {'OK', 'INCONSISTENT_EVIDENCE', 'MODEL_MISMATCH'}
MAX_FILE_BYTES = 64 * 1024 * 1024


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('nonfinite JSON number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def protocol():
    return strict_json(PROTOCOL_PATH.read_bytes())


def source_hashes():
    return {name: exact.sha((ROOT / name).read_bytes()) for name in (
        'tools/exact_teacher.py', 'tools/abductive_benchmark.py',
        'tools/abductive_scoring.py', 'docs/abductive-evaluation-protocol-v1.json')}


@lru_cache(maxsize=1)
def catalog():
    """Select by topology only, before seeing generated labels or model outcomes."""
    edges = list(itertools.combinations(range(5), 2))
    graphs = {}
    for mask in range(1 << len(edges)):
        graph = tuple(tuple(a for k, (a, b) in enumerate(edges)
                            if b == child and mask >> k & 1) for child in range(5))
        if max(map(len, graph)) > 2 or sum(not p for p in graph) > 3:
            continue
        ancestors = {4}
        for child in reversed(range(5)):
            if child in ancestors:
                ancestors.update(graph[child])
        if len(ancestors) != 5:
            continue
        graphs.setdefault(exact._graph_key(graph), graph)
    selected = sorted(graphs.items())
    result, offset = {}, 0
    for split in SPLITS:
        count = protocol()['splits'][split]
        for key, graph in selected[offset:offset + count]:
            result[key] = (split, graph)
        offset += count
    if len(result) != offset:
        raise ValueError('not enough distinct graph families')
    old = {exact._graph_key(graph) for _, graph in exact.FAMILIES.values()}
    if old.intersection(result):
        raise ValueError('historical family reused')
    return result


def make_question(family, variant):
    if family not in catalog() or type(variant) is not int or not 0 <= variant < 32:
        raise ValueError('unknown family or variant')
    graph = catalog()[family][1]
    scenario, scale = variant % 8, variant // 8
    denominators = (11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71,
                    73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151)
    # Names and target order vary independently of labels; every parent matters.
    order = sorted(range(5), key=lambda i: exact.sha(f'{family}/{variant}/{i}'.encode()))
    names = {i: f'x{order[i]}' for i in range(5)}
    nodes = []
    for i, parents in enumerate(graph):
        cpt = {}
        for bits in itertools.product('01', repeat=len(parents)):
            if not parents:
                denominator = denominators[variant]
                p = Fraction(1 + (3 * variant + i + 2) % (denominator - 1), denominator)
            elif scenario in (3, 6):
                p = Fraction(any(bit == '1' for bit in bits))
            elif scenario == 7:
                p = Fraction(sum(bit == '1' for bit in bits) % 2)
            else:
                p = Fraction(8 + scale, 10 + scale) if '1' in bits else Fraction(1, 10 + scale)
            cpt[''.join(bits)] = str(p)
        nodes.append({'id': names[i], 'parents': [names[p] for p in parents], 'p_true': cpt})
    roots = [node['id'] for node in nodes if not node['parents']]
    hypotheses = [{'id': f'h{i}', 'condition': [{name: True}]} for i, name in enumerate(roots)]
    hypotheses.append({'id': 'h_none', 'condition': [{name: False for name in roots}]})
    if len(roots) > 1:
        hypotheses.append({'id': 'h_all', 'condition': [{name: True for name in roots}]})
    target = roots[0]
    actions = [{'id': 'yes', 'condition': [{target: True}], 'if_true': '1', 'if_false': '0'},
               {'id': 'no', 'condition': [{target: False}], 'if_true': '1', 'if_false': '0'}]
    if scenario == 5:
        actions.append({'id': 'defer', 'condition': [{}], 'if_true': '2', 'if_false': '2'})
    evidence = [{'id': 'r0', 'event': nodes[-1]['id'], 'value': True}]
    if scenario == 1:
        evidence.append(dict(evidence[0], id='r1'))
    if scenario == 2:
        evidence.append(dict(evidence[0], id='r1', value=False))
    if scenario == 3:
        evidence += [{'id': f'r{i + 1}', 'event': name, 'value': False} for i, name in enumerate(roots)]
    if scenario == 4:
        evidence = []
    question = {'schema_version': 1, 'model': {'nodes': nodes}, 'evidence': evidence,
                'hypotheses': hypotheses, 'queries': deepcopy(hypotheses), 'actions': actions,
                'inspections': [{'event': node['id'], 'cost': '1' if scenario == 4 else
                                 '1/3' if node['id'] in roots else '0' if scenario == 7 else '1/20'}
                                for node in nodes]}
    exact.validate(question)
    return question


def timeline(question):
    event = question['model']['nodes'][-1]['id']
    def observe(identifier, available, value):
        return {'id': identifier, 'kind': 'observation', 'event': event, 'value': value,
                'observed_at': 0, 'available_at': available}
    return [observe('first', 1, True), observe('copy', 2, True),
            {'id': 'withdraw_first', 'kind': 'retraction', 'target': 'first', 'available_at': 3},
            {'id': 'withdraw_copy', 'kind': 'retraction', 'target': 'copy', 'available_at': 3},
            observe('corrected', 3, False), observe('future', 4, True)]


def active_evidence(records, as_of, names):
    if type(as_of) is not int or not 0 <= as_of <= 100:
        raise ValueError('bounded integer cutoff required')
    exact._list(records, 0, 32)
    seen, active, previous_time = set(), {}, -1
    observations = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError('record must be an object')
        kind = record.get('kind')
        expected = ({'id', 'kind', 'event', 'value', 'observed_at', 'available_at'}
                    if kind == 'observation' else {'id', 'kind', 'target', 'available_at'})
        exact._keys(record, expected)
        identifier, available = exact._name(record['id']), record['available_at']
        if (identifier in seen or type(available) is not int or
                not previous_time <= available <= as_of or available < 0):
            raise ValueError('duplicate, unordered or future record')
        seen.add(identifier)
        previous_time = available
        if kind == 'observation':
            if (record['event'] not in names or type(record['value']) is not bool or
                    type(record['observed_at']) is not int or
                    not 0 <= record['observed_at'] <= available):
                raise ValueError('invalid timed observation')
            observations.add(identifier)
            active[identifier] = {'id': identifier, 'event': record['event'], 'value': record['value']}
        elif kind == 'retraction':
            if record['target'] not in observations or record['target'] not in active:
                raise ValueError('retraction must name an active prior observation')
            del active[record['target']]
        else:
            raise ValueError('unknown record kind')
    return list(active.values())


def abduction_question(payload):
    exact._keys(payload, {'task', 'model', 'evidence', 'cause_variables', 'prediction_events', 'max_explanations'})
    roots, events = payload['cause_variables'], payload['prediction_events']
    exact._list(roots, 1, 3)
    exact._list(events, 0, 8)
    if len(set(roots)) != len(roots) or len(set(events)) != len(events):
        raise ValueError('duplicate root or prediction event')
    if type(payload['max_explanations']) is not int or payload['max_explanations'] != 8:
        raise ValueError('fixed explanation cap required')
    hypotheses = [{'id': f'c{i}', 'condition': [dict(zip(roots, bits))]}
                  for i, bits in enumerate(itertools.product((False, True), repeat=len(roots)))]
    question = {'schema_version': 1, 'model': payload['model'], 'evidence': payload['evidence'],
                'hypotheses': hypotheses, 'queries': deepcopy(hypotheses),
                'actions': [{'id': 'wait', 'condition': [{}], 'if_true': '0', 'if_false': '0'}],
                'inspections': []}
    nodes = exact.validate(question)
    if set(roots) != {node['id'] for node in nodes if not node['parents']}:
        raise ValueError('cause variables must be all declared roots')
    if set(events) - {node['id'] for node in nodes} or set(events) & {e['event'] for e in payload['evidence']}:
        raise ValueError('prediction events must be known and unobserved')
    return question


def input_question(payload):
    if not isinstance(payload, dict):
        raise ValueError('input object required')
    task = payload.get('task')
    if task == 'abduction':
        return abduction_question(payload)
    if task == 'inference':
        exact._keys(payload, {'task', 'question'})
        exact.validate(payload['question'])
        return payload['question']
    if task == 'revision':
        exact._keys(payload, {'task', 'question', 'as_of', 'records'})
        question = deepcopy(payload['question'])
        nodes = exact.validate(question)
        if question['evidence']:
            raise ValueError('timeline is the only evidence source')
        question['evidence'] = active_evidence(payload['records'], payload['as_of'], {n['id'] for n in nodes})
        exact.validate(question)
        return question
    raise ValueError('unknown task')


def reference(payload):
    question = input_question(payload)
    solved = exact.solve(question)
    if payload['task'] == 'abduction':
        explanations = []
        if solved['status'] == 'OK':
            for hypothesis in question['hypotheses']:
                key = hypothesis['id']
                if Fraction(solved['posterior'][key]) > 0:
                    explanations.append({'assignment': hypothesis['condition'][0],
                                         'probability': solved['posterior'][key],
                                         'predictions': {event: solved['hypothesis_predictions'][key]['predictions'][event]
                                                         for event in payload['prediction_events']}})
        return {'status': solved['status'], 'explanations': explanations}
    result = {'status': solved['status'], 'posterior': solved['posterior'],
              'action_values': {}, 'inspections': {}, 'normalizer': None}
    if payload['task'] == 'revision':
        result['active_evidence_ids'] = sorted(e['id'] for e in question['evidence'])
    if solved['status'] != 'OK':
        return result
    result['action_values'] = solved['decision']['action_values']
    values = [Fraction(action[field]) for action in question['actions'] for field in ('if_true', 'if_false')]
    costs = [Fraction(i['cost']) for i in question['inspections']]
    result['normalizer'] = str(max(values) - min(values) + max(costs, default=Fraction(0)))
    posterior, _ = exact._posterior(exact._worlds(question['model']['nodes']),
                                    {e['event']: e['value'] for e in question['evidence']})
    for event, inspection in solved['inspections'].items():
        branches = {}
        for outcome in (False, True):
            worlds, probability = exact._posterior(posterior, {event: outcome})
            branches[str(outcome).lower()] = {
                'probability': str(probability),
                'action_values': exact._strings(exact._actions(worlds, question['actions'])[0]) if probability else {},
            }
        result['inspections'][event] = {'cost': inspection['cost'], 'branches': branches}
    return result


def episode_inputs(question):
    yield {'task': 'inference', 'question': question}
    roots = [n['id'] for n in question['model']['nodes'] if not n['parents']]
    observed = {e['event'] for e in question['evidence']}
    yield {'task': 'abduction', 'model': question['model'], 'evidence': question['evidence'],
           'cause_variables': roots, 'prediction_events': [n['id'] for n in question['model']['nodes']
                                                         if n['id'] not in observed], 'max_explanations': 8}
    base = dict(question, evidence=[])
    stream = timeline(question)
    for cutoff in (1, 2, 3):
        yield {'task': 'revision', 'question': base, 'as_of': cutoff,
               'records': [r for r in stream if r['available_at'] <= cutoff]}


def generate_split(split, variants=20):
    if split not in SPLITS or type(variants) is not int or not 1 <= variants <= 32:
        raise ValueError('invalid split or variants')
    result = {'agent': [], 'evaluator': []}
    for family, (assignment, _) in catalog().items():
        if assignment != split:
            continue
        for variant in range(variants):
            question = make_question(family, variant)
            episode = exact.sha(exact.canonical(question))
            for payload in episode_inputs(question):
                identifier = exact.sha(exact.canonical(payload))
                result['agent'].append({'id': identifier, 'input': payload})
                result['evaluator'].append({'id': identifier, 'family': family, 'episode': episode,
                                            'reference': reference(payload)})
    return result


def audit_records(data):
    exact._keys(data, SPLITS)
    seen, episodes, families, counts, coverage = set(), {}, {}, {}, {}
    for split in SPLITS:
        exact._keys(data[split], {'agent', 'evaluator'})
        agents, labels = data[split]['agent'], data[split]['evaluator']
        if not agents or len(agents) != len(labels):
            raise ValueError('missing or unaligned records')
        counts[split], coverage[split] = len(agents), Counter()
        for agent, label in zip(agents, labels):
            exact._keys(agent, {'id', 'input'})
            exact._keys(label, {'id', 'family', 'episode', 'reference'})
            identifier = exact.sha(exact.canonical(agent['input']))
            question = input_question(agent['input'])
            signature = exact.structural_signature(question)
            if identifier in seen or agent['id'] != identifier or label['id'] != identifier:
                raise ValueError('duplicate or mismatched input identity')
            if (signature != label['family'] or signature not in catalog() or
                    catalog()[signature][0] != split):
                raise ValueError('family split or effective structure mismatch')
            if label['episode'] in episodes and episodes[label['episode']] != split:
                raise ValueError('episode crosses partitions')
            if label['reference'] != reference(agent['input']):
                raise ValueError('exact reference mismatch')
            seen.add(identifier)
            episodes[label['episode']] = split
            families[signature] = split
            coverage[split][agent['input']['task'] + '/' + label['reference']['status']] += 1
    return {'status': 'PASS', 'counts': counts,
            'family_counts': dict(Counter(families.values())),
            'episode_counts': dict(Counter(episodes.values())),
            'coverage': {split: dict(sorted(values.items())) for split, values in coverage.items()},
            'model_evaluation': 'NOT_RUN', 'confirmatory_ready': False}


def private_write(path, content):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(content)


def file_info(content):
    return {'sha256': exact.sha(content), 'bytes': len(content), 'records': len(content.splitlines())}


def write_dataset(destination, variants=20):
    data = {split: generate_split(split, variants) for split in SPLITS}
    audit = audit_records(data)
    destination = exact._local_path(destination)
    destination.mkdir(mode=0o700, exist_ok=False)
    try:
        files = {}
        for split in SPLITS:
            (destination / split).mkdir(mode=0o700)
            for kind in ('agent', 'evaluator'):
                name = f'{split}/{kind}.jsonl'
                content = b''.join(exact.canonical(row) for row in data[split][kind])
                private_write(destination / name, content)
                files[name] = file_info(content)
        manifest = {'version': protocol()['version'], 'source_hashes': source_hashes(),
                    'variants': variants, 'files': files, 'audit': audit,
                    'status': 'CPU_PREPARATION_NOT_CONFIRMATORY'}
        private_write(destination / 'manifest.json', exact.canonical(manifest))
        return manifest
    except BaseException:
        shutil.rmtree(destination)
        raise


def read_manifest(destination):
    destination = exact._local_path(destination)
    path = destination / 'manifest.json'
    if path.is_symlink() or path.stat().st_size > 1_000_000:
        raise ValueError('unsafe manifest')
    manifest = strict_json(path.read_bytes())
    exact._keys(manifest, {'version', 'source_hashes', 'variants', 'files', 'audit', 'status'})
    if (manifest['version'] != protocol()['version'] or manifest['source_hashes'] != source_hashes()
            or manifest['status'] != 'CPU_PREPARATION_NOT_CONFIRMATORY'
            or type(manifest['variants']) is not int or not 1 <= manifest['variants'] <= 32):
        raise ValueError('source-bound manifest mismatch')
    expected = {f'{s}/{k}.jsonl' for s in SPLITS for k in ('agent', 'evaluator')}
    exact._keys(manifest['files'], expected)
    return destination, manifest


def read_rows(destination, name, manifest):
    path = destination / name
    if any(p.is_symlink() for p in (path, path.parent)) or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('unsafe or oversized data file')
    raw = path.read_bytes()
    if file_info(raw) != manifest['files'][name]:
        raise ValueError('data hash/count mismatch')
    return [strict_json(line) for line in raw.splitlines()]


def audit_dataset(destination):
    destination, manifest = read_manifest(destination)
    if any(p.is_symlink() for p in destination.rglob('*')):
        raise ValueError('symlink dataset member')
    expected = {'manifest.json', *manifest['files']}
    if {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()} != expected:
        raise ValueError('unexpected dataset member')
    data = {s: {k: read_rows(destination, f'{s}/{k}.jsonl', manifest)
                for k in ('agent', 'evaluator')} for s in SPLITS}
    audit = audit_records(data)
    if audit != manifest['audit']:
        raise ValueError('audit metadata mismatch')
    for split in SPLITS:
        if data[split] != generate_split(split, manifest['variants']):
            raise ValueError('data differs from deterministic generator')
    return audit


def export_view(destination, output, *, split='train', training=False):
    """Training reads only train files. Evaluation export reads no label files."""
    if split not in SPLITS or (training and split != 'train'):
        raise ValueError('training export is train-only')
    destination, manifest = read_manifest(destination)
    agents = read_rows(destination, f'{split}/agent.jsonl', manifest)
    for row in agents:
        exact._keys(row, {'id', 'input'})
        input_question(row['input'])
        if row['id'] != exact.sha(exact.canonical(row['input'])):
            raise ValueError('input identity mismatch')
    rows = agents
    if training:
        from tools.abductive_scoring import optimal_response
        labels = read_rows(destination, 'train/evaluator.jsonl', manifest)
        expected = generate_split('train', manifest['variants'])
        if agents != expected['agent'] or labels != expected['evaluator']:
            raise ValueError('training data differs from generator')
        rows = [{'id': a['id'], 'messages': [
            {'role': 'user', 'content': exact.canonical(a['input']).decode().strip()},
            {'role': 'assistant', 'content': exact.canonical(optimal_response(a['input'], l['reference'])).decode().strip()}]}
            for a, l in zip(agents, labels)]
    output = exact._local_path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    try:
        content = b''.join(exact.canonical(row) for row in rows)
        private_write(output / 'records.jsonl', content)
        receipt = {'kind': 'training' if training else 'inputs_only', 'split': split,
                   'source_manifest_sha256': exact.sha(exact.canonical(manifest)),
                   'file': file_info(content), 'runtime_isolation': 'NOT_PROVEN_BY_FILE_EXPORT'}
        private_write(output / 'receipt.json', exact.canonical(receipt))
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
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('abductive benchmark failed: ' + type(error).__name__, file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
