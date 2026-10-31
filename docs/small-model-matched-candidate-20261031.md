# Prospective bounded E2B matched learning candidate

The actual E2B four-update run established CUDA adapter execution, saved bytes and
same-instance reload, but its single post-update response was invalid. E4B's actual
twenty-case comparison improved format following without establishing reliable
diagnosis. Continue to a direct learning comparison on E2B. This is a one-seed
candidate experiment; a positive conclusion requires subsequent confirmation.

Use the existing pinned E2B checkpoint, exact teacher, family catalog, B1 prompts,
collector, public preparation, owner and independent watcher. No new evaluator,
external training data, orchestration service or production integration is added.
The three arms are B1 (strong prompt, no updates), B2 (explicit forward-probability
and consistency/bookkeeping training), and S (specialist conditional inference,
abduction, static revision and temporal revision training). B2 is a narrow general-
reasoning control; it does not represent every general reasoning curriculum.

## Training budget and controls

Each trained arm uses the same64 train-only episodes, all from the frozen twelve
training families, covering eight scenario types. Four reasoning tasks per episode
give256 rows. Another64 identical formatting rows in both arms make320 updates per
arm. Common format practice supplies ordered field/value pairs from a train-only
target and asks for the exact JSON object; this target is deliberately available
in training and never in evaluation input. Every row is used once, in the same
deterministic seed17 hash order. Training includes no Augnes examples.

For the256 reasoning rows, both arms receive identical factual user payloads. S
uses the exact teacher's original conditional target. B2 explicitly overrides the
probability objective in its system prompt: unconditional marginals, complete
positive-prior cause assignments and forward predictions, while preserving
consistency status and active-record bookkeeping. B2 does not give incorrect
labels for the original task: its task instruction is different. This instruction
and target-distribution difference limits causal attribution to specialization
alone, and any degradation of B2 must not be treated as proof of S benefit.

Match320 updates, per-pair padded sequence length and per-pair loss-bearing token
count exactly. The loss quota is the smaller answer-token count, including the
terminal token. A fixed value-independent hash chooses the other supervised
positions in the longer answer; unsupervised labels are -100. Report unpadded
prompt/answer counts separately rather than claiming equal effective context.
Actual pinned-tokenizer qualification must establish the totals before allocation.
Maximum sequence length is3072 and effective sequence tokens are at most1,000,000
per arm. Preserve all masks and sequence hashes in reproducible source metadata.

Both trained arms start from separate untouched instances of the same frozen BF16
base. Use the already exercised last-query rank4 FP32 delta, alpha/rank1, SGD0.01,
gradient clipping1 and seed17. No optimizer, rank, step count or prompt is tuned
after candidate outputs. Emit every finished loss/gradient/update to raw stderr.
Verify both matrices changed, finite gradients, disabled-base equality, observable
enabled logit change, exact safetensors bytes and same-instance reload. Losses from
different rows are not a learning curve. The training worker then exits. A new
worker loads the original base and exported adapter, checks the train-probe input
and exact trained logit hash, and performs evaluation with zero further updates.
Preserve distinct process identities and idle-GPU teardown between all five jobs.

The free numerical control constructs tiny random CPU models and checks320
updates and fresh-model reload for each arm plus corrupt-artifact/probe/wrong-base
rejection. That is a same-process fresh-model implementation control, not actual
pretrained or fresh-process GPU evidence. Actual worker isolation, native tests,
full pinned checkpoint transfer/readback and all existing hardware controls remain
mandatory. The larger training jobs are private to the root supervisor, bounded by
the existing64MiB owner delivery, and only the selected job is copied into a worker.
The generic1MiB request/response limit remains unchanged; exported adapters are at
most512KiB and actual restore jobs at most1MiB. Evaluation workers receive no
teacher, references, other arm's training examples or prior responses.

## Evaluation and decision

Select96 distinct fresh development episodes from the existing eight development
families: twelve per family, twenty-four per task and twelve per scenario type.
Exclude the entire episode exposed in the old E2B baseline, not just its views.
No reserved-family labels are generated or inspected. Use the same96 inputs plus
the unchanged twenty Augnes packets in each arm:116 per arm,348 total. B1 then B2
then S is a fixed order, not a controlled latency comparison. All use4096 input
tokens,768 generated tokens,greedy decoding,60 seconds per request and1200 seconds
per collector including startup. Each separate training worker is bounded at600
seconds. The allocation-inclusive outer deadline overrides these local ceilings.

Initialize and preserve all348 assignments before allocation. Keep malformed,
truncated, interrupted and unstarted outcomes in their original denominators;
do not repair outputs or rescue selected cases. After both deletion proofs, use
the existing exact scorer on the96 synthetic inputs, reporting invalid rates and
task/family-level metrics with the original missing-output penalties. Report S
versus B1 as well as S versus B2. A narrow improvement over a degraded B2 is not
evidence of added value. Retain raw tokens, logits identities and adapter bytes.
The twenty Augnes cases receive source-grounded unblinded descriptive review;
format/label success is not semantic accuracy or real workflow benefit.

One seed, a small rank4 adapter, a narrow B2 curriculum and retrospective Augnes
cases limit conclusions. A null/negative result is a valid stopping decision for
this candidate; it does not prove no specialist model can work. A positive result
needs untouched-family and multi-seed confirmation. Current main-model/flow
comparison still requires an accessible Augnes connection/runtime configuration;
the three connected routes most recently failed. Do not substitute old defaults
or authored assistant responses for that comparison.

## Prospective allocation and continuation bounds

Both previous actual runs are deleted. At20:40 UTC the observed balance is
USD1.7174565922, autopay off, zero Pods and zero hourly spend. Observed continuation
spending isUSD1.1885875417, subject to delayed billing. Under the owner's continued
delegation inside the accepted prepaidUSD10 wallet, cap this one new allocation
atUSD0.90, cumulative continuation spending atUSD2.30 and projected credit at or
aboveUSD0.6060441339. The earlier assistant-set envelopes remain historical.
Total/work/cleanup/export limits are5340/4920/300/120 seconds. AtUSD0.59 compute
plus0.015 storage/hour, the all-in projection isUSD0.8974166667. Do not top up.

Review/start/state branches are bt-001-matched-candidate-20261031 /
bt-001-matched-candidate-start-20261031 / bt-001-matched-candidate-state-20261031;
namespace matched-candidate-paid-20261031, workflow small-model-matched.yml.
Require exact-source full free qualification and an unused single-use permit,
then fresh live account, complete inventory, stock and price admission. Preserve
the A6000/US-TX-1 failed-create exclusion, all isolation/hardware checks, independent
watcher and absence proofs. No overlap, automatic allocation retry, merge or
Augnes write. Actual prior training already exceeded12GB, so this path remains
unqualified for the owner's4070SUPER12GB. Continue through actual measurements
and interpretation within these bounds, stopping only at a genuine blocker.
