"""Pin and check real tokenizers and prepare development-only execution scopes.

No pretrained weights are downloaded or executed by this module.
"""
import argparse
from copy import deepcopy
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import re
import shutil
import struct
import sys
import urllib.request

from tools import abductive_baseline as prompts
from tools import abductive_benchmark as base
from tools import exact_teacher as exact
from tools import temporal_benchmark as temporal


LOCK_PATH = exact.ROOT / 'docs/small-model-runtime-lock-v1.json'
FILES = {'config.json', 'generation_config.json', 'tokenizer_config.json',
         'chat_template.jinja', 'tokenizer.json', 'processor_config.json', 'README.md'}
MODELS = {'E2B': 'google/gemma-4-E2B-it', 'E4B': 'google/gemma-4-E4B-it'}
NON_TEXT_PREFIXES = ('model.audio_tower.', 'model.vision_tower.', 'model.embed_audio.', 'model.embed_vision.')
PACKETS = {f'{arm}-{rendering}.jsonl' for arm in ('B0', 'B1') for rendering in ('json', 'controlled_text')}


def lock():
    data = base.strict_json(LOCK_PATH.read_bytes())
    if data['version'] != 'small-model-runtime-lock-v1' or set(data['models']) != set(MODELS):
        raise ValueError('unsupported runtime lock')
    for name, spec in data['models'].items():
        if spec['repo_id'] != MODELS[name] or set(spec['files']) != FILES:
            raise ValueError('unexpected model or source file')
        if len(spec['revision']) != 40 or any(c not in '0123456789abcdef' for c in spec['revision']):
            raise ValueError('immutable model revision required')
        header = spec['tensor_header']
        if (type(header['bytes']) is not int or not 0 < header['bytes'] < 1_000_000
                or header['range_end_inclusive'] != header['bytes'] + 7
                or header['url'] != f"https://huggingface.co/{spec['repo_id']}/resolve/{spec['revision']}/model.safetensors"):
            raise ValueError('invalid bounded tensor-header source')
    return data


def source_hashes():
    return dict(temporal.source_hashes(), **{name: exact.sha((exact.ROOT / name).read_bytes()) for name in (
        'tools/abductive_baseline.py', 'docs/abductive-baseline-protocol-v1.json',
        'tools/small_model_readiness.py', 'docs/small-model-runtime-lock-v1.json',
        'docs/small-model-cpu-requirements.txt', 'docs/small-model-gpu-requirements.txt')})


def checked_file(path, spec, maximum=64 * 1024 * 1024):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise ValueError('unsafe or oversized file')
    raw = path.read_bytes()
    if len(raw) != spec['bytes'] or exact.sha(raw) != spec['sha256']:
        raise ValueError('source bytes differ from lock')
    return raw


def validate_sources(root):
    root = exact._local_path(root)
    for name, spec in lock()['models'].items():
        directory = exact._local_path(root / name)
        allowed = FILES | {'hub-metadata.json', 'hub-tree.json', 'tensor-header.json'}
        if {p.name for p in directory.iterdir()} - allowed or any(p.is_symlink() for p in directory.iterdir()):
            raise ValueError('unexpected model directory member')
        for filename, info in spec['files'].items():
            checked_file(directory / filename, info)
        checked_file(directory / 'tensor-header.json', spec['tensor_header'], maximum=1_000_000)
    return root


def acquire_sources(output):
    """Fetch only the seven fixed public metadata/tokenizer files per model."""
    output = exact._local_path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    try:
        for name, spec in lock()['models'].items():
            (output / name).mkdir(mode=0o700)
            for filename, info in spec['files'].items():
                url = f"https://huggingface.co/{spec['repo_id']}/resolve/{spec['revision']}/{filename}"
                if url != info['url'] or not 0 < info['bytes'] <= 64 * 1024 * 1024:
                    raise ValueError('invalid pinned source')
                with urllib.request.urlopen(url, timeout=45) as response:
                    raw = response.read(info['bytes'] + 1)
                if len(raw) != info['bytes'] or exact.sha(raw) != info['sha256']:
                    raise ValueError('downloaded source mismatch')
                base.private_write(output / name / filename, raw)
            header = spec['tensor_header']
            request = urllib.request.Request(header['url'], headers={'Range': f"bytes=0-{header['range_end_inclusive']}"})
            with urllib.request.urlopen(request, timeout=45) as response:
                expected_range = f"bytes 0-{header['range_end_inclusive']}/{header['total_file_bytes']}"
                if response.status != 206 or response.headers.get('Content-Range') != expected_range:
                    raise ValueError('server did not honor the pinned bounded header range')
                raw = response.read(header['bytes'] + 9)
            if (len(raw) != header['bytes'] + 8 or struct.unpack('<Q', raw[:8])[0] != header['bytes']
                    or exact.sha(raw[8:]) != header['sha256']):
                raise ValueError('tensor header mismatch')
            base.private_write(output / name / 'tensor-header.json', raw[8:])
        validate_sources(output)
        return {'status': 'PASS_METADATA_AND_TOKENIZERS', 'models': list(MODELS),
                'lock_sha256': exact.sha(LOCK_PATH.read_bytes()), 'pretrained_weights_downloaded': False}
    except BaseException:
        shutil.rmtree(output)
        raise


def read_packets(directory):
    directory = exact._local_path(directory)
    if {p.name for p in directory.iterdir()} != {'manifest.json', *PACKETS}:
        raise ValueError('only the four qualified prompt packets and manifest are accepted')
    manifest_path = directory / 'manifest.json'
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 1_000_000:
        raise ValueError('unsafe prompt manifest')
    raw = manifest_path.read_bytes()
    manifest = base.strict_json(raw)
    if exact.sha(raw) != lock()['baseline_manifest_sha256']:
        raise ValueError('unqualified prompt manifest')
    packets = {}
    for name in sorted(PACKETS):
        content = checked_file(directory / name, manifest['files'][name])
        rows = [base.strict_json(line) for line in content.splitlines()]
        if len(rows) != manifest['assigned_cases_per_packet'] or len({r['id'] for r in rows}) != len(rows):
            raise ValueError('wrong or duplicate assigned cases')
        packets[name] = rows
    ids = [r['id'] for r in packets['B0-json.jsonl']]
    if any([r['id'] for r in rows] != ids for rows in packets.values()):
        raise ValueError('unpaired packet IDs')
    for index, row in enumerate(packets['B0-json.jsonl']):
        exact._keys(row, {'id', 'messages'})
        payload = base.strict_json(row['messages'][1]['content'])
        if exact.sha(exact.canonical(payload)) != row['id']:
            raise ValueError('input identity mismatch')
        for name, rows in packets.items():
            arm, rendering = name[:-6].split('-', 1)
            exact._keys(rows[index], {'id', 'messages'})
            if rows[index]['messages'] != prompts.messages(payload, arm, rendering):
                raise ValueError('prompt differs from qualified rendering')
    return packets, manifest


def rebuild_packets(output):
    """Recreate exactly the previously qualified input bytes without solving any case."""
    receipt = base.strict_json((exact.ROOT / 'docs/temporal-baseline-cpu-20261026.json').read_bytes())
    manifest = receipt['native_linux']['baseline_preparation']
    if exact.sha(exact.canonical(manifest)) != lock()['baseline_manifest_sha256']:
        raise ValueError('qualified packet receipt differs from runtime lock')
    for name, digest in manifest['source_hashes'].items():
        if exact.sha((exact.ROOT / name).read_bytes()) != digest:
            raise ValueError('original prompt source changed')
    inputs = []
    for family, (split, _) in base.catalog().items():
        if split != 'development':
            continue
        for variant in range(20):
            question = base.make_question(family, variant)
            for payload in [*base.episode_inputs(question), *temporal.episode_inputs(family, variant)]:
                inputs.append({'id': exact.sha(exact.canonical(payload)), 'input': payload})
    inputs.sort(key=lambda row: row['id'])
    if len(inputs) != manifest['assigned_cases_per_packet']:
        raise ValueError('reconstructed assignment size differs')
    output = exact._local_path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    try:
        for name in sorted(PACKETS):
            arm, rendering = name[:-6].split('-', 1)
            content = b''.join(exact.canonical({'id': row['id'], 'messages': prompts.messages(row['input'], arm, rendering)})
                               for row in inputs)
            expected = {k: manifest['files'][name][k] for k in ('sha256', 'bytes', 'records')}
            if base.file_info(content) != expected:
                raise ValueError('reconstructed packet bytes differ from qualified bytes')
            base.private_write(output / name, content)
        base.private_write(output / 'manifest.json', exact.canonical(manifest))
        return {'status': 'PASS_QUALIFIED_INPUT_RECONSTRUCTION', 'baseline_manifest_sha256': lock()['baseline_manifest_sha256'],
                'assigned_per_packet': len(inputs), 'packet_files': len(PACKETS), 'solver_called': False}
    except BaseException:
        shutil.rmtree(output)
        raise


def encode(tokenizer, messages, max_input_tokens):
    # Transformers 5.20 returns a BatchEncoding by default; len(result) is NOT
    # a token count. Require input_ids and compare with the rendered-text route.
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                              enable_thinking=False)
    encoded = tokenizer.apply_chat_template(messages, tokenize=True, return_dict=True,
                                             add_generation_prompt=True, enable_thinking=False,
                                             truncation=False, padding=False)
    ids = encoded['input_ids']
    if (not isinstance(ids, list) or not ids or any(type(i) is not int or i < 0 for i in ids)
            or encoded['attention_mask'] != [1] * len(ids)):
        raise ValueError('unbatched unpadded token IDs required')
    direct = tokenizer(rendered, add_special_tokens=False, truncation=False, padding=False)['input_ids']
    if ids != direct or ids.count(tokenizer.bos_token_id) != 1 or ids[0] != tokenizer.bos_token_id:
        raise ValueError('template/direct encoding mismatch or duplicated BOS')
    if not rendered.startswith('<bos><|turn>system\n') or not rendered.endswith('<|turn>model\n'):
        raise ValueError('unexpected system/generation role mapping')
    if '<|think|>' in rendered or '<|channel>thought' in rendered:
        raise ValueError('unexpected thinking-mode prefix')
    return {'input_tokens': len(ids), 'overflow': len(ids) > max_input_tokens,
            'token_ids_sha256': exact.sha(exact.canonical(ids)), 'rendered_sha256': exact.sha(rendered.encode())}


def distribution(values):
    values = sorted(values)
    if not values:
        raise ValueError('nonempty distribution required')
    return {'count': len(values), 'min': values[0], 'max': values[-1], 'sum': sum(values),
            **{f'p{q}': values[math.ceil(len(values) * q / 100) - 1] for q in (50, 95, 99)}}


def check_packages():
    spec = lock()['cpu_runtime']
    if platform.python_version() != spec['python']:
        raise ValueError('Python runtime differs from lock')
    actual = {name: importlib.metadata.version(name) for name in spec['packages']}
    if actual != spec['packages']:
        raise ValueError('CPU dependency versions differ from lock')
    return actual


def compare_tensor_header(expected, header, ignored, *, tied=True):
    observed = {}
    for key, value in header.items():
        if key == '__metadata__' or key.startswith(NON_TEXT_PREFIXES):
            continue
        if not key.startswith('model.language_model.') and key != 'lm_head.weight':
            raise ValueError('unknown checkpoint component')
        if value['dtype'] != 'BF16':
            raise ValueError('unexpected text checkpoint precision')
        observed[key.replace('model.language_model.', 'model.', 1)] = value['shape']
    if 'lm_head.weight' not in observed and tied and 'model.embed_tokens.weight' in observed:
        observed['lm_head.weight'] = observed['model.embed_tokens.weight']
    extra = set(observed) - set(expected)
    if (set(expected) - set(observed) or any(expected[k] != observed[k] for k in expected)
            or extra - set(ignored)):
        raise ValueError('official text tensor header does not match the mapped model layout')
    return len(extra)


def inspect_models(root):
    import torch
    from transformers import AutoConfig, Gemma4ForCausalLM
    result = {}
    for name in MODELS:
        config = AutoConfig.from_pretrained(root / name, local_files_only=True, trust_remote_code=False)
        with torch.device('meta'):
            model = Gemma4ForCausalLM(config.text_config)
        if any(not p.is_meta for p in model.parameters()):
            raise ValueError('metadata probe allocated model tensors')
        count = sum(p.numel() for p in model.parameters())
        header = base.strict_json((root / name / 'tensor-header.json').read_bytes())
        expected = {key: list(value.shape) for key, value in model.state_dict().items()}
        ignored = {'model.' + key + '.weight' for key in model.model._keys_to_ignore_on_load_unexpected}
        extra = compare_tensor_header(expected, header, ignored, tied=config.text_config.tie_word_embeddings)
        result[name] = {'model_class': type(model).__name__, 'text_parameter_count_meta': count,
                        'bf16_text_weight_bytes_lower_bound': count * 2,
                        'max_position_embeddings': config.text_config.max_position_embeddings,
                        'mapped_text_tensor_shapes_verified': len(expected), 'redundant_shared_kv_tensors': extra,
                        'tensor_values_verified': False, 'pretrained_weights_loaded': False, 'gpu_memory_measured': False}
        del model
    return result


def random_layout_probe(source, output):
    """Tiny random tensors exercise real E2B/E4B layer layouts, never pretrained capability."""
    check_packages()
    root = validate_sources(source)
    import torch
    from transformers import AutoConfig, Gemma4Config, Gemma4ForCausalLM, Gemma4ForConditionalGeneration, Gemma4TextConfig
    torch.set_num_threads(1)
    output = exact._local_path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    results = {}
    try:
        for name in MODELS:
            original = AutoConfig.from_pretrained(root / name, local_files_only=True, trust_remote_code=False)
            config = deepcopy(original.text_config.to_dict())
            config.update(vocab_size=64, vocab_size_per_layer_input=64, hidden_size=32, intermediate_size=64,
                          head_dim=8, global_head_dim=8, num_attention_heads=4, hidden_size_per_layer_input=4,
                          max_position_embeddings=128, sliding_window=32, dtype='float32')
            text_config = Gemma4TextConfig.from_dict(config)
            full_config = Gemma4Config(text_config=text_config, vision_config=None, audio_config=None)
            full_config._attn_implementation = 'sdpa'
            torch.manual_seed(17)
            full = Gemma4ForConditionalGeneration(full_config).eval()
            inputs = torch.tensor([[2, 3, 4, 5]], dtype=torch.long)
            with torch.inference_mode():
                expected = full(input_ids=inputs).logits
            destination = output / name
            full.save_pretrained(destination, safe_serialization=True)
            causal, info = Gemma4ForCausalLM.from_pretrained(destination, local_files_only=True,
                trust_remote_code=False, dtype=torch.float32, attn_implementation='sdpa', output_loading_info=True,
                key_mapping=lock()['model_loading']['key_mapping'])
            causal.eval()
            if any(info.get(key) for key in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
                raise ValueError('random full-to-text checkpoint mapping mismatch')
            with torch.inference_mode():
                observed = causal(input_ids=inputs).logits
                generated = causal.generate(inputs, max_new_tokens=2, do_sample=False,
                                             eos_token_id=1, pad_token_id=0)
            if not torch.equal(expected, observed) or not torch.equal(generated[:, :4], inputs):
                raise ValueError('random-layout logits or generation-prefix mismatch')
            results[name] = {'status': 'PASS_RANDOM_LAYOUT_ONLY', 'layers': text_config.num_hidden_layers,
                             'kv_shared_layers': text_config.num_kv_shared_layers,
                             'double_wide_mlp': text_config.use_double_wide_mlp,
                             'logits_max_abs_difference': float((expected - observed).abs().max()),
                             'generated_tokens': int(generated.shape[-1] - inputs.shape[-1]),
                             'pretrained_weights_loaded': False, 'training_performed': False}
            del causal, full
        base.private_write(output / 'report.json', exact.canonical(results))
        return results
    except BaseException:
        # Keep the failed probe's tiny random checkpoint for diagnosis.
        base.private_write(output / 'failed.json', exact.canonical({'status': 'FAIL_RANDOM_LAYOUT_ONLY'}))
        raise


def tokenize_packets(source, packets_path, output):
    packages = check_packages()
    root = validate_sources(source)
    packets, manifest = read_packets(packets_path)
    from transformers import AutoTokenizer
    models = inspect_models(root)
    limits = lock()['generation']
    rows, summaries = [], {}
    for name in MODELS:
        tokenizer = AutoTokenizer.from_pretrained(root / name, local_files_only=True, trust_remote_code=False)
        if limits['max_input_tokens'] + limits['max_new_tokens'] > models[name]['max_position_embeddings']:
            raise ValueError('experiment ceiling exceeds model context')
        summaries[name] = {}
        for packet, inputs in packets.items():
            selected = []
            for item in inputs:
                value = encode(tokenizer, item['messages'], limits['max_input_tokens'])
                value.update(model=name, packet=packet, id=item['id'])
                selected.append(value)
                rows.append(value)
            summaries[name][packet] = dict(distribution([r['input_tokens'] for r in selected]),
                                            overflow=sum(r['overflow'] for r in selected))
    overflow = sum(r['overflow'] for r in rows)
    report = {'status': 'FAIL_OVERFLOW' if overflow else 'PASS_TOKENIZATION_ONLY',
              'source_hashes': source_hashes(), 'cpu_packages': packages, 'models': models,
              'summaries': summaries, 'assignments': len(rows), 'overflow': overflow,
              'baseline_manifest_sha256': exact.sha(exact.canonical(manifest)),
              'generation': limits, 'pretrained_model_evaluation': 'NOT_RUN',
              'gpu_qualification': 'NOT_RUN', 'runtime_isolation': 'NOT_PROVEN', 'cases': rows}
    base.private_write(exact._local_path(output), exact.canonical(report))
    return report


def selected_cases(family_count):
    """Prespecified development families, variant 0; no reference/label access."""
    families = sorted(f for f, (split, _) in base.catalog().items() if split == 'development')
    if type(family_count) is not int or not 1 <= family_count <= len(families):
        raise ValueError('invalid development family count')
    selected = []
    for family in families[:family_count]:
        question = base.make_question(family, 0)
        episode = exact.sha(exact.canonical(question))
        payloads = list(base.episode_inputs(question)) + list(temporal.episode_inputs(family, 0))
        for payload in payloads:
            selected.append({'id': exact.sha(exact.canonical(payload)), 'family': family, 'episode': episode,
                             'task': payload['task'], 'as_of': payload.get('as_of')})
    return selected


def validate_report(report, packets):
    spec = lock()
    if (report['status'] != 'PASS_TOKENIZATION_ONLY' or report['overflow'] != 0
            or report['source_hashes'] != source_hashes()
            or report['baseline_manifest_sha256'] != lock()['baseline_manifest_sha256']
            or report['generation'] != lock()['generation']):
        raise ValueError('unqualified tokenization report')
    expected = {(model, packet, row['id']) for model in MODELS for packet, rows in packets.items() for row in rows}
    observed = set()
    grouped = {}
    for row in report['cases']:
        exact._keys(row, {'input_tokens', 'overflow', 'token_ids_sha256', 'rendered_sha256', 'model', 'packet', 'id'})
        key = (row['model'], row['packet'], row['id'])
        count = row['input_tokens']
        if (key not in expected or key in observed or type(count) is not int or
                not 0 < count <= spec['generation']['max_input_tokens'] or row['overflow'] is not False
                or any(not isinstance(row[k], str) or not re.fullmatch('[0-9a-f]{64}', row[k])
                       for k in ('token_ids_sha256', 'rendered_sha256'))):
            raise ValueError('invalid tokenization assignment')
        observed.add(key)
        grouped.setdefault(key[:2], []).append(count)
    if observed != expected or report['assignments'] != len(expected):
        raise ValueError('incomplete tokenization report')
    for (model, packet), values in grouped.items():
        if report['summaries'][model][packet] != dict(distribution(values), overflow=0):
            raise ValueError('token summary mismatch')


def prepare_scope(packets_path, report_path, output, *, scope='smoke'):
    if scope not in ('smoke', 'screening'):
        raise ValueError('unsupported development scope')
    packets, _ = read_packets(packets_path)
    report_path = exact._local_path(report_path)
    if report_path.is_symlink() or report_path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('unsafe tokenization report')
    raw = report_path.read_bytes()
    report = base.strict_json(raw)
    validate_report(report, packets)
    selection = selected_cases(1 if scope == 'smoke' else 8)
    ids = {row['id'] for row in selection}
    output = exact._local_path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    try:
        files = {}
        for name in ('B0-json.jsonl', 'B1-json.jsonl'):
            selected = [r for r in packets[name] if r['id'] in ids]
            if len(selected) != len(ids):
                raise ValueError('selection absent from qualified input grid')
            content = b''.join(exact.canonical(row) for row in selected)
            base.private_write(output / name, content)
            files[name] = base.file_info(content)
        tokens = {model: sum(c['input_tokens'] for c in report['cases']
                            if c['model'] == model and c['id'] in ids and c['packet'] in files) for model in MODELS}
        requests = len(ids) * len(files)
        plan = {'version': 'small-model-development-scope-v1', 'scope': scope,
                'status': 'PREPARED_NOT_GPU_QUALIFIED', 'split': 'development',
                'selection': selection, 'selection_rule': 'SHA-ordered development families, variant 0, all nine views; no outcome selection',
                'files': files, 'models': {n: {'repo_id': s['repo_id'], 'revision': s['revision']}
                                         for n, s in lock()['models'].items()},
                'requests_per_model': requests, 'total_requests': requests * len(MODELS),
                'input_tokens_per_model': tokens,
                'max_output_tokens_per_model': requests * lock()['generation']['max_new_tokens'],
                'generation': lock()['generation'], 'source_hashes': source_hashes(),
                'model_loading': lock()['model_loading'],
                'execution_limits_proposal': lock()['scope_limits_proposal'] if scope == 'smoke' else None,
                'tokenization_report_sha256': exact.sha(raw),
                'interpretation': 'implementation/throughput probe' if scope == 'smoke' else 'descriptive pilot; one episode per family, not a powered confirmation',
                'gpu_run_authorized': False, 'runtime_isolation': 'NOT_PROVEN',
                'missing_or_failed_assigned_cases': 'retained in denominator; no retries or replacement cases',
                'remaining_gates': ['actual checkpoint load and GPU peak/throughput', 'isolated inputs-only runtime',
                                    'fresh resource/price/balance check and bounded owner authorization if paid']}
        base.private_write(output / 'plan.json', exact.canonical(plan))
        return plan
    except BaseException:
        shutil.rmtree(output)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    acquire = commands.add_parser('acquire')
    acquire.add_argument('output', type=Path)
    rebuild = commands.add_parser('rebuild-packets')
    rebuild.add_argument('output', type=Path)
    tokenize = commands.add_parser('tokenize')
    tokenize.add_argument('source', type=Path)
    tokenize.add_argument('packets', type=Path)
    tokenize.add_argument('output', type=Path)
    probe = commands.add_parser('random-layout-probe')
    probe.add_argument('source', type=Path)
    probe.add_argument('output', type=Path)
    scope = commands.add_parser('prepare-scope')
    scope.add_argument('packets', type=Path)
    scope.add_argument('report', type=Path)
    scope.add_argument('output', type=Path)
    scope.add_argument('--scope', choices=('smoke', 'screening'), default='smoke')
    args = parser.parse_args(argv)
    try:
        if args.command == 'acquire':
            report = acquire_sources(args.output)
        elif args.command == 'rebuild-packets':
            report = rebuild_packets(args.output)
        elif args.command == 'tokenize':
            report = tokenize_packets(args.source, args.packets, args.output)
        elif args.command == 'random-layout-probe':
            report = {'status': 'PASS_RANDOM_LAYOUT_ONLY', 'models': random_layout_probe(args.source, args.output)}
        else:
            report = prepare_scope(args.packets, args.report, args.output, scope=args.scope)
    except (OSError, ValueError, TypeError, KeyError, ImportError) as error:
        print('small model readiness failed: ' + type(error).__name__, file=sys.stderr)
        return 2
    print(json.dumps({k: v for k, v in report.items() if k not in ('cases', 'selection')}, sort_keys=True, indent=2))
    return 0 if report['status'] != 'FAIL_OVERFLOW' else 2


if __name__ == '__main__':
    raise SystemExit(main())
