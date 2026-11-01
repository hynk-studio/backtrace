# Sixteen-example E2B trainability diagnostic

The owner instructed proceeding to the next step after the completed training
path audit in #51. This prospective diagnostic asks whether repeated full-target
SFT can learn fixed training examples and express that learning in free generation.
It does not estimate specialist generalization or Augnes value.

Select two status-OK training examples from distinct training families for each
of inference, abduction, revision and temporal revision, using the frozen hash
order in `small_model_trainability_data.py`. Pair each with a formatting exercise
that supplies the same answer as ordered fields. This gives eight reasoning and
eight format examples. Selection never uses held-out labels or model outputs.
These are explicitly training-set measurements; format inputs intentionally
contain the values to copy. This is not concealed evaluation-label leakage.

BASE generates once on all 16 prompts with the existing strong prompt. Q1 and Q4
start from separate untouched copies of the same pinned E2B checkpoint. Each
performs 640 SGD updates (40 identical ordered passes), rank 4, learning rate 0.01,
gradient clipping norm 1, seed 17, full answer plus template terminal supervision,
and no prompt/padding supervision. Q1 adapts the final query projection; Q4 adapts
the final four. Shared projections have the same initial matrices across arms.
The seed derivation is explicit and differs from the historical candidate; do
not claim a controlled causal comparison with that earlier run.

Before and after training, measure complete-target NLL on the same 16 examples,
including first-answer-token NLL and argmax. Save each adapter, verify same-instance
reload, destroy the training worker, then restore in a separate evaluation worker
and require exact reproduction of its trained probe logits with zero new updates.
Generate one response per original prompt in each arm: 48 assigned responses total.
Use greedy decoding, 768 new tokens and 60 seconds per request. Preserve missing,
invalid and interrupted outcomes; do not repair or retry them.

After both independent provider deletion proofs, score format answers for exact
JSON value preservation, and reasoning answers with the original task validator
and exact teacher. Report schema validity, exact JSON target matches and task
correctness separately. Numeric reasoning losses use the existing protocol
tolerance. A strict fit requires all 16 task-correct responses. Partial fit and
loss changes are descriptive; fixed-example memorization is not held-out gain.
A stronger adapter improving fit is evidence about this bounded configuration,
not proof that adapter capacity alone caused the old failure.

Reuse the existing owner/watcher, collector, isolation, hash-pinned delivery and
cleanup. One allocation, at most USD 0.75, 4,200 allocation-inclusive seconds
(3,780 work + 300 cleanup + 120 export), cumulative continuation at most USD 2.30,
and projected credit at least USD 0.6060441339. Actual affordability uses a fresh
account/stock/price snapshot. No top-up, overlapping allocation, automatic retry,
reuse of a consumed permit, main merge or Augnes write. Bind a new single-use
permit only after complete exact-source free qualification. Continue this bounded
step to real outputs and cleanup under the owner's existing delegation.

Review/start/state branches: `bt-001-trainability-20261101`,
`bt-001-trainability-start-20261101`, `bt-001-trainability-state-20261101`.
Namespace: `trainability-paid-20261101`. Original worker paths remain available
for historical reproduction; all previous source/start/state/result refs stay fixed.
