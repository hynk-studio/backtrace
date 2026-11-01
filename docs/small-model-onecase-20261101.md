# One-case reasoning train-fit diagnostic

Prospective scope, 2026-11-01. Follows Draft #52; the owner requested
“다음 검증 진행해”. This is one new diagnostic, not a retry of a consumed permit.

The previous full-target run learned all eight supplied-answer format cases but
none of eight reasoning cases. Test whether concentrating all updates on one
reasoning example lets the existing Q4 adapter produce its complete answer.
Success is a minimum memorization gate, not generalization or Augnes value.

## Fixed design

Select the minimum SHA-256 digest of the canonical pair
`['reasoning-onecase-v1', id]` among the previous eight train-only reasoning rows.
No generated output, loss or held-out label participates in selection.
The selected ID is
`c97ef7d722c04a0dab309c49b13cabe2e67feabad96e05c344f78698f7da9e62`,
a temporal-revision case from training family
`1e44d7f2434e9f5a4025cb6168fecd9dfd74fa184a0337c4ca937b0bb4afbc40`.

Use the unchanged pinned E2B backbone, last four query projections, rank 4,
seed 17, FP32 adapter, SGD 0.01 and gradient clipping at 1.0. Freeze the base.
Perform exactly 640 updates on the one complete answer and terminal token;
mask prompt/padding and reject truncation or a changed chat prefix. Historical
tokenization reports 1,357 prompt and 60 answer/terminal tokens: 906,880 effective
and 38,400 supervised tokens, verified again before any paid allocation.
This gives the selected example 640 visits versus 40 in the prior mixed run.
Architecture, optimizer and target encoder stay fixed; no hyperparameter search.

Assign two greedy generations in advance: BASE before training, then Q4 in a
fresh independent process after export, trainer teardown and exact adapter reload.
Use identical label-free prompts, maximum 768 output tokens and 60 seconds per
request. The fresh worker must reproduce the trained probe-logit hash and make
zero updates. Keep baseline/disabled-base probes, full per-step losses and norms,
before/after full-answer NLL, adapter bytes, raw outputs and all missing/invalid
assignments. No answer is supplied in either generation prompt.

After verified deletion, use the original trusted schema and task scorer with
the unchanged numerical tolerance. Report exact target JSON match separately.
The gate passes only if Q4 returns valid complete JSON, all required task fields,
correct posterior/decision/evidence and exact canonical target JSON. Merely
lower NLL, a correct first token or valid JSON does not pass. No held-out test or
broader training is authorized by a partial result.

## Execution and budget

Reuse the existing isolated worker, collector, transport, owner and independent
watcher. A small explicit profile supplies the one-case data; old sixteen-case
defaults remain covered by their tests. Do not create another lifecycle framework.
Before allocation, require all exact-source native tests, CPU preflight, pinned
tokenizer/checkpoint checks, the 640-update tiny-model numerical control, fresh
reload/corruption checks, ordinary-container isolation and independent cleanup.

New review/start/state branches are `bt-001-reasoning-onecase[-start|-state]-20261101`.
New namespace: `reasoning-onecase-paid-20261101`. Bind a single-use permit to the
fully qualified source. Maximum additional debit USD 0.55, cumulative continuation
cap USD 2.30, minimum projected remaining credit USD 0.6060441339. Allocation total
3,000 seconds: work 2,580, cleanup 300, export 120. The existing allocation-inclusive
timer and independent cached-identity deletion remain mandatory. Collector bound
1,500 seconds, trainer 600 and each evaluation worker 300.

Last observed balance is USD 1.1925423895; continuation debit USD 1.7135017444,
subject to billing lag. Refresh account, complete inventory, stock and exact quote
before the new permit; the owner refreshes again immediately before creation.
At the previous A40 compute quote USD 0.59/hour plus USD 0.015/hour storage projection,
the 3,000-second worst case is USD 0.5041666667. This is an estimate, not a fresh quote.
Prepare/download all bulk bytes before charging starts. One allocation only; no
automatic paid retry, top-up, main merge or Augnes write. Preserve every prior
source, result, start and consumed permit. Retain failed qualification attempts.

## Expected interpretation

A passing one-case result establishes memorization with this adapter. A failure
despite falling teacher-forced loss narrows the next investigation to adapter
capacity/optimization and complete free-generation behavior. Either outcome is
reported with original evidence. Actual service comparison remains dependent on
the separately unavailable Augnes connection.
