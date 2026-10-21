"""Real HTTP routing/middleware probe; model execution is explicitly excluded.

The full mode calls installed vLLM build_app and OpenAIServingModels. Only the
engine state is a CPU fixture. No route, middleware, HTTP response or serializer
is replaced. Uvicorn lifespan is disabled because GPU initialization is outside
this probe. The minimal mode is a separate compatibility regression control.
"""
import argparse
import importlib.metadata
import io
import json
import logging
import socket
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

PINS = {'starlette': '0.52.1', 'prometheus-fastapi-instrumentator': '7.1.0'}
SIGNATURE = "AttributeError: '_IncludedRouter' object has no attribute 'path'"


def build(mode):
    if mode == 'vllm':
        from vllm.entrypoints.openai.api_server import build_app
        from vllm.entrypoints.openai.models.protocol import BaseModelPath
        from vllm.entrypoints.openai.models.serving import OpenAIServingModels
        from vllm.v1.engine.exceptions import EngineDeadError

        class EngineState:
            model_config = SimpleNamespace(max_model_len=128)
            renderer = io_processor = input_processor = None
            calls = 0
            dead = False

            async def check_health(self):
                self.calls += 1
                if self.dead:
                    raise EngineDeadError()

        # These are API assembly options, not a model/engine configuration.
        args = argparse.Namespace(disable_fastapi_docs=False, enable_offline_docs=False,
            root_path='', allowed_origins=['*'], allow_credentials=False,
            allowed_methods=['*'], allowed_headers=['*'], api_key=None,
            enable_request_id_headers=False, middleware=[])
        app = build_app(args, supported_tasks=('generate',))
        engine = EngineState()
        app.state.engine_client = engine
        app.state.openai_serving_models = OpenAIServingModels(engine,
            [BaseModelPath(name='cpu-api-fixture', model_path='/unused/cpu-api-fixture')])
        app.state.enable_server_load_tracking = False
        app.state.server_load_metrics = 0
        return app, engine

    from fastapi import FastAPI, APIRouter
    from prometheus_client import CollectorRegistry
    from prometheus_fastapi_instrumentator import Instrumentator
    app, router = FastAPI(), APIRouter()

    @router.get('/health')
    async def health():
        return None

    @router.get('/v1/models')
    async def models():
        return {'object': 'list', 'data': []}

    app.include_router(router)
    Instrumentator(registry=CollectorRegistry()).instrument(app).expose(app)
    return app, None


def probe(mode, expected):
    import httpx
    import uvicorn
    pins = dict(PINS, fastapi='0.141.1' if expected == 'routing-error' else '0.136.3')
    if mode == 'vllm':
        pins['vllm'] = '0.19.1'
    observed = {name: importlib.metadata.version(name) for name in pins}
    if observed != pins:
        raise ValueError('API probe package versions differ from the selected control')
    app, engine = build(mode)
    log = io.StringIO()
    handler = logging.StreamHandler(log)
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger = logging.getLogger('uvicorn.error')
    access_logger = logging.getLogger('uvicorn.access')
    logger.addHandler(handler)
    access_logger.addHandler(handler)
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, lifespan='off', log_config=None, log_level='info',
                                          access_log=True, timeout_graceful_shutdown=2))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    responses = {}
    try:
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError('CPU HTTP server did not start')
            time.sleep(0.02)
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=5,
                          headers={'Connection': 'close'}) as client:
            for path in ('/health', '/v1/models'):
                # Repeated real requests also catch failures after middleware setup.
                replies = [client.get(path) for _ in range(3)]
                responses[path] = [r.status_code for r in replies]
                want = 500 if expected == 'routing-error' else 200
                if responses[path] != [want] * 3:
                    raise AssertionError(f'{path}: {responses[path]} expected {want}')
                if mode == 'vllm' and expected == 'success' and path == '/v1/models':
                    body = replies[-1].json()
                    assert body['object'] == 'list'
                    assert [r['id'] for r in body['data']] == ['cpu-api-fixture']
            if expected == 'success':
                responses['/metrics'] = client.get('/metrics').status_code
                responses['/unknown-api-probe'] = client.get('/unknown-api-probe').status_code
                assert responses['/metrics'] == 200
                assert responses['/unknown-api-probe'] == 404
                if engine is not None:
                    assert engine.calls == 3, 'real health handler must consult engine state'
                    engine.dead = True
                    responses['/health-engine-dead'] = client.get('/health').status_code
                    assert responses['/health-engine-dead'] == 503
                    assert engine.calls == 4
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        logger.removeHandler(handler)
        access_logger.removeHandler(handler)
    if thread.is_alive():
        raise RuntimeError('CPU HTTP server did not stop')
    if expected == 'routing-error' and SIGNATURE not in log.getvalue():
        raise AssertionError('negative control did not reproduce the observed routing traceback')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.startup_guard import HTTPFailureTrace
    trace = HTTPFailureTrace()
    trace.feed(log.getvalue().encode())
    if expected == 'routing-error' and trace.cause != SIGNATURE:
        raise AssertionError('startup guard did not classify the actual repeated API traceback')
    if expected == 'success' and trace.cause is not None:
        raise AssertionError('startup guard falsely classified successful HTTP replies')
    return {'status': 'PASS', 'mode': mode, 'expected': expected, 'versions': observed,
            'responses': responses, 'http_transport': 'real loopback TCP/Uvicorn',
            'app_factory': 'installed vLLM build_app' if mode == 'vllm' else 'authored minimal FastAPI control',
            'engine': 'CPU state fixture; no model execution', 'lifespan': 'OFF',
            'error_signature': SIGNATURE if expected == 'routing-error' else None,
            'startup_classifier': 'PASS on actual Uvicorn access/error logs',
            'gpu_allocations': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('minimal', 'vllm'), required=True)
    parser.add_argument('--expect', choices=('success', 'routing-error'), required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    result = probe(args.mode, args.expect)
    body = json.dumps(result, sort_keys=True)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(body + '\n')
    print(body)
