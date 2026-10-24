"""CPU-only preparation of a preregistered, budget-matched R0/R1/R2 pilot.

No provider API, model, evaluator, launch permit or production driver is invoked.
Task selection reads the private pinned JSONL but emits only IDs/repository/commit
metadata. Candidate archives are private local outputs, never official validation.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / 'docs/research-comparison-protocol.json'
ARMS = ('R0', 'R1', 'R2')
BUDGET = {'session_seconds': 300, 'charged_tool_calls': 30,
          'total_model_requests': 50, 'command_seconds': 60,
          'agent_child_seconds': 330}
PROMPT_PATHS = tuple('research/prompts/' + name + '.md' for name in (
    'common-system', 'common-analyzer', 'r1-system', 'r1-analyzer',
    'r2-system', 'r2-analyzer'))
OUTCOMES = ('RESOLVED', 'INCORRECT', 'TIMEOUT', 'PARTIAL_PATCH', 'NO_PATCH',
            'MODEL_ERROR', 'INFRA_FAILURE', 'INVALID_ARTIFACT', 'NOT_RUN')
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
SHA1 = re.compile(r'[0-9a-f]{40}\Z')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON object key')
        result[key] = value
    return result


def parse(data):
    try:
        return json.loads(data, object_pairs_hook=_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, UnicodeError):
        raise ValueError('invalid or ambiguous JSON') from None


def read_file(path, limit):
    path = Path(path).absolute()
    if (path.is_symlink() or path.resolve() != path or not path.is_file()
            or path.stat().st_size > limit):
        raise ValueError('regular bounded source file required')
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('source exceeds size limit')
    return data


def _source(root, name):
    path = root / name
    if path.resolve().parent != root.resolve() and root.resolve() not in path.resolve().parents:
        raise ValueError('protocol source escapes repository')
    return read_file(path, 8 * 1024**2)


def load_protocol(path=PROTOCOL_PATH, root=ROOT):
    protocol = parse(read_file(path, 512 * 1024))
    if (protocol.get('schema_version') != 1
            or protocol.get('protocol') != 'R012-matched-pilot-v1'
            or protocol.get('arms') != list(ARMS)
            or protocol.get('budget') != BUDGET
            or protocol.get('repetitions') != 1
            or protocol.get('compute_authorization') != 'NONE'
            or set(protocol.get('prompt_files', {})) != set(PROMPT_PATHS)):
        raise ValueError('unrecognized comparison protocol or unequal budget')
    for name, expected in protocol['prompt_files'].items():
        if digest(_source(root, name)) != expected:
            raise ValueError('prompt identity changed; version the protocol explicitly')
    for name, expected in protocol['frozen_source_files'].items():
        if digest(_source(root, name)) != expected:
            raise ValueError('historical runtime source changed')
    selection = protocol['selection']
    if (selection['primary_tasks'] != 6 or selection['reserve_tasks'] != 6
            or selection['excluded_instance_ids'] != ['fastapi_11194']
            or not {'fastapi/fastapi', 'tiangolo/fastapi'} <= set(selection['excluded_repositories'])
            or selection['metadata_sha256'] != 'e4b3fd60f69dbc2b9213e54eeb9636db78aefe92c1d06269d73d9f5f8f3c8ad6'
            or selection['metadata_bytes'] != 1984455
            or selection['distinct_ids'] != 129):
        raise ValueError('task source, exclusion or planned sample changed')
    return protocol


def _replace(data, before, after):
    if data.count(before) != 1:
        raise ValueError('unexpected pinned baseline shape')
    return data.replace(before, after, 1)


def candidate_files(files, protocol, prompts):
    expected = protocol['baseline']['files']
    if set(files) != set(expected) or any(digest(files[k]) != v for k, v in expected.items()):
        raise ValueError('exact original R0-clean six-file baseline required')
    if (set(prompts) != set(protocol['prompt_files'])
            or any(digest(prompts[k]) != v for k, v in protocol['prompt_files'].items())):
        raise ValueError('frozen authored prompt bytes required')
    common = dict(files)
    common['eval_config.yaml'] = _replace(common['eval_config.yaml'],
        b'max_tool_calls: 10', b'max_tool_calls: 30')
    common['eval_config.yaml'] = _replace(common['eval_config.yaml'],
        b'max_time_minutes: 1', b'max_time_minutes: 5')
    common['prompts/system.md'] = _replace(common['prompts/system.md'],
        b'(under 8\xe2\x80\x9310 turns)', b'(within the declared shared task budget)')
    common['prompts/system.md'] = _replace(common['prompts/system.md'],
        b'use `search_similar_code` with keywords from the error message',
        b'use `search_similar_code` with an indexed function or class identifier')
    for role in ('system', 'analyzer'):
        common['prompts/' + role + '.md'] += b'\n' + prompts['research/prompts/common-' + role + '.md']
    arms = {'R0': common}
    for arm, predecessor in (('R1', 'R0'), ('R2', 'R1')):
        arms[arm] = dict(arms[predecessor])
        for role in ('system', 'analyzer'):
            arms[arm]['prompts/' + role + '.md'] += b'\n' + prompts[
                'research/prompts/' + arm.lower() + '-' + role + '.md']
    validate_matched(arms, expected)
    return arms


def validate_matched(arms, expected_paths):
    if set(arms) != set(ARMS) or any(set(files) != set(expected_paths) for files in arms.values()):
        raise ValueError('all three exact candidate closures required')
    prompt_paths = {'prompts/system.md', 'prompts/analyzer.md'}
    for name in set(expected_paths) - prompt_paths:
        if len({arms[arm][name] for arm in ARMS}) != 1:
            raise ValueError('nonprompt files or budgets differ between arms')
    for role in prompt_paths:
        if not (arms['R1'][role].startswith(arms['R0'][role])
                and arms['R2'][role].startswith(arms['R1'][role])
                and len(arms['R0'][role]) < len(arms['R1'][role]) < len(arms['R2'][role])):
            raise ValueError('arm interventions must be nested prompt additions')


def archive_bytes(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, files[name])
    return output.getvalue()


def _read_baseline(data, protocol):
    baseline = protocol['baseline']
    if len(data) != baseline['archive_bytes'] or digest(data) != baseline['archive_sha256']:
        raise ValueError('baseline archive identity mismatch')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if (len(members) != len(baseline['files'])
                    or {m.filename for m in members} != set(baseline['files'])
                    or any(m.is_dir() or m.file_size > 128 * 1024
                           or stat.S_ISLNK(m.external_attr >> 16) for m in members)):
                raise ValueError('invalid baseline archive membership')
            return {name: archive.read(name) for name in baseline['files']}
    except (zipfile.BadZipFile, RuntimeError):
        raise ValueError('invalid baseline archive') from None


def _new_output(path, data):
    path = Path(path).absolute()
    if path.parent.resolve() != path.parent or not path.parent.is_dir():
        raise ValueError('existing output parent without symlinks required')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def build(baseline_path, destination, protocol, root=ROOT):
    files = _read_baseline(read_file(baseline_path, 128 * 1024), protocol)
    prompts = {name: _source(root, name) for name in protocol['prompt_files']}
    arms = candidate_files(files, protocol, prompts)
    archives = {arm + '.zip': archive_bytes(arms[arm]) for arm in ARMS}
    receipt = {'schema_version': 1, 'protocol': protocol['protocol'],
        'protocol_sha256': digest(encoded(protocol)), 'budget': protocol['budget'],
        'baseline_sha256': protocol['baseline']['archive_sha256'],
        'arms': {arm: {'archive_sha256': digest(archives[arm + '.zip']),
                      'archive_bytes': len(archives[arm + '.zip']),
                      'files': {k: digest(v) for k, v in arms[arm].items()}}
                 for arm in ARMS},
        'nonprompt_equality': 'PASS', 'official_cpu_validation': 'NOT RUN',
        'model_execution': 'NOT RUN', 'runner_integration': 'NOT RUN',
        'total_model_request_accounting': 'NOT RUN', 'token_accounting': 'NOT RUN'}
    archives['assembly-receipt.json'] = encoded(receipt)
    target = Path(destination).absolute()
    if target.parent.resolve() != target.parent or not target.parent.is_dir():
        raise ValueError('existing output parent without symlinks required')
    if target == Path(baseline_path).absolute() or target in Path(baseline_path).absolute().parents:
        raise ValueError('output must not contain the baseline input')
    os.mkdir(target, 0o700)
    try:
        for name, data in archives.items():
            _new_output(target / name, data)
    except BaseException:
        shutil.rmtree(target)
        raise
    return receipt


def select_tasks(data, protocol):
    policy = protocol['selection']
    if len(data) != policy['metadata_bytes'] or digest(data) != policy['metadata_sha256']:
        raise ValueError('pinned public metadata identity mismatch')
    records = {}
    allowed = set(policy['allowed_fields'])
    required = set(policy['required_fields'])
    for line in data.splitlines():
        if not line.strip():
            continue
        row = parse(line)
        if (not isinstance(row, dict) or not required <= set(row) or set(row) - allowed
                or not isinstance(row.get('instance_id'), str)
                or not ID.fullmatch(row['instance_id'])
                or not isinstance(row.get('repo'), str) or not REPO.fullmatch(row['repo'])
                or not isinstance(row.get('base_commit'), str) or not SHA1.fullmatch(row['base_commit'])
                or not isinstance(row.get('problem_statement'), str)):
            raise ValueError('unrecognized public metadata schema')
        if any(not isinstance(row[k], str) for k in ('patch', 'test_patch', 'hints_text') if k in row):
            raise ValueError('unrecognized public text field type')
        for name in ('FAIL_TO_PASS', 'PASS_TO_PASS'):
            if name in row and not (isinstance(row[name], str) or
                    isinstance(row[name], list) and all(isinstance(v, str) for v in row[name])):
                raise ValueError('unrecognized public test-list type')
        identifier = row['instance_id']
        if identifier in records:
            raise ValueError('duplicate public task ID')
        # No issue text, reference patch, test text or outcome enters selection.
        records[identifier] = {'instance_id': identifier, 'repo': row['repo'].lower(),
                               'base_commit': row['base_commit']}
    if len(records) != policy['distinct_ids']:
        raise ValueError('public task inventory count changed')
    if not set(policy['excluded_instance_ids']) <= set(records):
        raise ValueError('known exposed task missing from inventory')
    excluded_repos = set(policy['excluded_repositories'])
    if any(records[k]['repo'] not in excluded_repos for k in policy['excluded_instance_ids']):
        raise ValueError('exposed repository identity changed')
    eligible = [r for k, r in records.items() if k not in policy['excluded_instance_ids']
                and r['repo'] not in excluded_repos
                and r['base_commit'] not in policy['excluded_base_commits']]
    seed = policy['selection_seed']
    def rank(kind, name):
        return digest((seed + '\0' + kind + '\0' + name).encode())
    grouped = defaultdict(list)
    for row in eligible:
        grouped[row['repo']].append(row)
    repos = sorted(grouped, key=lambda name: (rank('repository', name), name))
    for repo in repos:
        grouped[repo].sort(key=lambda row: (rank('task', row['instance_id']), row['instance_id']))
    primary = [grouped[repo][0] for repo in repos[:policy['primary_tasks']]]
    used = {row['instance_id'] for row in primary}
    # Ordered reserves prefer one per selected repository; remaining candidates
    # follow the same repository/task ordering. Activation is never automatic.
    reserve_candidates = [grouped[r][1] for r in repos[:policy['primary_tasks']] if len(grouped[r]) > 1]
    reserve_candidates += [row for repo in repos for row in grouped[repo]
                           if row['instance_id'] not in used
                           and row not in reserve_candidates]
    reserves = reserve_candidates[:policy['reserve_tasks']]
    orders = list(itertools.permutations(ARMS))
    primary = [dict(row, slot=index + 1, repetition=1, arm_order=list(orders[index]))
               for index, row in enumerate(primary)]
    reserves = [dict(row, reserve_order=index + 1) for index, row in enumerate(reserves)]
    shortfalls = {'primary_tasks': policy['primary_tasks'] - len(primary),
                  'reserve_tasks': policy['reserve_tasks'] - len(reserves)}
    return {'schema_version': 1, 'protocol': protocol['protocol'],
        'protocol_sha256': digest(encoded(protocol)),
        'status': 'SELECTED' if not any(shortfalls.values()) else 'SELECTION_SHORTFALL',
        'source_sha256': digest(data), 'source_bytes': len(data),
        'inventory_count': len(records), 'eligible_tasks': len(eligible),
        'eligible_repositories': len(repos), 'excluded_tasks': len(records) - len(eligible),
        'metadata_projection_sha256': digest(encoded(sorted(records.values(), key=lambda r: r['instance_id']))),
        'exclusions_sha256': digest(encoded({k: policy[k] for k in (
            'excluded_instance_ids', 'excluded_repositories', 'excluded_base_commits')})),
        'selection_seed': seed, 'primary': primary, 'reserves': reserves,
        'shortfall': shortfalls, 'planned_model_runs': len(primary) * len(ARMS),
        'model_execution': 'NOT RUN', 'task_content_inspected_for_selection': False,
        'exposure_limit': 'Uninspected by this project as recorded; public/pretraining contamination is unknown.',
        'reserve_policy': 'No automatic replacement; document pre-outcome infrastructure exclusion, preserve original slot and all evidence.'}


def validate_selection(selection):
    """A shortfall or altered layout cannot quietly become a smaller study."""
    if not isinstance(selection, dict) or selection.get('status') != 'SELECTED':
        raise ValueError('complete six-repository selection required; shortfall needs an amendment')
    primary, reserves = selection.get('primary'), selection.get('reserves')
    if (not isinstance(primary, list) or len(primary) != 6
            or not isinstance(reserves, list) or len(reserves) != 6
            or selection.get('shortfall') != {'primary_tasks': 0, 'reserve_tasks': 0}
            or selection.get('planned_model_runs') != 18):
        raise ValueError('selection sample or reserve size changed')
    orders = list(itertools.permutations(ARMS))
    identifiers, repos = set(), set()
    for index, row in enumerate(primary):
        if (not isinstance(row, dict) or row.get('slot') != index + 1
                or row.get('repetition') != 1 or row.get('arm_order') != list(orders[index])
                or not isinstance(row.get('instance_id'), str) or not ID.fullmatch(row['instance_id'])
                or not isinstance(row.get('repo'), str) or not REPO.fullmatch(row['repo'])
                or not isinstance(row.get('base_commit'), str) or not SHA1.fullmatch(row['base_commit'])
                or row['instance_id'] in identifiers or row['repo'].lower() in repos):
            raise ValueError('selection identities, repository diversity or balanced orders changed')
        identifiers.add(row['instance_id'])
        repos.add(row['repo'].lower())
    for index, row in enumerate(reserves):
        if (not isinstance(row, dict) or row.get('reserve_order') != index + 1
                or not isinstance(row.get('instance_id'), str) or not ID.fullmatch(row['instance_id'])
                or not isinstance(row.get('repo'), str) or not REPO.fullmatch(row['repo'])
                or not isinstance(row.get('base_commit'), str) or not SHA1.fullmatch(row['base_commit'])
                or row['instance_id'] in identifiers):
            raise ValueError('invalid or overlapping reserve task')
        identifiers.add(row['instance_id'])


def summarize_outcomes(selection, rows):
    """Keep every assigned primary slot; incomplete pilots have no effect estimate."""
    validate_selection(selection)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError('outcome rows must be a JSON array of objects')
    planned = {(r['instance_id'], arm) for r in selection['primary'] for arm in ARMS}
    observed = {}
    for row in rows:
        key = (row.get('instance_id'), row.get('arm'))
        if key not in planned or key in observed or row.get('outcome') not in OUTCOMES:
            raise ValueError('duplicate, unassigned or unrecognized outcome')
        if row['outcome'] == 'RESOLVED' and (
                row.get('independent_evaluator_resolved') is not True
                or row.get('within_matched_budget') is not True):
            raise ValueError('resolved outcome needs independent correctness and budget evidence')
        observed[key] = row['outcome']
    counts = {arm: Counter({name: 0 for name in OUTCOMES}) for arm in ARMS}
    table = []
    for task in selection['primary']:
        values = {arm: observed.get((task['instance_id'], arm), 'NOT_RUN') for arm in ARMS}
        table.append({'instance_id': task['instance_id'], 'repo': task['repo'], **values})
        for arm, outcome in values.items():
            counts[arm][outcome] += 1
    complete = bool(planned) and not any(c['NOT_RUN'] for c in counts.values())
    contrasts = {}
    for treatment, control in (('R1', 'R0'), ('R2', 'R1'), ('R2', 'R0')):
        wins = sum(r[treatment] == 'RESOLVED' and r[control] != 'RESOLVED' for r in table)
        losses = sum(r[control] == 'RESOLVED' and r[treatment] != 'RESOLVED' for r in table)
        contrasts[treatment + '-' + control] = {
            'paired_task_count': len(table),
            'wins': wins if complete else None, 'losses': losses if complete else None,
            'resolved_rate_difference': (wins - losses) / len(table) if complete else None,
            'inference': 'DESCRIPTIVE_PILOT_ONLY; one sample per arm and six repository clusters at most'}
    return {'schema_version': 1, 'status': 'COMPLETE_DESCRIPTIVE_PILOT' if complete else 'INCOMPLETE_NO_EFFECT_ESTIMATE',
        'planned_runs': len(planned), 'reported_rows': len(observed),
        'denominator_per_arm': len(selection['primary']), 'counts': counts,
        'paired_outcomes': table, 'contrasts': contrasts,
        'failure_policy': 'Timeouts, model/infra failures and missing artifacts remain in assigned denominators; NOT_RUN stays explicit.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('validate')
    select = commands.add_parser('select')
    select.add_argument('metadata', type=Path)
    select.add_argument('output', type=Path)
    build_parser = commands.add_parser('build')
    build_parser.add_argument('baseline', type=Path)
    build_parser.add_argument('output_directory', type=Path)
    summarize = commands.add_parser('summarize')
    summarize.add_argument('selection', type=Path)
    summarize.add_argument('outcomes', type=Path, help='JSON array of planned outcome rows')
    summarize.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    try:
        protocol = load_protocol()
        if args.command == 'validate':
            result = {'status': 'PASS', 'protocol': protocol['protocol'],
                'protocol_sha256': digest(encoded(protocol)),
                'frozen_source_files': len(protocol['frozen_source_files']),
                'prompt_files': len(protocol['prompt_files']), 'budget': BUDGET,
                'model_execution': 'NOT RUN', 'compute_authorization': 'NONE'}
        elif args.command == 'select':
            result = select_tasks(read_file(args.metadata, protocol['selection']['metadata_bytes']), protocol)
            _new_output(args.output, encoded(result))
        elif args.command == 'build':
            result = build(args.baseline, args.output_directory, protocol)
        else:
            selection = parse(read_file(args.selection, 1024**2))
            if selection.get('protocol_sha256') != digest(encoded(protocol)):
                raise ValueError('selection belongs to a different frozen protocol')
            result = summarize_outcomes(selection, parse(read_file(args.outcomes, 1024**2)))
            _new_output(args.output, encoded(result))
    except (OSError, ValueError, KeyError, TypeError) as error:
        # Fixed validation messages contain no private source content or OS paths.
        message = str(error) if type(error) is ValueError else type(error).__name__
        print('research preparation failed: ' + message, file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
