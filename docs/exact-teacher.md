# Exact finite-world CPU teacher

This implements the small teacher proposed in [the experiment plan](experiment-plan.md).
It generates structured reasoning questions and exact reference answers without
calling a model, using a competition task, or starting training. It is a local
synthetic competence instrument. Software-engineering transfer remains untested.

## Reference distribution and question contract

`tools/exact_teacher.py` defines finite Boolean Bayesian DAGs with explicit
rational conditional probability tables (CPTs). Every question contains the
declared model, observations already obtained, hypothesis propositions, logical
queries, action utilities, and available inspection costs. The teacher enumerates
all assignments and computes

`P(world) = product_i P(node_i | parents_i)`

using Python `Fraction`. Conditioning, predictions, utility and inspection values
use that same joint distribution. Probabilities are emitted as reduced rational
strings; no floating-point tolerance changes a tie or a logical status.

The student task is to return: posterior hypothesis probabilities; which supplied
propositions are entailed, refuted or still unknown; predictions for unobserved
variables; predictions conditional on each hypothesis; expected action values;
the value of each available inspection; and whether to inspect or stop. Hypotheses
and utility conditions use disjunctive normal form: a list of conjunctions, where
`[]` is false and `[{}]` is true. Names are arbitrary identifiers, not answer hints.

The public solver API is `solve(question)`. The returned object is an evaluator
label and must not be added to the agent question. The function validates a
maximum of eight variables (256 assignments), 32 evidence records, 16 hypotheses,
16 queries, 16 actions and eight inspection options. Invalid input or a resource
bound violation raises an exception; it is not converted into an impossibility
label. There is no probabilistic solver or timeout-based answer approximation.

### What the answers mean

| Output | Meaning |
| --- | --- |
| `prior_hypotheses`, `posterior` | Marginal probabilities of the supplied propositions before and after evidence. Propositions may overlap; simultaneous causes are not forced into one normalized class. |
| `predictions` | Posterior-predictive probabilities `P(X | evidence)` for unobserved variables. |
| `hypothesis_predictions` | Forward predictions `P(X | hypothesis, evidence)`. A zero-probability hypothesis has status `ZERO_PROBABILITY_CONDITION` and null predictions. |
| `ENTAILED` / `REFUTED` / `UNKNOWN` | Respectively true in every / no / some positive-probability assignment consistent with the evidence. These are consequences of this declared finite model, not universal logical theorems. |
| `INCONSISTENT_EVIDENCE` | The same event is asserted both true and false. No posterior or decision is fabricated. |
| `MODEL_MISMATCH` | Consistent Boolean observations have zero joint probability under the declared model. This is a reason to reconsider the model; it does not identify or prove a particular missing cause. |
| `leader_overturned` | None of the initially highest-probability supplied hypotheses remains a posterior leader. It measures justified belief revision, not knowledge of a sampled true cause. |

No actual world is sampled. The agent sees the declared *possible-world model*,
including CPT parameters needed to derive the answer, but no realized hidden
cause, future observation, reference probability or decision label.

## Evidence identity and dependence

An evidence ID identifies one observation record; an event names one modeled
random variable. Repeating the same ID, or copying the same event/value under
another ID, does not multiply its likelihood. Conflicting reuse of a record ID
for different observations is rejected as malformed input. Different records
that assert opposite values for the same event produce `INCONSISTENT_EVIDENCE`.

Distinct events can still be dependent. Conditioning the complete joint
distribution retains shared causes, shared sensor noise and deterministic
copies. A genuinely independent new measurement must have its own modeled
random variable and the appropriate conditional distribution. Changing an
observation ID alone does not create a new measurement.

The analytic tests include a balanced hypothesis and a sensor with sensitivity
`3/4` and false-positive probability `1/4`. One positive reading gives posterior
`3/4`; duplicate records or a deterministic copy leave it at `3/4`. A second
conditionally independent positive sensor reading gives `9/10`. Another test
uses two independent causes and an OR alarm: after the alarm, the three possible
cause combinations each have mass `1/3`, both individual cause marginals are
`2/3`, and simultaneous causes retain probability `1/3`.

## Action and inspection values

For the current evidence, the best action value is

`max_action E[utility(action, world) | evidence]`.

For inspection `T`, gross inspection value is

`sum_outcome P(outcome | evidence) * max_action E[utility | evidence, outcome] - current_best_value`.

Net value subtracts the inspection's declared cost in the same utility units.
All optimal actions and all tied positive-net inspections are retained. The
teacher recommends stopping when no inspection has positive net value; stopping
wins exact zero-net ties. Re-reading a known event has zero gross value.

This is a **one-inspection horizon followed by one action**, not a proof that an
adaptive multi-inspection policy should stop. It does not optimize entropy,
pretend that information alone is useful, or compare utilities from different
questions without a shared scale.

For the balanced `3/4` sensor and correct/incorrect rewards `1/0`, the current
best value is `1/2`, the value after seeing the sensor is `3/4`, gross value is
`1/4`, and cost `1/10` gives net `3/20`. A separate decision rule acts only above
posterior `9/10`: both possible sensor outcomes leave the same action optimal,
so the sensor is informative but its gross decision value is exactly zero.

Generated questions make direct inspection of the target cause more expensive
than indirect sensors. Some optimal choices therefore inspect a downstream
variable, some stop because remaining observations are redundant, some stop
because the information cannot change the best action, and some stop because
cost exceeds a positive gross value.

## Structural split and generation

The partition is fixed before any model evaluation. Parameter variants, evidence
copies and decision-cost variants of one family stay in the same partition.

| Partition | Authored family | Dependency structure |
| --- | --- | --- |
| Train | `binary_sensor` | One cause and one noisy sensor. |
| Train | `shared_noise` | Two root variables feed two readings with shared noise; the readings are conditionally dependent given the target cause. |
| Train | `simultaneous_causes` | Two independent potential causes feed a shared observation. |
| Eval | `mediated_chain` | Cause, mediator and downstream reading. |
| Eval | `redundant_routes` | One cause branches into two routes that meet at another observation. |
| Eval | `interacting_causes` | Two potential causes meet at a mediator, followed by a downstream reading. |

The audit removes a declared edge if flipping that parent never changes a CPT
entry, then canonicalizes the directed graph over all variable relabelings.
Every generated question must match its family's expected signature. Train and
eval must have disjoint signatures and disjoint question identities. An unused
declared parent cannot fake a different structure, and an arbitrary family name
cannot excuse a graph mismatch.

This establishes separation of these **CPT-dependent graph families**, not full
semantic independence. Both partitions share Boolean primitives, question schema
and utility concepts; deterministic support can make some graph distinctions
observationally equivalent. In particular, the audit does not discover a minimum
graph under every zero-probability configuration, certify unknown future data,
or prove that success on three held-out motifs generalizes to real code.

The default eight variants per family cover ordinary posterior revision,
duplicate observations, contradictory evidence, coherent model mismatch,
expensive inspection, informative but decision-irrelevant inspection, consistent
deterministic entailment, and ties. The entailment variant infers the *unobserved*
target from a relational observation. At most 128 variants per family can be
generated (768 questions total); the maximum is tested for unique identities.
This cap is a CPU-bound convenience, not a justified training-set size.

## Reproduce and audit locally

From the repository root, choose a new destination under `.local`:

```sh
python3 -m unittest discover -s tests -p 'test_exact_teacher.py' -v
python3 -m tools.exact_teacher generate .local/my-exact-teacher --variants-per-family 8
python3 -m tools.exact_teacher audit .local/my-exact-teacher
```

The generator refuses an existing destination and output outside the repository's
`.local` directory. It writes mode-0700 directories and mode-0600 files:

| File | Contents |
| --- | --- |
| `train/agent.jsonl` | Training questions only. |
| `train/evaluator.jsonl` | Corresponding exact training targets and family metadata. |
| `eval/agent.jsonl` | Evaluation questions only. |
| `eval/evaluator.jsonl` | Evaluation references; exclude from model-visible input. |
| `manifest.json` | Generator source SHA-256, parameters, file hashes/lengths/counts and structural/coverage audit. |

`audit` checks file identities, recomputes each mathematical answer, checks exact
question/answer alignment, rechecks the structural split, and regenerates the
entire dataset under the recorded parameters to verify the exact row content.
The output has no timestamps or path-dependent content, so two runs of the same
source and parameters produce identical files. A source change invalidates the
old source-bound manifest rather than silently requalifying it.

File separation is an input-contract check, not an OS sandbox. A future training
loader may pair only training questions and targets; an evaluation loader must
expose only evaluation question records to the student. Mounting the containing
directory would expose the evaluator files and is not allowed by this contract.

## Observed CPU result, 2026-10-24

The focused suite passed **26 tests** in 3.902 seconds. Independent analytic
fixtures cover Bayes updates, observation dependence, new independent sensor
draws, simultaneous causes, forward predictions, undefined conditioning,
contradiction/model mismatch, exact inspection value, cost and ties. Dataset
tests cover deterministic bytes, permissions, no overwrite, agent/reference
separation, incorrect labels, incorrect family assignment and full maximum-size
generation. The dataset was generated and then audited successfully at
`.local/exact-teacher-release-20261024` with eight variants per family.

The independent Linux CPU run
[40072228708](https://github.com/hynk-studio/backtrace/actions/runs/40072228708)
passed all 419 repository tests and reproduced the same 48-question dataset.
Its [verification receipt](research-preparation-cpu-20261024.json) retains the
complete teacher manifest; all four generated JSONL hashes match the local audit.

Generator SHA-256:
`3a684f81eb21febff45d884febeac88208ce6a312147d1ed50d52391404f7314`.

| Measure | Train | Eval |
| --- | ---: | ---: |
| Questions / structurally distinct families | 24 / 3 | 24 / 3 |
| Valid posterior/decision questions | 18 | 18 |
| Contradictory-evidence questions | 3 | 3 |
| Coherent model-mismatch questions | 3 | 3 |
| Inspect / stop among valid questions | 7 / 11 | 9 / 9 |
| Duplicate-evidence questions | 3 | 3 |
| Prior leader overturned | 7 | 7 |
| Entailed / refuted / unknown query labels | 7 / 7 / 46 | 4 / 4 / 40 |
| Questions with informative zero-value inspection | 4 | 6 |

Some coverage categories overlap. Counts are exact teacher outputs, not student
accuracy. No model has answered these questions, no adapter has been trained,
and no transfer or calibration claim has been measured. The generated JSONL
files remain local and are not committed; their generator and tests are the
reproducible deliverable.
