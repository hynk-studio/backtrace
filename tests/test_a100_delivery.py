import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import a100_delivery as frozen


class FrozenDeliveryTests(unittest.TestCase):
    def test_pinned_inventories_have_no_unselected_task_inputs(self):
        task = json.loads(frozen.manifest('task'))
        self.assertEqual(len(task['files']), 8)
        self.assertEqual(sum(r['bytes'] for r in task['files']), 222386501)
        names = {r['path'] for r in task['files']}
        self.assertIn('agent-task.json', names)
        self.assertFalse(any('answer' in n or 'solution' in n or 'test_patch' in n for n in names))
        wheels = json.loads(frozen.manifest('wheels'))
        self.assertEqual(len(wheels['files']), 246)
        self.assertEqual(sum(r['bytes'] for r in wheels['files']), 5373545117)
        model = json.loads(frozen.manifest('model'))
        self.assertEqual(len(model['files']), 8)
        self.assertEqual(sum(r['bytes'] for r in model['files']), 23297590856)

    def test_changed_metadata_does_not_repin_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'docs').mkdir()
            (root / 'docs/a100-task-delivery.json').write_text('{"files":[]}')
            with patch.object(frozen, 'ROOT', root), self.assertRaisesRegex(ValueError, 'inventory changed'):
                frozen.manifest('task')

    def test_changed_driver_and_missing_payload_leave_no_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'one_task.py').write_text('print("untrusted")')
            with self.assertRaisesRegex(ValueError, 'driver changed'):
                frozen.build('driver', root, root / 'manifest.json')
            self.assertFalse((root / 'manifest.json').exists())
            with self.assertRaises(FileNotFoundError):
                frozen.build('task', root, root / 'manifest.json')
            self.assertFalse((root / 'manifest.json').exists())

    def test_owner_controller_is_excluded_from_workload_closure(self):
        self.assertFalse({'runpod_control.py', 'private_delivery.py', 'a100_delivery.py'}
                         & set(frozen.POD_TOOLS))
        for name in frozen.POD_TOOLS:
            self.assertTrue((frozen.ROOT / 'tools' / name).is_file())


if __name__ == '__main__':
    unittest.main()
