"""Project process evidence from ATIF, without publishing code or task text.

This is a diagnostic, never a correctness judge. A zero-exit command may be a
search, or an inadequate test. Unrecognized observations remain unknown.
"""
import json
import re

MUTATIONS = {'write_file', 'edit_file'}
FAILURE_TEXT = re.compile(r'Traceback \(most recent call last\)|\bAssertionError\b|'
                          r'(?im:^\s*test\w*[^\n]{0,120}\bfailed\s*:)|'
                          r'(?m:\b[1-9]\d* failed\b)')


def observation(step):
    container = step.get('observation')
    if not isinstance(container, dict):
        return None
    value = container.get('content')
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    return value if isinstance(value, dict) else None


def review(trace):
    mutations, commands, errors = [], [], []
    unknown = 0
    for position, step in enumerate(trace.get('steps', [])):
        calls = step.get('tool_calls', [])
        if not calls:
            continue
        # Do not attach one response to multiple invocations without call IDs.
        result = observation(step) if len(calls) == 1 else None
        if result is None:
            unknown += len(calls)
            continue
        name = calls[0].get('function_name')
        if result.get('status') == 'error':
            errors.append({'position': position, 'mutation': name in MUTATIONS,
                           'budget_exceeded': result.get('error_type') == 'BudgetExceeded'})
        if name in MUTATIONS and result.get('status') == 'ok':
            mutations.append(position)
        if name == 'run_command' and (result.get('status') == 'ok' or result.get('error_type') == 'CommandError'):
            details = result if result.get('status') == 'ok' else result.get('details', {})
            if not isinstance(details, dict):
                unknown += 1
                continue
            code = details.get('exit_code')
            output = '\n'.join(details[k] for k in ('stdout', 'stderr') if isinstance(details.get(k), str))
            commands.append({'position': position, 'exit_code': code if type(code) is int else None,
                             'failure_text': bool(FAILURE_TEXT.search(output))})
    after = [c for c in commands if mutations and c['position'] > mutations[-1]]
    flags = []
    if any(e['mutation'] for e in errors):
        flags.append('REJECTED_EDIT_OR_WRITE')
    if any(e['budget_exceeded'] for e in errors):
        flags.append('TOOL_BUDGET_EXHAUSTED')
    zero_failures = sum(c['exit_code'] == 0 and c['failure_text'] for c in commands)
    if zero_failures:
        flags.append('ZERO_EXIT_WITH_FAILURE_TEXT')
    if mutations and not after:
        flags.append('NO_COMMAND_AFTER_LAST_ACCEPTED_MUTATION')
    if after and (after[-1]['exit_code'] not in (0, None) or after[-1]['failure_text']):
        flags.append('LAST_POST_MUTATION_COMMAND_HAS_FAILURE_EVIDENCE')
    return {'schema_version': 1, 'kind': 'PROCESS_DIAGNOSTIC_NOT_CORRECTNESS',
            'accepted_mutations': len(mutations), 'rejected_mutations': sum(e['mutation'] for e in errors),
            'tool_errors': len(errors), 'budget_rejections': sum(e['budget_exceeded'] for e in errors),
            'command_observations': len(commands), 'nonzero_commands': sum(c['exit_code'] not in (0, None) for c in commands),
            'zero_exit_with_failure_text': zero_failures, 'post_mutation_commands': len(after),
            'last_post_mutation_exit_code': after[-1]['exit_code'] if after else None,
            'last_post_mutation_failure_text': after[-1]['failure_text'] if after else None,
            'unrecognized_tool_observations': unknown, 'flags': flags,
            'correctness': 'NOT ESTABLISHED; independent verifier required'}
