"""Use the qualified collector unchanged with a fixed one-case profile."""
import contextlib
import json
from pathlib import Path
import sys
from tools import small_model_trainability as entry, small_model_onecase_data as data


@contextlib.contextmanager
def configured():
    bindings = {'data': data, 'ARMS': data.ARMS,
                'JOBS': ('E2B-BASE-eval', 'E2B-Q4-train', 'E2B-Q4-eval'),
                'ENTRY_MODULE': 'tools.small_model_onecase', 'COLLECTOR_SECONDS': 1500,
                'COLLECT_SECONDS': 300, 'TRAIN_SECONDS': 600}
    old = {k: getattr(entry, k) for k in bindings}
    try:
        for k, v in bindings.items(): setattr(entry, k, v)
        yield
    finally:
        for k, v in old.items(): setattr(entry, k, v)


if __name__ == '__main__':
    operation, *args = sys.argv[1:]
    with configured():
        if operation in ('inspect-inputs', 'plan-gpu-inputs'):
            result = entry.inspect_inputs(Path(args[0]), cuda_runtime=operation == 'plan-gpu-inputs')
        elif operation == 'collect':
            result = entry.collect(Path(args[0]), Path(args[1]))
            entry.life.write(Path(args[1])/'trainability-result.json', result)
        elif operation == 'preserve': result = entry.preserve(Path(args[0]))
        elif operation == 'evaluate': result = entry.evaluate(Path(args[0]))
        else: raise ValueError('explicit one-case operation required')
    print(json.dumps(result, sort_keys=True), flush=True)
