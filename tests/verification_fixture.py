"""Authored, task-independent negative/positive controls at the model boundary."""
import json

FILENAME = 'backtrace_verification_probe.py'
COMMAND = 'python ' + FILENAME
SOURCE = '''# Backtrace CPU transport probe.
def successor(number):
    return number

if __name__ == '__main__':
    assert successor(3) == 4, 'BACKTRACE_ASSERTION_FAILURE'
    print('BACKTRACE_CHECK_PASS')
'''


def tool_result(messages):
    rows = [m for m in messages if m.get('role') in ('tool', 'tool_responses')]
    if not rows:
        raise AssertionError('real official tool response missing')
    value = rows[-1]['content']
    value = json.loads(value) if isinstance(value, str) else value
    if isinstance(value, dict) and set(value) == {'result'}:
        value = value['result']
        value = json.loads(value) if isinstance(value, str) else value
    if not isinstance(value, dict):
        raise AssertionError('structured original tool response required')
    return value


class VerificationSequence:
    def __init__(self, case):
        self.case, self.checked_exits = case, []

    def message(self, data, number):
        names = {r['function']['name'] for r in data['tools']}
        if number == 1:
            prompt = json.dumps([r.get('content') for r in data['messages'] if r.get('role') == 'system'])
            if 'Reproduction, correction, and verification' not in prompt:
                raise AssertionError('revised generic guidance did not reach model request')
        previous = tool_result(data['messages']) if number > 1 else None
        if self.case == 'budget-rejection':
            if number <= 31 and previous is not None and previous.get('status') != 'ok':
                raise AssertionError('tool failed before declared shared budget')
            if number == 1:
                action = ('write_file', {'filepath': FILENAME, 'content': SOURCE})
            elif 2 <= number <= 30:
                action = ('read_file', {'filepath': FILENAME, 'start_line': 1, 'end_line': 2})
            elif number == 31:
                action = ('edit_file', {'filepath': FILENAME, 'old_string': 'return number',
                                        'new_string': 'return number + 99  # REJECTED_MUTATION'})
            elif number == 32:
                if previous.get('status') != 'error' or previous.get('error_type') != 'BudgetExceeded':
                    raise AssertionError('real original tool did not reject the over-budget edit')
                action = ('submit_patch', {})
            elif number == 33:
                if previous.get('status') != 'ok':
                    raise AssertionError('original submit tool failed')
                return {'role': 'assistant', 'content': 'Unresolved CPU negative control; final edit was rejected.'}
            else:
                raise AssertionError('unexpected budget-control request')
        else:
            # Every expected observation comes from the original run_command;
            # model messages cannot stand in for actual child exit codes/output.
            expected = {3: 1, 5: 1, 7: 0, 9: 1, 11: 0}
            if number in expected:
                code = expected[number]
                details = previous if code == 0 else previous.get('details', {})
                if (previous.get('status') != ('ok' if code == 0 else 'error')
                        or (code != 0 and previous.get('error_type') != 'CommandError')
                        or details.get('exit_code') != code
                        or (code == 0 and 'BACKTRACE_CHECK_PASS' not in details.get('stdout', ''))
                        or (code != 0 and 'AssertionError' not in details.get('stderr', ''))):
                    raise AssertionError('actual before/after check does not match its control')
                self.checked_exits.append(code)
            elif previous is not None and previous.get('status') != 'ok':
                raise AssertionError('real edit/status/submission tool failed')
            actions = [
                ('write_file', {'filepath': FILENAME, 'content': SOURCE}),
                ('run_command', {'command': COMMAND}),
                ('edit_file', {'filepath': FILENAME, 'old_string': 'return number', 'new_string': 'return number + 2'}),
                ('run_command', {'command': COMMAND}),
                ('edit_file', {'filepath': FILENAME, 'old_string': 'return number + 2', 'new_string': 'return number + 1'}),
                ('run_command', {'command': COMMAND}),
                ('edit_file', {'filepath': FILENAME, 'old_string': 'return number + 1', 'new_string': 'return number + 3'}),
                ('run_command', {'command': COMMAND}),
                ('edit_file', {'filepath': FILENAME, 'old_string': 'return number + 3', 'new_string': 'return number + 1'}),
                ('run_command', {'command': COMMAND}),
                ('run_command', {'command': 'git diff --check'}),
                ('get_status', {}), ('submit_patch', {}),
            ]
            if number == 14:
                if self.checked_exits != [1, 1, 0, 1, 0]:
                    raise AssertionError('actual verification sequence incomplete')
                return {'role': 'assistant', 'content': 'Authored CPU check completed; this is not a model task score.'}
            if number > len(actions):
                raise AssertionError('unexpected verification-control request')
            action = actions[number - 1]
        name, arguments = action
        if name not in names:
            raise AssertionError('unchanged official tool schema missing')
        return {'role': 'assistant', 'content': None, 'tool_calls': [{
            'id': 'call_verification_' + str(number), 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(arguments)}}]}
