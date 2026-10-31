"""Reuse the pinned E2B sources and original development assignments.

Preparation downloads the actual checkpoint without allocating a GPU. No labels
or evaluator files are sent to a model. Execution is a later explicit entry.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import urllib.request
import zipfile

from tools import small_model_readiness as ready, small_model_runner as runner
from tools import small_model_lifecycle as life

ROOT = Path(__file__).resolve().parents[1]


def prepare(output, readiness_archive):
    output = Path(output).resolve(); output.mkdir(mode=0o700, parents=True, exist_ok=False)
    record = json.loads((ROOT/'docs/small-model-readiness-cpu-20261026.json').read_bytes())['artifact']
    raw = Path(readiness_archive).read_bytes()
    if hashlib.sha256(raw).hexdigest() != record['verified_sha256']:
        raise ValueError('historical tokenizer archive hash mismatch')
    with zipfile.ZipFile(readiness_archive) as archive:
        tokens = archive.read('tokenization-cases.json')
    expected = record['verified_members']['tokenization-cases.json']
    if len(tokens) != expected['bytes'] or life.digest(tokens) != expected['sha256']:
        raise ValueError('historical tokenizer report hash mismatch')
    (output/'tokenization.json').write_bytes(tokens)
    ready.rebuild_packets(output/'packets')
    ready.prepare_scope(output/'packets',output/'tokenization.json',output/'scope',scope='smoke')
    plan,schedule,_ = runner.load_scope(output/'scope',output/'packets',output/'tokenization.json')
    selected = [row for row in schedule if row['model']=='E2B']
    if len(selected)!=18 or {row['arm'] for row in selected}!={'B0','B1'}:
        raise ValueError('original 18 E2B assignments required')
    ready.acquire_sources(output/'sources')
    spec = ready.lock()['models']['E2B']; weight = spec['weights_metadata_only'][0]
    if shutil.disk_usage(output).free < weight['bytes'] + 4*1024**3:
        raise RuntimeError('insufficient free disk before checkpoint acquisition')
    model = output/'models/E2B'; model.mkdir(mode=0o700,parents=True)
    for name in ('config.json','generation_config.json'):
        shutil.copyfile(output/'sources/E2B'/name,model/name)
    destination = model/'model.safetensors'; started=time.monotonic(); size=0
    # The complete response is hash-checked against the previously pinned LFS OID.
    request=urllib.request.Request(spec['tensor_header']['url']+'?download=true')
    with urllib.request.urlopen(request,timeout=60) as response, destination.open('xb') as stream:
        if response.status!=200:raise ValueError('complete checkpoint response required')
        while chunk:=response.read(8*1024**2):
            size+=len(chunk)
            if size>weight['bytes'] or time.monotonic()-started>900:
                raise RuntimeError('checkpoint acquisition bound exceeded')
            stream.write(chunk)
    verified=runner.verify_pretrained_directory('E2B',model)
    result={'status':'PASS_PRETRAINED_BYTES_NOT_INFERENCE','weights':verified,
        'assigned':len(selected),'independent_development_episodes':1,
        'scope':'E2B_ONLY_FROM_ORIGINAL_SMOKE','excluded_model':'E4B_CONDITIONAL',
        'checkpoint_download_seconds':time.monotonic()-started,'pretrained_requests':0,
        'source_sha':__import__('os').environ.get('GITHUB_SHA')}
    life.write(output/'preparation.json',result); return result


if __name__=='__main__':
    if sys.argv[1]!='prepare':raise ValueError('preparation only')
    print(json.dumps(prepare(sys.argv[2],sys.argv[3]),sort_keys=True))
