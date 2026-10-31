"""Standalone offline CPU worker. Mounted alone, with no repository or evaluator.

The scripted mode is explicitly an authored qualification control, never a model.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import re
import sys
import time


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()


def send(value):
    sys.stdout.buffer.write(canonical(value))
    sys.stdout.buffer.flush()


def cuda_check(job):
    """Actual single-device kernels; never treats import success as GPU success."""
    import torch
    if torch.version.cuda != '12.6' or not torch.cuda.is_available():
        raise RuntimeError('CUDA 12.6 device unavailable; CPU fallback forbidden')
    if torch.cuda.device_count() != 1:
        raise RuntimeError('exactly one visible CUDA device required')
    prop=torch.cuda.get_device_properties(0)
    # PyTorch's CUuuid string is bare 8-4-4-4-12; nvidia-smi prefixes GPU-.
    # Normalize only that spelling, retaining exact full-device identity.
    uuid=str(prop.uuid)
    if not re.fullmatch(r'(?:GPU-)?[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',uuid):
        raise RuntimeError('malformed CUDA device UUID: '+uuid)
    uuid='GPU-'+uuid.removeprefix('GPU-').lower()
    if uuid.lower()!=job['gpu']['uuid'].lower():
        raise RuntimeError('GPU UUID mismatch: observed='+uuid+' expected='+job['gpu']['uuid'])
    if prop.major<8:
        raise RuntimeError('GPU compute capability below native BF16 requirement')
    if prop.total_memory<job['gpu']['minimum_total_bytes']:
        raise RuntimeError('GPU memory below required minimum')
    if not torch.cuda.is_bf16_supported(including_emulation=False):
        raise RuntimeError('native BF16 unsupported')
    exposed=sorted(p.name for p in Path('/dev').glob('nvidia[0-9]*'))
    if exposed != [job['gpu']['device_basename']]:
        raise RuntimeError('unexpected GPU device node exposure')
    torch.cuda.set_device(0)
    x=torch.eye(16,device='cuda:0',dtype=torch.bfloat16)
    q=torch.ones((1,1,4,16),device='cuda:0',dtype=torch.bfloat16)
    with torch.inference_mode():
        product=x@x
        attention=torch.nn.functional.scaled_dot_product_attention(q,q,q,dropout_p=0.0)
    torch.cuda.synchronize()
    if not torch.equal(product,x) or not torch.equal(attention,q):
        raise RuntimeError('BF16 matmul/SDPA control failed')
    free,total=torch.cuda.mem_get_info()
    return {'uuid':uuid,'name':prop.name,'capability':[prop.major,prop.minor],
            'total_bytes':total,'free_bytes':free,'compiled_cuda':torch.version.cuda,
            'compiled_arches':torch.cuda.get_arch_list(),'bf16_matmul':True,'bf16_sdpa':True,
            'device_nodes':exposed,'no_cpu_fallback':True}


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
    cuda_mode=job['mode'] in ('cuda_probe','pretrained_cuda','random_cuda_fixture')
    gpu=cuda_check(job) if cuda_mode else None
    if job['mode']=='cuda_probe':
        send({'status':'PASS_ACTUAL_CUDA_KERNELS','gpu':gpu})
        return
    tokenizer = AutoTokenizer.from_pretrained('/tokenizer', local_files_only=True, trust_remote_code=False)
    if job['mode'] not in ('random_fixture', 'scripted_control', 'pretrained_cpu','pretrained_cuda','random_cuda_fixture'):
        raise ValueError('unsupported worker mode')
    model = None
    load_started=time.monotonic()
    if cuda_mode:torch.cuda.reset_peak_memory_stats()
    if job['mode'] != 'scripted_control':
        model, info = Gemma4ForCausalLM.from_pretrained('/model', local_files_only=True,
            trust_remote_code=False, dtype=torch.float32 if job['mode'] in ('random_fixture','random_cuda_fixture') else torch.bfloat16,
            attn_implementation='sdpa', key_mapping=job['key_mapping'], output_loading_info=True,
            **({'device_map':{'':'cuda:0'}} if cuda_mode else {}))
        unexpected = set(info.get('unexpected_keys', []))
        allowed = set(job.get('allowed_unexpected_keys', []))
        if unexpected - allowed or any(info.get(k) for k in ('missing_keys', 'mismatched_keys', 'error_msgs')):
            raise ValueError('checkpoint did not load completely')
        model.eval()
        if cuda_mode and any(p.device.type!='cuda' or p.device.index!=0 for p in model.parameters()):
            raise RuntimeError('CPU/meta/offloaded parameter found')
    if cuda_mode:torch.cuda.synchronize()
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    send({'ready': True, 'mode': job['mode'], 'uid': os.getuid(),
          'caps': int(status['CapEff'].strip(), 16), 'no_new_privs': status['NoNewPrivs'].strip(),
          'pid_namespace': os.readlink('/proc/self/ns/pid'), 'net_namespace': os.readlink('/proc/self/ns/net'),
          **({'cuda':gpu,'load_seconds':time.monotonic()-load_started,
              'load_peak_allocated_bytes':torch.cuda.max_memory_allocated(),
              'load_peak_reserved_bytes':torch.cuda.max_memory_reserved()} if cuda_mode else {})})
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
        if cuda_mode:
            torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats()
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
            tensor = torch.tensor([ids], dtype=torch.long,device='cuda:0' if cuda_mode else 'cpu')
            with torch.inference_mode():
                generated = model.generate(input_ids=tensor, attention_mask=torch.ones_like(tensor),
                    max_new_tokens=job['max_new_tokens'], do_sample=False, num_beams=1,
                    eos_token_id=[1, 106, 50], pad_token_id=0)
            if not torch.equal(generated[:, :len(ids)], tensor):
                raise ValueError('generation changed input prefix')
            output = generated[0, len(ids):].tolist()
        if cuda_mode:torch.cuda.synchronize()
        send({'id': request['id'], 'input_tokens': len(ids), 'input_ids_sha256': digest,
              'output_ids': output, 'raw_text': tokenizer.decode(output, skip_special_tokens=False,
                                                               clean_up_tokenization_spaces=False),
              'elapsed_seconds': time.monotonic()-started,
              **({'cuda_metrics':{'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                    'peak_reserved_bytes':torch.cuda.max_memory_reserved(),
                    'post_free_bytes':torch.cuda.mem_get_info()[0],
                    'total_bytes':torch.cuda.mem_get_info()[1]}} if cuda_mode else {})})
        count += 1


if __name__ == '__main__':
    main()
