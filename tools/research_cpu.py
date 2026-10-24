"""Acquire pinned research inputs on a disposable free CPU runner.

Uses the existing Kaggle credential for its intended read-only service. Raw
competition inputs, signed URLs and reference answers never enter the report.
The temporary input tree is removed on success and failure. No provider client,
model execution, launch permit or persistent state write is invoked.
"""
import argparse
import contextlib
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import tempfile

from tools import research_comparison as comparison

ROOT = Path(__file__).resolve().parents[1]


def acquire(kind, client, destination):
    """Reuse the already reviewed bounded/hash-checked input transport."""
    from tools import cloud_resolver
    from tools.direct_delivery import pull
    if kind == 'metadata':
        manifest, sources = cloud_resolver.resolve_evaluator(client)
    elif kind == 'baseline':
        from tools.a100_delivery import manifest as frozen_manifest
        rows = json.loads(frozen_manifest('task'))['files']
        row = next(row for row in rows if row['path'] == 'r0-clean.zip')
        manifest = comparison.encoded({'schema_version': 1, 'phase': 'bootstrap', 'files': [row]})
        url = cloud_resolver.notebook_output_url(client, 'backtrace-r0-selected-inputs',
                                                'v1', row['path'])
        sources = {row['path']: cloud_resolver.public_source(url, row)}
    else:
        raise ValueError('unknown research input kind')
    return pull(destination, manifest, sources, hashlib.sha256(manifest).hexdigest(), 180)


def source_schema(data, protocol):
    """Field names/types only, useful if the frozen format rejects selection."""
    policy = protocol['selection']
    if len(data) != policy['metadata_bytes'] or comparison.digest(data) != policy['metadata_sha256']:
        raise ValueError('original metadata identity mismatch')
    types = {}
    count = 0
    for line in data.splitlines():
        if not line.strip():
            continue
        row = comparison.parse(line)
        if not isinstance(row, dict):
            raise ValueError('metadata record must be an object')
        count += 1
        for key, value in row.items():
            if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,79}', key):
                raise ValueError('unexpected metadata field name')
            types.setdefault(key, set()).add(type(value).__name__)
    return {'rows': count, 'fields': {k: sorted(v) for k, v in sorted(types.items())}}


def prepare(output, *, root=ROOT, client_factory=None, acquire_inputs=acquire):
    """Return a public receipt; retain no input bytes even when a stage fails."""
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('research receipt already exists')
    if not output.parent.is_dir() or output.parent.resolve() != output.parent:
        raise ValueError('existing real output parent required')
    protocol = comparison.load_protocol(root / 'docs/research-comparison-protocol.json', root)
    if client_factory is None:
        from tools.cloud_resolver import kaggle_client
        client_factory = kaggle_client
    local = root / '.local'
    local.mkdir(mode=0o700, exist_ok=True)
    if local.is_symlink() or local.resolve() != local.absolute():
        raise ValueError('local scratch must not be a symlink')
    report = {'schema_version': 1, 'kind': 'FREE_CPU_RESEARCH_PREPARATION',
              'protocol_sha256': comparison.digest(comparison.encoded(protocol)),
              'model_execution': 'NOT RUN', 'provider_operations': 0,
              'raw_competition_inputs_published': False,
              'compute_authorization': 'NONE', 'phase': 'input_resolution'}
    for key, name, pattern in [('source_sha', 'GITHUB_SHA', r'[0-9a-f]{40}'),
                                ('run_id', 'GITHUB_RUN_ID', r'[0-9]+')]:
        value = os.environ.get(name, '')
        if re.fullmatch(pattern, value):
            report[key] = value
    previous_logging = logging.root.manager.disable
    scratch = None
    try:
        with tempfile.TemporaryDirectory(prefix='research-inputs-', dir=local) as temp:
            scratch = Path(temp)
            # Library/SDK exceptions can contain signed URLs. Never print their
            # text, captured diagnostics or chained tracebacks to public logs.
            logging.disable(logging.CRITICAL)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with client_factory() as client:
                    report['phase'] = 'metadata_download'
                    report['metadata_delivery'] = acquire_inputs('metadata', client, scratch / 'metadata')
                    metadata = comparison.read_file(scratch / 'metadata/tasks.jsonl', 3 * 1024**2)
                    report['metadata_schema'] = source_schema(metadata, protocol)
                    report['phase'] = 'blind_selection'
                    report['selection'] = comparison.select_tasks(metadata, protocol)
                    report['phase'] = 'baseline_download'
                    report['baseline_delivery'] = acquire_inputs('baseline', client, scratch / 'baseline')
                    report['phase'] = 'candidate_assembly'
                    baseline = scratch / 'baseline/r0-clean.zip'
                    report['assembly'] = comparison.build(baseline, scratch / 'candidates', protocol, root)
                    report['status'] = ('PASS' if report['selection']['status'] == 'SELECTED'
                                        else 'SELECTION_SHORTFALL')
                    report['phase'] = 'complete'
    except Exception as error:
        report['status'] = 'FAILED'
        report['error_type'] = type(error).__name__
        # A fixed manifest member is useful diagnosis; arbitrary exception text
        # can contain signed URLs and remains private.
        path = getattr(error, 'input_path', None)
        if path in ('tasks.jsonl', 'r0-clean.zip'):
            report['input_path'] = path
    finally:
        logging.disable(previous_logging)
        report['temporary_inputs_removed'] = scratch is None or not scratch.exists()
    if not report['temporary_inputs_removed']:
        report['status'] = 'FAILED'
    comparison._new_output(output, comparison.encoded(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    try:
        report = prepare(args.output)
    except Exception as error:
        print(json.dumps({'status': 'FAILED', 'phase': 'initialization', 'error_type': type(error).__name__}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
