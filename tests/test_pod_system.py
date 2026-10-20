import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import pod_system, runpod_control
from tests.test_cloud_worker_permissions import mapped_workload_ids


class SystemPackagesTests(unittest.TestCase):
    def manifest(self):
        return {'schema_version': 1, 'image': pod_system.IMAGE, 'requested': ['git', 'patch'],
                'files': [{'path': name + '_1_amd64.deb', 'package': name, 'version': '1',
                           'architecture': 'amd64', 'bytes': 1,
                           'sha256': hashlib.sha256(b'x').hexdigest(),
                           'url': 'https://archive.ubuntu.com/ubuntu/pool/main/g/' + name + '.deb'}
                          for name in ('git', 'patch')]}

    def test_recorded_manifest_is_bound_to_the_exact_base_and_complete_scope(self):
        value = json.loads((Path(__file__).resolve().parents[1] / 'docs/a100-system-packages.json').read_text())
        pod_system.validate(value)
        self.assertEqual(value['image'], runpod_control.BASE)
        self.assertEqual(len(value['files']), 24)

    def test_untrusted_or_changed_system_package_never_reaches_dpkg(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); value = self.manifest()
            for row in value['files']: (root / row['path']).write_bytes(b'x')
            (root / value['files'][0]['path']).write_bytes(b'y')
            with patch.object(pod_system.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                    pod_system.install(value, time.time(), local_packages=root)
                run.assert_not_called()

    def test_path_and_origin_changes_are_rejected_before_network(self):
        for key, bad in [('url', 'https://example.com/package.deb'), ('path', '../package.deb'),
                         ('architecture', 'arm64'), ('bytes', -1)]:
            value = self.manifest(); value['files'][0][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError): pod_system.validate(value)

    @unittest.skipUnless(os.getuid() == 0 and mapped_workload_ids()
                         and all(shutil.which(n) for n in ('setpriv', 'git', 'patch')),
                         'actual mapped root Linux with harness utilities required')
    def test_actual_unprivileged_git_patch_roundtrip(self):
        self.assertEqual(pod_system.smoke(), 'PASS')


if __name__ == '__main__': unittest.main()
