"""Train-only CPU audit of the executed candidate and a prospective full target.

No pretrained model weights, GPU/provider entry, evaluation labels or training
updates. The historical generator, worker, masks and results remain unchanged.
"""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path

from tools import small_model_matched_data as data
from tools import small_model_readiness as ready
from tools import small_model_worker as worker
from tools.small_model_sft_inputs import causal_example, full_completion_example

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / 'docs/evidence/matched-qualified-run-41241191354/inputs/input-verification.json'
HISTORICAL_SHA256 = 'a178dd38eeb3826132e015c6b568dbed79e9b87bbd0a51797845f902ebc0e611'


def audit_targets(pairs):
    counts = Counter()
    for pair in pairs:
        if pair['split'] != 'train' or data.base.catalog()[pair['family']][0] != 'train':
            raise ValueError('audit accepts training families only')
        for arm in data.ARMS:
            row = pair['arms'][arm]
            answer = data.base.strict_json(row['answer'])
            if pair['kind'] == 'common_format':
                fields = data.base.strict_json(row['messages'][1]['content'])['fields']
                if answer != dict(fields):
                    raise ValueError('format target differs from its supplied values')
            else:
                payload = data.base.strict_json(row['messages'][1]['content'])
                converted, ref = data.reference(payload)
                data.score.validate_response(converted, answer)
                expected = (data.score.optimal_response(converted, ref) if arm == 'S'
                            else data.forward_answer(payload))
                if answer != expected:
                    raise ValueError('target differs from its declared objective')
                if arm == 'S':
                    scored = data.score.score_case(converted, answer, ref=ref)
                    if scored['response_status'] != 'VALID' or any(scored['losses'].values()):
                        raise ValueError('specialist target fails its own exact evaluator')
                counts[f'{arm}:{answer["status"]}'] += 1
            counts[f'{arm}:{pair["kind"]}'] += 1
    return {'checked_targets': len(pairs) * len(data.ARMS), 'counts': dict(counts),
            'boundary': 'Exact-teacher consistency, not an independent proof of all teacher labels.'}


def audit_tokens(tokenizer, pairs):
    historical_raw = HISTORICAL.read_bytes()
    if hashlib.sha256(historical_raw).hexdigest() != HISTORICAL_SHA256:
        raise ValueError('historical input evidence changed')
    historical = json.loads(historical_raw)
    materialized = data.materialize(tokenizer)
    for arm in data.ARMS:
        if data.digest(materialized['specifications'][arm]) != historical['specification_sha256'][arm]:
            raise ValueError('historical training specification did not reproduce')
    if materialized['pairs'] != historical['training']['pairs']:
        raise ValueError('historical token identities did not reproduce')
    generation = ready.lock()['generation']
    totals = {arm: Counter() for arm in data.ARMS}
    terminals = Counter()
    for index, pair in enumerate(pairs):
        for arm in data.ARMS:
            row = materialized['specifications'][arm]['rows'][index]
            new = full_completion_example(tokenizer, row['messages'], row['answer'],
                eos_token_ids=generation['eos_token_ids'], padded_tokens=row['padded_tokens'])
            prompt = worker.candidate_prompt(tokenizer, row['messages'])
            old_answer = tokenizer.encode(row['answer'], add_special_tokens=False) + [106]
            original_ids = prompt + old_answer
            actual_length = sum(new['attention_mask'])
            if new['input_ids'][:actual_length] != original_ids:
                raise ValueError('historical separate encoding differs from the full chat template')
            if tokenizer.pad_token_id != generation['pad_token_id']:
                raise ValueError('padding token differs from the pinned generation contract')
            supervised = sum(label != -100 for label in new['labels'])
            if supervised != len(old_answer) or new['labels'][len(prompt):actual_length] != old_answer:
                raise AssertionError('full completion is not supervised exactly once')
            dropped = len(old_answer) - len(row['supervised_positions'])
            totals[arm].update(rows=1, prompt_tokens=len(prompt), answer_tokens=len(old_answer),
                old_supervised_tokens=len(row['supervised_positions']),
                new_supervised_tokens=supervised, old_omitted_tokens=dropped,
                rows_with_omissions=int(dropped > 0), padded_tokens=len(new['input_ids']),
                omitted_first_answer_tokens=int(0 not in row['supervised_positions']))
            terminals[new['terminal_token_id']] += 1
    return {'historical_specifications_reproduced': historical['specification_sha256'],
            'historical_input_evidence_sha256': HISTORICAL_SHA256,
            'all_full_chat_and_historical_sequence_ids_equal': True,
            'all_generation_prefixes_equal': True, 'terminal_token_counts': dict(terminals),
            'totals': {arm: dict(value) for arm, value in totals.items()}}


def audit_causal_loss():
    """Compare the pinned actual model loss with independent shifted cross entropy."""
    import torch
    from transformers import Gemma4TextConfig, Gemma4ForCausalLM
    torch.set_num_threads(1)
    torch.manual_seed(17)
    config = Gemma4TextConfig(vocab_size=128, vocab_size_per_layer_input=128,
        hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=4,
        num_key_value_heads=2, head_dim=8, global_head_dim=8, hidden_size_per_layer_input=4,
        max_position_embeddings=128, sliding_window=32, num_kv_shared_layers=0,
        layer_types=['sliding_attention', 'full_attention'], dtype='float32')
    config._attn_implementation = 'sdpa'
    model = Gemma4ForCausalLM(config).eval()
    example = causal_example([2, 3, 4], [5, 6, 106], pad_token_id=0,
                             maximum_tokens=16, padded_tokens=8)
    tensors = {key: torch.tensor([value]) for key, value in example.items()}
    with torch.no_grad():
        output = model(**tensors, use_cache=False)
        manual = torch.nn.functional.cross_entropy(output.logits[:, :-1].float().reshape(-1, 128),
            tensors['labels'][:, 1:].reshape(-1), ignore_index=-100)
        per_token = torch.nn.functional.cross_entropy(output.logits[0, [2, 3, 4]].float(),
            torch.tensor([5, 6, 106]), reduction='none')
        unpadded = model(**{k: v[:, :6] for k, v in tensors.items()}, use_cache=False).loss
    if not torch.allclose(output.loss, manual, atol=1e-6, rtol=0):
        raise AssertionError('model loss does not match exactly one causal shift')
    if not torch.allclose(output.loss, per_token.mean(), atol=1e-6, rtol=0):
        raise AssertionError('first answer or terminal token lost')
    if not torch.allclose(output.loss, unpadded, atol=1e-6, rtol=0):
        raise AssertionError('masked padding changes the loss')
    source = inspect.getsource(model.loss_function)
    return {'status': 'PASS_RANDOM_CPU_CAUSAL_LOSS', 'model_loss': float(output.loss),
            'manual_shifted_loss': float(manual), 'unpadded_loss': float(unpadded),
            'prediction_positions': [2, 3, 4], 'target_ids': [5, 6, 106],
            'per_target_loss': per_token.tolist(), 'supervised_tokens': 3,
            'loss_function_source_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'loss_function_source': source, 'pretrained': False, 'updates': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tokenizer', type=Path)
    args = parser.parse_args()
    pairs = data.training_pairs()
    report = {'schema': 'training_path_audit_v1', 'source_sha': os.environ.get('GITHUB_SHA'),
              'historical_executed_source': '49191f580d35984a52e53f0df3c80d52350aead7',
              'train_only': True, 'targets': audit_targets(pairs),
              'paid_allocation': False, 'pretrained_weights': False, 'training_updates': 0,
              'capability_claim': 'NOT_ESTABLISHED'}
    if args.tokenizer:
        from transformers import AutoTokenizer
        spec = ready.lock()['models']['E2B']
        for name, info in spec['files'].items():
            ready.checked_file(args.tokenizer / name, info)
        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True, trust_remote_code=False)
        report['runtime'] = {name: importlib.metadata.version(name)
                             for name in ('torch', 'transformers', 'tokenizers')}
        report['tokens'] = audit_tokens(tokenizer, pairs)
        report['causal_loss'] = audit_causal_loss()
        report['status'] = 'PASS_TRAINING_PATH_AUDIT'
    else:
        report['status'] = 'PASS_TARGET_AUDIT_ONLY'
        report['tokens'] = report['causal_loss'] = 'NOT_RUN'
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
