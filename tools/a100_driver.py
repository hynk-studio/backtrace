"""A100-only serving seam for the frozen R0 task; no provider or task launcher.

Call only inside the qualified private driver, after provider expiry, isolation,
input and dependency gates. CPU tests inject hardware; they do not qualify a GPU.
"""
import ast
import csv
import io
import math
from pathlib import Path
import re
import time

from tools.compile_probe import MODEL_PATH
from tools.native_dtype import no_custom_ar_source, serving_sources
from tools.startup_guard import guarded_server

RUN_NAME = 'R0-clean-v2-one-public-task/A10080-TP1'
BASE_IMAGE = ('pytorch/pytorch:2.10.0-cuda12.8-cudnn9-runtime@sha256:'
              'b85566342b86d13a67712e9315d40cdc2dad7f8d86df1aff3831f80835edbcca')
INPUT_SHA256 = '6ed92f4e646c17728aa8b9ca433a032d61b6b06827eec463a02c00f331c25d60'


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('full numeric driver/toolkit version required')
    return tuple(map(int, value.split('.')))


def qualify_hardware(smi_csv, cuda, *, toolkit_version):
    """Read-only checks, no initialization/start. CSV columns are fixed below.

    nvidia-smi --query-gpu=name,uuid,memory.total,driver_version,mig.mode.current
      --format=csv,noheader,nounits
    The caller must capture this on the assigned host and supply the actual
    toolkit patch version, not infer it from torch.version.cuda ('12.8').
    """
    rows = list(csv.reader(io.StringIO(smi_csv), skipinitialspace=True))
    if len(rows) != 1 or len(rows[0]) != 5:
        raise ValueError('exactly one full physical GPU required')
    name, uuid, memory, driver, mig = [v.strip() for v in rows[0]]
    if name not in ('NVIDIA A100 80GB PCIe', 'NVIDIA A100-PCIE-80GB'):
        raise ValueError('approved A100 80GB PCIe required; no hardware fallback')
    if not uuid.startswith('GPU-') or mig != 'Disabled':
        raise ValueError('full GPU with MIG explicitly disabled required')
    if not memory.isdecimal() or int(memory) < 80000:
        raise ValueError('full 80GB GPU memory required')
    if version(driver) < (570, 124, 6) or version(toolkit_version) < (12, 8, 1):
        raise ValueError('driver >=570.124.06 and CUDA >=12.8.1 required')
    if not cuda.is_available() or cuda.device_count() != 1:
        raise ValueError('exactly one visible CUDA device required')
    if tuple(cuda.get_device_capability(0)) != (8, 0):
        raise ValueError('SM80 required')
    if not cuda.is_bf16_supported(including_emulation=False):
        raise ValueError('native BF16 required; no dtype fallback')
    return dict(name=name, uuid=uuid, memory_mib=int(memory), driver=driver,
                toolkit=toolkit_version, sm=[8, 0], native_bf16=True, tp=1)


def build_config(notebook_bytes, config_type, torch):
    """Use the hash-checked official config expression, preserving all defaults.

    No notebook imports/setup/startup/task cells execute. The existing native
    dtype and no-custom-all-reduce transforms are the only source edits.
    """
    _, native = serving_sources(notebook_bytes)
    source = no_custom_ar_source(native)
    assignments = [node for node in ast.parse(source).body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'vllm_cfg'
                           for t in node.targets)]
    if len(assignments) != 1:
        raise ValueError('expected one pinned VllmConfig expression')
    config = eval(compile(ast.Expression(assignments[0].value),
                          '<pinned-a100-config>', 'eval'),
                  {'VllmConfig': config_type, 'MODEL_PATH': Path(MODEL_PATH),
                   'tp_size': 1, 'torch': torch})
    if (str(config.model) != MODEL_PATH or config.tensor_parallel_size != 1
            or config.dtype != 'bfloat16' or config.max_model_len != 32768
            or config.startup_timeout != 1200
            or config.host != '127.0.0.1' or config.port != 8000
            or config.extra_args != ['--disable-custom-all-reduce']):
        raise ValueError('frozen A100 serving configuration mismatch')
    return config


def startup_deadline(allocation_requested_monotonic, *, now=None):
    """Same-host monotonic allocation clock; setup/startup included in 2700s.

    Provider UTC timers and independent deletion are separate prerequisites.
    Never transmit a monotonic origin between machines.
    """
    now = time.monotonic() if now is None else now
    if (not math.isfinite(now) or not math.isfinite(allocation_requested_monotonic)
            or allocation_requested_monotonic > now
            or now - allocation_requested_monotonic >= 1200):
        raise ValueError('allocation clock invalid or setup budget exhausted')
    return min(now + 1200, allocation_requested_monotonic + 2700)


def make_server(notebook_bytes, torch, smi_csv, *, toolkit_version,
                allocation_requested_monotonic, adapter_manifest,
                server_type, config_type, error_type):
    """Construct but do not start the actual guarded wrapper; fail closed.

    Caller owns one-start/one-task marker, root/dropped-UID boundary and all
    provider prerequisites. This helper alone is NOT a launch authorization.
    """
    deadline = startup_deadline(allocation_requested_monotonic)
    hardware = qualify_hardware(smi_csv, torch.cuda, toolkit_version=toolkit_version)
    if adapter_manifest.adapters:
        raise ValueError('frozen R0 has no adapters')
    config = build_config(notebook_bytes, config_type, torch)
    server = guarded_server(server_type, total_deadline=deadline,
                            error_type=error_type)(config, adapter_manifest=adapter_manifest)
    return server, hardware
