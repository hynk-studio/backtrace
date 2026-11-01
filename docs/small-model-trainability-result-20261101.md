# E2B trainability result: format learning, no reasoning fit

Full-target repeated SFT learned all eight supplied-answer formatting examples,
but neither adapter produced a valid answer to any of the eight reasoning
examples. The one-query and four-query variants both score 8/16 overall, entirely
from formatting. The experiment completed; the strict 16/16 train-fit gate failed.
This establishes a working learning/export/generation path for formatting and
does not establish reasoning competence, held-out generalization or Augnes value.

The immutable executed source is `ebe6fa37b44ad465c16fa36cd2823f55cf93a050`.
[Qualification 41283861825](https://github.com/hynk-studio/backtrace/actions/runs/41283861825)
passed all four jobs, 761 native tests, pinned-tokenizer checks and both random-model
CPU numerical controls. [Actual run 41284716992](https://github.com/hynk-studio/backtrace/actions/runs/41284716992)
completed successfully on one A40. [Draft #52](https://github.com/hynk-studio/backtrace/pull/52)
is stacked on the completed training-path audit in #51 and remains unmerged.

## Fixed experiment and actual outcomes

The [prospective protocol](small-model-trainability-20261101.md) selected two
status-OK training examples per reasoning task and paired each with a formatting
exercise containing the same target values. All 16 examples are train-only.
BASE, Q1 and Q4 received the same generation prompts. Each trained arm performed
640 SGD updates: 40 identical passes, seed 17, learning rate 0.01, clipping norm 1,
rank 4, full answer/EOS supervision, frozen base and no prompt/padding labels.
Each arm used 457,360 effective training tokens and 61,120 supervised tokens.
No held-out label or Augnes training example was used.

| Measurement | BASE | Q1: final query | Q4: final four queries |
| --- | ---: | ---: | ---: |
| Original assigned / collected responses | 16 / 16 | 16 / 16 | 16 / 16 |
| Strict JSON | 14/16 | 14/16 | 14/16 |
| Task schema valid | 0/16 | 8/16 | 8/16 |
| Exact target JSON match | 0/16 | 8/16 | 8/16 |
| Format task correct | 0/8 | 8/8 | 8/8 |
| Reasoning task correct | 0/8 | 0/8 | 0/8 |
| Strict fit: all 16 correct | No | No | No |

All 48 responses terminated normally; invalid JSON/schema responses remain in
the denominator without repair or retry. The protocol's original numeric
tolerance is retained. There are no schema-valid reasoning responses to support
a posterior-accuracy or decision-quality claim. Q1 and Q4 generate identical
token sequences on 15/16 examples; their one differing response still fails.

## What changed during training

| Fixed-target measurement | Before both | After Q1 | After Q4 |
| --- | ---: | ---: | ---: |
| All target-token mean NLL | 1.105007 | 0.741384 | 0.725599 |
| Reasoning target-token mean NLL | 2.070503 | 1.442265 | 1.413971 |
| Format target-token mean NLL | 0.139511 | 0.040504 | 0.037227 |
| Mean first-answer-token NLL | 0.000541 | 0.000504 | 0.000602 |

These are repeated measurements on identical examples, not losses on different
training batches. Both arms begin with identical fixed losses and untrained probe
logits. Their first-answer-token argmax agrees with fresh-worker free generation
in all 16 examples per arm. This does not expose a first-token boundary failure.

The baseline usually echoes the formatting input's `fields` wrapper. Both trained
arms instead produce the exact requested object and preserve every supplied value.
On reasoning prompts, six outputs per trained arm parse as JSON but fail task
schema validation; both abduction outputs fail JSON syntax. Observed errors
include missing decision `mode`, missing or incomplete posterior/evidence fields,
unquoted fractions and unevaluated arithmetic or literal template ellipses.
Raw errors are retained in [verification.json](evidence/trainability-paid-run-41284716992/verification.json).
No post-processing was used to turn these responses into successes.

Thus target loss decreases on reasoning examples without correct free-generated
reasoning answers. Query-only adaptation at either tested size is insufficient
for this fixed train-fit gate. This does not establish a unique cause, disprove
larger/different adapters, or causally attribute the historical failure to its
answer mask: dataset repetition, targets and initialization also differ from
that earlier experiment.

## Update, export and independent reload verification

| Verified measurement | Q1 | Q4 |
| --- | ---: | ---: |
| Updates | 640 | 640 |
| Trainable parameters | 22,528 | 65,536 |
| Training-routine seconds | 176.243 | 206.671 |
| Adapter bytes | 90,256 | 262,704 |
| Adapter on/off maximum probe-logit difference | 3.9921875 | 4.0546875 |
| Disabled-base / save-reload maximum difference | 0 / 0 | 0 / 0 |
| Peak allocated training bytes | 14,713,444,352 | 15,271,324,160 |
| Training / evaluation host PID | 385 / 409 | 428 / 452 |
| Evaluation-worker new updates | 0 | 0 |

Q1 adapts layer 34; Q4 adapts layers 31–34. Their differing projection dimensions
mean Q4 has 65,536 parameters, not four times Q1's count. Every A/B tensor changed;
all 1,280 logged step IDs, losses and finite gradient norms match their receipts.
Both trained probes reproduce exactly after save/reload and again in distinct
fresh evaluation workers. All five model workers exited and passed idle-GPU checks.
The 16 hardware/isolation checks and four CUDA comparison cases also passed.

Original adapter binaries are retained:

- [Q1-adapter.safetensors](evidence/trainability-paid-run-41284716992/Q1-adapter.safetensors), SHA256 `b2d35da5a4ea6935a88165c39fb6e9b867236a4526f3bea4813fbbfcfba9a29f`.
- [Q4-adapter.safetensors](evidence/trainability-paid-run-41284716992/Q4-adapter.safetensors), SHA256 `001668682d4248647cbada088e58e3c015f3bdbd5d5879922fb2de5406af0c0a`.

## Cleanup, cost and retained evidence

One A40 Pod `vlrpdwnk9gwyrl` in EU-SE-1 was requested at 07:31:22.612 UTC.
Execution completion was recorded at 07:52:40.745; the owner sent DELETE at
07:52:44.213. The independent watcher completed two absence observations at
07:54:38.320 and the owner completed its two observations at 07:55:45.692.
The complete 07:55:55 inventory contains zero Pods; hourly spend is zero and
autopay remains off. Both deletion records bind the same source, claim and Pod.

Observed credit changed from USD 1.4047911923 to USD 1.1925423895: a debit of
USD 0.2122488028 and cumulative continuation debit of USD 1.7135017444. Billing
can lag; these are observed balance differences, not a settled invoice. The run
stayed inside USD 0.75 / 4,200 seconds and the USD 2.30 continuation ceiling.
The single-use permit is consumed. No second allocation, top-up, main merge,
deployment or Augnes write occurred.

Both log-embedded archives and all 132 original actual-run members were verified
by SHA256. All 48 wire/ledger/collection/input chains, 11 state Git blobs, and
378 source-binding occurrences over 101 distinct paths were checked. The 56
original qualification members and their four job logs were also verified.
GitHub artifact digests are retained as metadata; they are not presented as
independently downloaded ZIP digests. Raw logs, invalid outputs, state records,
adapters and labeled derived analysis are retained in
[actual evidence](evidence/trainability-paid-run-41284716992),
[qualification evidence](evidence/trainability-qualified-run-41283861825) and
[fresh account evidence](evidence/trainability-account-run-41284622433).
The separate read-only refresh initially had a YAML parse error; its corrected
run succeeded without provider mutation. This did not consume a paid attempt.

Reproduce scoring and the evidence checks from this PR's unchanged execution code:

```sh
python -m tools.small_model_trainability evaluate docs/evidence/trainability-paid-run-41284716992/owner/minimum-owner/remote
PYTHONPATH=. python docs/evidence/trainability-paid-run-41284716992/verify.py
```

## Next decision

Do not promote either adapter or proceed to a generalization/service-benefit
claim. The next useful gate is reasoning-only train fit: start with one fixed
training example, require a complete correct free-generated answer, then widen
the train set before reserving a fresh generalization evaluation. Supplied-answer
formatting success must not satisfy that gate. Another paid experiment would be
a separate prospective design within the remaining budget; none was launched.
The previously recorded live Augnes connection problem remains a separate blocker
to service comparison, not an explanation for this offline reasoning failure.
