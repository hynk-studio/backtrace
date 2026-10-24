"""Small exact CPU teacher; no model, training, network, or competition inputs.

Questions declare finite Boolean Bayesian DAGs, observed events, propositions,
utilities and inspection costs. Enumeration is exact and bounded. An inspection
is a single observation followed by one action, not a multi-step search policy.
"""
import argparse
from collections import Counter
from fractions import Fraction
from functools import lru_cache
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
VERSION = 'finite-dag-exact-v1'
MAX_VARIABLES = 8
MAX_VARIANTS = 128
NAME = re.compile(r'[a-z][a-z0-9_]{0,31}\Z')
QUESTION_KEYS = {'schema_version', 'model', 'evidence', 'hypotheses', 'queries',
                 'actions', 'inspections'}
# Different unlabeled DAGs, not renamed/seed-only copies across the split.
FAMILIES = {
    'binary_sensor': ('train', ((), (0,))),
    'shared_noise': ('train', ((), (), (0, 1), (0, 1))),
    'simultaneous_causes': ('train', ((), (), (0, 1))),
    'mediated_chain': ('eval', ((), (0,), (1,))),
    'redundant_routes': ('eval', ((), (0,), (0,), (1, 2))),
    'interacting_causes': ('eval', ((), (), (0, 1), (2,))),
}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
            + '\n').encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rational(value, *, probability=False, nonnegative=False):
    """Refuse floating point, booleans and unbounded integer strings."""
    if type(value) is int:
        result = Fraction(value)
    elif isinstance(value, str) and re.fullmatch(r'-?\d{1,7}(?:/[1-9]\d{0,6})?', value):
        result = Fraction(value)
    else:
        raise ValueError('exact bounded integer or rational string required')
    if abs(result.numerator) > 1_000_000 or result.denominator > 1_000_000:
        raise ValueError('rational magnitude exceeds teacher bound')
    if probability and not 0 <= result <= 1:
        raise ValueError('probability outside [0,1]')
    if nonnegative and result < 0:
        raise ValueError('negative inspection cost')
    return result


def _name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError('bounded identifier required')
    return value


def _keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError('unexpected schema fields')


def _list(value, minimum, maximum):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError('list size outside teacher bound')
    return value


def _condition(value, names):
    # Disjunctive normal form: OR of AND clauses; [] is false and [{}] true.
    for clause in _list(value, 0, MAX_VARIABLES):
        if not isinstance(clause, dict) or set(clause) - names:
            raise ValueError('unknown proposition variable')
        if any(type(bit) is not bool for bit in clause.values()):
            raise ValueError('Boolean proposition values required')


def validate(question):
    _keys(question, QUESTION_KEYS)
    if type(question['schema_version']) is not int or question['schema_version'] != 1:
        raise ValueError('unsupported question schema')
    _keys(question['model'], {'nodes'})
    nodes = _list(question['model']['nodes'], 1, MAX_VARIABLES)
    names = set()
    for node in nodes:
        _keys(node, {'id', 'parents', 'p_true'})
        identifier = _name(node['id'])
        parents = _list(node['parents'], 0, MAX_VARIABLES - 1)
        if (identifier in names or len(parents) != len(set(parents))
                or any(parent not in names for parent in parents)):
            raise ValueError('unique topologically ordered DAG required')
        expected = {''.join(bits) for bits in itertools.product('01', repeat=len(parents))}
        _keys(node['p_true'], expected)
        for probability in node['p_true'].values():
            rational(probability, probability=True)
        names.add(identifier)
    for field in ('hypotheses', 'queries'):
        identifiers = set()
        for item in _list(question[field], 1, 16):
            _keys(item, {'id', 'condition'})
            if _name(item['id']) in identifiers:
                raise ValueError('duplicate proposition identifier')
            identifiers.add(item['id'])
            _condition(item['condition'], names)
    identifiers = set()
    for action in _list(question['actions'], 1, 16):
        _keys(action, {'id', 'condition', 'if_true', 'if_false'})
        if _name(action['id']) in identifiers:
            raise ValueError('duplicate action identifier')
        identifiers.add(action['id'])
        _condition(action['condition'], names)
        rational(action['if_true'])
        rational(action['if_false'])
    inspections = set()
    for inspection in _list(question['inspections'], 0, MAX_VARIABLES):
        _keys(inspection, {'event', 'cost'})
        event = inspection['event']
        if event not in names or event in inspections:
            raise ValueError('unique known inspection event required')
        inspections.add(event)
        rational(inspection['cost'], nonnegative=True)
    evidence_ids = {}
    for evidence in _list(question['evidence'], 0, 32):
        _keys(evidence, {'id', 'event', 'value'})
        identifier = _name(evidence['id'])
        if evidence['event'] not in names or type(evidence['value']) is not bool:
            raise ValueError('known Boolean evidence event required')
        identity = (evidence['event'], evidence['value'])
        if identifier in evidence_ids and evidence_ids[identifier] != identity:
            raise ValueError('one evidence ID cannot identify different observations')
        evidence_ids[identifier] = identity
    return nodes


def _matches(condition, world):
    return any(all(world[name] == value for name, value in clause.items())
               for clause in condition)


def _worlds(nodes):
    worlds = []
    for bits in itertools.product((False, True), repeat=len(nodes)):
        world = dict(zip((node['id'] for node in nodes), bits))
        weight = Fraction(1)
        for node in nodes:
            key = ''.join('1' if world[parent] else '0' for parent in node['parents'])
            p = rational(node['p_true'][key], probability=True)
            weight *= p if world[node['id']] else 1 - p
        if weight:
            worlds.append((world, weight))
    if sum(weight for _, weight in worlds) != 1:
        raise AssertionError('normalized CPTs must yield unit mass')
    return worlds


def _posterior(worlds, observed):
    compatible = [(world, weight) for world, weight in worlds
                  if all(world[name] == value for name, value in observed.items())]
    mass = sum((weight for _, weight in compatible), Fraction(0))
    return ([(world, weight / mass) for world, weight in compatible] if mass else []), mass


def _probability(worlds, condition):
    return sum((weight for world, weight in worlds if _matches(condition, world)), Fraction(0))


def _probabilities(worlds, propositions):
    return {item['id']: _probability(worlds, item['condition']) for item in propositions}


def _best(values):
    largest = max(values.values())
    return largest, sorted(key for key, value in values.items() if value == largest)


def _actions(worlds, actions):
    values = {}
    for action in actions:
        p = _probability(worlds, action['condition'])
        values[action['id']] = p * rational(action['if_true']) + (1-p) * rational(action['if_false'])
    best_value, best_actions = _best(values)
    return values, best_value, best_actions


def _strings(values):
    return {key: str(value) for key, value in values.items()}


def solve(question):
    """Return evaluator labels. Never inject this return value into agent input."""
    nodes = validate(question)
    prior = _worlds(nodes)
    observed, seen_ids = {}, set()
    duplicates = 0
    contradiction = False
    for item in question['evidence']:
        event, value = item['event'], item['value']
        if item['id'] in seen_ids or (event in observed and observed[event] == value):
            duplicates += 1
        if event in observed and observed[event] != value:
            contradiction = True
        observed[event] = value
        seen_ids.add(item['id'])
    answer = {'teacher_version': VERSION, 'status': 'OK',
              'reference': 'exact joint distribution of the declared Boolean DAG',
              'observations': {'received': len(question['evidence']), 'distinct_events': len(observed),
                               'duplicate_records_ignored': duplicates},
              'hypothesis_semantics': 'marginal propositions; not necessarily exclusive causes'}
    if contradiction:
        return dict(answer, status='INCONSISTENT_EVIDENCE', posterior=None, decision=None,
                    explanation='the same event is asserted both true and false')
    posterior, evidence_mass = _posterior(prior, observed)
    answer['evidence_probability'] = str(evidence_mass)
    if not posterior:
        return dict(answer, status='MODEL_MISMATCH', posterior=None, decision=None,
                    explanation='coherent observations have zero probability under the declared model; no missing cause is identified')
    hypotheses = _probabilities(posterior, question['hypotheses'])
    before = _probabilities(prior, question['hypotheses'])
    prior_leaders = _best(before)[1]
    current_leaders = _best(hypotheses)[1]
    query_probabilities = _probabilities(posterior, question['queries'])
    values, best_value, best_actions = _actions(posterior, question['actions'])
    answer.update({
        'prior_hypotheses': _strings(before), 'posterior': _strings(hypotheses),
        'prior_leaders': prior_leaders, 'posterior_leaders': current_leaders,
        'leader_overturned': not set(prior_leaders).intersection(current_leaders),
        'queries': {name: {'probability': str(p), 'logical_status':
                          'ENTAILED' if p == 1 else 'REFUTED' if p == 0 else 'UNKNOWN'}
                    for name, p in query_probabilities.items()},
        'predictions': {node['id']: str(_probability(posterior, [{node['id']: True}]))
                        for node in nodes if node['id'] not in observed},
        'decision': {'action_values': _strings(values), 'best_value': str(best_value),
                     'best_actions': best_actions}, 'inspections': {},
    })
    forward = {}
    for hypothesis in question['hypotheses']:
        probability = hypotheses[hypothesis['id']]
        conditional = [(world, weight / probability) for world, weight in posterior
                       if _matches(hypothesis['condition'], world)] if probability else []
        forward[hypothesis['id']] = {
            'status': 'DEFINED' if probability else 'ZERO_PROBABILITY_CONDITION',
            'predictions': {node['id']: str(_probability(conditional, [{node['id']: True}]))
                            for node in nodes if node['id'] not in observed} if probability else None,
        }
    answer['hypothesis_predictions'] = forward
    net_values = {}
    for inspection in question['inspections']:
        event = inspection['event']
        expected = Fraction(0)
        branches = []
        informative = False
        for outcome in (False, True):
            branch, probability = _posterior(posterior, {event: outcome})
            if not probability:
                continue
            _, value, actions = _actions(branch, question['actions'])
            conditional = _probabilities(branch, question['hypotheses'])
            informative |= conditional != hypotheses
            expected += probability * value
            branches.append({'outcome': outcome, 'probability': str(probability),
                             'posterior': _strings(conditional), 'best_actions': actions,
                             'best_value': str(value)})
        gross = expected - best_value
        if gross < 0:
            raise AssertionError('free observation cannot lower optimal expected utility')
        cost = rational(inspection['cost'], nonnegative=True)
        net = gross - cost
        net_values[event] = net
        answer['inspections'][event] = {
            'already_observed': event in observed, 'informative_about_hypotheses': informative,
            'expected_best_action_value': str(expected), 'gross_value': str(gross),
            'cost': str(cost), 'net_value': str(net), 'outcomes': branches,
        }
    maximum = max(net_values.values(), default=Fraction(0))
    answer['recommendation'] = {
        'mode': 'INSPECT' if maximum > 0 else 'STOP',
        'inspections': sorted(event for event, value in net_values.items() if value == maximum) if maximum > 0 else [],
        'stop_actions': best_actions,
        'zero_net_ties': sorted(event for event, value in net_values.items() if value == 0),
        'horizon': 'one inspection, then one action; stop wins zero-net ties',
    }
    return answer


@lru_cache(maxsize=256)
def _graph_key(parent_indices):
    edges = {(parent, child) for child, parents in enumerate(parent_indices) for parent in parents}
    n = len(parent_indices)
    # Canonical directed adjacency across all relabelings (<= 8! permutations).
    smallest = min(''.join('1' if (p[i], p[j]) in edges else '0'
                           for i in range(n) for j in range(n))
                   for p in itertools.permutations(range(n)))
    return sha(f'{n}:{smallest}'.encode())


def structural_signature(question):
    """Unlabeled *effective* DAG; unused declared parents cannot fake separation."""
    nodes = validate(question)
    positions = {node['id']: i for i, node in enumerate(nodes)}
    effective = []
    for node in nodes:
        parents = []
        cpt = {key: rational(value) for key, value in node['p_true'].items()}
        for offset, parent in enumerate(node['parents']):
            if any(cpt[key] != cpt[key[:offset] + '1' + key[offset+1:]]
                   for key in cpt if key[offset] == '0'):
                parents.append(positions[parent])
        effective.append(tuple(parents))
    return _graph_key(tuple(effective))


def make_question(family, variant):
    """Deterministic, authored world families. No sampled latent truth exists."""
    if family not in FAMILIES or type(variant) is not int or not 0 <= variant < MAX_VARIANTS:
        raise ValueError('unknown family or invalid variant')
    _, graph = FAMILIES[family]
    scenario = variant % 8
    scale = variant // 8
    nodes = []
    for index, parents in enumerate(graph):
        cpt = {}
        for assignment in itertools.product('01', repeat=len(parents)):
            key = ''.join(assignment)
            if not parents:
                p = Fraction(1, 2) if scenario == 7 else Fraction(1 + scale, 4 + scale)
            elif scenario in (3, 6):
                # Deterministic parity remains dependent on every declared parent.
                p = Fraction(sum(bit == '1' for bit in assignment) % 2)
            elif family == 'shared_noise':
                p = Fraction(sum(bit == '1' for bit in assignment) % 2)
            else:
                active = any(bit == '1' for bit in assignment)
                p = Fraction(9 + scale, 10 + scale) if active else Fraction(1, 10 + scale)
            cpt[key] = str(p)
        nodes.append({'id': f'v{index}', 'parents': [f'v{p}' for p in parents], 'p_true': cpt})
    # Unequal independent causes make a repeated shared-noise sensor informative.
    if family == 'shared_noise' and scenario != 7:
        nodes[1]['p_true'][''] = '1/10'
    evidence = []
    if scenario in (0, 1):
        evidence = [{'id': 'seen', 'event': nodes[-1]['id'], 'value': True}]
    if scenario == 1:
        evidence += [dict(evidence[0]), dict(evidence[0], id='copied')]
    if scenario == 2:
        evidence = [{'id': 'first', 'event': 'v0', 'value': True},
                    {'id': 'second', 'event': 'v0', 'value': False}]
    if scenario == 3:
        child = next(node for node in nodes if node['parents'])
        evidence = [{'id': f'parent_{i}', 'event': parent, 'value': False}
                    for i, parent in enumerate(child['parents'])]
        evidence += [{'id': 'impossible', 'event': child['id'], 'value': True}]
    if scenario == 6:
        # Infer the unobserved target through a deterministic relation, rather
        # than relabeling an explicitly observed target as logical entailment.
        child = next(node for node in nodes if node['parents'])
        evidence = [{'id': f'known_parent_{i}', 'event': parent, 'value': False}
                    for i, parent in enumerate(child['parents']) if parent != 'v0']
        evidence += [{'id': 'related_observation', 'event': child['id'], 'value': True}]
    yes, no = [{'v0': True}], [{'v0': False}]
    hypotheses = [{'id': 'h_true', 'condition': yes}, {'id': 'h_false', 'condition': no}]
    queries = list(hypotheses)
    if len([parents for parents in graph if not parents]) > 1:
        queries += [{'id': 'both_causes', 'condition': [{'v0': True, 'v1': True}]},
                    {'id': 'either_cause', 'condition': [{'v0': True}, {'v1': True}]}]
    reward = str(Fraction(100 + scale, 100))
    actions = [{'id': 'act_true', 'condition': yes, 'if_true': reward, 'if_false': '0'},
               {'id': 'act_false', 'condition': no, 'if_true': reward, 'if_false': '0'}]
    if scenario == 5:
        actions.append({'id': 'safe', 'condition': [{}], 'if_true': '2', 'if_false': '2'})
    # Direct cause inspection is expensive; indirect sensors can be optimal.
    # High costs force stopping; zero-cost non-root tests preserve exact ties.
    inspections = [{'event': node['id'], 'cost':
                    '1' if scenario == 4 else '1/3' if node['id'] == 'v0'
                    else '0' if scenario == 7 else '1/20'} for node in nodes]
    return {'schema_version': 1, 'model': {'nodes': nodes}, 'evidence': evidence,
            'hypotheses': hypotheses, 'queries': queries, 'actions': actions,
            'inspections': inspections}


def _coverage(labels):
    counts = Counter()
    for label in labels:
        answer = label['answer']
        counts[answer['status']] += 1
        counts['duplicate_evidence_cases'] += answer['observations']['duplicate_records_ignored'] > 0
        if answer['status'] != 'OK':
            continue
        counts[answer['recommendation']['mode']] += 1
        counts['prior_leader_overturned'] += answer['leader_overturned']
        counts['posterior_ties'] += len(answer['posterior_leaders']) > 1
        counts['ambiguous_propositions'] += any(q['logical_status'] == 'UNKNOWN' for q in answer['queries'].values())
        for query in answer['queries'].values():
            counts['query_' + query['logical_status'].lower()] += 1
        counts['possible_simultaneous_causes'] += ('both_causes' in answer['queries']
                                                  and Fraction(answer['queries']['both_causes']['probability']) > 0)
        counts['informative_zero_value_cases'] += any(
            item['informative_about_hypotheses'] and Fraction(item['gross_value']) == 0
            for item in answer['inspections'].values())
        counts['cost_blocks_positive_value_cases'] += any(
            Fraction(item['gross_value']) > 0 and Fraction(item['net_value']) <= 0
            for item in answer['inspections'].values())
    return dict(sorted(counts.items()))


def generate(variants_per_family=8):
    if type(variants_per_family) is not int or not 1 <= variants_per_family <= MAX_VARIANTS:
        raise ValueError('variants per family must be between 1 and 128')
    data = {split: {'agent': [], 'evaluator': []} for split in ('train', 'eval')}
    for family, (split, _) in FAMILIES.items():
        for variant in range(variants_per_family):
            question = make_question(family, variant)
            identifier = sha(canonical(question))
            data[split]['agent'].append({'id': identifier, 'question': question})
            data[split]['evaluator'].append({'id': identifier, 'family': family,
                                            'structural_signature': structural_signature(question),
                                            'answer': solve(question)})
    audit = audit_records(data)
    return data, audit


def audit_records(data):
    """Recompute labels, verify alignment and reject effective-topology leakage."""
    _keys(data, {'train', 'eval'})
    signatures, identifiers = {}, {}
    coverage = {}
    for split in ('train', 'eval'):
        _keys(data[split], {'agent', 'evaluator'})
        agents, labels = data[split]['agent'], data[split]['evaluator']
        _list(agents, 1, 3 * MAX_VARIANTS)
        _list(labels, 1, 3 * MAX_VARIANTS)
        if len(agents) != len(labels):
            raise ValueError('missing or unaligned teacher records')
        signatures[split], identifiers[split] = set(), set()
        for agent, label in zip(agents, labels):
            _keys(agent, {'id', 'question'})
            _keys(label, {'id', 'family', 'structural_signature', 'answer'})
            identifier = sha(canonical(agent['question']))
            signature = structural_signature(agent['question'])
            if identifier in identifiers[split]:
                raise ValueError('duplicate question identity')
            if agent['id'] != identifier or label['id'] != identifier:
                raise ValueError('question/label identity mismatch')
            if signature != label['structural_signature'] or label['answer'] != solve(agent['question']):
                raise ValueError('structural signature or exact label mismatch')
            if label['family'] not in FAMILIES or FAMILIES[label['family']][0] != split:
                raise ValueError('family assigned to wrong split')
            if signature != _graph_key(FAMILIES[label['family']][1]):
                raise ValueError('question does not have its declared family structure')
            identifiers[split].add(identifier)
            signatures[split].add(signature)
        coverage[split] = _coverage(labels)
    if identifiers['train'] & identifiers['eval'] or signatures['train'] & signatures['eval']:
        raise ValueError('train/eval structural or exact-question leakage')
    return {'status': 'PASS', 'method': 'disjoint authored families and unlabeled effective DAGs',
            'counts': {split: len(identifiers[split]) for split in identifiers},
            'structural_signatures': {split: sorted(values) for split, values in signatures.items()},
            'family_assignments': {name: values[0] for name, values in FAMILIES.items()},
            'coverage': coverage,
            'limitations': 'shared Boolean primitives; small authored family set; no real-code transfer claim'}


def _local_path(destination):
    destination = Path(destination).absolute()
    local = ROOT / '.local'
    local.mkdir(mode=0o700, exist_ok=True)
    if local.is_symlink():
        raise ValueError('local output root must not be a symlink')
    if not destination.is_relative_to(local) or destination == local:
        raise ValueError('teacher output must be a new directory beneath repository .local')
    if any(part.is_symlink() for part in [destination, *destination.parents] if part.is_relative_to(local)):
        raise ValueError('symlink output path refused')
    if not destination.resolve().is_relative_to(local.resolve()):
        raise ValueError('output path escapes local root')
    return destination


def write_dataset(destination, variants_per_family=8):
    data, audit = generate(variants_per_family)
    destination = _local_path(destination)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        files = {}
        for split in ('train', 'eval'):
            (destination / split).mkdir(mode=0o700)
            for kind in ('agent', 'evaluator'):
                name = f'{split}/{kind}.jsonl'
                content = b''.join(canonical(row) for row in data[split][kind])
                descriptor = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(content)
                files[name] = {'sha256': sha(content), 'bytes': len(content), 'records': len(data[split][kind])}
        manifest = {'schema_version': 1, 'teacher_version': VERSION,
                    'generator_sha256': sha(Path(__file__).read_bytes()),
                    'variants_per_family': variants_per_family, 'files': files, 'audit': audit,
                    'training': 'NOT RUN', 'model_evaluation': 'NOT RUN',
                    'agent_input_policy': 'question/model only; labels and family metadata in evaluator files'}
        descriptor = os.open(destination / 'manifest.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(canonical(manifest))
        return manifest
    except BaseException:
        shutil.rmtree(destination)
        raise


def audit_dataset(destination):
    destination = _local_path(destination)
    expected = {'manifest.json', 'train/agent.jsonl', 'train/evaluator.jsonl',
                'eval/agent.jsonl', 'eval/evaluator.jsonl'}
    if any(path.is_symlink() for path in destination.rglob('*')):
        raise ValueError('symlink dataset member refused')
    if {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()} != expected:
        raise ValueError('unexpected dataset files')
    manifest = json.loads((destination / 'manifest.json').read_bytes())
    data = {split: {} for split in ('train', 'eval')}
    for split in ('train', 'eval'):
        for kind in ('agent', 'evaluator'):
            name = f'{split}/{kind}.jsonl'
            raw = (destination / name).read_bytes()
            rows = [json.loads(line) for line in raw.splitlines()]
            if manifest['files'][name] != {'sha256': sha(raw), 'bytes': len(raw), 'records': len(rows)}:
                raise ValueError('dataset file hash/count mismatch')
            data[split][kind] = rows
    audit = audit_records(data)
    if (audit != manifest['audit'] or manifest['teacher_version'] != VERSION
            or manifest['generator_sha256'] != sha(Path(__file__).read_bytes())):
        raise ValueError('manifest audit/version mismatch')
    expected_data, expected_audit = generate(manifest['variants_per_family'])
    if data != expected_data or audit != expected_audit:
        raise ValueError('dataset differs from recorded deterministic generator parameters')
    return audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    generation = commands.add_parser('generate')
    generation.add_argument('destination', type=Path)
    generation.add_argument('--variants-per-family', type=int, default=8)
    auditing = commands.add_parser('audit')
    auditing.add_argument('destination', type=Path)
    args = parser.parse_args(argv)
    try:
        result = (write_dataset(args.destination, args.variants_per_family) if args.command == 'generate'
                  else audit_dataset(args.destination))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('exact teacher failed: ' + type(error).__name__, file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
