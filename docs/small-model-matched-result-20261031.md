# Matched E2B candidate completed: no supported specialist benefit

Actual [run41242457133](https://github.com/hynk-studio/backtrace/actions/runs/41242457133)
completed all348 assigned generations and640 CUDA training updates. Both trained
adapters changed, were exported, and reproduced their trained probe logits exactly
in separate evaluation processes. Both controllers independently proved the GPU
deleted. This establishes execution and artifact provenance, not useful learning.

The candidate failed its development comparison. Of96 synthetic responses per
arm, the unchanged task validator accepted8 for untrained B1 and0 for either B2
or specialist S. Those eight B1 outputs are schema-valid, not eight exact answers.
Every decision-regret endpoint received its original maximum penalty in all arms.
S did not improve over B1 or B2; training also lost the eight valid B1 abduction
responses. Do not adopt these adapters or run confirmation for this candidate.
This negative result is specific to the tested configuration, not a finding that
all small specialist models or all general-reasoning curricula fail.

## Actual comparison

All three arms used the same pinned E2B backbone, B1 evaluation prompts,96 fresh
development episodes and20 unchanged Augnes packets, greedy decoding and the
same input/output/request ceilings. All116 responses per arm were received; no
assignment was unstarted, interrupted or retried. The raw collector's OK means
strict JSON with a permitted finish, not task validity or correct reasoning.

| Observed quantity | B1: no training | B2: forward reasoning/bookkeeping | S: specialist |
| --- | ---: | ---: | ---: |
| Received / assigned |116/116|116/116|116/116|
| Collector OK / invalid output |99/17|82/34|86/30|
| Synthetic strict JSON /96 |80|63|68|
| Synthetic task-schema valid /96 |8|0|0|
| Augnes strict JSON /20 |19|19|18|
| Augnes frozen structural checks /20 |14|9|12|

No malformed output was repaired. Missing fields, unsupported decision forms,
unquoted arithmetic fractions and invalid probability distributions remain
failures. The retained first-rejection observations describe validator behavior;
they are not a new scorer or a causal diagnosis of training failure.

The following are existing scorer family means; lower is better. Invalid outputs
retain unit penalties, and undefined posterior cases have only their applicable
status/evidence endpoints. Each task assigns24 distinct episodes across eight
development families. The temporal posterior/decision subset contains seven
families; no unsupported denominator of96 is used for these conditional metrics.

| Endpoint | Applicable cases / families | B1 | B2 | S |
| --- | ---: | ---: | ---: | ---: |
| Inference decision regret |17/8|1.000000|1.000000|1.000000|
| Static revision decision regret |24/8|1.000000|1.000000|1.000000|
| Temporal revision decision regret |19/7|1.000000|1.000000|1.000000|
| Inference posterior MAE |17/8|1.000000|1.000000|1.000000|
| Abduction posterior MAE |17/8|0.661346|1.000000|1.000000|
| Static revision posterior MAE |24/8|1.000000|1.000000|1.000000|
| Temporal revision posterior MAE |19/7|1.000000|1.000000|1.000000|
| Abduction status error |24/8|0.666667|1.000000|1.000000|

All eight valid B1 responses were abduction responses. S-minus-B1 abduction
posterior MAE is+0.338654 at the family-mean level, a worse descriptive result;
S-minus-B2 is0. Other task status errors are1 in all arms. The raw report retains
all cases, task/family means, forward-prediction and hypothesis-set errors, and
the separate temporal posterior endpoints. There is no confidence interval or
multi-seed claim. Final snapshots alone do not measure trajectory invariance or
update/correction direction.

## Actual learning and resource evidence

Both arms completed the prospectively fixed320 updates with21,754 supervised and
343,722 padded tokens. Unpadded effective sequence tokens differed:343,722 for B2
and310,766 for S. Each used64 train-only episodes,256 reasoning rows and64 shared
format rows, the fixed seed17 order, last-query rank4 FP32 adapter, SGD0.01 and
gradient clipping1. There were no Augnes training examples or post-result tuning.
B2's different instruction/target distribution remains a limitation: this narrow
forward-probability control does not represent all general reasoning.

| Verified observation | B2 | S |
| --- | ---: | ---: |
| Updates / trainable parameters |320 /22,528|320 /22,528|
| Recorded training routine seconds |54.774139|57.064510|
| Maximum adapter-on/off probe logit difference |3.750000|2.687500|
| Disabled versus untouched-base difference |0|0|
| Same-instance save/reload difference |0|0|
| Peak allocated training bytes |15,426,802,688|15,432,886,272|
| Peak reserved training bytes |21,716,008,960|21,716,008,960|
| Exported safetensors bytes |90,256|90,256|
| Training / evaluation host process IDs |386 /410|429 /453|

Every raw finished-step record agrees with the qualified row identity, loss,
gradient norm and supervision quota. Both A and B matrices changed with finite
gradients. Export hashes are B2
`c8102c5d37727fa11a51e43a2c004ba8e2617ef52e84e33caa6bec1c9126b620`
and S`de42439452bc7f065e2d2aed031814a78a5e3d932fc60334f6606562a0505fcb`.
The binaries are retained as[B2-adapter.safetensors](evidence/matched-paid-run-41242457133/B2-adapter.safetensors)
and[S-adapter.safetensors](evidence/matched-paid-run-41242457133/S-adapter.safetensors).
Each fresh evaluation worker loaded the original base and reproduced the trained
full FP32 last-logit SHA256, with zero evaluation-time updates. All five worker
processes exited and passed the existing idle-GPU check before the next job.
Different-row losses are not a learning curve.

Actual inference peak allocated bytes were9,442,055,680 /9,442,145,280 /
9,442,145,792 for B1/B2/S. Their summed generation times were356.579 /331.577 /
351.603 seconds for8,503 /7,363 /7,882 tokens. Fixed arm order and different output
lengths prevent a controlled speed-superiority claim. These are A40 observations,
not measurements on the owner's4070SUPER12GB. Both training peaks exceed12GB;
the actual deployment artifact, long-input/concurrent headroom and quantization
quality remain unqualified.

## Source-grounded Augnes review

All60 case responses were covered by the retained unblinded, criterion-level
[manual review](evidence/matched-paid-run-41242457133/manual-screening-review.json).
All20 new B1 raw texts and token sequences exactly match the previously retained
two-run E2B screening; its existing notes were reused only after that equality
check. They are not20 new independent quality observations. Of116 matched S
responses,14 exactly match B1 and54 exactly match B2; among20 Augnes cases those
counts are5 and8 respectively.

S recognizes in1448 that saturation must not prevent issuer revocation, whereas
B2 calls the refusal correct. This is a local content improvement, but S still
lacks a bounded remedy and non-revival/provenance/boundary controls. Other cases
show substantial remaining failures:1408 reverses the persistence-failure versus
follow-up gap's causal order;1274 uses a controlled omitted-signal failure to
describe an unobserved actual invocation;1316 blames resume/historical routes that
the facts say work;1329 unnecessarily stops an authorized correction;1278 is
malformed and mixes a relevant differential probe with an unsupported regression
claim and an out-of-scope disconfirming check. Many SOURCE/DISPOSABLE labels or
empty checks have no observable falsifier. All arms correctly propose the bounded
documentation task in1350, so that case is not a training gain.

The earlier independent E4B screening reached20 strict JSON/20 structural outputs
but also failed to establish useful diagnostic or workflow benefit; see
[PR49](https://github.com/hynk-studio/backtrace/pull/49). Structural counts and
retrospective acceptable decision labels are not semantic accuracy. None of the
suggested checks was executed, and no human-time saving or counterfactual task
resolution is claimed. The20 authored packets span17 author-defined families,
not a prospective blinded service experiment.

## Provenance, cleanup and cost

The immutable executed source is`49191f580d35984a52e53f0df3c80d52350aead7`, local
equivalent`54a9fa4c937beff969124af73d63683e50faecd1`, tree
`1846b130f1f0c37842f8f4188cb7662c1825cfc9`. Free qualification41241191354 passed744
native tests,17 container controls, input qualification and full checkpoint
readback at this source. Actual execution passed all four CUDA comparison cases
and16 hardware/isolation checks, with CPU fallback forbidden. The full runtime
and model-assets transfers/readbacks passed in22.814 and49.245 seconds.

The source-bound permit was single use. One A40 Pod`lo5msifkddry2s` inEU-SE-1 was
requested at21:17:35.975 UTC. Done was recorded at21:48:44.935. The owner sent
DELETE at21:48:49.030; owner and watcher each retained two absence observations,
completed at21:51:50.894 and21:51:37.511 respectively. The later complete inventory
at21:52:02 contains zero Pods; hourly spend is zero and autopay remains off.

Observed credit changed fromUSD1.7174565922 toUSD1.4047911923, an observed allocation
cost ofUSD0.3126653999 and cumulative continuation cost ofUSD1.5012529416. Billing
can lag; these are observed balance differences, not a settled invoice. The run
stayed inside the prospectiveUSD0.90 allocation/USD2.30 continuation envelope.
No top-up, overlapping allocation, automatic retry, main-branch merge or Augnes
write occurred.

Both downloaded ZIP digests, all432 raw members,372 nested source bindings over
98 paths, all348 wire/ledger/collection/input identities and eight immutable
state Git blobs were independently checked. Raw files, adapters and clearly
labeled derived reports are retained in
[matched-paid-run-41242457133](evidence/matched-paid-run-41242457133).

| Original artifact | ID | SHA256 |
| --- | --- | --- |
| Owner |13059491588|`1a19e536fe85138959a65566520e9387176a6f522b743e1dd48bf52da504ceae`|
| Watcher |13059371993|`c8d7e7cf1d710b3d1a86c0d67617d49b5cb436d6d59c289fd22990864794971e`|

The artifact display names contain the workflow's historical CPU wording. Actual
GPU identity, kernel, training and generation receipts establish the executed
mode; artifact names alone are not hardware evidence.

## Decision and remaining external blocker

This candidate is complete and negative. Retain the result and do not deploy the
adapters, tune against these outputs, or spend on multi-seed confirmation of an
unsupported gain. Reserved-family labels remain untouched. A different training
design would be a new exploratory candidate with its own prospective bounds;
these results neither identify the failure's unique cause nor justify an
unbounded search for a positive answer.

The wider goal, demonstrating added value in actual Augnes work at a fixed
additional-cost budget against the existing flow and another main-model review,
remains incomplete. A fresh post-execution read again returned
UNAVAILABLE/mcp_network_error/Connection failed for all three connected Augnes
routes. The available integrations provide no service-restart/connection-repair
operation; the earlier plugin search found no alternative. Local MCP service or
tunnel restoration is external to this session. Once a working connection is
available, establish the current runtime/model and fresh shadow-case protocol;
do not substitute old defaults or authored assistant answers for that comparator.
No model API key was created and no live service mutation was attempted.
