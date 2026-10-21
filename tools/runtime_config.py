"""Narrow loopback serving metadata through vLLM's supported middleware hook.

Read only the initialized application's actual engine config. No model call,
system-environment collection, development-mode API, or authored ready reply.
"""

MIDDLEWARE = 'tools.runtime_config.RuntimeConfigMiddleware'
PATH = '/backtrace/runtime-config'


class RuntimeConfigMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'] != PATH:
            return await self.app(scope, receive, send)
        from starlette.responses import JSONResponse
        if scope.get('method') != 'GET':
            response = JSONResponse({'error': 'GET required'}, status_code=405)
        else:
            try:
                config = scope['app'].state.vllm_config
                model, parallel = config.model_config, config.parallel_config
                body = {'vllm_config': {
                    'model_config': {'model': model.model, 'dtype': str(model.dtype),
                                     'max_model_len': model.max_model_len},
                    'parallel_config': {'tensor_parallel_size': parallel.tensor_parallel_size,
                        'disable_custom_all_reduce': parallel.disable_custom_all_reduce}}}
            except (AttributeError, KeyError, TypeError):
                response = JSONResponse({'error': 'engine configuration unavailable'}, status_code=503)
            else:
                response = JSONResponse(body)
        await response(scope, receive, send)
