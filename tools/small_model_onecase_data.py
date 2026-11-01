"""A fixed train-only reasoning case, without supplied-answer formatting rows."""
from copy import deepcopy
from tools import small_model_trainability_data as previous
from tools.small_model_sft_inputs import full_completion_example

prior = previous.prior
ARMS = ('BASE', 'Q4')
ROW_COUNT = 1
REQUIRE_EXACT = True
STEPS = 640
RESTORE_SCHEMA = 'reasoning_onecase_restore_v1'
SELECTED_ID = 'c97ef7d722c04a0dab309c49b13cabe2e67feabad96e05c344f78698f7da9e62'


def examples():
    candidates = [r for r in previous.examples() if r['kind'] == 'reasoning']
    row = min(candidates, key=lambda r: prior.digest(['reasoning-onecase-v1', r['id']]))
    if row['id'] != SELECTED_ID or prior.base.catalog()[row['family']][0] != 'train':
        raise ValueError('fixed training case identity changed')
    return [deepcopy(row)]


def materialize(tokenizer):
    example = examples()[0]
    batch = full_completion_example(tokenizer, example['messages'], example['answer'],
                                    eos_token_ids=[1, 106, 50])
    effective = len(batch['input_ids']) * STEPS
    if effective > 1_000_000:
        raise ValueError('one-case training token ceiling exceeded')
    row = {k: example[k] for k in ('id', 'messages', 'answer')} | {
        'sequence_sha256': prior.digest(batch['input_ids']),
        'prompt_tokens': batch['prompt_tokens'], 'answer_tokens': batch['completion_tokens']}
    spec = {'schema': 'reasoning_onecase_adapter_v1', 'arm': 'Q4', 'rows': [row],
            'rank': 4, 'steps': STEPS, 'seed': 17, 'learning_rate': 0.01,
            'maximum_tokens': 3072, 'projection_count': 4}
    return {'specifications': {'Q4': spec},
            'examples': [{k: v for k, v in example.items() if k not in ('messages', 'answer')}],
            'epochs': STEPS, 'rows_per_arm': ROW_COUNT,
            'effective_training_tokens_per_arm': effective,
            'supervised_tokens_per_arm': batch['completion_tokens'] * STEPS,
            'qualification': 'ONE_CASE_TRAIN_ONLY_NOT_GENERALIZATION'}


# Exercise exactly the new profile through the same independently reloaded tiny
# model control. This is a numerical implementation check, never a model result.
CPU_CONTROL = (previous.CPU_CONTROL
    .replace("[('Q1',1),('Q4',4)]", "[('Q4',4)]")
    .replace('trainability_adapter_v1', 'reasoning_onecase_adapter_v1')
    .replace('trainability_restore_v1', RESTORE_SCHEMA)
    .replace('range(16)', 'range(1)').replace('640', str(STEPS)))
