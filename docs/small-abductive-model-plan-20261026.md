# Small abductive model: evidence before deployment

Decision date: 2026-10-26; revised 2026-10-31 UTC. Status: **actual E2B baseline
and three Augnes development replays completed; synthetic responses all invalid;
replay content mixed. Conditional E4B comparison is next. Training and practical
workflow comparisons remain NOT_RUN**. Refs [BT-001](https://github.com/hynk-studio/backtrace/issues/1).

The [actual result](small-model-e2b-result-20261031.md) records 24 responses from
run 41206950960 after the passive bind/listen correction. All 18 frozen synthetic
responses failed task validation under both B0 and B1. The three retrospective
Augnes cases show some appropriate stop/local-fix directions, but unsupported
hypotheses and output-format failures. Both controllers proved deletion. The
conditional E4B comparator now addresses an observed basic-capability question;
no specialist benefit or production usefulness is established. Historical failed
attempts remain in the [execution record](small-model-e2b-execution-20261031.md).

## Active objective and delegated continuation (2026-10-31 KST)

The owner authorized continued work toward the proposed goal. Produce evidence
that a small diagnostic model improves Augnes's next decision: maintain or revise
an assessment, choose one useful check, proceed, stop or defer. Proceeding without
further diagnosis can be correct. Limit explanations to three candidates with
source-grounded support, conflicts and missing assumptions. Inputs distinguish
current goals, constraints, observations, prior model claims, allowed checks and
costs. Outputs remain review candidates, without automatic execution, Perspective
promotion or product deployment.

[Owner decision #41](https://github.com/hynk-studio/backtrace/issues/41) abandons
Kaggle competition work, submission, packaging and leaderboard optimization.
Historical results and protocols stay intact. Start with the prepared E2B. E4B is
a conditional capacity comparator if the executable E2B path exposes inadequate
basic capability; its 18 deferred assignments are not E2B failures. One E2B result
cannot establish a verdict on all small models.

The new instruction supersedes historical preparation-only approval stops for
the necessary bounded next step. Implement, test and open reviewable PRs without
repeated routine confirmation. The first paid step remains **one CUDA diagnostic,
at most USD 1 and 3,000 allocation-inclusive seconds, USD 0.50 credit reserve**.
Bind a fresh single-use permit to qualified source and refresh balance/price.
No top-up, automatic second allocation or reuse of consumed scopes. A later
experiment needs an affordable scope based on actual measurements; delegation is
not an unlimited budget. Preserve independent cleanup and all failure evidence.
Do not merge the historical Draft stack merely to advance research.

| Step | Bounded deliverable | Decision enabled |
| --- | --- | --- |
| 1 | This plan alignment | Remove obsolete competition and early-replay gates |
| 2 | One existing A/B/C GPU comparison | Identify a failing layer or stop same-route rental |
| 3 | Existing 18 E2B assignments (9 development cases × B0/B1), plus 3–5 time-cutoff Augnes replays | Observe real responses, validity, latency/memory and diagnostic value |
| 4 | Tiny real update/save/reload; then one seed each of B2 and S | Separate implementation feasibility from possible specialist benefit |
| 5 | About 20 independent offline/shadow episodes | Compare decisions and cost against the existing flow and additional main-model review |
| 6 | New untouched families/cases and three training seeds for the selected claim | Confirm only the benefit supported by screening |

Step 3 may go directly to step 5 with useful B1 outputs; training is optional.
Early replay does not wait for synthetic superiority, broader generators, power
analysis or final test sealing. Initial B2/S training ceilings are **1,024 episodes
or 1,000,000 effective training tokens per arm, whichever comes first**, using
existing generators. Screen on about 100 fresh development cases, explicitly
reporting any reused structures. One seed selects candidates only. Match token
budgets, context-length distributions, updates and checkpoint rules. Start with
competing explanations, disconfirmation, duplicate/stale/retracted evidence versus
state change, and justified proceed/stop decisions.

Measure requested capability separately from appropriate diagnostic initiation:
neutral instructions on both diagnosis-needed and no-diagnosis cases suffice;
no autonomous caller is needed. For Augnes value, compare existing flow, one
additional main-model review, untrained small-model suggestions and (if available)
specialist suggestions. Match **additional cost ceilings per episode**; report
latency, tokens, checks and reviewer effort separately. Do not claim all resource
measures are simultaneously matched. Keep future outcomes out of inputs. An
unexecuted check remains a proposal, not a resolved task.

Activation steering is an optional sequential experiment only after repeated
evidence that strong instructions elicit useful capability which neutral
instructions underuse. Try one fixed additive direction, at most two layers ×
three strengths on development data, then freeze one setting. Compare no
intervention and equal-norm random directions on held-out episodes; control answer
tokens, length and difficulty. Stop for style-only changes or needless diagnosis.
No new SAE training, broad neuron search or parallel second project is justified.

### Existing first-response path and remaining blocker

`tools/small_model_minimum_diagnostic.py` binds the existing owner/watcher to
`connected(..., comparison_only=True)` and `DIAGNOSTIC_RECORDED`. Its paid
comparison is recorded; the original wrapper failed on a duplicate exclusive
receipt write. The corrected wrapper preserves the original receipt and adds
a separate summary. Measurement completion still never means hardware success.

Preserve original smoke inputs, prompts, assignment IDs and scorer. Select the
existing E2B 18 assignments prospectively; leave E4B deferred. These nine views
come from one development family/episode, not nine independent episodes. The native CUDA
collector in `tools/small_model_gpu.py` and raw collector in
`tools/small_model_runner.py` are reusable, but the qualified OCI worker rejects
pretrained/CUDA inference. The prepared cases are **not yet an executable provider
baseline**. After diagnosis, make only the necessary collector connection and
qualify real model loading, memory, output collection and cleanup. Random CPU
outputs never count as pretrained evidence.

## Historical CUDA preparation and retained evidence (2026-10-27 KST)

**Infrastructure expansion is paused. The next question is where CUDA fails.**
The [last hardware attempt](small-model-minimum-retry-20261027.md) passed actual
provider readiness, pinned runtime delivery, device inventory and an 8 GiB
resident-memory probe, then failed at CUDA initialization with error 304. Both
controllers confirmed deletion. The added filter remains a hypothesis. There is
no unused paid authorization, and this revision performs no provider allocation.
This is no evidence against specialist learning: the research experiment has
not yet been reached.

Keep the established time/cost cap and independent cleanup, evaluator-only
answers, raw outputs and failures, B1 strong prompting and B2 general-reasoning
training controls, and the distinction between synthetic accuracy and Augnes
usefulness. Change the order and size of implementation, not these standards.
A proposed change must identify the uncertainty it reduces and the decision it
enables. Defer changes that cannot do either. Do not add another agent/provider
controller, evaluator layer, model candidate or benchmark before the baseline.

The current free change extends the existing hardware worker/supervisor and SSH
collector. A/B/C each get a fresh process and the same installed runtime, GPU
UUID, sanitized environment and 30-second ceiling:

| Case | Configuration | Question |
| --- | --- | --- |
| A | Trusted root, ordinary provider OCI, no additional project filter | Does the common provider/runtime CUDA path work? |
| B | UID/GID 65532, cleared groups/capabilities, fixed limits and no-new-privileges, no additional filter | Does the worker privilege/restriction layer change the outcome? |
| C | Same as B with the unchanged project filter before CUDA | Does adding this filter change the outcome? |

The original torch CUDA/BF16/SDPA probe runs first. Each case preserves a pre-CUDA
identity/filter-count/limit checkpoint, raw stdout/stderr and its result, actual
exit status and process-absence observation. Supplemental driver/runtime return
codes, device-open errno and loaded CUDA library paths/hashes follow the primary
probe; these are not independent controls or substitutes for a failed result.
A timeout, lost transport or incomplete record is inconclusive, not a CUDA FAIL.
Successful device enumeration alone is never CUDA success. CPU comparisons are
labeled CPU_CONTROLS_ONLY even if an authored test fixture reports success.

| Complete A/B/C kernel results | Decision |
| --- | --- |
| fail / fail / fail | Investigate the common provider/image/library path; this does not exclude additional worker problems. Stop renting the same path without discriminating evidence. |
| pass / fail / fail | Narrow to worker identity/privileges/limits/device access; it does not identify one restriction. |
| pass / pass / fail | The added filter is implicated. Identify the rejected call before a narrow correction; do not remove the filter or move initialization ahead of it on inference alone. |
| pass / pass / pass | The current path works but the historical failure is not reproduced. Complete the existing actual GPU interruption checks, then proceed toward the baseline. |
| Any other pattern, unequal starting conditions, missing result or unconfirmed teardown | Inconclusive. Stop; preserve all observations and reconsider the execution environment. |

**A future paid diagnostic is one allocation, not a retry loop.** Its proposal
keeps the existing maximum USD 1, 3,000 allocation-inclusive seconds, USD 0.50
reserve, no top-up and no automatic second create; refresh affordability before
requesting approval. Work/export/cleanup remain 2,580/120/300 seconds. The three
cases consume at most 90 worker seconds within that window. If available, a
bounded denied-call trace may follow the first comparison in the same allocation;
record its availability/failure and treat traced runs as supplementary because
tracing changes execution. No tracing tool or capability is silently installed
or enabled on paid hardware. No repeated A/B/C run substitutes for missing logs.
If this one diagnosis does not distinguish a relevant layer, or a layer is
implicated without evidence supporting a correction, stop the same-route rental
and review the environment choice before any further paid proposal. Export errors
must never suppress deletion; unresolved deletion prevents further compute.

The comparison code has no provider-create operation. Existing historical paid
start branches, claims and receipts remain fixed; no new paid scope is created.
Free validation reuses the existing exact-image workflow's container job. The
owner/watcher jobs for historical scopes do not run on this preparation branch.
The unchanged independent deletion controller is reused later, not rebuilt here.
A denied-syscall trace is still NOT COLLECTED. Free checks qualify instrumentation
only; actual GPU A/B/C, GPU interruption and pretrained performance remain NOT RUN.

Local validation of this preparation: 31 of 32 focused tests pass; the actual
privilege-change test fails with EPERM at capability drop. This Work host reports
zero effective/permitted/bounding capabilities, including no CAP_SETPCAP, so it
cannot qualify the ordinary-OCI A/B/C boundary. Do not skip or relabel that failure.
The full local suite ran 671 tests with six failures, ten errors and four skips;
five failures/ten errors/four skips match the preceding local environment paths,
with the new boundary failure reported separately. Preflight and diff checks pass.
Original failed logs and partial results are retained locally. They remain failed
local observations, separate from the native qualification below.

Free exact-image run [40464148007](https://github.com/hynk-studio/backtrace/actions/runs/40464148007)
at source `21f362ca1ca23d29f16351096b9c3e7b14d4847a` passed on its first attempt:
671 native tests in 185.385 seconds with no failures/errors/skips, preflight and
all 17 container controls. The [verified CPU evidence](small-model-cuda-diagnostic-cpu-20261027.json)
retains the original A/B/C streams and observations. A ran as root with one
ambient filter; B ran as UID/GID 65532 with zero capabilities, no-new-privileges
and one filter; C had the same worker restrictions and two filters. Environment,
limits, interpreter and loaded CUDA runtime hash matched. All three correctly
rejected the missing GPU; their decision is CPU_CONTROLS_ONLY. Each process was
confirmed absent, and container cleanup had two absence reads. The artifact ZIP
digest, all 34 members and all 64 source hashes were checked. No runtime correction
or repeat native run was needed. The original filter, model kernel probe,
provider/deadline controller, runtime lock, smoke inputs and scorer are unchanged.
This establishes a functioning comparison instrument, not CUDA success, a fixed
304 error, or a complete newly authorized paid launch.

The comparison-only entry is the existing `connected(..., comparison_only=True)`
(or `exercise(..., comparison_only=True)` after installation). It records A/B/C
without repeating the resident-memory/interruption campaign. The existing paid
owner still uses its historical entry; no paid adapter/authorization is created
in this preparation. Connecting a newly authorized diagnostic must reuse the
existing owner/watcher and export/deletion limits, with this prepared comparison
as its measurement payload, not introduce another lifecycle framework.

After the common execution path works, use the **existing 18 E2B assignments**
(nine development cases, each B0/B1) from the original 36-assignment smoke.
Preserve their input bytes, prompts, scoring and assigned denominators. Report
valid/invalid/missing responses, posterior/decision error, cold loading and
observed latency/VRAM/RAM. With this small sample, latency quantiles are descriptive.
Do not wait for broader E2/E3 construction, power analysis or final test sealing
before measuring this development baseline. These later gates still apply to
confirmatory claims. E4B remains the deferred 18 assignments, not silently dropped
or counted as E2B failures; extend to it after the shared path works.

Then verify a small actual E2B update, changed adapter tensors, save/reload and
adapter-on/off behavior. This demonstrates implementation only. B1/B2/S controlled
comparison and untouched evaluation are required for a learning claim. Soon after
the initial baseline, review three to five development-only Augnes case replays
with evidence cutoffs: plausible explanations, disconfirming predictions, useful
next checks and unsupported claims. Use source-grounded review and retain
ambiguity. This early gap check does not require product integration, does not
publish private cases and does not certify deployment usefulness.

Progress reports have three items: what was learned; what remains unknown; what
decision the next task enables. The assistant manages identifiers and approval
records. Completion means a decision-relevant uncertainty decreased, not that
more preparation files or tests were produced.

The owner clarified that speed is not the objective. The first objective is to
establish whether a small specialist model learns useful abductive inference,
with possible Augnes use considered from the outset. E2B and E4B are candidates;
neither is selected for deployment. A short training run checks implementation,
not this research objective. Negative and inconclusive findings are valid results.

The principal question is: **does specialist training improve evidence-grounded
hypothesis formation, revision and inspection choice on unseen problems, beyond
strong prompting and matched general-reasoning training?** A separate question
is whether that improvement helps an Augnes workflow at acceptable resource cost.
Passing the first does not answer the second.

Kaggle submission is abandoned in the active plan (owner decision #41). The incomplete coding
pilot and its traces remain evidence, but extending that campaign is no longer
the next milestone. Historical protocols, outcomes and consumed compute scopes
are preserved. This plan changes no Augnes runtime or durable state.

## What exists and what is missing

The [exact teacher](exact-teacher.md) currently generates 24 training and 24
evaluation questions across three structural families in each partition. It
enumerates a supplied finite probability model and supplied hypotheses; it
does not discover a causal graph or generate new hypothesis structures. Its
inspection policy has one observation followed by one action. Zero-support
model mismatch is narrower than detecting arbitrary missing causes.

These historical 48 questions are development fixtures. Their exposed labels and
repeatedly inspected families must not become the new confirmatory test. No student
baseline, training run, adapter save/reload or Augnes integration has been measured.
The completed coding pilot does not estimate a training effect.
The [first A1 implementation](abductive-evaluation-20261026.md) now adds a new
candidate dataset, exact scoring and train/input exports. Its E2 task constructs
root assignments under a supplied model; E3 covers fixed-world evidence updates.
The [temporal extension](temporal-baseline-20261026.md) adds a supplied unrolled
state model, delayed old evidence, changing-state posteriors, and paired
JSON/controlled-English development prompts. Broader hypothesis/model
construction and real-world temporal/textual transfer remain open.
The [runtime preparation](small-model-readiness-20261026.md) now pins official
E2B/E4B revisions and a CPU dependency closure, verifies actual token counts and
prepares bounded development inputs. Tiny random CPU layout probes establish
checkpoint mapping only. Pretrained inference, tiny updates and trained-adapter
save/reload are still NOT RUN; the CUDA dependency set is resolved only.
The [isolated CPU collector](small-model-runner-20261026.md) adds bounded raw
output collection, evaluator connection and interrupted-run recovery. Its
authored controls and tiny random model outputs are instrument qualification,
not learned capability or actual pretrained baselines. Native run 40328552441
passed 592 tests and the complete instrument controls, including both random
fixtures and actual process-loss recovery; see the
[source-bound receipt](small-model-runner-cpu-20261026.json). A1 remains partial.
The [CUDA preparation](small-model-gpu-20261026.md) now implements the package,
device and measurement path for the original smoke. Physical GPU qualification,
pretrained performance and the allocation-inclusive provider lifecycle remain
separate gates; the free package/CPU controls cannot satisfy them.
Native run 40335270281 passed 604 tests and the exact 56-package CUDA installation
plus CPU/control checks. Its [receipt](small-model-gpu-cpu-20261026.json) leaves
physical GPU and pretrained performance explicitly NOT RUN.

## Intended Augnes role and input/output contract

The candidate is a bounded diagnostic component. Given a question, evidence
available at a stated time, source identities, prior hypotheses and allowed
checks, it proposes explanations and the next useful check or a justified stop.
The surrounding system retains retrieval, permissions and final decisions.

Inputs must distinguish observations from previous model claims and assumptions.
Preserve event identity, source/dependency links, observation time and availability
time. A record arriving later must not enter an earlier snapshot. A repeated
observation is not a new independent measurement. Temporal tasks must distinguish
new evidence about an old state from an actual change in the underlying state.

Outputs have a bounded hypothesis count and contain:

- Candidate hypotheses, supporting and conflicting evidence IDs, and assumptions.
- Predictions that would distinguish alternatives; no requirement to name a unique
  cause when the evidence does not identify one.
- What changed from the previous assessment and which new evidence justifies it.
- A proposed check and its decision relevance, or stop/defer/escalate with reason.
- Explicit unknown, inconsistent-evidence and model-inadequacy states.
- Probabilities only when their semantics are defined. Exact synthetic posterior
  estimates and empirically calibrated deployment confidence are different fields.

Constrain explanations to auditable evidence references and short justifications;
do not score fluent rationales as correctness. Hypotheses may overlap or coexist,
so their marginal probabilities need not sum to one. Observational association
alone must not be described as an identified causal intervention effect.

The read-only Augnes type inspection found an `abductive_hypothesis` category,
source references, missing-assumption notes, counterclaims and review cues in
`types/research-candidate-logical-claim-shape.ts`. A later adapter can map into
those concepts, but this is not yet an implemented or fully compatible interface.
Initial evaluation produces offline candidate records only; promotion into
Perspective or execution is a separate product decision.

## Evaluation layers

| Layer | Question and examples | Ground truth and limits |
| --- | --- | --- |
| E1: declared finite model | Posterior revision, ambiguous/simultaneous causes, duplicate or correlated evidence, contradiction, inspection or stop | Exact enumeration; measure numerical and decision error. This tests inference under a supplied model. |
| E2: partial model and hypothesis construction | Missing candidate cause, unseen combinations, alternative explanations, discrimination by forward predictions | New bounded generators with evaluator-only worlds and executable checks. Accept equivalent explanations and observational ambiguity; do not force recovery of one sampled cause. |
| E3: temporal and textual transfer | Plain-language observations, distracting statements, delayed/stale/retracted evidence, changed states and wrong initial leaders | Versioned observation streams and information cutoffs. Keep text-only changes paired with the same world and in the same split. |
| E4: Augnes case replay and shadow use | Interrupted work, conflicting project records, failed checks, changed assumptions, choosing what to inspect next | Time-cutoff replay followed by fresh prospective cases. Blinded rubric, source verification and observed check outcomes; no invented exact real-world posterior. |

E2 needs more than adding variants to the current teacher. Define a bounded
hypothesis language, equivalence rules and allowed observations first. Where a
latent explanation is not identifiable, score predictive adequacy, coverage of
plausible alternatives and appropriate uncertainty. Distinguish input defects,
logical contradiction, missing model support and ordinary low-probability events.

E3 initially uses a declared finite horizon. Any multi-check experiment requires
an explicit transition/observation model and dynamic-programming or exhaustive
reference policy; the current one-step teacher cannot certify long-horizon value.

## Comparisons that identify the effect

Run the following comparisons **within each backbone**, with the same evaluation
inputs, system prompt, tools, context/output ceilings and decoding policy unless
a difference is the explicitly named treatment. E2B and E4B use separate adapters.

| Arm | Purpose |
| --- | --- |
| B0: instruction model, minimal task prompt | Basic capability reference. |
| B1: instruction model, strong diagnostic prompt | Main no-training comparator; select the prompt on development data only. |
| B2: general-reasoning SFT, B1 prompt | Controls for generic training exposure and output-format learning. Include the same schema/format practice without the specialist curriculum. |
| S: specialist SFT, B1 prompt | Tests the additional value of the abductive curriculum. |
| T: model plus bounded exact solver, where applicable | Practical system alternative when a declared model can be solved exactly; report separately from unaided model ability. |

B2 and S share checkpoint/revision, tokenizer/template, trainable modules/rank,
optimizer, precision, training token budget, sequence-length distribution,
update schedule, validation frequency and hyperparameter-search allowance.
Record residual differences and actual compute rather than asserting a perfect
match. Count all prompt search, failed runs, retries and inference calls. Never
attribute an E4B-versus-E2B gap to specialist training.

Use identical settings within a backbone for the controlled comparison. For
deployment selection, additionally compare quality at matched wall-time/cost
budgets across sizes. Separate precision effects from training effects by
evaluating the untrained and trained model at the same deployment precision.

After a credible gain, use limited ablations for evidence-dependence handling,
revision and inspection-choice training to investigate mechanism. Ablations are
not required before the first useful baseline and must not expand an unbounded
search. RL is not the initial method; start with supervised adapter training.

## Data, split and replication discipline

1. Implement and audit train, development and sealed confirmatory partitions.
   Group by underlying causal/problem family and episode, not wording or seed.
   Keep relabelings, paraphrases, parameter variants and all snapshots of one
   episode together. Detect graph and semantic-template overlap explicitly.
2. Reserve new structures and compositions, parameter ranges, evidence lengths,
   source-dependence patterns and natural-language renderings. Report these
   distribution shifts separately. Do not assume graph disjointness proves
   semantic independence or absence of pretraining contamination.
3. Initial evaluation planning target: at least 20 held-out family groups with
   at least 20 cases each, including paired evidence revisions. This is a
   coverage target, not a power calculation or 400 independent families.
   Use development-only variance/power analysis to set the final sample size
   for the predeclared effect before sealing the evaluation manifest.
4. Use three independent training seeds for each backbone/arm for which a
   confirmatory claim is made. A single-seed run is screening only. Report all
   seeds; select checkpoints using a fixed development criterion, not test
   scores. If sampling at inference, predeclare repeated draws and their budget.
5. Hash-lock source, partitions, inputs, labels, prompts, model revision,
   dependencies and scoring before confirmatory execution. Evaluation loaders
   expose questions only; evaluator labels and future events are inaccessible
   to training, retrieval and inference. Model-generated data requires
   provenance and validation and cannot label its own confirmatory answers.
6. Resample/aggregate at the family or episode level and report seed variability
   separately. Paired comparisons use the same cases across arms. Do not pool
   template copies as independent evidence or repeatedly peek until significant.
   A changed design after results requires a new untouched test, with old results
   retained. Limited data or repetitions yields INCONCLUSIVE, not a relaxed gate.

## Metrics and decision rules

Freeze exact formulas, thresholds and aggregation in a machine-readable protocol
before the first confirmatory run. The following are project decision defaults,
not externally established universal standards. Any revision must occur before
test access and retain the earlier protocol.

For E1, report posterior mean absolute error against the exact distribution and
normalized decision regret separately. Regret compares the selected stop/check
plan to the optimal plan under the same horizon and costs. Normalize by the
declared utility range plus maximum inspection cost; define zero-range cases
explicitly. Overlapping hypotheses are scored as marginals. Invalid outputs get
maximum error/regret in the assigned denominator, with parser failures separately
reported. Contradiction/model-mismatch cases have a separate status endpoint;
undefined posteriors are never imputed. Brier/reliability analysis of predicted
events requires separately sampled outcomes and appropriate grouping; exact
posterior error alone is not real-world calibration.

| Decision | Required evidence |
| --- | --- |
| Implementation works | Actual gradient update; adapter tensors change; save/reload reproduces outputs within declared tolerance; adapter-on/off comparison; measured memory and execution time. No capability claim. |
| Specialist learning on E1 | Decision regret is primary; posterior error is secondary. Freeze a worthwhile effect and uncertainty rule against B1/B2 using development variance/cost, before fresh confirmatory data. Use three seeds and family-level uncertainty. Near-zero comparator error is a ceiling, not permission to divide by zero. |
| Generalizes beyond E1 | Positive E2/E3 results under their separately frozen prediction/coverage/revision rubrics; report each layer and distribution shift. E1 alone cannot pass this gate. |
| Candidate for bounded offline/shadow screening | Usable actual outputs and source-grounded development replay; no synthetic-superiority prerequisite. Report contradiction handling, unsupported claims, needless checks/deferral and schema following with uncertainty. About 20 episodes cannot establish one-percentage-point non-inferiority. |
| Candidate for product integration | Fresh prospective shadow results show useful check selection or better supported hypotheses at the fixed review/cost budget, beyond the existing workflow. Validate the actual deployment artifact and resource envelope; a replay-only gain is insufficient. |

The old dual 10% improvement / one-percentage-point margin remains in history,
not an early-replay gate. Freeze confirmatory thresholds before test access; never
relax them after seeing results. A separate positive
claim about any exploratory metric or either model needs appropriate multiplicity
handling or a fresh confirmatory test. Do not pick a model after inspecting its
test result and call that same result independent confirmation.

E2/E3 scoring must include hypothesis precision/coverage with a fixed maximum
candidate count, prediction validity, correct revision versus needless reversal,
duplicate-evidence invariance and missing-model detection. More guesses, more
checks or automatic abstention must not inflate success. Report risk versus
coverage and the cost of deferral. Freeze the detailed E2/E3 rubric during A1;
until it exists, broad abductive competence cannot be certified.

E4 compares the existing Augnes workflow, one additional main-model review, an
untrained small-model suggestion and a specialist if available. Randomize and blind output
labels where feasible; retain disagreements and use source-grounded review,
not an LLM judge as the sole authority. Fix the additional-cost ceiling; report reviewer effort and inspection cost. Measure useful hypotheses/checks, unnecessary checks, unsupported claims,
revision after disconfirmation, and accepted versus rejected suggestions.
Do not claim counterfactual task resolution from an unexecuted recommendation.

## Execution sequence and current gates

| Stage | Deliverable | Current status |
| --- | --- | --- |
| A0: goal and capability contract | Augnes-first plan; E2B first, E4B conditional; competition abandoned | Documented; no model result |
| A1: actual baseline and early replay | Existing 18 E2B B0/B1 assignments and 3–5 development replays | Completed E2B 18 assignments plus six responses for three replays; all synthetic task outputs invalid, replay content mixed. Conditional E4B comparison next |
| A2: optional training feasibility | Tiny update/save/reload and observed resource budget | NOT RUN |
| A3: candidate screening | One-seed matched B2/S; bounded data/token ceilings | NOT RUN; B1 can bypass training for shadow screening |
| A4: practical value | About 20 independent offline/shadow episodes, four flow comparisons | NOT RUN; does not require synthetic superiority |
| A5: confirmation and adoption judgment | Fresh families, three seeds where learning is claimed, measured deployment artifact | NOT RUN; no Kaggle decision remains |

Add only components required for the next measurement; do not rebuild agent or
provider frameworks. E4B is conditional on an identified capacity question. Keep
unperformed confirmation explicit; exploratory success does not qualify deployment.

For potential use on the owner's RTX 4070 SUPER 12GB, measure inference peak
VRAM/RAM, cold load, p50/p95 latency, output validity, long-input degradation and
concurrent-work headroom at realistic context lengths. The device is a target,
not an observed runtime in this session. Record quality loss after quantization.
Training need not use the deployment device; fit and throughput are unmeasured.
Kaggle-specific loader/attachment work is outside the active research plan.

## Provenance and scope

Read 2026-10-26 UTC through source tools; web document bytes were not archived
and no webpage SHA-256 is claimed:

- [Google Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4):
  E2B is 2.3B effective/5.1B with embeddings; E4B is 4.5B/8B. The labels are not
  interchangeable with ordinary 2B/4B memory estimates. The subsequent runtime
  lock pins baseline revisions/tokenizers; training and adapter identities
  remain to be established in A2.
- [Unsloth training guide](https://unsloth.ai/docs/models/gemma-4/train):
  training support and memory guidance are implementation leads, not measured
  Backtrace resource requirements or evidence of diagnostic learning.
- [Augnes type contract](https://github.com/hynk-studio/augnes/blob/main/types/research-candidate-logical-claim-shape.ts):
  GitHub blob `f1931f4102d1a964de55fbe1ced68a8c754fd8ed`, fetched read-only;
  structure preview with no truth, Perspective-promotion or execution authority.
- Backtrace baseline: `3b0f5e8028a7835ac44b8e9cffd488b185e1e127`,
  tree `fcfd51d46f2bcd1226827ea74f90c6a2d40860b3`, Draft #28;
  [pilot evidence](research-reduced9-execution-20261026.md) and
  [teacher evidence](exact-teacher.md) remain unchanged.

The original plan update changed research documents only. Subsequent A1 CPU
implementations are linked above with their own scope and validation. The
readiness stage executes tiny random CPU models only; none executes pretrained
evaluation, authorizes paid training, publishes private Augnes cases or changes
another repo.
Within the current delegated continuation, any paid run needs a concrete
qualified, affordable, bounded scope; previous
permits stay consumed. Current credit is not a demonstration that this full
evaluation program is funded. No merger, issue closure or submission follows.
