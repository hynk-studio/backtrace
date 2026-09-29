"""Run only the inspected official CPU directory, model and schema checks."""
import argparse
import json
import os
import sys
import zipfile
from importlib.metadata import distribution
from pathlib import Path

from artifacts import verify_artifacts
from backtrace import InspectionError, MANIFEST, digest


def check_installed_wheels(root):
    """Refuse changed official implementation bytes, even at the same version."""
    for record in json.loads(MANIFEST.read_text())['official_artifacts']:
        if not record['local_path'].endswith('.whl'):
            continue
        with zipfile.ZipFile(root / record['local_path']) as wheel:
            metadata = wheel.read(next(n for n in wheel.namelist()
                                       if n.endswith('.dist-info/METADATA'))).decode()
            fields = dict(line.split(': ', 1) for line in metadata.splitlines()
                          if line.startswith(('Name: ', 'Version: ')))
            installed = distribution(fields['Name'])
            if installed.version != fields['Version']:
                raise InspectionError('official package version mismatch; use docs/cpu-requirements.txt')
            for name in wheel.namelist():
                if name.endswith('.py'):
                    if digest(installed.locate_file(name).read_bytes()) != digest(wheel.read(name)):
                        raise InspectionError('installed official Python source differs from acquired wheel')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    args = parser.parse_args()
    try:
        if sys.prefix == sys.base_prefix:
            raise InspectionError('use an isolated Python 3.12+ venv; see docs/r0.md')
        verify_artifacts(args.artifacts)
        root = args.artifacts.resolve()
        check_installed_wheels(root)
        # Imports do not need account credentials, dotenv or remote model metadata.
        environment = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'TMPDIR')}
        os.environ.clear()
        os.environ.update(environment, OTEL_SDK_DISABLED='true',
                          LITELLM_LOCAL_MODEL_COST_MAP='True', PYTHON_DOTENV_DISABLED='1')
        from adk_submission import discover_adapters, validate_directory
        from adk_submission.schema import SandboxedAgentConfig
        from adk_submission.yaml_loader import load_yaml
        from swegemma.config import build_submission_limits
        from swegemma.models.discovery import validate_single_declared_model

        sample = root / 'sample_submission'
        limits, generation = build_submission_limits()
        directory = validate_directory(sample, limits=limits)
        model = validate_single_declared_model(sample)
        if model != 'gemma-4-31b-it-qat-w4a16-ct':
            raise InspectionError('unexpected competition model')
        agents = []
        for rel in ('agent.yaml', 'sub_agents/code_analyzer.yaml'):
            config = SandboxedAgentConfig.model_validate(load_yaml(sample / rel, sample, limits)).root
            generation.validate_config(config.generate_content_config.model_dump(exclude_none=True), config.name)
            agents.append({'path': rel, 'adapter': config.adapter})
        adapters = discover_adapters(sample, adapter_extensions=limits.adapter_extensions)
        print(json.dumps({'official_cpu_checks': 'PASS', 'subject': 'unchanged official starter',
                          'checks': ['competition directory limits', 'single declared model',
                                     'include loading', 'agent schemas', 'generation constraints',
                                     'adapter discovery'],
                          'directory_files': len(directory.all_files), 'single_model': model,
                          'agent_schemas': agents, 'adapters': sorted(adapters.adapters),
                          'compile_and_tool_binding': 'NOT RUN', 'model_execution': 'NOT RUN',
                          'submission': 'NOT RUN', 'hosted_scoring': 'NOT RUN'}, indent=2))
        return 0
    except Exception as error:
        # Never print exception data originating in an artifact or environment.
        detail = str(error) if isinstance(error, InspectionError) else type(error).__name__
        print('Official CPU checks did not pass: ' + detail + '. See docs/r0.md.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
