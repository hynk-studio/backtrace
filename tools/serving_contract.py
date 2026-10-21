"""The metadata exchange actually required by the frozen R0 driver.

Shared by deployment and free HTTP qualification so a new required request
cannot be added only to the paid path. These are metadata calls, not inference.
"""
import json
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener
from tools.runtime_config import PATH


def inspect_server(base_url, model):
    parsed = urlsplit(base_url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != '/v1' or not parsed.port):
        raise ValueError('loopback v1 inference endpoint required')
    origin = base_url[:-3]
    opener = build_opener(ProxyHandler({}))
    replies = []
    for path in (PATH, '/v1/models'):
        with opener.open(origin + path, timeout=10) as response:
            if response.status != 200:
                raise ValueError('required serving metadata is not ready')
            body = response.read(4 * 1024**2 + 1)
            if len(body) > 4 * 1024**2:
                raise ValueError('serving metadata exceeds bound')
            replies.append(json.loads(body))
    info, models = replies
    config = info['vllm_config']
    parallel = config['parallel_config']
    if (config['model_config']['dtype'] not in ('torch.bfloat16', 'bfloat16')
            or config['model_config']['model'] != str(model)
            or config['model_config']['max_model_len'] != 32768
            or parallel['tensor_parallel_size'] != 1
            or parallel['disable_custom_all_reduce'] is not True
            or str(model) not in [row['id'] for row in models['data']]):
        raise ValueError('observed server differs from frozen R0 settings')
    return info, models
