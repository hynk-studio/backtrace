"""Frozen inference-only command and fail-closed initialized cache contract.

No paid launch entrypoint: provisioning/authorization and real GPU readiness are
separate stages. This module never imports task archives or evaluator labels.
"""
from tools.research_official import MODEL_PATH

PATH='/backtrace/split-runtime-config'
MIDDLEWARE='tools.research_split_server.RuntimeConfigMiddleware'


def server_configuration(port=8000):
    from adk_submission import VllmConfig
    return VllmConfig(model=MODEL_PATH,host='127.0.0.1',port=port,dtype='bfloat16',
        max_model_len=32768,tensor_parallel_size=1,gpu_memory_utilization=.9,
        tool_call_parser='gemma4',reasoning_parser='gemma4',
        default_chat_template_kwargs={'enable_thinking':True},
        extra_args=['--disable-custom-all-reduce','--no-enable-prefix-caching',
                    '--middleware',MIDDLEWARE])


def observed_configuration(config):
    model,parallel,cache=config.model_config,config.parallel_config,config.cache_config
    result={'model':model.model,'dtype':str(model.dtype),'max_model_len':model.max_model_len,
        'tensor_parallel_size':parallel.tensor_parallel_size,
        'disable_custom_all_reduce':parallel.disable_custom_all_reduce,
        'enable_prefix_caching':cache.enable_prefix_caching}
    if (result['model']!=MODEL_PATH or result['dtype'] not in ('bfloat16','torch.bfloat16')
            or result['max_model_len']!=32768 or result['tensor_parallel_size']!=1
            or result['disable_custom_all_reduce'] is not True
            or result['enable_prefix_caching'] is not False):
        raise ValueError('initialized split serving configuration mismatch')
    return result


class RuntimeConfigMiddleware:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['path']!=PATH:
            return await self.app(scope,receive,send)
        from starlette.responses import JSONResponse
        try:
            if scope.get('method')!='GET':raise ValueError('metadata GET required')
            observed=observed_configuration(scope['app'].state.vllm_config)
        except (AttributeError,KeyError,TypeError,ValueError):
            response=JSONResponse({'status':'NOT_READY'},status_code=503)
        else:response=JSONResponse({'status':'PASS','observed':observed})
        await response(scope,receive,send)
