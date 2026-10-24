"""Official compiler qualification of the exact three matched candidates.

Executed in a disposable CPU child with denied networking, processes and model
generation. The same package bytes used in the successful runtime are required.
"""
import argparse
import asyncio
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import research_comparison as c
from tools.compile_probe import MODEL, MODEL_PATH, NoExecution, no_request_client, require
from tools.official_check import check_directory


def check_wheels(wheels):
    rows = c.parse((c.ROOT / 'docs/source-manifest.json').read_bytes())['official_artifacts']
    checked = []
    for row in rows:
        if not row['local_path'].startswith('wheels/'):
            continue
        data = c.read_file(Path(wheels) / Path(row['local_path']).name, 4 * 1024**2)
        require(len(data) == row['size_bytes'] and c.digest(data) == row['sha256'], 'official wheel bytes changed')
        with zipfile.ZipFile(Path(wheels) / Path(row['local_path']).name) as wheel:
            metadata = wheel.read(next(n for n in wheel.namelist() if n.endswith('.dist-info/METADATA'))).decode()
            fields = dict(line.split(': ', 1) for line in metadata.splitlines() if line.startswith(('Name: ', 'Version: ')))
            installed = distribution(fields['Name'])
            require(installed.version == fields['Version'], 'official package version changed')
            for name in wheel.namelist():
                if name.endswith('.py'):
                    require(installed.locate_file(name).read_bytes() == wheel.read(name), 'installed official source changed')
            checked.append({'name': fields['Name'], 'version': fields['Version'], 'sha256': row['sha256']})
    require(len(checked) == 5, 'five official distributions required')
    return checked


def materialize_candidate(archive, arm, target):
    # The actual assembly receipt is already committed from the prior execution.
    evidence = c.parse((c.ROOT / 'docs/research-preparation-cpu-20261024.json').read_bytes())
    expected = evidence['research_inputs']['assembly']['arms'][arm]
    data = c.read_file(archive, 128 * 1024)
    require(len(data) == expected['archive_bytes'] and c.digest(data) == expected['archive_sha256'],
            'exact preregistered candidate required')
    target.mkdir(mode=0o700)
    with zipfile.ZipFile(archive) as package:
        require(len(package.infolist()) == 6 and set(package.namelist()) == set(expected['files']),
                'candidate membership changed')
        for name, digest in expected['files'].items():
            member = package.read(name)
            require(c.digest(member) == digest, 'candidate member changed')
            path = target / name; path.parent.mkdir(parents=True, exist_ok=True)
            c._new_output(path, member)
    return expected


def construct(sample, workspace, guard):
    from adk_submission import VllmConfig, VllmServer, compile_submission, discover_adapters
    from adk_submission.yaml_loader import load_yaml
    from google.adk.agents import Agent
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.tools.agent_tool import AgentTool
    from google.adk.tools.function_tool import FunctionTool
    from swegemma.config import EvalConfig, build_submission_limits
    from swegemma.context import SwegemmaContext
    from swegemma.sandbox import AdkSandboxCodeExecutor
    import yaml
    limits, generation = build_submission_limits()
    adapters = discover_adapters(sample, limits.adapter_extensions)
    require(not adapters.adapters, 'adapters must remain absent')
    server = VllmServer(VllmConfig(model=MODEL_PATH, tool_call_parser='gemma4', reasoning_parser='gemma4'),
                        adapter_manifest=adapters)
    try:
        models = server.create_model_registry(aliases=[MODEL], model_prefix='openai/', api_key='EMPTY')
        model = models.get(MODEL)
        require(isinstance(model, LiteLlm), 'real official LiteLlm registry required')
        model.llm_client = no_request_client(guard)
        raw = yaml.safe_load((sample / 'eval_config.yaml').read_text())['evaluation']
        require(raw == {'timeout_seconds': 60, 'max_tool_calls': 30, 'max_time_minutes': 5, 'max_turns': 50},
                'matched budget changed')
        config = EvalConfig(tasks_path=workspace / 'absent.jsonl', snapshots_dir=workspace / 'absent-snapshots',
                            results_dir=workspace / 'results', submission_dir=sample, models=models,
                            sandbox='subprocess', **raw)
        context = SwegemmaContext(task_id='cpu-construction', repo='fixture/repository',
            problem_statement='Authored CPU fixture', budget=config.budget, harness=config.harness,
            graph_dir=str(workspace / 'absent-graphs'), embeddings_dir=str(workspace / 'absent-embeddings'))
        tools = context.create_tools()
        executor = AdkSandboxCodeExecutor(sandbox=None, timeout_seconds=60, start_time=context.task_start_time,
                                        max_time_minutes=5, budget_check_fn=context.check_budget)
        root = compile_submission(sample, tools, models, limits=limits, generation_constraints=generation,
                                  adapter_manifest=adapters, code_executor=executor, script_timeout=60)
        require(isinstance(root, Agent), 'official root class changed')
        delegates = [t for t in root.tools if isinstance(t, AgentTool)]
        require(len(delegates) == 1 and delegates[0].skip_summarization is True, 'delegation wiring changed')
        reports = []
        for agent, path in ((root, 'agent.yaml'), (delegates[0].agent, 'sub_agents/code_analyzer.yaml')):
            config_yaml = load_yaml(sample / path, sample, limits)
            require(agent.instruction == config_yaml['instruction'], 'instruction binding changed')
            require(agent.generate_content_config.model_dump(exclude_none=True) == config_yaml['generate_content_config'],
                    'generation config changed')
            require(agent.model.llm_client is model.llm_client, 'shared model client boundary lost')
            require(agent.model.model == 'openai/' + MODEL_PATH, 'model binding changed')
            for expected, tool in zip(config_yaml['tools'], agent.tools):
                if isinstance(expected, str):
                    require(tool is tools[expected], 'original tool callable changed')
            declarations = asyncio.run(agent.canonical_tools())
            require(all(isinstance(t, (FunctionTool, AgentTool)) and t._get_declaration() is not None
                        for t in declarations), 'official tool declarations missing')
            reports.append({'name': agent.name, 'instruction_sha256': c.digest(agent.instruction.encode()),
                            'tools': [t.name for t in declarations], 'sampling': config_yaml['generate_content_config']})
        require(context.llm_calls_used == context.tool_calls_used == 0 and server.process is None,
                'construction unexpectedly executed')
        guard.assert_unused()
        return {'status': 'PASS', 'agents': reports, 'original_tools': sorted(tools),
                'shared_root_delegate_client': True, 'budget': raw, 'forbidden_attempts': len(guard.attempts)}
    finally:
        server.stop(); Path(server.log_path).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheels', type=Path); parser.add_argument('candidates', type=Path)
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args()
    guard = NoExecution(); guard.install()
    report = {'official_wheels': check_wheels(args.wheels), 'arms': {}, 'model_execution': 'NOT RUN'}
    c.load_protocol()
    args.workspace.mkdir(mode=0o700)
    for arm in c.ARMS:
        sample = args.workspace / arm
        expected = materialize_candidate(args.candidates / (arm + '.zip'), arm, sample)
        report['arms'][arm] = {'archive_sha256': expected['archive_sha256'],
            'schema': check_directory(sample, candidate=True),
            'compiler': construct(sample, args.workspace, guard)}
    guard.assert_unused(); report['status'] = 'PASS'
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Tracebacks are retained only in encrypted CPU evidence by the caller.
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(1)
