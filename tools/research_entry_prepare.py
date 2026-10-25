"""Prepare immutable source and read-only inputs before the allocation clock."""
import json
from pathlib import Path

from tools import research_entry_contract as c, cloud_resolver as resolver
from tools.a100_delivery import manifest
from tools.cloud_transport import build
from tools import ssh_bootstrap as ssh
from tools.research_serving_delivery import bundle
from tools.research_split import credentials
from tools.research_runtime import prepare as cpu_runtime
from tools.research_verifier_cpu import readable_tree


def prepare(root,inputs,output,*,authored_cpu):
    root=Path(root);root.mkdir(mode=0o711)
    private=root/'private';private.mkdir(mode=0o700)
    built=build(private/'transport')
    if not built['matches_prior_transport']:raise ValueError('transport pin changed')
    binaries=private/'transport/dropbear-DROPBEAR_2026.94'
    initializer=ssh.prepare(binaries/'dropbear',binaries/'dropbearkey',private/'ssh',profile='actions-20261019')
    pins=credentials(private/'tls')
    payload=private/'payload';rows=json.loads(bundle(payload,private/'tls',authored_cpu=authored_cpu))
    model=manifest('model')
    name='docs/research-entry-model-manifest.json';p=payload/name;p.write_bytes(model);p.chmod(0o600)
    rows['files'].append({'path':name,'bytes':len(model),'sha256':c.digest(model)})
    payload_manifest=private/'payload-manifest.json';payload_manifest.write_bytes(c.encoded(rows));payload_manifest.chmod(0o600)
    with resolver.kaggle_client() as client:
        streams={'wheels':{'manifest':manifest('wheels').decode(),'sha256':c.digest(manifest('wheels')),
                           'sources':resolver.resolve_wheels(client)}}
        if not authored_cpu:
            streams['model']={'manifest':model.decode(),'sha256':c.digest(model),'sources':resolver.resolve_model(client)}
    python,runtime=cpu_runtime(root/'cpu-runtime',Path(inputs)/'wheels');readable_tree(root/'cpu-runtime')
    directory=root/'execution';directory.mkdir(mode=0o711)
    # Worker credentials/logs stay in the private directory; tool subprocesses
    # traverse only the separate public work/runtime ancestors.
    configuration={'directory':str(directory),'inputs':str(inputs),'output':str(output),
        'ssh_directory':str(private/'ssh'),'tls_directory':str(private/'tls'),'server_sha256':pins['server_sha256'],
        'payload':str(payload),'payload_manifest':str(payload_manifest),'streams':streams,
        'cpu_python':str(python),'cpu_wheels':str(root/'cpu-runtime/wheels'),'authored_cpu':authored_cpu}
    return configuration,initializer,{'transport':built,'cpu_runtime':runtime,
        'payload_manifest_sha256':c.digest(payload_manifest.read_bytes()),'payload_files':rows['files'],
        'model_weights_downloaded':0,'implementation':c.source_files()}
