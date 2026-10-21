# R0 API readiness recovery

**Latest outcome, 2026-10-22 KST:** the single recovery authorization is now
consumed. Actual GPU health returned HTTP 200, then the retained driver's
`/server_info?config_format=json` request returned 404 before inference/task
entry. Owner and watcher independently confirmed deletion. Read
[the execution record](a100-execution-20261022.md) and its evidence JSON.
The earlier preparation and unused-scope observations below are historical.

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
Both controls passed on the free Actions host and inside the exact deployment
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
- Full Linux suite and actual full runtime/app assembly: PASS in Actions.
  Pinned-image and remaining full qualification: PASS after the renewed handoff.
- Actual corrected GPU API readiness, inference, public task, evaluation and
  result recovery: NOT RUN. A fresh successful receipt and matching independent
  watcher are required before the single paid launch.

## Success criterion

Model loading, API readiness, public-task completion and result recovery are
separate milestones. The task is complete only when its result is retrieved and
interpreted, followed by independent Pod-absence and account-spending checks.
CPU checks or model loading alone do not complete R0.

Full free run 39615323568 at `1dc5437df47ec7a00205ccb6bfdb647ded727b8d`
passed the actual installed vLLM HTTP comparison after all 246 wheels were
verified and installed offline. Corrected health/models returned 200; old
FastAPI reproduced the exact 500 traceback. Both dependency checks passed.
It then failed at the missing original-reference handoff deadline, before the
pinned-image and later controller checks. That failure remains recorded.

The original private reference archive was subsequently recovered from the
prior working folder: 193,863 bytes, SHA256
`b3845934d3a848f83d65ef1c31c784ffc0fb9faf7ab30323a6b4b5e3d9308c0b`.
All eleven members (491,594 bytes) passed the unchanged original manifest.
The speculative saved-notebook fallback was removed after the observed absence
of those references. The next free run uses the established ephemeral age
handoff; no original plaintext or credential is published.

Linux workflow 39615323075 passed all 283 tests in 28.437 seconds, CPU
preflight and the exact-pin minimal real HTTP controls. At that checkpoint, full pinned-image and
controller qualification still required a fresh successful run. No GPU was
allocated; no scientific task, evaluation or inference ran.

## Completed free qualification

Run **39619584739**, job **119289147735**, attempt 1 passed at source
`328bdc7c7ebadbce5f32930af8126ffda363895b`; final projected report emitted at
2026-10-21T15:04:16Z. The renewed receipt binds all **58** operational files.
The previous missing-reference failure above remains part of the record.

- All 246 wheel, eight task and eleven original-reference bodies verified.
  Full runtime installed offline on Actions and in the pinned deployment image.
- Actual installed vLLM HTTP controls passed in both environments: corrected
  health/models 3x200, metrics 200, unknown route 404 and engine-dead health 503.
  Exact old FastAPI returned 3x500 on health and models with the original cause.
  Both dependency checks passed, and actual log classification passed.
- Actual sandbox dependency/UID prerequisites and worker cleanup passed in
  both environments; the retained driver passed seven boundary cases.
- All five concurrent owner/watcher scenarios passed, including delayed old
  heartbeats, worker failure, stale worker, state failure and owner cancellation.
  Provider replies are authored CPU fixtures; these are not paid GPU results.
- The same source passed all 283 Linux tests in 30.914 seconds, local-tooling
  preflight and the minimal exact-pin HTTP comparison (run 39619584891).

No GPU, inference, public task or evaluation ran. A fresh matching watcher
and available approved offer remain necessary for the single authorized launch.
At 14:45:25Z, the independent read-only account check found zero Pods, zero
spend/hour, Auto-Pay off, unchanged USD 7.6341384961 balance and no qualified
offer in any of the four approved regions. The authorization is still unused.
