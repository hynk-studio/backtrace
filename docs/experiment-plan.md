# Bounded research sequence

Question: does specialist post-training in logical/abductive inference, Bayesian
belief revision and decision-relevant inspection improve resolved software tasks
under a matched total inference budget?

## Current evidence, 24 October 2026 KST

The [real R1 v2 diagnostic](verified-gpu-20261024.md) completed model execution,
patch submission, public verification (four tests passed) and resource cleanup.
It reused an inspected task. The historical one-minute R0 timeout and five-minute
R1 success have different budgets and cannot establish an R1 treatment effect.
The successful model still omitted verification after its final production edit.

The owner next authorized free CPU steps 1 and 2: freeze the successful runtime
and prepare a fair comparison; implement a small exact teacher. Their current
observed results are in [research-preparation-20261024.md](research-preparation-20261024.md).
No new GPU execution, training, paid retry or competition submission is part of
this slice. Historical receipts and consumed authorizations remain unchanged.

| Stage | Intervention | Present evidence and next gate |
| --- | --- | --- |
| R0 | Frozen no-LoRA scaffold under the common five-minute budget | New comparison candidate assembled on CPU. Matched model run NOT RUN. |
| R1 | R0 plus generic reproduction/review/verification guidance | New generic control assembled on CPU. Historical R1 v2 is an execution anchor, not a clean generic-review estimate. |
| R2 | R1 plus hypotheses, forward predictions, evidence revision and useful-inspection guidance | Prompt-only candidate assembled on CPU. Model comparison NOT RUN. |
| R3 | R2 runtime plus a specialist post-trained adapter | Exact teacher prepared; adapter training, save/reload and runtime attachment NOT RUN. |

## 1. Matched coding pilot

Use [matched-comparison.md](matched-comparison.md) and its machine-readable
[protocol](research-comparison-protocol.json). The runtime lock binds the actual
successful source, exact image, checkpoint/tokenizer/template file identities,
official harness/tools, runtime wheel closure and evaluator dependencies.
It does not claim that those large model/runtime assets were reacquired here.

All new arms share factual tool-contract corrections and budget instructions.
R0 retains the original scaffold's existing review language. R1 adds only the
declared generic review bundle. R2 adds the bounded diagnostic bundle to R1.
The historical prompt called R1 v2 already mentioned a leading explanation,
an alternative and a distinguishing check. Reusing that label as a pure generic
control would obscure the intended R2 contrast; it remains explicitly historical.

The common allowances are 300 seconds of agent work, 30 charged tools and
50 total model requests, including delegated work and retries. Commands have a
60-second ceiling within remaining work time. The 330-second child ceiling
includes teardown; it is not another 30 seconds of reasoning. Longer prompts
are part of treatment cost. Record actual prompt/output/reasoning tokens and
missing counters; equal time/call maxima do not prove equal realized token use.
Global request accounting and actual runner integration must be demonstrated
before a strict matched-inference claim. No historical receipt qualifies new
candidates or a multi-task execution campaign.

Select six primary tasks by deterministic round-robin across at least three
eligible repositories, plus six ordered reserves, using the pinned public
metadata and committed hash-ordering rule. The initial six-distinct-repository
proposal encountered a real metadata-only shortfall: excluding FastAPI leaves
62 tasks in three repositories. Preserve that v1 receipt and the explicit v2
amendment; the revised sample still has only three repository clusters.
Exclude the repeatedly inspected `fastapi_11194`, its repository aliases and
base snapshot. Only ID/repository/base-commit metadata enters selection; do not
inspect problem statements, reference patches or test labels. The source must
match its known size/hash and 129-ID inventory. A missing source or insufficient
eligible repositories is an explicit incomplete selection, not permission to
invent IDs or silently shrink the design.

Each primary task receives all three arms once, with the six arm permutations
counterbalanced across tasks. Use fresh workspaces and conversations, and never
share an earlier arm's trace, edited files or outcomes with another arm.
Reserves cannot replace hard tasks, failures or unfavorable outcomes. A corrupt
or unavailable input may motivate a recorded amendment only before any arm
outcome. Six tasks from three repositories and one stochastic sample per arm are a feasibility pilot,
not a powered demonstration of general superiority.

The primary endpoint is independent resolution within the common allowances.
Keep every assigned slot in the denominator, including model/infra failures,
timeouts, partial patches and explicit NOT RUN slots. Preserve negative/null
results. Report paired R1–R0, R2–R0 and especially R2–R1 outcomes, without an
effect estimate for incomplete pilots or invented statistical certainty.
Future larger studies need predeclared repetitions and uncertainty that respects
repository/family dependence.

Track final-edit retesting independently of correctness. The existing
`NO_COMMAND_AFTER_LAST_ACCEPTED_MUTATION` flag sees recognized edit/write tools;
it does not prove full shell/delegate mutation coverage. A later zero-exit
command does not prove a relevant same-check retest. Retain YES/NO/UNKNOWN plus
mutation/check ordering and coverage evidence for that stronger metric.

## 2. Small exact CPU teacher

The implemented [teacher](exact-teacher.md) uses finite Boolean probability
models with rational conditional tables and complete bounded enumeration.
Its exact labels include hypothesis posteriors, posterior-predictive and
hypothesis-conditioned forward predictions, logical status and expected utility
of inspection. The stated probability model is part of the question; a sampled
true world, evaluator answer or future sampled outcome is never part of the
agent input.

Cover duplicate/repeated evidence, dependent observations, incorrect initial
leaders, contradictory observations, zero-support model mismatch, ambiguous
causes and simultaneous causes. Unknown propositions, contradiction and model
mismatch are distinct states. A bounded solver error is not a false proposition
or a measured model failure. Do not force a unique cause when observations
cannot identify one.

Inspection value is the expected value of choosing the best action after an
observation minus the value of the best action now. Subtract explicit inspection
cost separately. A test can change beliefs while having zero decision value.
Include useful indirect inspections, redundant tests, excessive-cost tests and
stopping/tie cases. The implementation uses one-step observation value; it does
not claim an optimal long-horizon experiment policy or causal intervention effect.

The generator assigns disjoint underlying DAG families to train/evaluation,
checks canonical structural signatures and forbids decorative independent nodes
from manufacturing a nominal split. Splits are not based only on seeds, wording
or renaming. The audit binds the generator and regenerates the rows/labels. This
is an explicit small-family structural audit, not a proof against every form of
semantic or pretraining leakage.

Agent and evaluator JSONL files remain separate. Training may deliberately join
training questions and labels later; evaluation labels stay out of model input
and optimizer data. No real competition examples or leaderboard feedback become
training labels. Exact synthetic competence and real software-engineering
transfer are separate outcomes.

## 3. Adapter feasibility and training controls — later work

R2 need not outperform R1 before a small, explicitly budgeted R3 feasibility
experiment. Promptability and learnability are different hypotheses. First
verify the exact trainable checkpoint, tokenizer/template and adapter target
modules, one tiny training step, save/reload and attachment to the competition
runtime. An inference-quantized model is not assumed directly trainable; a PEFT
file is not assumed portable merely because its extension matches.

Training-specific claims require a general-reasoning training control matched
on data volume, tokens/steps, checkpoint, optimizer, adapter capacity and
evaluation schedule, with remaining differences reported. Loading an adapter
or reducing training loss does not establish useful diagnostic learning.
Large training remains blocked until compatibility and the tiny end-to-end
training/attachment path are actually demonstrated.

## Evidence and paid-compute boundary

Report independently: CPU tooling tests; input acquisition/pins; candidate
assembly; actual official schema/compiler validation; permitted model-task
execution; external correctness verification; resource cleanup; Kaggle
acceptance and hosted scoring. An earlier stage does not establish a later one.

Any future paid proposal must give the exact hardware and checkpoint, memory
measurement, bounded startup/work/retrieval/cleanup time, maximum total cost,
fresh single-use authorization and independent cleanup. Old one-task budgets
and consumed scopes are not a multi-arm allocation permit. This preparation
does not reset claims, alter provider settings, merge the PR, accept terms or
submit to the competition.
