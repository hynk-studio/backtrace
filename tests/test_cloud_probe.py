import hashlib
import io
import json
import os
import unittest
from unittest.mock import patch
import zipfile
from contextlib import redirect_stdout

from tools import cloud_probe


class Response:
    def __init__(self, data, url='https://storage.googleapis.com/test/file?private=hidden'):
        self.url, self.raw = url, io.BytesIO(data)
        self.headers = {'Content-Length': str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        pass


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.data = b'fixture-only-input'
        self.row = {'path': 'a.json', 'bytes': len(self.data),
                    'sha256': hashlib.sha256(self.data).hexdigest()}

    def test_exact_raw_and_single_member_zip(self):
        self.assertEqual(cloud_probe.verify_small_response(Response(self.data), self.row)['encoding'], 'raw')
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as archive:
            archive.writestr('a.json', self.data)
        self.assertEqual(cloud_probe.verify_small_response(Response(out.getvalue()), self.row)['encoding'], 'zip')

    def test_wrong_host_or_bytes_are_not_authenticated_input(self):
        for response in (Response(self.data, 'https://storage.googleapis.com.evil.invalid/a'),
                         Response(self.data + b'x')):
            with self.assertRaises(ValueError):
                cloud_probe.verify_small_response(response, self.row)

    def test_extra_archive_member_is_rejected(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as archive:
            archive.writestr('a.json', self.data)
            archive.writestr('extra.json', b'private')
        with self.assertRaises(ValueError):
            cloud_probe.verify_small_response(Response(out.getvalue()), self.row)

    def test_missing_secret_and_redacted_failure_output(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                cloud_probe.secret('RUNPOD_API_KEY')
        out = io.StringIO()
        with (patch.object(cloud_probe, 'runpod_read', side_effect=ValueError('secret-value-url')),
                patch.object(cloud_probe, 'kaggle_checks', side_effect=ValueError('other-secret')),
                redirect_stdout(out)):
            self.assertEqual(cloud_probe.main(), 1)
        self.assertNotIn('secret-value-url', out.getvalue())
        self.assertNotIn('other-secret', out.getvalue())
        self.assertEqual(json.loads(out.getvalue())['gpu_allocations'], 0)
