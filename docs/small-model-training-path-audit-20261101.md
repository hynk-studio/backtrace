# E2B training-path audit — 2026-11-01

Step 1 is complete. The executed candidate's tokenization, assistant boundary,
terminal token and causal label alignment reproduced correctly. No defect in
those parts was found that explains the failed generations. Its incomplete
answer supervision is a measured design limitation, not a proven root cause.
A separate full-completion encoder is implemented and verified for the next
trainability diagnostic. The paid worker and the original result are unchanged.

## Evidence

- Base result: `5de0a29b5e9e9583878a035b678f9760b3278c22` / Draft #50.
- Original executed source: `49191f580d35984a52e53f0df3c80d52350aead7`.
- Audited implementation: `71264147bf6fbdd8a89a1bbe0b58030a3442e8f1`.
- [CPU run 41273756723](https://github.com/hynk-studio/backtrace/actions/runs/41273756723)
  passed on attempt 1; job `124751633754`. All 54 focused tests also passed locally.
- [Machine-readable audit](evidence/training-path-audit-run-41273756723/training-path-audit.json),
  [job log](evidence/training-path-audit-run-41273756723/job-124751633754.log), and
  [provenance](evidence/training-path-audit-run-41273756723/provenance.json).

The report was extracted from the complete fetched job log by removing timestamp
prefixes. The original three-file Actions artifact is `13069464536`; its ZIP hash
in provenance is reported by GitHub, not independently verified from downloaded
ZIP bytes. The retained log/report have their own locally verified hashes.

The run downloaded only seven hash-pinned E2B tokenizer/metadata files and the
existing pinned CPU dependencies. It used Transformers 5.20.2, tokenizers 0.23.3,
and torch 2.13.0+cpu. It did not download pretrained weights, allocate a GPU,
perform training updates, generate reserved-family labels, or change Augnes.

## What passed

| Check | Observed result | Limit |
| --- | --- | --- |
| Training targets | All 640 targets match their declared training objectives; 128 are shared formatting targets | Exact-teacher self-consistency plus analytic witness tests, not an independent proof of every generated label |
| Original materialization | Both complete specification SHA-256 values and all 640 prompt/answer sequence identities reproduce | Historical training inputs, not generalization |
| Chat boundary | Full assistant-chat tokenization equals the historical prompt plus separately encoded answer on all 640 rows | Applies to these pinned templates and rows |
| Generation prefix | Every training prefix equals the worker's generation prefix | No train/generate prefix mismatch observed |
| Terminal | The full template ends the answer with token 106 in every row; it is in the pinned generation stop set | The historical literal 106 was correct here |
| Causal loss | Actual tiny random Gemma model loss and independently shifted cross entropy both equal 4.877192497253418 | CPU implementation check, not pretrained/GPU learning evidence |
| First/last targets and padding | First answer and terminal each contribute once; prompt/padding are ignored; padded and unpadded losses agree | No double shift or off-by-one loss alignment observed |
| Prospective full target | All answer tokens and the template terminal are supervised; overflow is rejected without truncation | Prepared input function, not a trained model |

The numerical test uses prediction positions 2, 3 and 4 for target IDs 5, 6 and
106. Labels are intentionally **unshifted** in the input: the pinned causal loss
performs the shift internally. Pre-shifting labels would introduce an error.

## Measured omission in the old design

| Quantity | B2 | Specialist S |
| --- | ---: | ---: |
| Training rows | 320 | 320 |
| Complete answer tokens, including terminal | 23,257 | 24,093 |
| Originally supervised tokens | 21,754 | 21,754 |
| Omitted answer tokens | 1,503 (6.463%) | 2,339 (9.708%) |
| Rows with any omitted token | 78 | 110 |
| Rows omitting the first answer token | 19 | 20 |
| Tokens supervised by the new full-completion encoder | 23,257 | 24,093 |

These omissions were the deliberate per-pair loss-token matching rule, not data
corruption or an unnoticed tokenizer failure. The old terminal was always
supervised. Changing to complete answers removes this confound prospectively;
it does not establish that the omissions caused the zero-valid-output result.
Complete supervision means the two original curricula no longer have exactly
equal loss-bearing token totals. Future comparisons must report actual budgets
and match through sampling/length strata or declared tolerances, rather than
silently dropping answer tokens or claiming the old exact match still holds.

## What remains unresolved

The candidate had only 22,528 trainable parameters on the final query projection,
one pass over 320 rows, SGD at 0.01, and no fixed-example before/after generation
test. Finite gradients, changed adapters and exact reload establish execution,
not the ability to learn this task. First/last logged losses concern different
rows and are not a learning curve.

B2's targets correctly follow its *different* unconditional/STOP objective. It
therefore cannot serve as a representative general-reasoning control for the
conditional inference/inspection evaluation. Do not relabel those targets as
incorrect for their own prompts, or treat beating B2 as specialist advantage.
A future comparison needs a suitable general-reasoning control.

The original 8/96, 0/96, 0/96 schema-valid counts and all raw failures stand.
No output repair, retrospective success reclassification, broader capacity
verdict, deployment claim or new balance/resource observation follows here.

## Next bounded decision

Use the full-completion encoder in a prospective 8–16-example train-only
diagnostic. Freeze the examples and update budget before running, evaluate the
same examples' complete-target loss and free-generated responses before and
after training, and report schema validity and target correctness separately.
Fixed training-example success is a trainability control, not a held-out gain.
Use the existing capped lifecycle and independent cleanup; do not rebuild the
provider/agent framework. Keep any next measured correction bounded and based
on the diagnostic result.

The live Augnes connection failure blocks current-service value comparison. It
does not block this offline audit or the next training diagnosis. This PR does
not start that paid diagnostic or reuse any consumed permit.
