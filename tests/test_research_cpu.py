import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import research_comparison as comparison
from tools import research_cpu


class ResearchInputTests(unittest.TestCase):
    def fixtures(self):
        protocol = copy.deepcopy(comparison.load_protocol())
        records = [{'instance_id': 'fastapi_11194', 'repo': 'fastapi/fastapi',
                    'base_commit': 'a' * 40, 'problem_statement': 'private issue',
                    'patch': 'PRIVATE_REFERENCE_SENTINEL', 'test_patch': 'PRIVATE_TEST_SENTINEL'}]
        records += [{'instance_id': f'repo{i}_{j}', 'repo': f'owner/repo{i}',
                     'base_commit': f'{i + 1:040x}', 'problem_statement': 'private issue',
                     'patch': 'PRIVATE_REFERENCE_SENTINEL', 'test_patch': 'PRIVATE_TEST_SENTINEL'}
                    for i in range(6) for j in range(2)]
        data = b''.join((json.dumps(r) + '\n').encode() for r in records)
        protocol['selection'].update(metadata_bytes=len(data),
            metadata_sha256=comparison.digest(data), distinct_ids=len(records))
        return protocol, data

    def test_success_projects_metadata_and_removes_all_raw_inputs(self):
        protocol, data = self.fixtures()
        destinations = []

        def acquire(kind, client, destination):
            destination.mkdir()
            destinations.append(destination)
            if kind == 'metadata':
                (destination / 'tasks.jsonl').write_bytes(data)
            else:
                (destination / 'r0-clean.zip').write_bytes(b'fixture baseline')
            print('SDK_SIGNED_URL_SENTINEL')
            return {'verified': True, 'files': 1}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'receipt.json'
            with patch.object(comparison, 'load_protocol', return_value=protocol), \
                    patch.object(comparison, 'build', return_value={'nonprompt_equality': 'PASS'}):
                captured = io.StringIO()
                with contextlib.redirect_stdout(captured):
                    report = research_cpu.prepare(output, root=root,
                        client_factory=contextlib.nullcontext, acquire_inputs=acquire)
            self.assertEqual(report['status'], 'PASS')
            self.assertEqual(len(report['selection']['primary']), 6)
            self.assertTrue(report['temporary_inputs_removed'])
            self.assertTrue(all(not p.exists() for p in destinations))
            self.assertEqual(captured.getvalue(), '')
            self.assertNotIn('PRIVATE_REFERENCE_SENTINEL', output.read_text())
            self.assertNotIn('SDK_SIGNED_URL_SENTINEL', output.read_text())
            self.assertNotIn('private issue', output.read_text())
            before = output.read_bytes()
            with self.assertRaises(ValueError):
                research_cpu.prepare(output, root=root)
            self.assertEqual(output.read_bytes(), before)

    def test_failure_redacts_exceptions_and_cleans_downloaded_metadata(self):
        protocol, data = self.fixtures()
        paths = []

        def acquire(kind, client, destination):
            destination.mkdir()
            paths.append(destination)
            (destination / 'tasks.jsonl').write_bytes(data)
            raise RuntimeError('secret URL and PRIVATE_REFERENCE_SENTINEL')

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(comparison, 'load_protocol', return_value=protocol):
                report = research_cpu.prepare(root / 'receipt.json', root=root,
                    client_factory=contextlib.nullcontext, acquire_inputs=acquire)
            self.assertEqual(report['status'], 'FAILED')
            self.assertEqual(report['error_type'], 'RuntimeError')
            self.assertEqual(report['phase'], 'metadata_download')
            self.assertTrue(report['temporary_inputs_removed'])
            self.assertTrue(all(not p.exists() for p in paths))
            self.assertNotIn('secret URL', json.dumps(report))
            self.assertNotIn('PRIVATE_REFERENCE_SENTINEL', json.dumps(report))

    def test_schema_has_only_names_and_types_and_requires_exact_bytes(self):
        protocol, data = self.fixtures()
        schema = research_cpu.source_schema(data, protocol)
        self.assertEqual(schema['fields']['patch'], ['str'])
        self.assertNotIn('PRIVATE_REFERENCE_SENTINEL', json.dumps(schema))
        with self.assertRaises(ValueError):
            research_cpu.source_schema(data + b'\n', protocol)


if __name__ == '__main__':
    unittest.main()
