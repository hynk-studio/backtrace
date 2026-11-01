"""One prospective bounded allocation through the existing owner and watcher."""
import contextlib
import json
import sys
from tools import small_model_trainability_scope as previous, small_model_onecase as onecase

REVIEW = 'bt-001-reasoning-onecase-retry-20261101'
START = 'bt-001-reasoning-onecase-retry-start-20261101'
STATE_BRANCH = 'bt-001-reasoning-onecase-retry-state-20261101'
NAMESPACE = 'reasoning-onecase-retry-paid-20261101'
WORKFLOW = '.github/workflows/small-model-onecase.yml'
INSTRUCTION = '다시 하자'
PERMIT_MODE = 'OWNER_APPROVED_E2B_REASONING_ONECASE_RETRY'
CONTRACT = dict(previous.CONTRACT, scope='E2B_REASONING_ONECASE_640_RETRY_V1',
    pretrained_requests=2, training_steps=640, total_seconds=3000, work_seconds=2580,
    maximum_additional_usd='0.55', train_examples_per_arm=1,
    training_steps_per_arm=640, training_epochs=640, arms=['BASE', 'Q4'])
original_sources = previous.sources


def sources():
    extra = ('tools/small_model_onecase.py', 'tools/small_model_onecase_data.py',
             'tools/small_model_onecase_scope.py', 'tests/test_small_model_onecase.py',
             'docs/small-model-onecase-20261101.md',
             'docs/small-model-onecase-retry-20261101.md',
             '.github/workflows/small-model-trainability.yml', WORKFLOW)
    return dict(original_sources(), **{p: previous.minimum.life.digest(
        (previous.minimum.ROOT/p).read_bytes()) for p in extra})


@contextlib.contextmanager
def profile():
    bindings = {k: globals()[k] for k in ('REVIEW', 'START', 'STATE_BRANCH',
        'NAMESPACE', 'WORKFLOW', 'INSTRUCTION', 'PERMIT_MODE', 'CONTRACT', 'sources')}
    bindings.update(FREE_NAMESPACE_PREFIX='reasoning-onecase-retry-free-',
                    REMOTE_MODULE='tools.small_model_onecase_scope')
    old = {k: getattr(previous, k) for k in bindings}
    try:
        for k, v in bindings.items(): setattr(previous, k, v)
        with onecase.configured(): yield
    finally:
        for k, v in old.items(): setattr(previous, k, v)


@contextlib.contextmanager
def configured():
    with profile(), previous.configured(): yield


def validate_permit(value, source, now):
    with profile(): return previous.validate_permit(value, source, now)


if __name__ == '__main__':
    with profile(): result = previous.dispatch(sys.argv[1:])
    print(json.dumps({'status': result['status']}), flush=True)
    raise SystemExit(0 if result['status'] in ('PASS_TRAINABILITY_COLLECTION',
        'PASS_FREE_MINIMUM_ENTRY', 'PASS_FREE_REMOTE_CLEANUP', 'DELETED') else 1)
