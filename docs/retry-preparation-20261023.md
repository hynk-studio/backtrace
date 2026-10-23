# Free preparation after the unresolved R1 task

The last real model completed its session but did not resolve the public task.
This work changes generic verification guidance and preserves that failed result.
It does not launch another GPU, renew a paid authorization, or supply a task answer.

The original trace is byte-bound in `retry-preparation-diagnosis-20261023.json`.
The reproduction caught exceptions and printed failures while exiting zero on
three runs. The final intended implementation edit was rejected by the original
tool at the 30-call limit. The submitted patch therefore contained the earlier
shared-default change and reproduction script, not the rejected edit. The actual
independent verifier result remains **2 passed / 2 failed**. No task-specific
correction or evaluator-only answer is included in the revised candidate.

The R1 v2 candidate changes only the generic system/analyzer prompts relative to
R1 v1. Original six-file hashes are checked before either derivative is applied.
The same 300-second session, 30 charged tools, 50 model calls, checkpoint, task,
sampling and official tool implementations remain. Guidance starts verification
with six charged tools and 90 seconds left, requires a nonzero original failure,
the same assertion after accepted edits, inspection of editing-tool responses,
and an honest unresolved report when checks fail. This reserve is declarative;
it is not an extra allowance or a new tool interceptor.

Artifact validation now projects a privacy-preserving process diagnostic from
the original ATIF observations. Rejected edits, budget errors and zero-exit
failure text remain visible even when `submit_patch` succeeds. It does not score
correctness or treat a zero-exit search command as a passing test. Historical R1
verification stays explicitly bound to its original protocol.

| Check | Failure it can detect | Practical limit |
| --- | --- | --- |
| Original receipt and trace review | Budget rejection, swallowed failure text, unsupported applied-edit claims | Cannot infer an unknown root cause or task correctness |
| Real subprocess assertion controls | Passing exit after swallowed failure; wrong edit still fails; later edit invalidates earlier success | Authored check, not model reasoning |
| Original tools through full HTTP/runner path on host and exact image | Wrong/check/correct/check/stale/check sequence; actual 30-tool rejection; recovered patch excludes rejected edit | Scripted model replies; adherence by Gemma is unmeasured |
| Linux nested-process regression | Inner server phase fails to reap its orphan workers | Corrected real GPU teardown remains unrun |
| Full SSH/install/API/task/evaluator/lifecycle regression | Setup and boundary regressions from the changed source | CPU cannot qualify GPU loading or native generation |
| Source/claim/ref preservation | Reuse of stale qualification or a consumed paid attempt | Fresh live launch identity and stock are future gates |

Validation results are pending at this source checkpoint. Record the exact run,
source, bindings, private artifact recovery and negative controls before marking
free preparation complete. Retain any intermediate failures rather than replacing
them with the eventual passing result.

Another paid attempt still needs a fresh explicit scope, its own immutable state
namespace and source qualification, current budget/stock checks and an independent
watcher. Do not automatically repeat the known public task as a held-out benchmark
or claim the new generic prompt has improved model accuracy.

The first complete free run 39960937719 at e63306f6aa97e16426c0cbe6ee7701b3d53d4179
failed only at SSH fixture container cleanup: Docker rm exceeded 30 seconds.
Actual installation/driver prerequisites passed in 260.170s; all seven host and
seven offline-image task cases passed, including the new original-tool controls.
The original Docker removal state was not retained, so do not infer why the CLI
timed out or claim the original container was confirmed absent. Preserve this
failed report and its 152 encrypted private records.

The free-container helper now requests removal once and requires two successful
consecutive exact-name absence reads within one 120-second budget. Query errors,
malformed output, a changed identity and a still-present container cannot pass.
Both full SSH and offline-image cleanup use it. Actual Docker controls inject a
lost acknowledgement after real removal and a false acknowledgement while the
container remains present. These are authored faults, not a reproduction of the
unknown original daemon cause. Early encrypted diagnostics now include the SSH
setup result, so this failure is visible before later image checks finish.
