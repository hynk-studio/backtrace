"""Standalone offline CPU worker. Mounted alone, with no repository or evaluator.

The scripted mode is explicitly an authored qualification control, never a model.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import sys
import time


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


def send(value):
    sys.stdout.buffer.write(canonical(value))
    sys.stdout.buffer.flush()


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    job = json.loads(Path('/job.json').read_bytes())
    if job.get('fault') == 'startup_hang' and job['mode'] == 'scripted_control':
        time.sleep(60)
    if {n: importlib.metadata.version(n) for n in job['packages']} != job['packages']:
        raise ValueError('worker dependency mismatch')
    import torch
    from transformers import AutoTokenizer, Gemma4ForCausalLM
    torch.set_num_threads(1)
    tokenizer = AutoTokenizer.from_pretrained('/tokenizer', local_files_only=True, trust_remote_code=False)
    if job['mode'] not in ('random_fixture', 'scripted_control', 'pretrained_cpu'):
        raise ValueError('unsupported worker mode')
    model = None
    if job['mode'] != 'scripted_control':
        model, info = Gemma4ForCausalLM.from_pretrained('/model', local_files_only=True,
            trust_remote_code=False, dtype=torch.float32 if job['mode']=='random_fixture' else torch.bfloat16,
            attn_implementation='sdpa', key_mapping=job['key_mapping'], output_loading_info=True)
        unexpected = set(info.get('unexpected_keys', []))
        allowed = set(job.get('allowed_unexpected_keys', []))
        if unexpected - allowed or any(info.get(k) for k in ('missing_keys', 'mismatched_keys', 'error_msgs')):
            raise ValueError('checkpoint did not load completely')
        model.eval()
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    send({'ready': True, 'mode': job['mode'], 'uid': os.getuid(),
          'caps': int(status['CapEff'].strip(), 16), 'no_new_privs': status['NoNewPrivs'].strip(),
          'pid_namespace': os.readlink('/proc/self/ns/pid'), 'net_namespace': os.readlink('/proc/self/ns/net')})
    count = 0
    while True:
        raw = sys.stdin.buffer.readline(65537)
        if not raw:
            return
        if len(raw) > 65536 or not raw.endswith(b'\n'):
            raise ValueError('oversized request')
        request = json.loads(raw)
        expected = {'id', 'messages', 'input_tokens', 'input_ids_sha256'}
        if job['mode'] == 'scripted_control':
            expected.add('fixture_ids')
        if set(request) != expected:
            raise ValueError('unexpected request fields')
        started = time.monotonic()
        ids = tokenizer.apply_chat_template(request['messages'], tokenize=True, return_dict=True,
            add_generation_prompt=True, enable_thinking=False, truncation=False, padding=False)['input_ids']
        digest = hashlib.sha256(canonical(ids)).hexdigest()
        if len(ids) != request['input_tokens'] or digest != request['input_ids_sha256']:
            raise ValueError('tokenization differs from qualified input')
        if not 0 < len(ids) <= job['max_input_tokens']:
            raise ValueError('input overflow')
        if job['mode'] == 'scripted_control':
            # Only the qualification coordinator can select this explicit mode.
            # It has no pretrained-model result label or provider execution path.
            if count == job.get('fault_at'):
                fault = job.get('fault')
                if fault == 'hang':
                    time.sleep(60)
                elif fault == 'crash':
                    os._exit(23)
                elif fault == 'oversize':
                    sys.stdout.write('x' * (1024 * 1024 + 1)); sys.stdout.flush(); time.sleep(60)
                elif fault == 'wrong_id':
                    request['id'] = 'unassigned'
            output = request['fixture_ids']
        else:
            tensor = torch.tensor([ids], dtype=torch.long)
            with torch.inference_mode():
                generated = model.generate(input_ids=tensor, attention_mask=torch.ones_like(tensor),
                    max_new_tokens=job['max_new_tokens'], do_sample=False, num_beams=1,
                    eos_token_id=[1, 106, 50], pad_token_id=0)
            if not torch.equal(generated[:, :len(ids)], tensor):
                raise ValueError('generation changed input prefix')
            output = generated[0, len(ids):].tolist()
        send({'id': request['id'], 'input_tokens': len(ids), 'input_ids_sha256': digest,
              'output_ids': output, 'raw_text': tokenizer.decode(output, skip_special_tokens=False,
                                                               clean_up_tokenization_spaces=False),
              'elapsed_seconds': time.monotonic()-started})
        count += 1


if __name__ == '__main__':
    main()
