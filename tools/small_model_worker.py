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


def adapter_feasibility(model, tokenizer, specification):
    """Four train-only SGD updates on one query projection; implementation evidence."""
    import base64
    import math
    import tempfile
    import torch
    from safetensors.torch import save_file, load_file
    expected={'schema','rows','rank','steps','seed','learning_rate','maximum_tokens'}
    if (set(specification)!=expected or specification['schema']!='tiny_lora_feasibility_v1'
            or specification['rank']!=4 or specification['steps']!=4
            or specification['seed']!=17 or specification['learning_rate']!=0.01
            or specification['maximum_tokens']!=2048 or len(specification['rows'])!=4):
        raise ValueError('fixed four-update feasibility contract required')
    rows=specification['rows']; encoded=[]
    device=next(model.parameters()).device
    for row in rows:
        if (set(row)!={'id','messages','answer'} or not re.fullmatch('[0-9a-f]{64}',row['id'])
                or not isinstance(row['messages'],list) or not isinstance(row['answer'],str)):
            raise ValueError('bounded training row required')
        json.loads(row['answer'])
        prompt=tokenizer.apply_chat_template(row['messages'],tokenize=True,return_dict=True,
            add_generation_prompt=True,enable_thinking=False,truncation=False,padding=False)['input_ids']
        answer=tokenizer.encode(row['answer'],add_special_tokens=False)+[106]
        if not 0<len(prompt)<len(prompt)+len(answer)<=2048:
            raise ValueError('training sequence overflow')
        encoded.append((prompt,answer))
    if len({r['id'] for r in rows})!=4:raise ValueError('distinct training inputs required')
    model.eval();model.requires_grad_(False)
    candidates=[(name,module) for name,module in model.named_modules()
                if name.endswith('.q_proj') and isinstance(module,torch.nn.Linear)]
    if not candidates:raise ValueError('linear query projection absent')
    name,projection=candidates[-1]
    rank=4
    if 4*rank*(projection.in_features+projection.out_features)>450_000:
        raise ValueError('bounded adapter exceeds artifact allowance')
    torch.manual_seed(17)
    class Delta(torch.nn.Module):
        def __init__(self):
            super().__init__();self.enabled=True
            self.a=torch.nn.Parameter(torch.empty(rank,projection.in_features,device=device,dtype=torch.float32))
            self.b=torch.nn.Parameter(torch.zeros(projection.out_features,rank,device=device,dtype=torch.float32))
            torch.nn.init.kaiming_uniform_(self.a,a=math.sqrt(5))
        def hook(self,module,args,output):
            if not self.enabled:return output
            update=torch.nn.functional.linear(torch.nn.functional.linear(args[0].float(),self.a),self.b)
            return output+update.to(output.dtype)  # alpha/rank = 1, no dropout.
    delta=Delta();handle=projection.register_forward_hook(delta.hook)
    model.add_module('_backtrace_adapter',delta)
    original={k:v.detach().clone() for k,v in delta.state_dict().items()}
    def logits():
        ids=torch.tensor([encoded[0][0]],device=device,dtype=torch.long)
        with torch.no_grad():
            return model(input_ids=ids,attention_mask=torch.ones_like(ids),
                         use_cache=False,logits_to_keep=1).logits.detach().float().cpu()
    before=logits();losses=[];gradients=[];started=time.monotonic()
    if device.type=='cuda':torch.cuda.reset_peak_memory_stats()
    for prompt,answer in encoded:
        ids=torch.tensor([prompt+answer],device=device,dtype=torch.long)
        labels=torch.tensor([[-100]*len(prompt)+answer],device=device,dtype=torch.long)
        for parameter in delta.parameters():parameter.grad=None
        loss=model(input_ids=ids,attention_mask=torch.ones_like(ids),labels=labels,use_cache=False).loss
        if not torch.isfinite(loss):raise ValueError('nonfinite training loss')
        loss.backward()
        if any(p.grad is None or not torch.isfinite(p.grad).all() for p in delta.parameters()):
            raise ValueError('missing or nonfinite adapter gradient')
        norm=torch.nn.utils.clip_grad_norm_(delta.parameters(),1.0,error_if_nonfinite=True)
        with torch.no_grad():
            for parameter in delta.parameters():parameter.add_(parameter.grad,alpha=-0.01)
        losses.append(float(loss.detach()));gradients.append(float(norm))
    changed=[k for k,v in delta.state_dict().items() if not torch.equal(v,original[k])]
    if not changed:raise ValueError('adapter did not change')
    trained=logits();delta.enabled=False;disabled=logits();delta.enabled=True
    if not torch.equal(before,disabled):raise ValueError('disabled adapter changed base behavior')
    difference=float((trained-disabled).abs().max())
    if not difference>0:raise ValueError('no observable adapter-on/off logit difference')
    with tempfile.TemporaryDirectory(prefix='backtrace-adapter-') as directory:
        path=Path(directory)/'adapter.safetensors'
        save_file({k:v.detach().cpu().contiguous() for k,v in delta.state_dict().items()},str(path))
        raw=path.read_bytes()
        if len(raw)>524288:raise ValueError('adapter export too large')
        restored=load_file(str(path),device='cpu')
        if set(restored)!=set(original):raise ValueError('saved adapter key mismatch')
        with torch.no_grad():
            for parameter in delta.parameters():parameter.zero_()
            for k,v in delta.state_dict().items():v.copy_(restored[k].to(device))
    reloaded=logits()
    if not torch.equal(trained,reloaded):raise ValueError('save/reload logits differ at zero tolerance')
    if device.type=='cuda':torch.cuda.synchronize()
    result={'status':'PASS_TINY_UPDATE_SAVE_RELOAD_ONLY','training_steps':4,'rank':rank,
        'optimizer':'SGD','learning_rate':0.01,'seed':17,'target_module':name,
        'trainable_parameters':sum(p.numel() for p in delta.parameters()),
        'training_input_sha256':hashlib.sha256(canonical(specification)).hexdigest(),
        'sequence_tokens':[len(p)+len(a) for p,a in encoded],
        'supervised_tokens':[len(a) for p,a in encoded], 'losses':losses,'gradient_norms':gradients,
        'changed_tensors':changed,'adapter_on_off_max_logit_difference':difference,
        'disabled_base_max_logit_difference':0.0,'save_reload_max_logit_difference':0.0,
        'before_first_token':int(before.argmax(-1).item()),'after_first_token':int(trained.argmax(-1).item()),
        'seconds':time.monotonic()-started,'adapter_bytes':len(raw),
        'adapter_sha256':hashlib.sha256(raw).hexdigest(),'adapter_safetensors_base64':base64.b64encode(raw).decode(),
        'capability_claim':'NOT_ESTABLISHED',
        **({'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
            'peak_reserved_bytes':torch.cuda.max_memory_reserved()} if device.type=='cuda' else {})}
    # Keep the trained adapter enabled for the separately assigned generation.
    for parameter in delta.parameters():parameter.grad=None
    return result


def candidate_delta(model):
    """Separate bounded candidate path; the historical four-update path is unchanged."""
    import math
    import torch
    model.eval();model.requires_grad_(False)
    if hasattr(model,'_backtrace_candidate_adapter') or hasattr(model,'_backtrace_adapter'):
        raise ValueError('candidate requires an untouched base instance')
    candidates=[(n,m) for n,m in model.named_modules()
                if n.endswith('.q_proj') and isinstance(m,torch.nn.Linear)]
    if not candidates:raise ValueError('linear query projection absent')
    name,projection=candidates[-1]
    if 4*4*(projection.in_features+projection.out_features)>450_000:
        raise ValueError('candidate adapter export bound exceeded')
    device=next(model.parameters()).device
    torch.manual_seed(17)
    class Delta(torch.nn.Module):
        def __init__(self):
            super().__init__();self.enabled=True
            self.a=torch.nn.Parameter(torch.empty(4,projection.in_features,device=device,dtype=torch.float32))
            self.b=torch.nn.Parameter(torch.zeros(projection.out_features,4,device=device,dtype=torch.float32))
            torch.nn.init.kaiming_uniform_(self.a,a=math.sqrt(5))
        def hook(self,module,args,output):
            if not self.enabled:return output
            update=torch.nn.functional.linear(torch.nn.functional.linear(args[0].float(),self.a),self.b)
            return output+update.to(output.dtype)
    delta=Delta();projection.register_forward_hook(delta.hook)
    model.add_module('_backtrace_candidate_adapter',delta)
    return name,delta,device


def candidate_prompt(tokenizer,messages):
    ids=tokenizer.apply_chat_template(messages,tokenize=True,return_dict=True,
        add_generation_prompt=True,enable_thinking=False,truncation=False,padding=False)['input_ids']
    if not 0<len(ids)<3072:raise ValueError('bounded candidate prompt required')
    return ids


def candidate_logits(model,ids,device):
    import torch
    tensor=torch.tensor([ids],device=device,dtype=torch.long)
    with torch.no_grad():
        result=model(input_ids=tensor,attention_mask=torch.ones_like(tensor),
            use_cache=False,logits_to_keep=1).logits.detach().float().cpu().contiguous()
    if not torch.isfinite(result).all():raise ValueError('nonfinite probe logits')
    return result


def candidate_train(model,tokenizer,spec):
    """320 paired-mask SGD updates; emit each finished update before the final receipt."""
    import base64
    import tempfile
    import torch
    from safetensors.torch import save_file,load_file
    keys={'schema','arm','rows','rank','steps','seed','learning_rate','maximum_tokens'}
    if (set(spec)!=keys or spec['schema']!='matched_candidate_adapter_v1' or spec['arm'] not in ('B2','S')
            or spec['rank']!=4 or spec['steps']!=320 or spec['seed']!=17
            or spec['learning_rate']!=0.01 or spec['maximum_tokens']!=3072
            or not isinstance(spec['rows'],list) or len(spec['rows'])!=320):
        raise ValueError('fixed matched candidate training contract required')
    rowkeys={'id','messages','answer','padded_tokens','supervised_positions',
             'prompt_tokens','answer_tokens','sequence_sha256'}
    encoded=[];seen=set()
    for row in spec['rows']:
        if (set(row)!=rowkeys or not re.fullmatch('[0-9a-f]{64}',row['id']) or row['id'] in seen
                or not isinstance(row['answer'],str) or not isinstance(row['messages'],list)):
            raise ValueError('distinct bounded candidate row required')
        seen.add(row['id']);json.loads(row['answer'])
        prompt=candidate_prompt(tokenizer,row['messages'])
        answer=tokenizer.encode(row['answer'],add_special_tokens=False)+[106]
        positions=row['supervised_positions'];padded=row['padded_tokens']
        if (type(padded) is not int or not len(prompt)+len(answer)<=padded<=3072
                or len(prompt)!=row['prompt_tokens'] or len(answer)!=row['answer_tokens']
                or hashlib.sha256(canonical(prompt+answer)).hexdigest()!=row['sequence_sha256']
                or not isinstance(positions,list) or not positions
                or any(type(i) is not int for i in positions) or positions!=sorted(set(positions))
                or positions[0]<0 or positions[-1]!=len(answer)-1):
            raise ValueError('candidate token identity, padding or mask mismatch')
        encoded.append((prompt,answer,set(positions),padded))
    if sum(len(p)+len(a) for p,a,_,_ in encoded)>1_000_000:
        raise ValueError('effective training token ceiling exceeded')
    name,delta,device=candidate_delta(model)
    original={k:v.detach().clone() for k,v in delta.state_dict().items()}
    probe=encoded[0][0];before=candidate_logits(model,probe,device)
    losses=[];gradients=[];started=time.monotonic()
    if device.type=='cuda':torch.cuda.reset_peak_memory_stats()
    for step,(prompt,answer,positions,padded) in enumerate(encoded,1):
        padding=padded-len(prompt)-len(answer)
        ids=torch.tensor([prompt+answer+[0]*padding],device=device,dtype=torch.long)
        mask=torch.tensor([[1]*(padded-padding)+[0]*padding],device=device,dtype=torch.long)
        labels=torch.tensor([[-100]*len(prompt)+[v if i in positions else -100 for i,v in enumerate(answer)]
                             +[-100]*padding],device=device,dtype=torch.long)
        for parameter in delta.parameters():parameter.grad=None
        loss=model(input_ids=ids,attention_mask=mask,labels=labels,use_cache=False).loss
        if not torch.isfinite(loss):raise ValueError('nonfinite candidate loss')
        loss.backward()
        if any(p.grad is None or not torch.isfinite(p.grad).all() for p in delta.parameters()):
            raise ValueError('missing or nonfinite candidate gradient')
        norm=torch.nn.utils.clip_grad_norm_(delta.parameters(),1.0,error_if_nonfinite=True)
        with torch.no_grad():
            for parameter in delta.parameters():parameter.add_(parameter.grad,alpha=-0.01)
        losses.append(float(loss.detach()));gradients.append(float(norm))
        print(json.dumps({'phase':'CANDIDATE_UPDATE_FINISHED','arm':spec['arm'],'step':step,
            'id':spec['rows'][step-1]['id'],'loss':losses[-1],'gradient_norm':gradients[-1],
            'supervised_tokens':len(positions),'elapsed_seconds':time.monotonic()-started}),file=sys.stderr,flush=True)
    for parameter in delta.parameters():parameter.grad=None
    changed=[k for k,v in delta.state_dict().items() if not torch.equal(v,original[k])]
    if set(changed)!={'a','b'}:raise ValueError('both candidate matrices must change')
    trained=candidate_logits(model,probe,device);delta.enabled=False
    disabled=candidate_logits(model,probe,device);delta.enabled=True
    if not torch.equal(before,disabled):raise ValueError('candidate altered frozen base')
    difference=float((trained-disabled).abs().max())
    if not difference>0:raise ValueError('candidate has no observable logit change')
    with tempfile.TemporaryDirectory(prefix='backtrace-candidate-') as directory:
        path=Path(directory)/'adapter.safetensors'
        save_file({k:v.detach().cpu().contiguous() for k,v in delta.state_dict().items()},str(path))
        raw=path.read_bytes()
        if len(raw)>524288:raise ValueError('candidate adapter export too large')
        restored=load_file(str(path),device='cpu')
        if set(restored)!=set(original):raise ValueError('candidate tensor keys differ')
        with torch.no_grad():
            for parameter in delta.parameters():parameter.zero_()
            for k,v in delta.state_dict().items():v.copy_(restored[k].to(device))
    reloaded=candidate_logits(model,probe,device)
    if not torch.equal(trained,reloaded):raise ValueError('candidate same-instance reload differs')
    if device.type=='cuda':torch.cuda.synchronize()
    return {'status':'PASS_MATCHED_CANDIDATE_TRAINING','arm':spec['arm'],'training_steps':320,
        'updates_in_worker':320,'rank':4,'seed':17,'learning_rate':0.01,'optimizer':'SGD',
        'target_module':name,'trainable_parameters':sum(p.numel() for p in delta.parameters()),
        'training_input_sha256':hashlib.sha256(canonical(spec)).hexdigest(),
        'sequence_tokens':[len(p)+len(a) for p,a,_,_ in encoded],
        'padded_tokens':[n for _,_,_,n in encoded],'supervised_tokens':[len(m) for _,_,m,_ in encoded],
        'losses':losses,'gradient_norms':gradients,'changed_tensors':changed,
        'adapter_on_off_max_logit_difference':difference,'disabled_base_max_logit_difference':0.0,
        'save_reload_max_logit_difference':0.0,'seconds':time.monotonic()-started,
        'adapter_bytes':len(raw),'adapter_sha256':hashlib.sha256(raw).hexdigest(),
        'adapter_safetensors_base64':base64.b64encode(raw).decode(),
        'probe_messages':spec['rows'][0]['messages'],'probe_input_ids_sha256':hashlib.sha256(canonical(probe)).hexdigest(),
        'trained_probe_logits_sha256':hashlib.sha256(trained.numpy().tobytes()).hexdigest(),
        'capability_claim':'NOT_ESTABLISHED',**({'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
        'peak_reserved_bytes':torch.cuda.max_memory_reserved()} if device.type=='cuda' else {})}


def candidate_restore(model,tokenizer,spec):
    """Fresh model/process reload, bound to the original training probe and artifact."""
    import base64
    import tempfile
    import torch
    from safetensors.torch import load_file
    keys={'schema','arm','training_steps','training_input_sha256','adapter_bytes','adapter_sha256',
          'adapter_safetensors_base64','target_module','probe_messages','probe_input_ids_sha256',
          'trained_probe_logits_sha256'}
    if (set(spec)!=keys or spec['schema']!='matched_candidate_restore_v1'
            or spec['arm'] not in ('B2','S') or spec['training_steps']!=320
            or type(spec['adapter_bytes']) is not int or not 0<spec['adapter_bytes']<=524288
            or not isinstance(spec['adapter_safetensors_base64'],str)
            or len(spec['adapter_safetensors_base64'])>700000
            or any(not re.fullmatch('[0-9a-f]{64}',spec[k]) for k in
                ('training_input_sha256','adapter_sha256','probe_input_ids_sha256','trained_probe_logits_sha256'))):
        raise ValueError('bounded candidate restore contract required')
    raw=base64.b64decode(spec['adapter_safetensors_base64'],validate=True)
    if len(raw)!=spec['adapter_bytes'] or hashlib.sha256(raw).hexdigest()!=spec['adapter_sha256']:
        raise ValueError('candidate adapter identity mismatch')
    probe=candidate_prompt(tokenizer,spec['probe_messages'])
    if hashlib.sha256(canonical(probe)).hexdigest()!=spec['probe_input_ids_sha256']:
        raise ValueError('candidate reload probe mismatch')
    name,delta,device=candidate_delta(model)
    if name!=spec['target_module']:raise ValueError('candidate target module mismatch')
    with tempfile.TemporaryDirectory(prefix='backtrace-restore-') as directory:
        path=Path(directory)/'adapter.safetensors';path.write_bytes(raw)
        values=load_file(str(path),device='cpu')
    if set(values)!={'a','b'}:raise ValueError('candidate tensor keys mismatch')
    with torch.no_grad():
        for k,v in delta.state_dict().items():
            if values[k].dtype!=torch.float32 or values[k].shape!=v.shape or not torch.isfinite(values[k]).all():
                raise ValueError('candidate tensor dtype, shape or values mismatch')
            v.copy_(values[k].to(device))
    observed=hashlib.sha256(candidate_logits(model,probe,device).numpy().tobytes()).hexdigest()
    if observed!=spec['trained_probe_logits_sha256']:raise ValueError('fresh candidate reload logits mismatch')
    delta.requires_grad_(False)
    return {'status':'PASS_FRESH_PROCESS_CANDIDATE_RELOAD','arm':spec['arm'],
        'training_steps':320,'updates_in_worker':0,'adapter_bytes':len(raw),
        'adapter_sha256':spec['adapter_sha256'],'training_input_sha256':spec['training_input_sha256'],
        'target_module':name,'probe_input_ids_sha256':spec['probe_input_ids_sha256'],
        'observed_probe_logits_sha256':observed,'capability_claim':'NOT_ESTABLISHED'}


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
    load_metrics=({'cuda':gpu,'load_seconds':time.monotonic()-load_started,
        'load_peak_allocated_bytes':torch.cuda.max_memory_allocated(),
        'load_peak_reserved_bytes':torch.cuda.max_memory_reserved()} if cuda_mode else {})
    adaptation=None;candidate=None
    if sum(k in job for k in ('adapter_feasibility','candidate_training','candidate_restore'))>1:
        raise ValueError('one explicit adapter operation per worker required')
    if 'adapter_feasibility' in job:
        if job['mode'] not in ('pretrained_cuda','random_fixture'):
            raise ValueError('adapter requires a model and explicit bounded job')
        adaptation=adapter_feasibility(model,tokenizer,job['adapter_feasibility'])
    for operation,function in (('candidate_training',candidate_train),('candidate_restore',candidate_restore)):
        if operation in job:
            if job['mode'] not in ('pretrained_cuda','random_fixture'):
                raise ValueError('candidate operation requires a qualified model job')
            candidate=function(model,tokenizer,job[operation])
    if cuda_mode:torch.cuda.synchronize()
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    send({'ready': True, 'mode': job['mode'], 'uid': os.getuid(),
          'caps': int(status['CapEff'].strip(), 16), 'no_new_privs': status['NoNewPrivs'].strip(),
          'pid_namespace': os.readlink('/proc/self/ns/pid'), 'net_namespace': os.readlink('/proc/self/ns/net'),
          **({'adapter_feasibility':adaptation} if adaptation else {}),
          **({'candidate_adapter':candidate} if candidate else {}),
          **load_metrics})
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
