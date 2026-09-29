# Bounded research sequence

Question: does specialist post-training in logical/abductive inference, Bayesian
belief revision and decision-relevant inspection improve resolved software tasks
under a matched total inference budget?

This slice has run CPU tooling tests, artifact pin checks and official CPU
directory/model/include/schema/generation validation separately on the original
sample and the reproducible R0-clean archive. **R0, R1, R2 and R3 model/task runs:
NOT RUN.** No synthetic teacher, inference, adapter training or Kaggle submission
has run. A valid hosted run and evidence of improvement are separate outcomes.

| Stage | Intervention | Gate / comparison |
| --- | --- | --- |
| R0 | Frozen R0-clean no-LoRA derivative | Authorized two-line/four-file adapter removal only; immutable ten-file official reference retained. Six-file package reproduced and candidate CPU checks pass (docs/r0.md). No task run yet. |
| R1 | Strong generic review/inspection prompt | Match R0 runtime and budget; control for the benefit of generic review rather than specialized reasoning. |
| R2 | Bounded diagnostic prompt guidance | Compare with R1 and R0 under the same limits. No new reasoning engine. |
| R3 | R2 runtime prompt/harness plus specialist post-trained adapter | Test learning separately from promptability; use an appropriately matched general-reasoning training control for training-specific claims. |

R1/R2 retain R0-clean's scaffold, tools and budgets apart from their declared
prompt intervention. R3 adds experimental adapters to that matched scaffold;
do not mix the official example adapters into the comparison. Their presence,
metadata and discovery do not establish training history or usefulness.

R2 guidance pairs inverse hypothesis formation with forward predictions. Track
evidence identity/dependence, revise beliefs after observations, detect missing
causes/model failure, ask whether another inspection could change the decision,
and choose when to stop and act. Do not invent numerical posterior confidence for
real repository diagnoses. Logical inconsistency, unknown/unproved propositions,
and inference-tool timeouts are different states.

Keep the verified checkpoint, harness, tools, task split and total inference limits
matched. Diagnostic calls, retries, additional inspections, and any delegated calls
count against the budget. Freeze prompt/harness versions and record actual token,
call and wall-time use. Allocate runs before seeing held-out outcomes; preserve
negative, ambiguous and null results. Do not select a stronger control only after
seeing a favorable result.

R2 need not improve performance before a small, explicitly budgeted R3 feasibility
experiment: promptability and learnability are different hypotheses. Nevertheless,
large training is blocked until exact adapter compatibility, a tiny-batch training
step, save/reload, and attachment to the competition checkpoint/runtime all succeed.
An inference-quantized checkpoint is not assumed trainable, and a PEFT artifact is
not assumed portable merely because its extension matches.

## Possible next research slice, not implemented here

A tiny exact CPU teacher for finite logical/probabilistic worlds may follow the
baseline work. Specify the world generator and reference distribution before
probability scoring. Cover duplicate evidence, dependent observations, wrong
initial hypotheses, missing causes, ambiguous posterior states and simultaneous
causes where applicable. Include cases where inspection changes the best action,
where further inspection has no decision value, and where stopping is appropriate.
Distinguish inspection value from action value; never force a unique cause where
observations cannot identify one.

Separate agent-visible inputs from evaluator-only causes, answers, future
observations and labels. Split by underlying world/problem family, not merely by
paraphrase, seed or surface form. Audit leakage before training/evaluation. Do not
use hidden competition cases or leaderboard feedback as training labels. Public
development-task `patch`/`test_patch` fields belong to separate evaluator storage,
not the runtime agent prompt. Local synthetic competence does not establish
transfer to real software-engineering tasks.

For training-specific comparisons, match general-reasoning control data volume,
training token/step budget, checkpoint, optimizer, adapter capacity and evaluation
schedule as closely as justified. Report remaining differences explicitly; neither
mechanical adapter loading nor training-loss improvement proves diagnostic benefit.

## Outcomes and evidence

Primary competition-facing outcome: **resolved tasks under the fixed budget**.
Secondary outcomes: total latency and compute/cost, timeouts, unnecessary edits,
unnecessary inspections, recovery from wrong hypotheses, and basic coding/tool-use
regressions. Record failures and budget exhaustion in denominators. Compare paired
task outcomes with uncertainty appropriate to sample size and family dependence.
Probability metrics apply only with a defensible reference distribution.

Report these independently: local tooling tests; official requirements/starter
acquired and pinned; candidate archive built/inspected; official validation;
permitted end-to-end task; Kaggle acceptance; hosted scoring. Candidate packaging
and the documented CPU checks pass. Compilation/tool binding and every model,
submission and scoring stage remain NOT RUN. Do not infer usefulness, training
compatibility, transfer or submission acceptance from an earlier stage.

## Future paid-compute proposal, not authorization

Before any paid probe, the owner must approve a concrete capped proposal:

| Field | Required proposal content / current status |
| --- | --- |
| Candidate GPU | Exact type/count, informed by measured memory needs. Notebook L4 x4 is an inference example, not a selected training configuration. Unselected. |
| VRAM | Weight format, activations, sequence/batch size, optimizer and adapter memory plus headroom. Unmeasured; no numeric claim yet. |
| Wall-time | Explicit hard ceiling, startup allowance and cancellation threshold. Not allocated. |
| Storage | Bounded checkpoint/cache/adapter/log space and retention. Not allocated. |
| Auto-stop/cleanup | Independent job timeout, provider stop confirmation, removal of rented storage and redacted receipts. Not configured. |
| Compatibility | Exact checkpoint revision, tokenizer/template, quantization/training path and runtime version. Unverified. |
| Adapter assumptions | Format, rank, target modules, registration and save/reload/attachment test. Notebook PEFT/rank hints do not establish compatibility. |
| Cost ceiling | Provider price and maximum total charge including storage/egress, approved by owner before execution. No spend authorized. |

Until these are resolved, use local/free CPU for source review, tooling, exact
small teachers and tests only. This first PR does not build the teacher, a training
pipeline, RL campaign, multi-agent hierarchy, full prover or central architecture.
