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

Final-source run [39926119986](https://github.com/hynk-studio/backtrace/actions/runs/39926119986),
at `5b2f5cd11875c7eeb58c0ec906a1290b57b91237`, attempt 1, passed the actual Linux
suite (**350 tests, 31.572 seconds**), CPU preflight, official candidate checks,
real HTTP/runner/tools/UID/transport/evaluator paths on the host and the exact
pinned offline image. All **91** bound source hashes match the current code.

| Actual CPU environment | Task seconds | Charged tools | Chat requests | Submitted/recovered |
| --- | ---: | ---: | ---: | --- |
| Actions host | 71.140 | 12 | 14 | PASS |
| Exact offline deployment image | 71.266 | 12 | 14 | PASS |

The scenario really crosses the former 60-second/ten-tool limits. It adds a
harmless README fixture marker through the original command tool, receives an
empty original graph query, performs repository text search with the original
command tool, executes charged read commands, submits, and recovers the actual
305-byte patch and ATIF trace. Search decisions and chat content are scripted;
this establishes an executable path, not Gemma compliance or patch correctness.
The read-only analyzer's prompt is checked against its actual four declared
tools; only the parent receives command/submission instructions. The actual
`swegemma.context` tool factory is unchanged.

Missing-route, model-error, full-tool/delegation and actual public verifier
controls also passed in both environments. The authored neutral transport patch
fails two of four public tests, while the evaluator-only reference passes all
four. These are plumbing controls, not a new model score. **104** encrypted
private records were recovered; public/private projections, both real task
receipts, all four JUnit hashes/counts and the CPU-log hash were independently
verified. Raw public report, normalized execution proof and effective policy are
in the adjacent task-calibration JSON files.

Local focused checks passed **54** tests. The earlier complete local suite
retains this host's known foreign-procfs limits (349 before the last capability
regression, 5 failures / 7 errors / 2 skips); actual target Linux passes all 350.
The dedicated task-only mode marks unchanged SSH/full-setup/lifecycle checks
**NOT RUN**, and cannot issue paid-launch qualification.

The initial YAML failure 39921711124 had zero jobs. Free runs 39921830089,
39924443142 and 39924951197 were superseded; their unit steps are not final-source
qualification. The first host experiment actually completed its 69.268-second
scripted task with four charged calls, but its oracle wrongly counted uncharged
`get_status` calls as budget use. The final oracle uses charged command reads
and asserts measured usage above ten. The superseded owner-encrypted diagnostic
is retained. No GPU was used in any of these free checks.

## Paid boundary

All historical authorizations remain consumed. The changed source invalidates
the old launch receipt, and the new driver expects its new protocol in a future
single-use permit. The existing consumed controller scope still names R0, so it
cannot silently launch the calibration. A successful free workflow is not a new
paid-launch receipt or permission to retry. All 213 previous state blobs are unchanged; only eight free receiver/cipher/diagnostic blobs were added. All 20 actual paid/watch heads are fixed. No paid/watch branch, claim, main,
PR #16, merge, account setting or recurring wait is changed.

Any future comparison must match budget, guidance, original tools and total diagnostics
across its arms. The original one-minute R0 result stays recorded as a timeout;
this combined budget/search calibration cannot isolate either change's effect.
