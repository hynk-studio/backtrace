import ast
from pathlib import Path
import tempfile
import unittest

from tools.guard_driver import ANCHOR, prepare, transform


class DriverTransformTests(unittest.TestCase):
    def test_narrow_transform_keeps_serving_payload(self):
        source = ("NATIVE_SERVING='authored fixture bytes'\ndef server_phase():\n" + ANCHOR +
                  " shutil.copyfile(__file__,CODE/'one_task.py')\n if True:\n"
                  "  event('server_stop_returned',seconds=time.time()-start)\n")
        after = transform(source)
        self.assertIn("NATIVE_SERVING='authored fixture bytes'", after)
        self.assertEqual(after.count('total_deadline=startup_total_deadline'), 1)
        self.assertEqual(after.count("'startup_observation'"), 1)
        ast.parse(after)
        with self.assertRaises(ValueError):
            transform(after)

    def test_unpinned_driver_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'old.py'
            source.write_text('raise RuntimeError("must never execute")')
            output = Path(directory) / 'new'
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                prepare(source, output)
            self.assertFalse(output.exists())
