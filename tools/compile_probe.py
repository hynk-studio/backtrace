"""Bounded official R0-clean construction only: no server, generation or sandbox run."""
import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

# Also usable by an isolated (-I) child, without PYTHONPATH or inherited credentials.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.backtrace import InspectionError, digest
from tools.artifacts import verify_artifacts
from tools.official_check import check_directory, check_installed_wheels
from tools.r0 import expected_candidate, inspect_candidate

FROZEN_SHA256 = '2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358'
MODEL = 'gemma-4-31b-it-qat-w4a16-ct'
MODEL_PATH = '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'
WALL_SECONDS = 45


class NoExecution:
    """Process-local Python API guard for inspected code, not an OS security sandbox."""
    def __init__(self):
        self.attempts = []

    def deny(self, boundary):
        self.attempts.append(boundary)
        raise InspectionError('construction probe blocked ' + boundary)

    def audit(self, event, args):
        if (event in ('socket.connect', 'socket.bind', 'socket.sendto', 'socket.sendmsg',
                      'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr')
                or (event == 'socket.__new__' and args[1] in (socket.AF_INET, socket.AF_INET6))):
            self.deny('network access')
        if event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.exec', 'os.fork'):
            self.deny('process execution')

    def install(self):
        # Permanent for this disposable child; includes requests swallowed by dependencies.
        sys.addaudithook(self.audit)
        # urllib3 probes IPv6 with a bind during import. Disable that capability probe
        # in this network-disabled child; all socket operations are still guarded.
        socket.has_ipv6 = False

    def assert_unused(self):
        if self.attempts:
            raise InspectionError('a forbidden operation was attempted during construction')


def no_request_client(guard):
    from google.adk.models.lite_llm import LiteLLMClient

    class NoRequestClient(LiteLLMClient):
        """Official LiteLlm client injection point; no synthetic responses."""
        def __deepcopy__(self, memo):
            return self  # compiler copies models; retain one attempt counter

        async def acompletion(self, *args, **kwargs):
            guard.deny('model generation')

        def completion(self, *args, **kwargs):
            guard.deny('model generation')

    return NoRequestClient()


def construct(sample, workspace, guard):
    """Real compiler/registries/classes; explicit absent task/sandbox and denied client."""
    from adk_submission import VllmConfig, VllmServer, compile_submission, discover_adapters
    from google.adk.agents import Agent
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.tools.agent_tool import AgentTool
    from google.adk.tools.function_tool import FunctionTool
    from swegemma.config import EvalConfig, build_submission_limits
    from swegemma.context import SwegemmaContext
    from swegemma.sandbox import AdkSandboxCodeExecutor
    from adk_submission.yaml_loader import load_yaml
    import yaml

    limits, generation = build_submission_limits()
    adapters = discover_adapters(sample, limits.adapter_extensions)
    require(not adapters.adapters, 'unexpected adapters')
    # Matches notebook registry construction; __init__ only creates a temporary log.
    # No context manager: VllmServer.__enter__ would start a server.
    server = VllmServer(VllmConfig(model=MODEL_PATH, tool_call_parser='gemma4',
                                 reasoning_parser='gemma4', max_loras=8, max_lora_rank=128,
                                 startup_timeout=1200), adapter_manifest=adapters)
    try:
        models = server.create_model_registry(aliases=[MODEL], model_prefix='openai/', api_key='EMPTY')
        model = models.get(MODEL)
        require(isinstance(model, LiteLlm), 'registry fell back to a model string')
        model.llm_client = no_request_client(guard)
        raw_budget = yaml.safe_load((sample / 'eval_config.yaml').read_text())['evaluation']
        require(raw_budget == {'timeout_seconds': 60, 'max_tool_calls': 10,
                               'max_time_minutes': 1, 'max_turns': 50}, 'budget drift')
        config = EvalConfig(tasks_path=workspace / 'absent-tasks.jsonl',
                            snapshots_dir=workspace / 'absent-snapshots',
                            results_dir=workspace / 'unused-results', submission_dir=sample,
                            models=models, sandbox='subprocess', **raw_budget)
        context = SwegemmaContext(task_id='authored-construction-fixture', repo='synthetic/fixture',
                                  problem_statement='Authored construction fixture; do not execute.',
                                  budget=config.budget, harness=config.harness,
                                  graph_dir=str(workspace / 'absent-graphs'),
                                  embeddings_dir=str(workspace / 'absent-embeddings'))
        require(context.sandbox is None, 'unexpected sandbox')
        tools = context.create_tools()
        code_executor = AdkSandboxCodeExecutor(
            sandbox=None, timeout_seconds=config.harness.command_timeout_seconds,
            start_time=context.task_start_time, max_time_minutes=config.budget.time_minutes,
            budget_check_fn=context.check_budget)
        root = compile_submission(sample, tools, models, limits=limits,
                                  generation_constraints=generation, adapter_manifest=adapters,
                                  code_executor=code_executor, script_timeout=60)
        require(isinstance(root, Agent), 'unexpected root class')
        wrapped = [tool for tool in root.tools if isinstance(tool, AgentTool)]
        require(len(wrapped) == 1 and wrapped[0].skip_summarization is True,
                'AgentTool wiring drift')
        analyzer = wrapped[0].agent
        require(isinstance(analyzer, Agent), 'unexpected analyzer class')
        reports = []
        for agent, rel in ((root, 'agent.yaml'), (analyzer, 'sub_agents/code_analyzer.yaml')):
            raw = load_yaml(sample / rel, sample, limits)
            require(raw.get('adapter') is None and raw['model'] == MODEL, 'model/adapter drift')
            require(agent.name == raw['name'] and agent.instruction == raw['instruction'], 'prompt drift')
            require(agent.generate_content_config.model_dump(exclude_none=True)
                    == raw['generate_content_config'], 'sampling drift')
            require(isinstance(agent.canonical_model, LiteLlm), 'external/default model fallback')
            require(agent.model.llm_client is model.llm_client, 'no-request client boundary lost')
            require(agent.model.model == 'openai/' + MODEL_PATH, 'model target drift')
            extra = agent.model._additional_args
            require(extra['api_base'] == 'http://127.0.0.1:8000/v1', 'endpoint drift')
            require(extra['extra_body']['chat_template_kwargs']['enable_thinking'] is True,
                    'thinking bridge drift')
            require('reasoning_effort' not in extra, 'unexpected reasoning effort rewrite')
            for item, tool in zip(raw['tools'], agent.tools):
                if isinstance(item, str):
                    require(tool is tools[item], 'tool callable binding drift')
            canonical = asyncio.run(agent.canonical_tools())
            declarations = []
            for tool in canonical:
                require(isinstance(tool, (FunctionTool, AgentTool)), 'unexpected tool class')
                declaration = tool._get_declaration()
                require(declaration is not None and declaration.name == tool.name, 'missing tool schema')
                declarations.append({'name': tool.name, 'class': type(tool).__name__})
            require(len(declarations) == len(raw['tools']), 'tool count drift')
            reports.append({'name': agent.name, 'class': type(agent).__name__,
                            'instruction_sha256': digest(agent.instruction.encode()),
                            'model_alias': raw['model'], 'model_target': agent.model.model,
                            'adapter': None, 'sampling': raw['generate_content_config'],
                            'tools': declarations})
        require({item for raw in (load_yaml(sample / 'agent.yaml', sample, limits),
                                 load_yaml(sample / 'sub_agents/code_analyzer.yaml', sample, limits))
                 for item in raw['tools'] if isinstance(item, str)} == set(tools), 'tool registry drift')
        budgets = {'command_timeout_seconds': config.harness.command_timeout_seconds,
                   'tool_calls': config.budget.tool_calls, 'time_minutes': config.budget.time_minutes,
                   'turns': config.budget.turns}
        require(budgets == {'command_timeout_seconds': 60, 'tool_calls': 10,
                            'time_minutes': 1, 'turns': 50}, 'runtime budget drift')
        require(context.tool_calls_used == 0 and context.llm_calls_used == 0, 'unexpected tool/model activity')
        require(server.process is None, 'server unexpectedly started')
        guard.assert_unused()
        return {'construction': 'PASS', 'callable_and_schema_binding': 'PASS', 'agents': reports,
                'registered_tools': sorted(tools), 'skip_summarization': wrapped[0].skip_summarization,
                'budget': budgets, 'model_registry': type(models).__name__,
                'model_client_boundary': 'injected NoRequestClient; generation raises, no fake response',
                'sandbox_boundary': 'None; synthetic context only; real AdkSandboxCodeExecutor constructed',
                'network_boundary': 'Python audit denial; IPv6 import capability probe disabled',
                'forbidden_operation_attempts': len(guard.attempts),
                'tool_execution': 'NOT RUN', 'server_startup': 'NOT RUN',
                'model_execution': 'NOT RUN', 'kaggle_execution': 'NOT RUN',
                'submission': 'NOT RUN', 'hosted_scoring': 'NOT RUN'}
    finally:
        server.stop()
        # Official stop() returns early when never started, leaving its empty log.
        Path(server.log_path).unlink(missing_ok=True)


def require(condition, message):
    if not condition:
        raise InspectionError(message)


def worker(artifacts, candidate, workspace):
    require(sys.prefix != sys.base_prefix, 'use the pinned isolated CPU venv')
    guard = NoExecution()
    guard.install()
    verify_artifacts(artifacts)
    check_installed_wheels(artifacts)
    local, files = inspect_candidate(candidate, expected_candidate(artifacts))
    require(local['sha256'] == FROZEN_SHA256 and candidate.stat().st_size == 6230,
            'candidate is not the frozen R0-clean archive')
    sample = workspace / 'candidate'
    for name, data in files.items():
        path = sample / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    cpu = check_directory(sample, candidate=True)
    report = construct(sample, workspace, guard)
    report.update(candidate_sha256=local['sha256'], candidate_bytes=6230,
                  official_cpu_checks=cpu['official_cpu_checks'], python=sys.version.split()[0],
                  platform=sys.platform, machine=os.uname().machine)
    guard.assert_unused()
    require(digest(candidate.read_bytes()) == FROZEN_SHA256, 'candidate changed during probe')
    return report


def run_probe(artifacts, candidate, python, timeout=WALL_SECONDS):
    """Sanitized child with a finite wall limit and disposable writable workspace."""
    artifacts, candidate = Path(artifacts).resolve(), Path(candidate).resolve()
    with tempfile.TemporaryDirectory(prefix='backtrace-compile-') as temporary:
        workspace = Path(temporary).resolve()
        environment = {'PATH': os.defpath, 'LANG': 'en_US.UTF-8', 'TMPDIR': str(workspace),
                       'OTEL_SDK_DISABLED': 'true', 'PYTHON_DOTENV_DISABLED': '1',
                       'LITELLM_LOCAL_MODEL_COST_MAP': 'True', 'LITELLM_TELEMETRY': 'False',
                       'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
        command = [str(Path(python).absolute()), '-I', '-B', str(Path(__file__).resolve()),
                   str(artifacts), str(candidate), '--worker']
        try:
            result = subprocess.run(command, cwd=workspace, env=environment,
                                    capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise InspectionError('CPU construction exceeded its finite wall-time cap; child stopped') from None
        if result.returncode != 0:
            # Our child emits an authored diagnostic or exception type, never raw errors.
            try:
                detail = json.loads(result.stdout)['error']
            except (ValueError, KeyError, TypeError):
                detail = 'CPU construction failed without a structured diagnostic'
            raise InspectionError(detail)
        report = json.loads(result.stdout)
    report['temporary_workspace_cleanup'] = 'PASS'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--official-python', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.worker:
            report = worker(args.artifacts, args.candidate, Path.cwd().resolve())
        else:
            require(args.official_python is not None, 'provide --official-python for the pinned CPU venv')
            report = run_probe(args.artifacts, args.candidate, args.official_python)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception as error:
        detail = str(error) if isinstance(error, InspectionError) else type(error).__name__
        if args.worker:
            print(json.dumps({'error': detail}))
        else:
            print('CPU construction probe failed: ' + detail, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
