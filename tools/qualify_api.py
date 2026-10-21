"""CPU-only qualification of the installed API and its rejected old pin."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run_checks(python, old_wheel, output, log):
    output = Path(output)
    output.mkdir(mode=0o700)
    old_wheel = Path(old_wheel)
    expected = json.loads((ROOT / 'docs/a100-api-runtime-amendment.json').read_text())['original']
    if (old_wheel.name != expected['path'] or old_wheel.stat().st_size != expected['bytes']
            or hashlib.sha256(old_wheel.read_bytes()).hexdigest() != expected['sha256']):
        raise ValueError('negative control requires the exact previous FastAPI wheel')
    env = dict(PATH='/usr/bin:/bin', HOME=str(output), LANG='C.UTF-8',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', OTEL_SDK_DISABLED='true',
               PYTHON_DOTENV_DISABLED='1', VLLM_NO_USAGE_STATS='1', DO_NOT_TRACK='1',
               LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_TELEMETRY='False')
    results = {}
    with tempfile.TemporaryDirectory(prefix='backtrace-api-control-') as directory:
        # Only a verified official wheel is extracted into this private CPU overlay.
        with zipfile.ZipFile(old_wheel) as archive:
            for name in archive.namelist():
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise ValueError('unsafe negative control wheel')
            archive.extractall(directory)
        for selected, overlay in (('success', None), ('routing-error', directory)):
            bootstrap = 'import sys,runpy\n'
            if overlay:
                bootstrap += 'sys.path.insert(0,' + repr(overlay) + ')\n'
            # pip check is recorded for both combinations; neither alone is an API gate.
            command = bootstrap + "sys.argv=['pip','check'];runpy.run_module('pip',run_name='__main__')"
            subprocess.run([str(python), '-I', '-c', command], env=env,
                           stdout=log, stderr=log, check=True, timeout=60)
            report = output / (selected + '.json')
            audit = ("def audit(event,args):\n"
                     " if event=='socket.connect' and (not isinstance(args[1],tuple) or args[1][0] not in ('127.0.0.1','::1')):\n"
                     "  raise RuntimeError('API qualification blocks external connections')\n"
                     "sys.addaudithook(audit)\n")
            command = bootstrap + audit + ('sys.argv=' + repr(['api_probe.py', '--mode', 'vllm',
                '--expect', selected, '--output', str(report)]) + '\n'
                + 'runpy.run_path(' + repr(str(ROOT / 'tools/api_probe.py')) + ",run_name='__main__')")
            subprocess.run([str(python), '-I', '-c', command], env=env,
                           stdout=log, stderr=log, check=True, timeout=180)
            results[selected] = json.loads(report.read_text())
    return {'status': 'PASS', 'corrected_and_negative_control': results,
            'pip_check': 'PASS for both; HTTP results differ',
            'model_initialization': 'NOT RUN', 'gpu_allocations': 0}
