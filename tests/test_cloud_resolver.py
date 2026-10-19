import hashlib
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import cloud_resolver as resolver


class Response:
    def __init__(self, data=b'', *, url='https://files.pythonhosted.org/fixture.whl', size=100):
        self.data, self.url = data, url
        self.headers = {'Content-Length': str(size)}
        self.status_code = 200

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def raise_for_status(self): pass
    def iter_content(self, size): yield self.data


class ResolverTests(unittest.TestCase):
    def test_large_input_resolution_reads_headers_only(self):
        row = {'path': 'weights.safetensors', 'bytes': 10 * 1024**3, 'sha256': 'a' * 64}
        response = Response(url='https://storage.googleapis.com/private/model?signature=hidden', size=row['bytes'])
        with patch.object(response, 'iter_content', side_effect=AssertionError('metadata probe must not read weights')):
            source = resolver.source_from_response(response, row)
        self.assertEqual(source['wire_bytes'], row['bytes'])
        self.assertEqual(source['encoding'], 'raw')
        response.headers['Content-Encoding'] = 'gzip'
        with self.assertRaises(ValueError): resolver.source_from_response(response, row)

    def test_pypi_filename_size_and_digest_all_must_match(self):
        row = {'name': 'fixture', 'version': '1.0', 'path': 'fixture-1.0-py3-none-any.whl',
               'bytes': 100, 'sha256': 'a' * 64}
        item = {'filename': row['path'], 'size': 100, 'digests': {'sha256': 'b' * 64},
                'url': 'https://files.pythonhosted.org/fixture.whl'}
        response = Response(json.dumps({'urls': [item]}).encode())
        with (patch.dict(sys.modules, {'requests': SimpleNamespace(get=lambda *a, **k: response)}),
              patch.object(resolver, 'public_source') as download):
            with self.assertRaises(ValueError): resolver.pypi_source(row)
            download.assert_not_called()

    def test_unpinned_notebook_payload_is_never_executed(self):
        source = json.dumps({'cells': [{'cell_type': 'code', 'source': [
            "raise AssertionError('must not execute')\nPAYLOAD='changed'"]}]}).encode()
        with self.assertRaises(ValueError): resolver.packed_inputs(source)


if __name__ == '__main__': unittest.main()
