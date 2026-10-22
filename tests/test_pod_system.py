import copy
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import patch

from tools import pod_system, runpod_control
from tests.test_cloud_worker_permissions import mapped_workload_ids


class SystemPackagesTests(unittest.TestCase):
    def response(self, row, data=b'x', *, url=None):
        response = io.BytesIO(data)
        response.geturl = lambda: row['url'] if url is None else url
        return response

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

    def test_transient_disconnect_http_503_and_short_body_retry_exact_reads(self):
        for mode in ('disconnect', '503', 'short-body'):
            value = self.manifest(); calls = []
            def opening(url, *, timeout):
                calls.append(url)
                self.assertGreater(timeout, 0); self.assertLessEqual(timeout, 60)
                row = next(row for row in value['files'] if row['url'] == url)
                if len(calls) == 1:
                    if mode == 'disconnect': raise http.client.RemoteDisconnected('synthetic')
                    if mode == '503': raise urllib.error.HTTPError(url, 503, 'synthetic', {}, None)
                    return self.response(row, b'')
                return self.response(row)
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as name, \
                    patch.object(pod_system.urllib.request, 'urlopen', side_effect=opening), \
                    patch.object(pod_system.time, 'sleep') as sleep:
                target = Path(name) / 'packages'
                result = pod_system.download(value, target, deadline=time.time()+10)
                self.assertEqual(result['status'], 'PASS')
                self.assertEqual(calls, [value['files'][0]['url']]*2 + [value['files'][1]['url']])
                sleep.assert_called_once()
                self.assertEqual([p.read_bytes() for p in sorted(target.iterdir())], [b'x', b'x'])

    def test_persistent_disconnect_is_bounded_to_three_without_partial_files(self):
        with tempfile.TemporaryDirectory() as name, \
                patch.object(pod_system.urllib.request, 'urlopen', side_effect=http.client.RemoteDisconnected('synthetic')) as opening, \
                patch.object(pod_system.time, 'sleep') as sleep:
            target = Path(name) / 'packages'
            with self.assertRaises(http.client.RemoteDisconnected):
                pod_system.download(self.manifest(), target, deadline=time.time()+10)
            self.assertEqual(opening.call_count, 3)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual(list(target.iterdir()), [])

    def test_permanent_http_redirect_and_hash_failures_do_not_retry(self):
        for mode in ('404', 'redirect', 'hash'):
            value = self.manifest(); row = value['files'][0]
            def opening(url, *, timeout):
                if mode == '404': raise urllib.error.HTTPError(url, 404, 'synthetic', {}, None)
                return self.response(row, b'y' if mode == 'hash' else b'x',
                                     url='https://example.invalid/package' if mode == 'redirect' else None)
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as name, \
                    patch.object(pod_system.urllib.request, 'urlopen', side_effect=opening) as opened, \
                    patch.object(pod_system.time, 'sleep') as sleep:
                target = Path(name) / 'packages'
                with self.assertRaises((ValueError, urllib.error.HTTPError)):
                    pod_system.download(value, target, deadline=time.time()+10)
                opened.assert_called_once(); sleep.assert_not_called()
                self.assertEqual(list(target.iterdir()), [])

    def test_retry_does_not_extend_the_shared_deadline(self):
        clock = [100.0]
        def disconnected(*args, **kwargs):
            clock[0] = 101.0
            raise http.client.RemoteDisconnected('synthetic')
        with tempfile.TemporaryDirectory() as name, \
                patch.object(pod_system.urllib.request, 'urlopen', side_effect=disconnected) as opening, \
                patch.object(pod_system.time, 'time', side_effect=lambda:clock[0]), \
                patch.object(pod_system.time, 'sleep') as sleep:
            with self.assertRaisesRegex(TimeoutError, 'system input deadline'):
                pod_system.download(self.manifest(), Path(name)/'packages', deadline=101.0)
            opening.assert_called_once(); sleep.assert_not_called()

    @unittest.skipUnless(os.getuid() == 0 and mapped_workload_ids()
                         and all(shutil.which(n) for n in ('setpriv', 'git', 'patch')),
                         'actual mapped root Linux with harness utilities required')
    def test_actual_unprivileged_git_patch_roundtrip(self):
        self.assertEqual(pod_system.smoke(), 'PASS')


if __name__ == '__main__': unittest.main()
