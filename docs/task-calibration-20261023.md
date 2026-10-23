# Five-minute task/search calibration

The owner requested implementation and verification after the recommendation
to correct the real task budget and failed search path before retrying. This
is free CPU preparation only. No new allocation is authorized.

## Runtime change

The production `cloud_task.prepare` path first reproduces the exact historical
cloud driver (`174bd6359c3e3f53e149a2ec5210cb220ab46ec41e1e9b34b6b0c915631c55b1`),
then creates `R1-budget5m-search-guidance-v1/A10080-TP1`. The prepared driver is
`eca5e2ee5065419272e99f8407d09e63798801640f2a8005e5189e7aba9f1b79`.

The original eight task inputs, original six-file baseline ZIP, original model,
sampling and wheel bytes remain unchanged. After original input verification,
the driver derives the writable candidate: a five-minute session, 30 shared
tools, unchanged 50 LLM turns and 60-second command timeout, plus generic root
and analyzer search/completion guidance. No task-specific solution, public
reference patch or evaluator record enters these changes.

The outer agent child is 330 seconds. Both pre-server and post-readiness checks
reserve server shutdown (30 seconds), retrieval (180 seconds) and provider
cleanup (300 seconds). Before server startup the minimum is 1740 useful / 2040
total seconds; after readiness it is 540 / 840. A late setup or an inner-only
budget extension is blocked. The allocation-inclusive 5400/6900/7200 limits and
wallet/cumulative limits are unchanged.

The root and analyzer prompts now request bare graph identifiers, a read-only
`git grep` through the original `run_command` after an empty graph result, and
submission reserves of two tools / 45 seconds. Each operation uses the original
shared tool budget. The original tool factories, signatures and implementations
remain unchanged. This is prompt guidance, not deterministic enforcement of the
model's next action or a guarantee of patch correctness.

The pinned primary `HARNESS_README.md` states that submitted YAML resolves
against closed host registries. A private host-side automatic tool override
would not establish official submission compatibility, so it is excluded from
the final driver. Actual CPU checks assert the original `swegemma` tool factory.

Calibrated completion requires the expected protocol, exact declared budget,
nonempty byte/hash-matched patch, `patch_submitted=true`, a submission invocation
in the ATIF trace, no agent error and matched successful model HTTP receipts.
Legacy validation keeps its ten-tool limit. A recovered partial patch is still
incomplete even if some public tests pass.

## Verification

- Local focused checks: 53 tests passed after removing the private tool override;
  CPU preflight and all workflow YAML parsing passed.
- The initial implementation used an automatic host override. Linux 351 checks
  passed in run 39921830089, but its unfinished full probe is superseded. Its
  passing unit step does not qualify the final source. The initial YAML-only
  failure 39921711124 had zero jobs.
- Final exact-source Linux, host and offline-image task checks: NOT RUN at this
  checkpoint. Original-input installation remains pinned. The dedicated free
  mode executes all changed task/HTTP/evaluator boundaries and the exact image;
  it marks unchanged SSH/lifecycle checks NOT RUN and cannot become paid-launch
  qualification. This avoids repeatedly requalifying unchanged infrastructure
  to obtain a task-path result.
- Actual CPU case: add a harmless fixture marker using the real command tool,
  request an empty graph search with a bare symbol, then invoke the original
  command tool for text search. Cross the historical 60-second/ten-tool limits,
  submit and recover the actual patch/trace. Both searches are counted.
- Existing HTTP-error, complete-tool and public evaluator controls remain.
  CPU chat content and the fallback decision are scripted; no Gemma reasoning,
  compliance with guidance, GPU inference, task solution rate, submission
  acceptance or matched research improvement is established.

## Paid boundary

All historical authorizations remain consumed. The changed source invalidates
the old launch receipt, and the new driver expects its new protocol in a future
single-use permit. The existing consumed controller scope still names R0, so it
cannot silently launch the calibration. A successful free workflow is not a new
paid-launch receipt or permission to retry. No paid/watch branch, claim, main,
PR #16, merge, account setting or recurring wait is changed.

Any future comparison must match budget, guidance, original tools and total diagnostics
across its arms. The original one-minute R0 result stays recorded as a timeout;
this combined budget/search calibration cannot isolate either change's effect.
