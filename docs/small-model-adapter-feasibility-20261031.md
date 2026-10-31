# E2B tiny adapter implementation probe

This is the plan's actual update/save/reload step, not a specialist-benefit test.
The measured E2B baseline failed its synthetic response contract; the E4B capacity
comparison is running separately. Its resource must be proved deleted before any
new allocation. Neither outcome establishes whether specialist training helps.

Reuse the same pinned E2B checkpoint, BF16/SDPA worker, exact-source qualification
and owner/watcher. Freeze four supervised updates before execution: the first
lexicographic **train** family, variant 1, with inference, abduction, final static
revision and final temporal revision. Targets come from the existing exact
teacher/scorer. They are checked against the train catalog and do not overlap the
existing development assignments. No development/held-out answer is sent to the
worker. Original B0/B1 generation prompts and three replay packets remain fixed.

Only the last linear attention query projection receives a rank-4 additive
adapter. All base parameters stay frozen. A uses seeded Kaiming initialization;
B starts at zero. Alpha/rank is one; there is no dropout. Four plain SGD updates
use learning rate 0.01 and gradient-norm clipping at one. This deliberately tiny
fixed probe is meant to expose a real update in BF16, not to select a useful
optimizer, rank, module set, curriculum or checkpoint. Only answer tokens and the
existing turn terminator are supervised; prompts are masked. Each complete
training sequence is bounded at 2,048 tokens and checked before allocation.

The worker must observe finite gradients/loss, changed adapter tensors and a
nonzero adapter-on/off logit difference on a training prompt. Disabling the
adapter must reproduce initial base logits exactly. It writes safetensors to a
fresh temporary directory, reads them back, clears its adapter tensors and
restores the saved values; recomputed logits must equal the trained logits at
zero tolerance. No pickled code is loaded. The at-most-512-KiB adapter bytes,
SHA-256, token/parameter counts, gradient norms, losses, elapsed time and measured
GPU peaks travel through the existing bounded JSON channel. The adapter remains
enabled for the original 24 assigned generations; they are explicitly recorded
as trained implementation-probe outputs, not an untrained baseline or matched S
arm. A trained output can still be wrong or invalid.

Free qualification additionally runs the same update/save/reload function with a
tiny random Gemma and synthetic token IDs in the pinned CPU runtime. It verifies
numerical plumbing only. Actual CUDA backward/serialization still requires the
real paid worker. The existing 17 isolation/lifecycle controls and missing-GPU
refusal remain required. Load metrics are captured before training so they are
not confused with training peaks/time.

The new source-bound review/start/state names use `bt-001-e2b-adapter-20261031`,
`bt-001-e2b-adapter-start-20261031` and
`bt-001-e2b-adapter-state-20261031`; namespace is `e2b-adapter-paid-20261031`.
The reduced allocation-inclusive limit is **2,200 seconds**: 1,780 work, 300
cleanup and 120 export. The existing controller now reads those already-declared
duration fields instead of hardcoded defaults; its historical default remains
3,000/2,580/300/120. Independent cleanup and deadline checks bind the shorter
claim. Maximum projection is USD 0.370, still subject to the remaining cumulative
USD 1 ceiling, fresh stock/price/account observation and USD 0.50 reserve. No
overlapping GPU, automatic reallocation, top-up or production write is allowed.

Actual feasibility has not yet run. Passing it enables a concrete matched B2/S
screen; it supplies no specialist-learning, unseen-problem, Augnes-utility or
deployment claim. Failure must remain evidence and may motivate only a supported
correction. Do not stop the delegated research merely because a PR or this tiny
implementation probe finishes.
