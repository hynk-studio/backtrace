import subprocess
import unittest

from tools.free_container_cleanup import remove

NAME = 'backtrace-free-full-setup-123'
IDENTITY = 'a' * 64


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


class CleanupTests(unittest.TestCase):
    def invoke(self, states, *, timeout=4, request_error=False):
        clock = Clock(); calls = []
        def run(command, **kwargs):
            calls.append((command, kwargs['timeout']))
            if command[1:3] == ['rm', '-f']:
                if request_error:
                    raise subprocess.TimeoutExpired(command, kwargs['timeout'])
                return subprocess.CompletedProcess(command, 0, '', '')
            state = states.pop(0) if len(states) > 1 else states[0]
            if state == 'error': return subprocess.CompletedProcess(command, 1, '', 'daemon unavailable')
            if state == 'timeout': raise subprocess.TimeoutExpired(command, kwargs['timeout'])
            output = {'absent': '', 'present': IDENTITY + ' ' + NAME + '\n',
                      'replacement': 'b' * 64 + ' ' + NAME + '\n', 'malformed': '???\n'}[state]
            return subprocess.CompletedProcess(command, 0, output, '')
        report = remove(NAME, container_id=IDENTITY, timeout=timeout, run=run, wall=clock, sleep=clock.sleep)
        self.assertLessEqual(clock.now, timeout)
        self.assertTrue(all(0 < bound <= timeout for _, bound in calls))
        return report, calls

    def test_timeout_ack_is_resolved_by_two_actual_absence_reads(self):
        report, calls = self.invoke(['present', 'absent', 'absent'], request_error=True)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['absence_reads'], 2)
        self.assertEqual(report['request']['error_type'], 'TimeoutExpired')
        self.assertEqual(sum(c[1:3] == ['rm', '-f'] for c, _ in calls), 1)

    def test_successful_request_does_not_hide_persistent_container(self):
        report, _ = self.invoke(['present'])
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['absence_reads'], 0)

    def test_daemon_errors_timeouts_and_malformed_output_never_mean_absence(self):
        for state in ('error', 'timeout', 'malformed'):
            with self.subTest(state=state):
                report, _ = self.invoke([state])
                self.assertEqual(report['status'], 'FAIL')
                self.assertEqual(report['absence_reads'], 0)

    def test_absence_must_be_consecutive(self):
        report, _ = self.invoke(['absent', 'error', 'absent'], timeout=3)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['absence_reads'], 1)

    def test_replaced_identity_is_not_removed_or_accepted(self):
        report, calls = self.invoke(['replacement'])
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['observations'], [{'state': 'IDENTITY_MISMATCH'}])
        self.assertEqual(calls[0][0][-1], IDENTITY)

    def test_foreign_names_and_invalid_budget_are_rejected_before_docker(self):
        def forbidden(*args, **kwargs): raise AssertionError('docker invoked')
        for name, duration in (('production', 120), (NAME, float('inf')), (NAME, 0)):
            with self.assertRaises(ValueError): remove(name, timeout=duration, run=forbidden)


if __name__ == '__main__': unittest.main()
