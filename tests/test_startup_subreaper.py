"""Regression for the actual outer-root/inner-server ownership topology."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import startup_guard


class NestedSubreaperTests(unittest.TestCase):
    def test_unavailable_local_owner_blocks_before_server_spawn(self):
        started = []
        class Lifecycle:
            config = SimpleNamespace(startup_timeout=1)
            def start(self): started.append(True)
        guarded = startup_guard.guarded_server(Lifecycle,
            total_deadline=time.monotonic() + 10, error_type=RuntimeError)
        with patch.object(startup_guard, 'child_subreaper', side_effect=OSError('unavailable')):
            with self.assertRaises(OSError): guarded().start()
        self.assertEqual(started, [])

    def test_dropped_uid_server_reaps_its_workers_before_outer_driver(self):
        if sys.platform != 'linux' or os.getuid() != 0:
            self.skipTest('real root Linux ownership required')
        if int(Path('/proc/self/stat').read_text().split(' ', 1)[0]) != os.getpid():
            self.skipTest('real local procfs required')
        path = Path(__file__).with_name('official_startup_reaper.py')
        result = subprocess.run([sys.executable, str(path), '--expect', 'clean'],
            check=True, text=True, capture_output=True, timeout=25)
        report = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['subreaper_after_start'], 1)
        self.assertEqual(report['subreaper_after_stop'], 0)
        self.assertEqual(report['outer_reaped'], [])
        self.assertEqual(report['group_members_after_stop'], [])


if __name__ == '__main__': unittest.main()
