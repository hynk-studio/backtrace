# Five-minute task/search calibration

The owner requested implementation and verification after the recommendation
to correct the real task budget and failed search path before retrying. This
is free CPU preparation only. No new allocation is authorized.

## Runtime change

The production `cloud_task.prepare` path first reproduces the exact historical
cloud driver (`174bd6359c3e3f53e149a2ec5210cb220ab46ec41e1e9b34b6b0c915631c55b1`),
then creates `R1-budget5m-search-fallback-v1/A10080-TP1`. The prepared driver is
`32517bf07d280fea6f7f7a226914cc4262c34de49f988a53499229ce4ce4aefd`.

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

The runtime wraps the pinned bound graph tool without changing the installed
wheel. Simple `def`/`class` query prefixes become identifiers. If the graph is
empty, a bounded literal `git grep` runs through the actual official command
tool. Graph and text operations both consume the shared budget. Text fallback
is suppressed if it would use the final two tools / 45 seconds (including the
five-second text-command allowance). The guidance asks the
agent to preserve those resources for submission; it does not guarantee the
model will obey or that the patch is correct.

Calibrated completion requires the expected protocol, exact declared budget,
nonempty byte/hash-matched patch, `patch_submitted=true`, a submission invocation
in the ATIF trace, no agent error and matched successful model HTTP receipts.
Legacy validation keeps its ten-tool limit. A recovered partial patch is still
incomplete even if some public tests pass.

## Verification

- Local focused checks: 55 tests passed, CPU preflight passed; original private
  driver reproduced and calibrated workload closure verified (23 files).
- Complete local suite: 351 tests executed; 5 failures / 7 errors / 2 skips,
  matching this host's previously documented foreign-procfs limitations. Actual
  owner/UID checks require the Actions Linux host.
- Exact-source Linux suite, actual host and exact offline-image driver/runner:
  NOT RUN at this implementation checkpoint.
- Planned actual CPU case: add a harmless fixture marker using the real command
  tool, request an empty graph search, verify actual normalized text-search
  output and two counted operations, cross the original 60-second session and
  ten-tool limits, submit and recover the actual patch/trace.
- Existing HTTP-error, complete-tool and public evaluator controls remain.
  CPU chat content is scripted; no Gemma reasoning, GPU inference, task solution
  rate, submission acceptance or matched research improvement is established.

## Paid boundary

All historical authorizations remain consumed. The changed source invalidates
the old launch receipt, and the new driver expects its new protocol in a future
single-use permit. The existing consumed controller scope still names R0, so it
cannot silently launch the calibration. A successful free workflow is not a new
paid-launch receipt or permission to retry. No paid/watch branch, claim, main,
PR #16, merge, account setting or recurring wait is changed.

Any future comparison must match budget, guidance, tools and total diagnostics
across its arms. The original one-minute R0 result stays recorded as a timeout;
this combined budget/search calibration cannot isolate either change's effect.
