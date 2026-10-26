# Small-model evaluation: first CPU implementation

Scope: A1 in the [research plan](small-abductive-model-plan-20261026.md).
This implements candidate data, exact references, file projections and descriptive
scoring. **No model has been evaluated or trained.** The new
[protocol](abductive-evaluation-protocol-v1.json) cannot grant a capability pass.
Development baselines, sample-size/power analysis and final confirmatory sealing
remain pending. Historical teacher, coding protocols and paid sources are unchanged.

## Implemented tasks and limits

| Task | Implemented contract | Remaining limitation |
| --- | --- | --- |
| `inference` | Supplied finite DAG, overlapping hypotheses, evidence, payoffs and one-step inspection costs. Exact posterior error and the model's actual decision policy. | Numerical inference under a declared model, not recovery of an unknown causal structure. |
| `abduction` | Construct complete Boolean assignments to up to three named root causes, with probabilities and forward predictions. No candidate assignment list is supplied. | Bounded hypothesis language with the forward model supplied; no discovery of new cause variables, free-form explanations or missing edges. |
| `revision` | Three time-cutoff snapshots: initial observation, duplicate, then explicit retraction/correction. Score posterior, active evidence IDs, duplicate invariance and revision direction. | Fixed-world evidence availability/correction only; no natural-language transfer, changing world states or long-horizon policy yet. |

Ambiguous assignments are retained, including simultaneous causes. No sampled
latent cause becomes the unique answer. Assignment/dictionary order does not
affect matching. Complete root assignments are exclusive and sum to one;
supplied inference hypotheses can overlap and need not sum to one. Probabilities
are model-relative, not calibrated confidence about Augnes.

The exact enumerator is reused without altering its source or old fixtures.
New generator/scorer use standard-library Python with no network/provider/model
calls. Dataset directories/files have 0700/0600 permissions and require new local
output paths. Generated datasets and labels are not committed.

## Candidate dataset and separation

Enumerate five-node DAGs with indegree at most two, at most three roots and every
node ancestral to the final observation. Canonicalize effective unlabeled graphs;
select 40 of 49 distinct graphs by hash order before observing labels. All edges
affect their CPTs. No old teacher family is reused.

| Partition | Graph families | Episodes at 20 variants | Input records |
| --- | ---: | ---: | ---: |
| Training | 12 | 240 | 1,200 |
| Development | 8 | 160 | 800 |
| Reserved candidate test | 20 | 400 | 2,000 |
| Total | 40 | 800 | 4,000 |

An episode contributes one inference question, one abduction question and three
revision snapshots. **4,000 records are not 4,000 independent problems.** Variants,
task views and snapshots of one graph stay together. Shared probability primitives
and schema mean topology separation does not prove semantic independence or transfer.

Coverage includes duplicate/correlated evidence, contradictions, zero-support
model mismatch, multiple causes, costly checks and decision-irrelevant checks.
Deterministic parity can make an observation impossible without contradictory
records; this remains MODEL_MISMATCH with no fabricated posterior.

Agent JSONL contains only `id` and `input`; family/episode metadata and references
remain in evaluator JSONL. Auditing checks strict schemas, identities, effective
graph assignment, cross-split episodes, reference recomputation, source/file hashes
and deterministic regeneration. Rehashing altered data cannot bypass regeneration.
Strict JSON rejects duplicate keys and nonfinite constants.

Training export accepts only training, reads only its two data files and regenerates
targets before emitting user/assistant messages. Input export reads no evaluator
files. Prohibited-file read traps test both boundaries. A future model runner must
feed input/message content only; IDs and manifest metadata are transport information.
This file separation is **not an OS sandbox**. Give the eventual trainer/inference
process only the exported view, never the complete dataset directory.

## Response and scoring contract

Inference responses contain `status`, `posterior` and `decision`. Status is OK,
INCONSISTENT_EVIDENCE or MODEL_MISMATCH; non-OK requires null posterior/decision.
A decision is STOP with an action ID, or INSPECT with an event and an action for
each Boolean outcome. Regret uses these actual actions, subtracts inspection cost,
compares with the exact best stop/check policy, and normalizes by utility range
plus maximum check cost. Zero-range cases have zero valid regret. Impossible
branches have zero weight; exact zero-net ties select STOP in training targets.

Abduction responses contain status and explanations, each with assignment,
probability and requested event predictions. Duplicate semantic assignments,
unknown fields/events, excess guesses or unnormalized distributions are invalid.
Score support precision/recall, MAE over all root assignments and conditional
prediction MAE. Missing supported assignments get maximal forward error. Report
these separately from E1, rather than combining them into one headline score.

Revision adds `active_evidence_ids`. Retractions must name active prior observations.
Future-available records, unordered availability, impossible timestamps and evidence
in the base question are rejected. Duplication preserves both valid distributions
and correctly undefined states. Revision-direction error supplements numerical
posterior error; it does not replace magnitude accuracy.

Predictions accept finite JSON numbers or bounded rational/decimal strings.
Booleans, nonfinite and out-of-range probabilities are rejected. No clipping,
posterior normalization or JSON repair is performed.

All assigned cases remain. Missing/invalid outputs get loss 1 on applicable
endpoints. Incorrect abstention cannot remove an OK case from the denominator.
Only reference status determines when posterior/regret is undefined; those cases
retain status scoring. Duplicate/foreign prediction IDs reject the result file.

Reports expose case and equal-weight family means separately by task, per-family
values, missing/invalid counts and paired revision measures. Confidence intervals,
training-seed uncertainty, calibration and promotion are not computed. Development
measurements and a locked analysis protocol remain prerequisites for confirmation.

## Reproduce

Choose new output paths for each source version; source edits invalidate manifests.

```sh
python3 -m unittest discover -s tests -p 'test_abductive_benchmark.py' -v
python3 -m tools.abductive_benchmark generate .local/my-abductive-data --variants 20
python3 -m tools.abductive_benchmark audit .local/my-abductive-data
python3 -m tools.abductive_benchmark export-training .local/my-abductive-data .local/my-train-view
python3 -m tools.abductive_benchmark export-inputs .local/my-abductive-data .local/my-dev-view --split development
python3 -m tools.abductive_scoring .local/my-abductive-data .local/my-predictions.jsonl --split development --output .local/my-score.json
```

Prediction JSONL has one `id`/`response` object per answered case. An empty file
is a missing-response control, not a zero-case experiment. Scoring requires
evaluator access and must not run inside the model sandbox.

## Validation record

Initial focused run: 21 tests passed. Full local generation/audit produced the
4,000 records above. Authored all-record oracle controls found an evaluator bug:
duplicated impossible evidence was penalized even when both answers correctly
declared MODEL_MISMATCH. Corrected scoring preserves undefined states; a new
analytic regression passes. Final focused run: **22 tests passed**. First-control
results are retained as evaluator debugging evidence, not student-model failures.

The initial local full run attempted 532 tests with 5 failures, 10 errors and
4 skips. Three errors involve the supplied pip bootstrap fixture; other errors
and startup-observation failures involve procfs/PID namespace mismatch. It is
not a full-suite pass. A separate native Ubuntu workflow runs all tests, complete
data generation/audit, exports and authored oracle/missing-response controls.
The final native Linux run
[40281911634](https://github.com/hynk-studio/backtrace/actions/runs/40281911634)
at source `4063ce3d4b811d27e10218241871ccb55e76ad8d` passed **533 tests with no
failures, errors or skips**, CPU preflight, all 4,000 data records and both export
paths. Authored oracle and missing-response controls passed in all partitions,
including undefined-state duplication. These controls are not student scores.
The [receipt](abductive-evaluation-cpu-20261026.json) retains the initial local
failure and first oracle bug, verifies all seven artifact members and source
hashes, and records final data/export/control hashes. The downloaded artifact
SHA-256 matched GitHub's digest. Subsequent changes are documentation only.

Next scientific work: development model baselines, broader E2/E3 capabilities,
power analysis and final test sealing. A2 training-environment save/reload remains
separate. No paid allocation, training, Augnes mutation, merge or submission is
part of this CPU implementation.
