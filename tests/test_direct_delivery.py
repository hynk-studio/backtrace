import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools import direct_delivery as direct


class Response(io.BytesIO):
    def __init__(self, body, status=200, **headers):
        super().__init__(body)
        self.status = status
        self.headers = {'Content-Length': str(len(body)), **headers}


class DirectDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = b'frozen-model-fixture' * 1024
        self.row = {'path': 'nested/model.bin', 'bytes': len(self.payload),
                    'sha256': hashlib.sha256(self.payload).hexdigest()}
        self.data = json.dumps({'schema_version': 1, 'phase': 'model', 'files': [self.row]}).encode()
        self.sha = hashlib.sha256(self.data).hexdigest()
        self.source = {'url': 'https://storage.googleapis.com/private/frozen?signature=SECRET',
                       'encoding': 'raw', 'wire_bytes': len(self.payload)}
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request)
        self.assertLessEqual(timeout, 15)
        return Response(self.payload)

    def pull(self, **kwargs):
        return direct.pull(self.root / 'model', self.data, {self.row['path']: self.source},
                           self.sha, 30, opener=kwargs.get('opener', self.open))

    def test_atomic_exact_download_has_no_urls_or_credentials_in_receipt(self):
        result = self.pull()
        self.assertTrue(result['verified'])
        self.assertEqual((self.root / 'model/nested/model.bin').read_bytes(), self.payload)
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('Authorization', self.calls[0].headers)
        with self.assertRaises(ValueError):
            self.pull()

    def test_wrong_digest_never_activates_and_leaves_restart_lock(self):
        with self.assertRaisesRegex(direct.DownloadError, 'identity'):
            self.pull(opener=lambda *a, **k: Response(b'x' * len(self.payload)))
        self.assertFalse((self.root / 'model').exists())
        self.assertEqual({p.name for p in self.root.iterdir()}, {'.model.delivery-lock'})
        with self.assertRaises(FileExistsError):
            self.pull()

    def test_interrupted_body_resumes_at_exact_offset(self):
        requests = []
        def opener(request, **kwargs):
            requests.append(request)
            if len(requests) == 1:
                return Response(self.payload[:100], **{'Content-Length': str(len(self.payload))})
            self.assertEqual(request.get_header('Range'), 'bytes=100-')
            return Response(self.payload[100:], status=206,
                            **{'Content-Range': f'bytes 100-{len(self.payload)-1}/{len(self.payload)}'})
        self.assertTrue(self.pull(opener=opener)['verified'])
        self.assertEqual(len(requests), 2)

    def test_range_ignored_or_wrong_content_range_is_refused(self):
        for mode in ('ignored', 'wrong'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'part'; path.write_bytes(self.payload[:100])
                reply = Response(self.payload) if mode == 'ignored' else Response(
                    self.payload[100:], status=206, **{'Content-Range': 'bytes 0-1/2'})
                with self.assertRaises(direct.DownloadError):
                    direct.download_wire(path, self.source, 10, opener=lambda *a, **k: reply,
                                         clock=lambda: 1)
                self.assertEqual(path.stat().st_size, 100)

    def test_malformed_length_never_downloads_payload(self):
        with self.assertRaisesRegex(direct.DownloadError, 'Content-Length'):
            self.pull(opener=lambda *a, **k: Response(self.payload, **{'Content-Length': '999999'}))
        self.assertFalse((self.root / 'model').exists())

    def test_only_exact_https_storage_host_is_accepted(self):
        for url in ('http://storage.googleapis.com/x', 'https://storage.googleapis.com.evil/x',
                    'https://user:secret@storage.googleapis.com/x', 'https://127.0.0.1/x',
                    'https://storage.googleapis.com:444/x', 'https://storage.googleapis.com/x#secret'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                direct.validate_url(url)
        with self.assertRaises(direct.DownloadError):
            direct.NoRedirect().redirect_request(None, None, None, None, None, None)

    def test_extra_source_cannot_exfiltrate_or_supply_evaluator_inputs(self):
        sources = {self.row['path']: self.source, 'answer.json': self.source}
        with self.assertRaises(ValueError):
            direct.pull(self.root / 'model', self.data, sources, self.sha, 30, opener=self.open)
        self.assertEqual(self.calls, [])

    def test_single_member_zip_is_verified_against_uncompressed_identity(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('model.bin', self.payload)
        wire = stream.getvalue()
        self.source.update(encoding='single-file-zip', wire_bytes=len(wire))
        self.assertTrue(self.pull(opener=lambda *a, **k: Response(wire))['verified'])

    def test_archive_with_extra_member_is_not_extracted(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('model.bin', self.payload)
            archive.writestr('../escape', b'x')
        wire = stream.getvalue()
        self.source.update(encoding='single-file-zip', wire_bytes=len(wire))
        with self.assertRaisesRegex(direct.DownloadError, 'expected regular file'):
            self.pull(opener=lambda *a, **k: Response(wire))
        self.assertFalse((self.root / 'escape').exists())

    def test_expired_deadline_makes_no_http_request(self):
        with self.assertRaisesRegex(direct.DownloadError, 'deadline'):
            direct.download_wire(self.root / 'wire', self.source, 1, opener=self.open, clock=lambda: 2)
        self.assertEqual(self.calls, [])

    def test_bounded_retries_sanitize_transport_failures(self):
        calls = []
        def failed(*args, **kwargs):
            calls.append(1)
            raise OSError('https://storage.googleapis.com/x?SECRET')
        with self.assertRaises(direct.DownloadError) as caught:
            self.pull(opener=failed)
        self.assertEqual(len(calls), 3)
        self.assertNotIn('SECRET', str(caught.exception))

    def test_changed_manifest_is_rejected_before_opening(self):
        with self.assertRaises(ValueError):
            direct.pull(self.root / 'model', self.data, {self.row['path']: self.source},
                        '0' * 64, 30, opener=self.open)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
