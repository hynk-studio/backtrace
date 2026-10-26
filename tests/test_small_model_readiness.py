"""Token-count, provenance and matched-scope failure controls without third-party imports."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools import abductive_baseline as prompts
from tools import abductive_benchmark as base
from tools import exact_teacher as exact
from tools import small_model_readiness as ready


class FakeTokenizer:
    bos_token_id = 2
    def __init__(self):
        self.ids = [2, 7, 8, 9, 10]
        self.direct = self.ids.copy()
        self.mask = [1] * 5
        self.rendered = '<bos><|turn>system\nInstructions.<turn|>\n<|turn>user\nQuestion.<turn|>\n<|turn>model\n'
        self.calls = []

    def apply_chat_template(self, messages, **kwargs):
        self.calls.append(kwargs)
        return {'input_ids': self.ids, 'attention_mask': self.mask} if kwargs['tokenize'] else self.rendered

    def __call__(self, rendered, **kwargs):
        self.calls.append(kwargs)
        return {'input_ids': self.direct}


class TokenizationTests(unittest.TestCase):
    def test_counts_ids_not_batch_encoding_keys(self):
        tokenizer = FakeTokenizer()
        result = ready.encode(tokenizer, [], 5)
        self.assertEqual(result['input_tokens'], 5)
        self.assertFalse(result['overflow'])
        self.assertEqual(result['token_ids_sha256'], exact.sha(exact.canonical(tokenizer.ids)))
        self.assertFalse(tokenizer.calls[1]['truncation'])
        self.assertFalse(tokenizer.calls[1]['padding'])
        self.assertFalse(tokenizer.calls[1]['enable_thinking'])
        self.assertFalse(tokenizer.calls[2]['add_special_tokens'])

    def test_overflow_is_reported_without_truncating(self):
        result = ready.encode(FakeTokenizer(), [], 4)
        self.assertTrue(result['overflow'])
        self.assertEqual(result['input_tokens'], 5)

    def test_double_bos_or_different_tokenization_is_rejected(self):
        for values in ([2, 2, 8, 9, 10], [3, 7, 8, 9, 10]):
            tokenizer = FakeTokenizer()
            tokenizer.ids = tokenizer.direct = values
            with self.assertRaises(ValueError):
                ready.encode(tokenizer, [], 100)
        tokenizer = FakeTokenizer()
        tokenizer.direct = [2, 20, 21]
        with self.assertRaises(ValueError):
            ready.encode(tokenizer, [], 100)

    def test_nested_boolean_negative_and_padded_ids_rejected(self):
        for ids, mask in [([[2, 3]], [1]), ([2, True], [1, 1]), ([2, -1], [1, 1]), ([2, 3], [1, 0]), ([], [])]:
            tokenizer = FakeTokenizer()
            tokenizer.ids, tokenizer.mask = ids, mask
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                ready.encode(tokenizer, [], 100)

    def test_thinking_or_wrong_role_prefix_rejected(self):
        for text in ('<bos><|turn>user\nQuestion.<turn|>\n<|turn>model\n',
                     '<bos><|turn>system\n<|think|>Instructions.<|turn>model\n',
                     '<bos><|turn>system\nInstructions.<|turn>model\n<|channel>thought\n'):
            tokenizer = FakeTokenizer()
            tokenizer.rendered = text
            with self.assertRaises(ValueError):
                ready.encode(tokenizer, [], 100)

    def test_nearest_rank_quantiles_and_sum(self):
        result = ready.distribution(list(range(1, 101)))
        self.assertEqual(result, {'count': 100, 'min': 1, 'max': 100, 'sum': 5050, 'p50': 50, 'p95': 95, 'p99': 99})
        with self.assertRaises(ValueError):
            ready.distribution([])


class WeightLayoutTests(unittest.TestCase):
    def fixture(self):
        expected = {'model.embed_tokens.weight': [64, 32], 'lm_head.weight': [64, 32], 'model.norm.weight': [32]}
        header = {'model.language_model.embed_tokens.weight': {'shape': [64, 32], 'dtype': 'BF16'},
                  'model.language_model.norm.weight': {'shape': [32], 'dtype': 'BF16'}}
        return expected, header

    def test_tied_head_and_known_nontext_components_are_handled(self):
        expected, header = self.fixture()
        header['model.vision_tower.layer.weight'] = {'shape': [4, 4], 'dtype': 'BF16'}
        self.assertEqual(ready.compare_tensor_header(expected, header, set()), 0)
        with self.assertRaises(ValueError):
            ready.compare_tensor_header(expected, header, set(), tied=False)

    def test_missing_wrong_shape_precision_and_unknown_component_rejected(self):
        expected, header = self.fixture()
        changes = [lambda h:h.pop('model.language_model.norm.weight'),
                   lambda h:h['model.language_model.norm.weight'].update(shape=[64]),
                   lambda h:h['model.language_model.norm.weight'].update(dtype='F32'),
                   lambda h:h.update({'unknown.weight': {'shape': [1], 'dtype': 'BF16'}})]
        for change in changes:
            bad = deepcopy(header)
            change(bad)
            with self.assertRaises(ValueError):
                ready.compare_tensor_header(expected, bad, set())

    def test_only_exact_declared_redundant_keys_are_ignored(self):
        expected, header = self.fixture()
        key = 'model.layers.15.self_attn.k_proj.weight'
        header[key.replace('model.', 'model.language_model.', 1)] = {'shape': [8, 32], 'dtype': 'BF16'}
        self.assertEqual(ready.compare_tensor_header(expected, header, {key}), 1)
        with self.assertRaises(ValueError):
            ready.compare_tensor_header(expected, header, set())
        with self.assertRaises(ValueError):
            ready.compare_tensor_header(expected, header, {key + '.unexpected'})


class LocalCase(unittest.TestCase):
    def setUp(self):
        (exact.ROOT / '.local').mkdir(exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix='small-model-tests-', dir=exact.ROOT / '.local'))

    def tearDown(self):
        shutil.rmtree(self.root)


class ProvenanceTests(LocalCase):
    def test_full_packet_reconstruction_matches_published_hashes_without_labels(self):
        original = Path.read_bytes
        def guard(path):
            if path.name == 'evaluator.jsonl':
                raise AssertionError('label file opened')
            return original(path)
        with patch.object(Path, 'read_bytes', guard), patch.object(exact, 'solve', side_effect=AssertionError('solver called')):
            report = ready.rebuild_packets(self.root / 'reconstructed')
            packets, _ = ready.read_packets(self.root / 'reconstructed')
        self.assertEqual(report['assigned_per_packet'], 1440)
        self.assertTrue(all(len(rows) == 1440 for rows in packets.values()))

    def test_bytes_sizes_and_symlinks_are_checked(self):
        path = self.root / 'source'
        path.write_bytes(b'abc')
        spec = {'bytes': 3, 'sha256': exact.sha(b'abc')}
        self.assertEqual(ready.checked_file(path, spec), b'abc')
        for wrong in ({'bytes': 4, 'sha256': spec['sha256']}, {'bytes': 3, 'sha256': '0'*64}):
            with self.assertRaises(ValueError):
                ready.checked_file(path, wrong)
        link = self.root / 'link'
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            ready.checked_file(link, spec)

    def test_existing_destination_is_preserved_before_network_access(self):
        destination = self.root / 'exists'
        destination.mkdir()
        (destination / 'keep').write_text('keep')
        with patch.object(ready.urllib.request, 'urlopen', side_effect=AssertionError('network')):
            with self.assertRaises(FileExistsError):
                ready.acquire_sources(destination)
        self.assertEqual((destination / 'keep').read_text(), 'keep')

    def test_failed_download_cleans_only_new_destination(self):
        destination = self.root / 'download'
        with patch.object(ready.urllib.request, 'urlopen', side_effect=OSError('offline')):
            with self.assertRaises(OSError):
                ready.acquire_sources(destination)
        self.assertFalse(destination.exists())

    def test_wrong_python_or_dependency_version_rejected(self):
        with patch.object(ready.platform, 'python_version', return_value='0.0.0'):
            with self.assertRaises(ValueError):
                ready.check_packages()
        with patch.object(ready.platform, 'python_version', return_value='3.12.14'), \
             patch.object(ready.importlib.metadata, 'version', return_value='0.0.0'):
            with self.assertRaises(ValueError):
                ready.check_packages()

    def packets(self):
        family = next(f for f, (split, _) in base.catalog().items() if split == 'development')
        payload = {'task': 'inference', 'question': base.make_question(family, 0)}
        identifier = exact.sha(exact.canonical(payload))
        result, files = {}, {}
        directory = self.root / 'packets'
        directory.mkdir()
        for name in sorted(ready.PACKETS):
            arm, rendering = name[:-6].split('-', 1)
            rows = [{'id': identifier, 'messages': prompts.messages(payload, arm, rendering)}]
            raw = b''.join(exact.canonical(row) for row in rows)
            (directory / name).write_bytes(raw)
            result[name] = rows
            files[name] = base.file_info(raw)
        manifest = {'files': files, 'assigned_cases_per_packet': 1}
        raw = exact.canonical(manifest)
        (directory / 'manifest.json').write_bytes(raw)
        spec = deepcopy(ready.lock())
        spec['baseline_manifest_sha256'] = exact.sha(raw)
        return directory, result, spec

    def test_paired_packet_read_never_opens_labels_or_calls_solver(self):
        directory, expected, spec = self.packets()
        original = Path.read_bytes
        def guard(path):
            if path.name == 'evaluator.jsonl':
                raise AssertionError('labels opened')
            return original(path)
        with patch.object(ready, 'lock', return_value=spec), patch.object(Path, 'read_bytes', guard), \
             patch.object(exact, 'solve', side_effect=AssertionError('solver called')):
            observed, _ = ready.read_packets(directory)
        self.assertEqual(observed, expected)

    def test_foreign_member_and_tampered_packet_rejected(self):
        directory, _, spec = self.packets()
        with patch.object(ready, 'lock', return_value=spec):
            (directory / 'evaluator.jsonl').write_text('labels')
            with self.assertRaises(ValueError):
                ready.read_packets(directory)
            (directory / 'evaluator.jsonl').unlink()
            with (directory / 'B0-json.jsonl').open('ab') as stream:
                stream.write(b' ')
            with self.assertRaises(ValueError):
                ready.read_packets(directory)

    def test_changed_manifest_cannot_rehash_mutated_prompts(self):
        directory, _, spec = self.packets()
        manifest = base.strict_json((directory / 'manifest.json').read_bytes())
        manifest['assigned_cases_per_packet'] = 2
        (directory / 'manifest.json').write_bytes(exact.canonical(manifest))
        with patch.object(ready, 'lock', return_value=spec), self.assertRaises(ValueError):
            ready.read_packets(directory)


class ScopeTests(LocalCase):
    def fixture(self):
        selection = ready.selected_cases(8)
        packets = {name: [{'id': row['id'], 'messages': []} for row in selection] for name in ready.PACKETS}
        rows = [dict(ready.encode(FakeTokenizer(), [], 100), model=model, packet=packet, id=row['id'])
                for model in ready.MODELS for packet, values in packets.items() for row in values]
        report = {'status': 'PASS_TOKENIZATION_ONLY', 'overflow': 0, 'source_hashes': ready.source_hashes(),
                  'baseline_manifest_sha256': ready.lock()['baseline_manifest_sha256'],
                  'generation': ready.lock()['generation'], 'cases': rows, 'assignments': len(rows),
                  'summaries': {model: {packet: dict(ready.distribution([5]*len(values)), overflow=0)
                                         for packet, values in packets.items()} for model in ready.MODELS}}
        return selection, packets, report

    def test_selection_preserves_complete_episodes_and_development_membership(self):
        with patch.object(exact, 'solve', side_effect=AssertionError('solver called')):
            selected = ready.selected_cases(8)
        self.assertEqual(len(selected), 72)
        families = {r['family'] for r in selected}
        self.assertEqual(len(families), 8)
        self.assertTrue(all(base.catalog()[f][0] == 'development' for f in families))
        for family in families:
            rows = [r for r in selected if r['family'] == family]
            self.assertEqual(len({r['episode'] for r in rows}), 1)
            self.assertEqual({r['as_of'] for r in rows if r['task']=='temporal_revision'}, {2,3,4,5})
            self.assertEqual({r['as_of'] for r in rows if r['task']=='revision'}, {1,2,3})
        for invalid in (0, 9, True):
            with self.assertRaises(ValueError):
                ready.selected_cases(invalid)

    def test_missing_duplicate_foreign_and_inflated_token_rows_rejected(self):
        _, packets, report = self.fixture()
        ready.validate_report(report, packets)
        changes = [lambda r:r['cases'].pop(), lambda r:r['cases'].append(r['cases'][0]),
                   lambda r:r['cases'][0].update(id='foreign'),
                   lambda r:r['cases'][0].update(input_tokens=999999),
                   lambda r:r['cases'][0].update(input_tokens=True),
                   lambda r:r['cases'][0].update(overflow=True),
                   lambda r:r['cases'][0].update(token_ids_sha256='bad')]
        for change in changes:
            changed=deepcopy(report)
            change(changed)
            with self.assertRaises(ValueError):
                ready.validate_report(changed, packets)

    def test_stale_sources_overflow_and_false_summary_rejected(self):
        _, packets, report=self.fixture()
        changes=[lambda r:r.update(status='FAIL_OVERFLOW'), lambda r:r.update(source_hashes={}),
                 lambda r:r['summaries']['E2B']['B0-json.jsonl'].update(sum=0)]
        for change in changes:
            changed=deepcopy(report)
            change(changed)
            with self.assertRaises(ValueError):
                ready.validate_report(changed,packets)

    def test_smoke_and_screening_budgets_remain_matched_and_unauthorized(self):
        _, packets, report=self.fixture()
        path=self.root/'tokens.json'
        path.write_bytes(exact.canonical(report))
        for scope, expected in [('smoke',18),('screening',144)]:
            with patch.object(ready,'read_packets',return_value=(packets,{})):
                plan=ready.prepare_scope(self.root,path,self.root/scope,scope=scope)
            self.assertEqual(plan['requests_per_model'],expected)
            self.assertEqual(plan['total_requests'],expected*2)
            self.assertFalse(plan['gpu_run_authorized'])
            self.assertEqual(plan['max_output_tokens_per_model'],expected*4096)
            self.assertEqual(plan['input_tokens_per_model'],{'E2B':expected*5,'E4B':expected*5})
            self.assertEqual({v['records'] for v in plan['files'].values()},{expected//2})


if __name__ == '__main__':
    unittest.main()
