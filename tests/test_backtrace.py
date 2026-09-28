"""Synthetic local safety fixtures only; no official competition samples."""
import contextlib
import io
import json
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import backtrace as bt


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.archive = Path(self.temp.name) / 'input.zip'

    def make(self, entries, compression=zipfile.ZIP_STORED):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.archive, 'w', compression=compression) as z:
                for name, content in entries:
                    z.writestr(name, content)
        return self.archive

    def reject(self, entries, allowed=('notes.txt',), **kwargs):
        self.make(entries, **kwargs)
        with self.assertRaises((bt.InspectionError, zipfile.BadZipFile)):
            bt.inspect_archive(self.archive, allowed)

    def test_valid_reproducible_read_only_report(self):
        self.make([('docs/', ''), ('docs/notes.txt', 'Synthetic fixture')])
        before = self.archive.read_bytes()
        first = bt.inspect_archive(self.archive, ['docs/notes.txt'])
        self.assertEqual(first, bt.inspect_archive(self.archive, ['docs/notes.txt']))
        self.assertEqual(first['sha256'], bt.digest(before))
        self.assertEqual(first['official_validator'], 'NOT RUN')
        self.assertEqual(self.archive.read_bytes(), before)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [self.archive])

    def test_traversal_and_portability(self):
        for name in ('../notes.txt', '/notes.txt', 'a/../../notes.txt', 'a\\notes.txt',
                     'C:/notes.txt', './notes.txt', 'a//notes.txt', 'a/./notes.txt',
                     'a/../notes.txt', 'n\u00f6tes.txt'):
            with self.subTest(name=name):
                self.reject([(name, 'x')])

    def test_nul_name_in_actual_archive_bytes(self):
        self.make([('notes.txtXignored', 'x')])
        self.archive.write_bytes(self.archive.read_bytes().replace(b'notes.txtXignored', b'notes.txt\x00ignored'))
        with self.assertRaises(bt.InspectionError):
            bt.inspect_archive(self.archive, ['notes.txt'])

    def test_duplicates_and_aliases(self):
        self.reject([('notes.txt', 'x'), ('notes.txt', 'y')])
        self.reject([('notes.txt', 'x'), ('Notes.txt', 'y')], ['notes.txt', 'Notes.txt'])
        self.reject([('a.txt', 'x'), ('a.txt/n.txt', 'y')], ['a.txt', 'a.txt/n.txt'])

    def test_secrets_cache_weights_and_labels(self):
        for name in ('.env', 'kaggle.json', 'credentials.json', 'cookies.txt', 'token.json',
                     '__pycache__/a.py', 'cache/a.txt', 'model.safetensors', 'model.bin',
                     'adapter_model.safetensors', 'labels.json', 'answers.txt',
                     'hidden/a.txt', 'ground_truth.json', 'archive.zip'):
            with self.subTest(name=name):
                self.reject([(name, 'x')], [name])

    def test_content_filter(self):
        for content in ('api_key: synthetic-value', '{"password": "synthetic"}',
                        '-----BEGIN PRIVATE KEY-----', 'ghp_' + 'a' * 36,
                        'latent_causes = []', 'future_observations: []',
                        'reference_answer: x', 'test_patch: x', '\x00binary', b'\xff'):
            with self.subTest(content=type(content).__name__):
                self.reject([('notes.txt', content)])

    def test_unrelated_and_missing_files(self):
        self.reject([('notes.txt', 'x'), ('unrelated.txt', 'x')])
        self.reject([('notes.txt', 'x')], ['notes.txt', 'missing.txt'])
        self.reject([('unrelated/', ''), ('notes.txt', 'x')])
        self.reject([], ['notes.txt'])
        self.reject([('notes.txt', 'x')], [])

    def test_symlink_and_special_files(self):
        for kind in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR):
            info = zipfile.ZipInfo('notes.txt')
            info.create_system = 3
            info.external_attr = (kind | 0o777) << 16
            self.reject([(info, 'target')])

    def test_resource_ceilings(self):
        self.reject([('notes.txt', 'a' * 10000)], compression=zipfile.ZIP_DEFLATED)
        self.make([('notes.txt', '12345')])
        for name, value in [('MAX_MEMBER', 4), ('MAX_TOTAL', 4), ('MAX_ENTRIES', 0), ('MAX_ARCHIVE', 4)]:
            with self.subTest(limit=name), patch.object(bt, name, value):
                with self.assertRaises(bt.InspectionError):
                    bt.inspect_archive(self.archive, ['notes.txt'])

    def test_corrupt_crc(self):
        self.make([('notes.txt', 'unique-payload')])
        self.archive.write_bytes(self.archive.read_bytes().replace(b'unique-payload', b'broken-payload'))
        with self.assertRaises(zipfile.BadZipFile):
            bt.inspect_archive(self.archive, ['notes.txt'])

    def test_encryption_flag(self):
        self.make([('notes.txt', 'x')])
        raw = bytearray(self.archive.read_bytes())
        for signature, offset in [(b'PK\x03\x04', 6), (b'PK\x01\x02', 8)]:
            index = raw.index(signature) + offset
            raw[index] |= 1
        self.archive.write_bytes(raw)
        with self.assertRaises(bt.InspectionError):
            bt.inspect_archive(self.archive, ['notes.txt'])

    def test_unreviewed_metadata(self):
        self.make([('notes.txt', 'x')])
        with zipfile.ZipFile(self.archive, 'a') as archive:
            archive.comment = b'opaque data'
        with self.assertRaises(bt.InspectionError):
            bt.inspect_archive(self.archive, ['notes.txt'])
        info = zipfile.ZipInfo('notes.txt')
        info.comment = b'opaque data'
        self.reject([(info, 'x')])
        info.comment = b''
        info.extra = b'\xfe\xca\x00\x00'
        self.reject([(info, 'x')])

    def test_cli_redacts_content_and_paths(self):
        self.make([('notes.txt', 'api_key: never-echo-this')])
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = bt.main(['inspect', str(self.archive), '--allow', 'notes.txt'])
        self.assertEqual(code, 2)
        self.assertNotIn('never-echo-this', stdout.getvalue() + stderr.getvalue())
        self.assertNotIn(str(self.archive), stderr.getvalue())

    def test_preflight_and_baseline_gate(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(bt.main(['preflight']), 0)
        self.assertEqual(json.loads(output.getvalue())['official_baseline'], 'BLOCKED')
        with contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(bt.main(['baseline']), 2)
        self.assertIn('HARNESS_README.md', error.getvalue())
        self.assertFalse(any(Path(self.temp.name).iterdir()))


class AcquisitionTests(unittest.TestCase):
    def test_pin_and_no_overwrite(self):
        source = '{"nbformat":4,"cells":[]}'
        spec = {'notebook': {'acquisition_url': 'https://www.kaggle.com/example',
                             'version': 2, 'sha256': bt.digest(source.encode())}}
        payload = {'metadata': {'currentVersionNumber': 2}, 'blob': {'source': source}}
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / 'manifest.json'
            manifest.write_text(json.dumps(spec))
            target = Path(directory) / 'starter.ipynb'
            def response(*args, **kwargs):
                return io.BytesIO(json.dumps(payload).encode())
            with patch.object(bt, 'MANIFEST', manifest), patch.object(bt.urllib.request, 'urlopen', response):
                receipt = bt.acquire_notebook(target)
                self.assertEqual(target.read_bytes(), source.encode())
                self.assertEqual(receipt['execution'], 'NOT RUN')
                with self.assertRaises(FileExistsError):
                    bt.acquire_notebook(target)
                payload['metadata']['currentVersionNumber'] = 3
                with self.assertRaises(bt.InspectionError):
                    bt.acquire_notebook(Path(directory) / 'changed.ipynb')
                payload['metadata']['currentVersionNumber'] = 2
                payload['blob']['source'] += ' '
                with self.assertRaises(bt.InspectionError):
                    bt.acquire_notebook(Path(directory) / 'changed.ipynb')
                self.assertFalse((Path(directory) / 'changed.ipynb').exists())


if __name__ == '__main__':
    unittest.main()
