# R0 API readiness recovery

The owner instructed **권고대로 수행하자** after the failure was reproduced and
the overall process reconsidered. This scope implements the recommended API
correction and free qualification, followed by **one** existing public-task run
only when all gates pass. It does not reset any historical paid claim.

- Recovery branch: `bt-001-api-readiness-recovery`, based on PR #7 head
  `50c9ee629b9a0d59dcd076d26eca80fe9969b376`.
- Fresh authorization namespace: `owner-api-recovery-20261021`.
- Dedicated start/watch branches: `bt-001-a100-start-api-recovery` and
  `bt-001-a100-watch-api-recovery`. Creating them is a separate launch action.
- Existing USD 10 wallet, USD 8 cumulative early stop, one A100 80GB PCIe,
  one server and `fastapi_11194` public task; 5,400/6,900/7,200-second setup,
  useful-work and allocation-to-confirmed-deletion limits remain unchanged.
- No additional funding, automated paid retry, training, submission or merge.

## Runtime change and evidence boundary

Only FastAPI changes: **0.141.1 → 0.136.3**. Starlette 0.52.1,
prometheus-fastapi-instrumentator 7.1.0, vLLM 0.19.1, model, prompts and inference
settings remain unchanged. The replacement wheel was downloaded and its SHA-256
verified against PyPI release metadata. Exact old/new identities are in
`a100-api-runtime-amendment.json`; the runtime lock, delivery inventory and its
bound fingerprint are updated together. The old wheel is CPU-test-only.

Primary source inspection: installed-version upstream source at
`https://github.com/vllm-project/vllm/tree/v0.19.1/vllm/entrypoints`;
`openai/api_server.py`, `openai/models/{api_router,serving}.py` and
`serve/instrumentator/{metrics,health}.py`. These locate the app factory, actual
routers, model serializer and metrics middleware. Execution of the pinned
installed wheel is the qualifying evidence, not tag inspection alone.

`tools/api_probe.py` makes real loopback TCP requests through Uvicorn. Full mode
uses installed vLLM `build_app`, actual routers/middleware and
`OpenAIServingModels`; only engine state is a CPU fixture, and GPU lifespan
initialization is explicitly disabled. It verifies health, model serialization,
metrics, unknown routes and an engine-dead 503. No HTTP response or route handler
is replaced. It does not establish actual model readiness or inference.

`tools/qualify_api.py` compares the corrected environment to an isolated overlay
containing the exact old FastAPI wheel, with all other installed packages held
constant. Both combinations must pass `pip check`; old-pin real requests must
produce the original `_IncludedRouter.path` traceback, while the correction
must return 200. The guard must recognize the actual Uvicorn failure logs.
Both controls run on the free Actions host and inside the exact deployment
image. Their source files are bound into the renewed qualification receipt.

## Startup failure handling

Three identical complete ASGI tracebacks paired with consecutive `/health` 500
responses end startup promptly. A connection failure, a 503, a lone exception,
quoted traceback or changing errors do not satisfy that rule. Existing terminal
engine/worker checks and the total deadline remain in force.

The first readiness exception is retained across cleanup inside the wrapper and
the caller's subsequent `finally`. Cleanup failures are recorded separately,
including when the wrapper calls stop before raising its timeout. These changes
do not treat failed cleanup observation as proof of process or Pod deletion.

## Validation status at implementation

- Local minimal real HTTP control: corrected health/model endpoints return 200;
  old FastAPI returns 500 with the exact previous traceback. The real-log error
  classifier passes. This is a minimal integration control, not the full runtime.
- Five new classification/cleanup tests pass; 79 cloud tests pass with one
  environment skip. Updated delivery inventory checks pass.
- Local full discovery was run. Twelve existing foreign-procfs limitations and
  two environment skips prevent a local full-pass claim. A stale wheel-byte
  expectation exposed by the version change was corrected and rechecked.
- Required full Linux suite, exact full runtime/app assembly and pinned-image
  qualification: PENDING GitHub Actions.
- Actual corrected GPU API readiness, inference, public task, evaluation and
  result recovery: NOT RUN. A fresh successful receipt and matching independent
  watcher are required before the single paid launch.

## Success criterion

Model loading, API readiness, public-task completion and result recovery are
separate milestones. The task is complete only when its result is retrieved and
interpreted, followed by independent Pod-absence and account-spending checks.
CPU checks or model loading alone do not complete R0.

The free qualifier first tries to recover the eleven exact original references
from the already hash-pinned private notebook data archive. It selects only the
original manifest paths and rechecks every byte hash; notebook code is never
executed. The prior encrypted handoff remains available when those original
references are absent. Current competition downloads never replace old inputs.
