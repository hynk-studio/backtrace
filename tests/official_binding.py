"""Opt-in real compiler regressions, using only authored synthetic YAML fixtures.

Run in the pinned CPU venv with env -i as documented in docs/verification.md.
Separate from standard-library test discovery; never launches a model or sandbox.
"""
import asyncio
import os
import signal
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compile_probe import NoExecution, no_request_client
from tools.artifacts import verify_artifacts
from tools.official_check import check_installed_wheels


class OfficialBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.guard = NoExecution()
        self.client = no_request_client(self.guard)
        from adk_submission import ModelRegistry
        from google.adk.models.lite_llm import LiteLlm
        from swegemma.context import SwegemmaContext
        self.models = ModelRegistry()
        self.models.register('fixture_model', LiteLlm(model='openai/fixture', llm_client=self.client,
                                                     api_base='http://127.0.0.1:1/v1', api_key='EMPTY'))
        self.context = SwegemmaContext(task_id='fixture', repo='authored/fixture')
        self.tools = self.context.create_tools()
        self.write('fixture_model', 'get_status')

    def write(self, model, tool):
        (self.root / 'agent.yaml').write_text(
            f'name: fixture_agent\nmodel: {model}\ninstruction: Authored test fixture.\ntools:\n  - {tool}\n')

    def compile(self):
        from adk_submission import compile_submission
        return compile_submission(self.root, self.tools, self.models)

    def test_real_compiler_and_callable_schema(self):
        from google.adk.agents import Agent
        from google.adk.tools.function_tool import FunctionTool
        agent = self.compile()
        self.assertIsInstance(agent, Agent)
        tools = asyncio.run(agent.canonical_tools())
        self.assertIsInstance(tools[0], FunctionTool)
        self.assertIs(tools[0].func, self.tools['get_status'])
        self.assertEqual(tools[0]._get_declaration().name, 'get_status')
        self.assertEqual(self.context.tool_calls_used, 0)

    def test_unknown_tool_is_rejected_by_real_resolver(self):
        from adk_submission.errors import ToolNotFoundError
        self.write('fixture_model', 'not_registered')
        with self.assertRaises(ToolNotFoundError):
            self.compile()

    def test_unknown_model_is_rejected_by_real_resolver(self):
        from adk_submission.errors import ModelNotFoundError
        self.write('not_registered', 'get_status')
        with self.assertRaises(ModelNotFoundError):
            self.compile()

    def test_generation_fails_at_injected_client_without_request(self):
        from google.adk.models.llm_request import LlmRequest
        from google.genai import types
        from tools.backtrace import InspectionError
        agent = self.compile()
        async def attempt():
            request = LlmRequest(contents=[types.Content(role='user', parts=[types.Part(text='fixture')])])
            async for _ in agent.model.generate_content_async(request):
                self.fail('no synthetic or actual response is permitted')
        with self.assertRaisesRegex(InspectionError, 'blocked model generation'):
            asyncio.run(attempt())
        self.assertEqual(self.guard.attempts, ['model generation'])

    def test_streaming_client_also_rejects_generation(self):
        from tools.backtrace import InspectionError
        with self.assertRaisesRegex(InspectionError, 'blocked model generation'):
            self.compile().model.llm_client.completion('fixture', [], [], stream=True)

    def test_installed_network_and_process_guards(self):
        from tools.backtrace import InspectionError
        with self.assertRaisesRegex(InspectionError, 'blocked network access'):
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with self.assertRaisesRegex(InspectionError, 'blocked process execution'):
            subprocess.run([sys.executable, '-c', 'raise SystemExit(99)'])


if __name__ == '__main__':
    if sys.prefix == sys.base_prefix or any(key in os.environ for key in ('OPENAI_API_KEY', 'KAGGLE_API_TOKEN')):
        raise SystemExit('Use env -i with the pinned CPU venv; see docs/verification.md')
    # unittest propagates KeyboardInterrupt, allowing the temporary-root cleanup to run.
    def time_limit(*_):
        raise KeyboardInterrupt('CPU binding tests exceeded their 40-second cap')
    signal.signal(signal.SIGALRM, time_limit)
    signal.alarm(40)
    with tempfile.TemporaryDirectory(prefix='backtrace-binding-tests-') as temporary:
        os.chdir(temporary)
        tempfile.tempdir = temporary
        os.environ.update(OTEL_SDK_DISABLED='true', PYTHON_DOTENV_DISABLED='1',
                          LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_TELEMETRY='False',
                          HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        NoExecution().install()
        verify_artifacts(ROOT / '.local/official')
        check_installed_wheels(ROOT / '.local/official')
        result = unittest.main(exit=False, verbosity=2).result
    signal.alarm(0)
    sys.exit(not result.wasSuccessful())
