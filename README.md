# Backtrace

Current priority, 2026-10-26: **establish whether a small specialist model learns
useful abductive inference, with potential Augnes use in view**. Speed of the
first training run is not the research objective. E2B and E4B are candidates;
Kaggle submission is an optional later decision.

The [small-model plan](docs/small-abductive-model-plan-20261026.md) separates
exact synthetic inference, hypothesis construction, temporal/textual transfer
and Augnes case evaluation. Compare specialist training with strong prompting
and matched general-reasoning training within each model size. Require unseen
problem families, repeated seeds, uncertainty and measured deployment cost.
See the [overall sequence](docs/experiment-plan.md) for current priorities.

The [CPU teacher](docs/exact-teacher.md) has 24 training and 24 evaluation
questions with exact labels. It receives a declared model and candidate
hypotheses; these are development fixtures, not evidence of learned abduction.
The [new evaluation implementation](docs/abductive-evaluation-20261026.md) adds
40 disjoint graph families, 4,000 candidate records, train-only exports, bounded
hypothesis construction, timed evidence revision and exact scoring. These are
CPU instruments and controls, not model-performance results. The
[temporal extension](docs/temporal-baseline-20261026.md) adds 3,200 changing-state
snapshots and paired JSON/controlled-English B0/B1 development prompts. It reuses
the same 800 episodes and 40 families, rather than adding independent cases.
A1 remains partial pending model baselines, missing-model construction, real
language transfer, power analysis and final test sealing. The
[runtime preparation](docs/small-model-readiness-20261026.md) pins official
E2B/E4B revisions and a hash-locked CPU environment, checks all 11,520 actual
tokenization assignments, and prepares 36-request smoke / 288-request screening
scopes across both models. Explicit checkpoint key mapping passes tiny random
CPU loading probes. The [CPU collector](docs/small-model-runner-20261026.md)
connects isolated raw-token generation, durable output collection and the exact
evaluators. Its [native qualification](docs/small-model-runner-cpu-20261026.json)
passed 592 tests and explicit random/authored/failure-recovery controls. Actual pretrained loading,
NVIDIA device/kernel qualification and GPU memory/throughput measurements remain unqualified.
The [CUDA preparation](docs/small-model-gpu-20261026.md) now adds explicit device
checks, no-fallback CUDA execution and a fixed baseline plan. Its free CUDA-build
installation/CPU compatibility qualification passed 604 native tests, the exact
56-package CUDA install, CPU controls and missing-GPU rejection. The
[receipt](docs/small-model-gpu-cpu-20261026.json) keeps this separate from physical
GPU kernel/driver and pretrained measurements.
The [pre-minimum preparation](docs/small-model-precheck-20261026.md) adds
allocation-clock supervision, bounded evidence export, cleanup-only resource
observations and effective cgroup memory checks. It separates a hardware-only
checkpoint from the unchanged full-model baseline. Native run 40349526548 passed
620 tests and 14 operational cases, including the actual interrupted collector.
All eleven CPU export archives were independently verified. The
[receipt](docs/small-model-precheck-cpu-20261026.json) preserves two earlier native
failures and local environment failures. The
[provider follow-up](docs/small-model-provider-20261027.md) now verifies live
authenticated account/quotes, exact-image delivery of the new payload and a
bounded remote observer on an independent runner. The default container fails
the current native namespace/cgroup prerequisites. The observer terminated after
its liveness check; no paid cleanup target is armed. The
[ordinary-container correction](docs/small-model-container-20261027.md) now keeps
the evaluator outside the inference container, installs exact Python 3.12.14
and the 56-wheel CUDA closure, and enforces a non-root socket/process-filtered
worker. Native run 40445252781 passed 639 tests and 23 container
controls, both 36-assignment CPU controls and actual remote worker-loss cleanup.
All random raw outputs match the earlier native result. Production CUDA
integration, provider memory admission, resource-bound independent deletion and
physical GPU checks remain pending; paid launch is disabled.
Training, adapter save/reload and Augnes integration are **NOT RUN**.

The [latest coding pilot](docs/research-reduced9-execution-20261026.md) attempted
nine R0/R1/R2 slots. Two original patches were submitted and evaluated; one
resolved its task, seven slots had no submission, and the pilot is INCOMPLETE.
The [trace analysis](docs/research-reduced9-timeout-analysis-20261026.md) and
all original outcomes remain preserved. This is not a training-effect estimate.
Both cleanup proofs passed and its paid permit is consumed. The original
[matched comparison](docs/matched-comparison.md) is now a deferred transfer track.

## Historical setup milestones

The following paragraphs describe earlier bounded stages. Their NOT RUN and
approval statements are historical; use the current evidence report above for
the present research state. Original receipts and consumed attempts are retained.

Backtrace starts with [Issue #1](https://github.com/hynk-studio/backtrace/issues/1)
and the [Gemma 4 Developer Agent competition](https://www.kaggle.com/competitions/gemma-4-developer-agent).
The official guide, ten-file starter, and five harness/schema wheels are now
acquired and pinned locally. **R0-clean is packaged reproducibly** as a six-file
no-LoRA derivative, preserving the ten-file official reference. Official CPU
directory, model, include, schema and generation checks pass separately on the
original and actual candidate archive. The official compiler also constructs
both agents and binds their real harness callables/schemas in a bounded CPU probe.
That CPU probe's model client rejects requests and its sandbox is absent.
Two separately authorized T4 attempts loaded the pinned checkpoint with observed
FP16 resolution and failed before healthy serving or task execution. The first
hit custom-all-reduce; the additional **T4-native-no-custom-ar** run applied the
approved flag and exposed a Triton attention shared-memory limit (98,304 bytes
required, 65,536 available). Both attempts are consumed and their GPU sessions
terminated. See the [latest report](docs/r0-no-custom-ar.md), the
[first GPU failure](docs/r0-native-dtype.md), and the original
[pre-allocation STOP](docs/r0-smoke-attempt.md).
See [R0 and the probe](docs/r0.md) and the [frozen smoke recipe](docs/r0-smoke.md).

The [startup observer](docs/startup-guard.md) now fails fast on confirmed engine
failure while the API parent remains alive, tested through the real wrapper with
disposable CPU processes. A [conditional A100 80GB TP=1 proposal](docs/r0-a100-proposal.md)
records cost, image and account prerequisites. The owner subsequently authorized
one conditional A10080-TP1 attempt (50 minutes; original $2 control policy,
subsequently amended as above). The original create failed; the owner-directed
follow-up allocated the A100 but stopped during input transfer. A100 inference
has **not run**. Both the [original failed create](docs/a100-first-create-attempt.md)
and the [allocated follow-up](docs/a100-owner-region-execution.md) remain recorded.
The [Linux CPU follow-up](docs/a100-cpu-qualification.md) fixes fixture boot timing,
adds A100-only serving checks and an offline dependency qualification command,
and records the original Cloud access/storage blockers. The subsequent
[Kaggle CPU follow-up](docs/kaggle-cpu-followup.md) restored the private driver and
exact notebook v2, tested the official lifecycle, and found three incompatible
dependency pins. On 2026-10-16 the owner approved the
[three-package runtime amendment](docs/a100-runtime-amendment.md), now used by
the offline installer. The original v25 acquisition manifest remains intact.
The [offline CPU follow-up](docs/a100-offline-qualification.md) restores the exact
original README and prepares the 245-package runtime closure plus a pinned pip
bootstrap wheel. It records actual offline installs, official CPU checks and
the remaining A100 driver and provider prerequisites separately. The approved
delivery can use a private offline bootstrap on the pinned public base; a private
image or registry is optional. The [free-resource assessment](docs/free-resource-assessment.md)
records the account's actual T4-only GPU menu, the prepared private A100 driver,
and why the next frozen GPU experiment needs access to a suitable larger GPU.

## Local checks

The basic inspector/preflight uses Python 3.9+ and the standard library.
The complete Linux control/transport qualification uses CPython 3.12, a real
root PID namespace, OpenSSL 3 and OpenSSH client tools; no provider key is needed.
From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
```

`preflight` reports local interpreter readiness, not competition readiness.
Packaging additionally requires the acquired pins and the separate official CPU
environment described below. The bounded private smoke driver is recorded by
hash in the execution report; it is not a general inference or submission tool.

Verify the locally acquired artifact pins without importing their code:

```sh
python3 tools/backtrace.py verify-artifacts .local/official
```

For the separately installed, pinned Python 3.12 CPU validation environment and
the official checks, follow [docs/r0.md](docs/r0.md). These checks are distinct
from the standard-library ZIP inspector below.

With those verified inputs and the pinned CPU venv available:

```sh
mkdir -p .local/r0-clean
python3 tools/backtrace.py baseline .local/official .local/r0-clean/candidate.zip --official-python .local/cpu-checks/bin/python
.local/cpu-checks/bin/python tools/official_check.py .local/official --candidate .local/r0-clean/candidate.zip
python3 tools/compile_probe.py .local/official .local/r0-clean/candidate.zip --official-python .local/cpu-checks/bin/python
```

The build pins the original, removes only the two authorized adapter lines,
excludes four adapter files, and validates the staged archive before publishing
it. Existing outputs are never overwritten; failed checks remove staged output.
`baseline` with no arguments still exits **2**, names the required inputs and
creates no archive. Generated assets and receipts stay local and Git-ignored.
The compiler probe requires the frozen 6,230-byte candidate identity; it runs in
a credential-cleared child with a 45-second cap and temporary workspace cleanup.
It does not start a server or exercise a sandbox. Its explicit boundary
substitutions and separate opt-in integration tests are in [verification](docs/verification.md).

Acquire only the pinned public notebook source (network required; never executed):

```sh
python3 tools/backtrace.py acquire-notebook .local/starter.ipynb
```

This refuses overwrites and notebook version/hash drift. Preserve its JSON receipt.
The public API points to the current notebook, so a later revision will require
review and repinning, not silent acceptance. This is not a full historical mirror.

Select the smoke task in a private preparation process, before inspecting answers:

```sh
python3 tools/select_smoke_task.py .local/smoke/evaluator-only/tasks.jsonl .local/smoke/agent-task.json
```

This emits only five agent fields to a new mode-0600 file and prints an identity
receipt. It rejects conflicting duplicate IDs and existing outputs. Keep the
original metadata (including reference fields) outside agent-readable storage;
this selector does not establish an OS sandbox or a complete input bundle.

Inspect a separately acquired ZIP without extraction, with an explicit list of
expected files, for example:

```sh
python3 tools/backtrace.py inspect .local/review.zip --allow docs/notes.txt
```

This example is generic, **not** a competition sample or allowed Kaggle layout.
Every expected file must be listed exactly. The inspector rejects unsafe or
ambiguous paths, duplicates, links, special/encrypted members, unexpected files,
common credential/evaluator markers, caches, binary weights, nested archives,
and excessive sizes/ratios. It accepts only bounded UTF-8 text. Local ceilings
are 64 MiB compressed/expanded, 16 MiB per member, 1,000 entries, and 200:1 ratio;
these are **not Kaggle limits**. Adapters are deliberately unsupported here.

A pass is a reproducible local inspection report, not a security guarantee,
permission to redistribute, or official validation. Name/content heuristics can
miss disguised secrets and answers, and can flag harmless examples. Review
allowlisted content and provenance manually. No artifact is imported or run.

## Evidence and scope

See [competition contract](docs/competition-contract.md),
[source manifest](docs/source-manifest.json), [experiment plan](docs/experiment-plan.md),
and [verification report](docs/verification.md).

Current scope is small-model research preparation and evaluation design.
Training implementation is planned; product integration, a central model, a
general formal prover, RL campaign and new agent hierarchy are not implemented
by this change. Transfer and adapter learning remain untested. All earlier paid
attempts are consumed. The human controls merges, new paid execution and
competition submissions.
No repository license has been selected. Third-party code, weights and data are
not included.
