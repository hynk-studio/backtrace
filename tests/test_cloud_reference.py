import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import cloud_reference as ref


class ReferenceTests(unittest.TestCase):
    def fixture(self, *, changed=False, extra=False):
        data = b'frozen reference'
        manifest = json.dumps({'files': [{'path': 'sample/a.py', 'bytes': len(data),
                                         'sha256': hashlib.sha256(data).hexdigest()}]}).encode()
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as archive:
            archive.writestr('sample/a.py', b'changed referenc' if changed else data)
            if extra: archive.writestr('../unexpected', b'extra')
        return manifest, raw.getvalue(), data

    def test_frozen_bodies_are_verified_before_activation(self):
        manifest, archive, data = self.fixture()
        with tempfile.TemporaryDirectory() as td, patch.object(ref, 'official_manifest', return_value=manifest):
            root = Path(td) / 'refs'
            result = ref.restore_zip(archive, root)
            self.assertEqual((root / 'sample/a.py').read_bytes(), data)
            self.assertEqual(result['verified_files'], 1)
            self.assertFalse((root / 'sample/a.py').stat().st_mode & 0o077)

    def test_changed_or_extra_input_never_creates_target(self):
        for options in ({'changed': True}, {'extra': True}):
            manifest, archive, _ = self.fixture(**options)
            with tempfile.TemporaryDirectory() as td, patch.object(ref, 'official_manifest', return_value=manifest):
                root = Path(td) / 'refs'
                with self.assertRaises(ValueError): ref.restore_zip(archive, root)
                self.assertFalse(root.exists())

    def test_transfer_namespace_cannot_select_paid_state(self):
        with self.assertRaises(ValueError): ref.transfer_path('../a100-state', 'a' * 40)
        with self.assertRaises(ValueError): ref.transfer_path('123', '../claim')
        self.assertTrue(ref.transfer_path('123', 'a' * 40).startswith('a100-transfer/123-'))


if __name__ == '__main__': unittest.main()
