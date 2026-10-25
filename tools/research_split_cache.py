"""Read the frozen v25 serving wheel on free CPU; never acquire a model."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

from tools import research_comparison as c, cloud_resolver as resolver
from tools.direct_delivery import pull
from tools.linux_runtime import supplied_records
from tools.cloud_seal import seal

SOURCE_PINS = {
    'vllm/engine/arg_utils.py': 'b576b4e3156e7669857e2ed6cbd9a4ac50062472501bc39a80d3642991b5f362',
    'vllm/config/cache.py': '0f5728cafef37cc6af9b4ebc440a2cf0458e49f28f39268e20399aae15c696b3',
    'vllm/utils/argparse_utils.py': '8e54055d4ed3d30b49169fb6a9dfa0628d6ada2509c20711527abd953fb73dd9',
    'vllm/entrypoints/openai/cli_args.py': '095d24532102f71586197b2a2cd84701e00cfa35aa97f3a6121e6ec66eb752cf'}


def qualify_sources(files):
    """Execute the exact pinned BooleanOptionalAction registration slice.

    This is deliberately narrower than importing the GPU engine or asserting an
    initialized model's cache state. Runtime metadata must independently pass.
    """
    if {n:c.digest(p.read_bytes()) for n,p in files.items()} != SOURCE_PINS:
        raise ValueError('serving implementation changed')
    source=files['vllm/engine/arg_utils.py'].read_text(); tree=ast.parse(source)
    assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)
        and isinstance(n.value,ast.Attribute) and ast.unparse(n.value)=='argparse.BooleanOptionalAction'
        and ast.unparse(n.targets[0])=="kwargs[name]['action']"]
    registration=[n for n in ast.walk(tree) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
        and n.value.args and isinstance(n.value.args[0],ast.Constant)
        and n.value.args[0].value=='--enable-prefix-caching']
    cache=ast.parse(files['vllm/config/cache.py'].read_text())
    defaults=[n for n in ast.walk(cache) if isinstance(n,ast.AnnAssign)
        and isinstance(n.target,ast.Name) and n.target.id=='enable_prefix_caching']
    if len(assignments)!=1 or len(registration)!=1 or len(defaults)!=1:
        raise ValueError('cache argument implementation shape changed')
    default=ast.literal_eval(defaults[0].value)
    parser=argparse.ArgumentParser()
    namespace={'argparse':argparse,'name':'enable_prefix_caching',
        'kwargs':{'enable_prefix_caching':{'default':default}}}
    exec(compile(ast.Module(body=assignments,type_ignores=[]),'<pinned-vllm-bool-action>','exec'),namespace)
    namespace.update(cache_group=parser.add_argument_group('CacheConfig'),cache_kwargs=namespace['kwargs'])
    exec(compile(ast.Module(body=registration,type_ignores=[]),'<pinned-vllm-cache-registration>','exec'),namespace)
    observed={key:parser.parse_args(args).enable_prefix_caching for key,args in (
        ('omitted',[]),('disabled',['--no-enable-prefix-caching']),('enabled',['--enable-prefix-caching']))}
    if observed != {'omitted':None,'disabled':False,'enabled':True}:
        raise ValueError('cache flag parser semantics changed')
    return {'status':'PASS','scope':'PINNED_ARGPARSE_REGISTRATION_SLICE', 'observed':observed,
        'cache_config_default':default, 'flag':'--no-enable-prefix-caching',
        'initialized_gpu_cache':'NOT_RUN; require observed engine cache_config.enable_prefix_caching is False'}


def acquire(output):
    from kagglesdk.datasets.types.dataset_api_service import ApiDownloadDatasetRequest
    output = Path(output); output.mkdir(mode=0o700, parents=True)
    row, = [r for r in supplied_records() if r['path'].startswith('vllm-')]
    with tempfile.TemporaryDirectory(prefix='split-cache-') as temporary:
        root = Path(temporary)
        with resolver.kaggle_client() as client:
            request = ApiDownloadDatasetRequest()
            request.owner_slug = 'metric'; request.dataset_slug = 'gemma-4-developer-agent-wheelhouse'
            request.dataset_version_number = 25; request.file_name = row['path']
            response = resolver.retry_read(lambda: client.datasets.dataset_api_client.download_dataset(request))
            source = resolver.source_from_response(response, row)
        manifest = c.encoded({'schema_version': 1, 'phase': 'bootstrap', 'files': [
            {k: row[k] for k in ('path', 'bytes', 'sha256')}]})
        pull(root/'wheel', manifest, {row['path']: source}, c.digest(manifest), 300)
        files = {}
        with zipfile.ZipFile(root/'wheel'/row['path']) as archive:
            for name in ('vllm/engine/arg_utils.py', 'vllm/config/cache.py',
                         'vllm/utils/argparse_utils.py', 'vllm/entrypoints/openai/cli_args.py'):
                target = root / Path(name).name
                target.write_bytes(archive.read(name)); files[name] = target
        report = {'status': 'SOURCE_ACQUIRED', 'wheel': row, 'model_files': 0,
                  'sources': {n: hashlib.sha256(p.read_bytes()).hexdigest() for n,p in files.items()},
                  'cache_runtime_execution': 'NOT_RUN'}
        report['parser_slice']=qualify_sources(files)
        report['status']='PASS'
        report['encrypted_sources'] = seal(files, output/'cache-sources.age')
    c._new_output(output/'cache.json', c.encoded(report))
    return report


if __name__ == '__main__':
    print(json.dumps(acquire(sys.argv[1])))
