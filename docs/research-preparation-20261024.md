# Research preparation after the successful diagnostic

Scope: the owner's 24 October 2026 KST request to proceed with steps 1 and 2 of
the original research plan. This is free CPU work, stacked on Draft PR #20 at
`04ec3016c2631a2f0c08a004a2e1ecdbdb7b4fea`, referencing open Issue #1.

The preparation is delivered in [Draft PR #21](https://github.com/hynk-studio/backtrace/pull/21).
The actual [Linux CPU run 40072228708](https://github.com/hynk-studio/backtrace/actions/runs/40072228708)
at source `817eb5d7df921fa1d4f849da0e25f8e1f724af21` succeeded: **419 tests,
original-input verification, six-plus-six task selection, matched candidate
assembly and exact teacher generation all passed**. The machine-readable
[verification receipt](research-preparation-cpu-20261024.json) binds the run,
source tree, protocol, input/ZIP hashes, selection and teacher manifest.

## What is prepared

- A [matched comparison protocol](matched-comparison.md) that preserves all 105
  historical source fingerprints and exact model/runtime/input identities, while
  separating new generic-review R1 from diagnostic R2.
- Actual R0/R1/R2 candidate assembly from the recovered original six-file
  no-LoRA baseline. Two builds are byte-identical; four nonprompt files are
  identical across arms. Original third-party inputs/archives stay private.
- A strict, deterministic metadata-only selector for six primary tasks across
  the three available unexposed repositories and six ordered reserves, plus
  paired outcome bookkeeping. The initial six-repository shortfall is preserved.
  The [committed selection](research-selection-20261024.json) fixes actual IDs,
  base commits and balanced arm orders before model execution.
- A [small exact teacher](exact-teacher.md) with rational Bayesian/logic/decision
  labels, distinct train/evaluation structures and reproducible leakage audits.
- A separate free CPU workflow for the full Linux suite, teacher generation and
  authenticated original-input acquisition. It has read-only repository access,
  uses the existing Kaggle credential only to read the original metadata and
  saved R0-clean ZIP, has no RunPod secret and publishes only public receipts.
  Raw downloaded inputs are removed.

## Evidence in this preparation

The completed Linux run passed **419 tests in 33.889 seconds**, with no errors,
failures or skips. CPU preflight, all 105 historical source fingerprints and all
six authored prompt fingerprints passed. The 53 new focused tests comprise
26 teacher, 24 comparison and three input-preparation tests. The separately
reviewed selector rejects underfilled studies, altered assignments, duplicate
outcomes and malformed inventories before producing a summary.

The original metadata and original 6,230-byte R0-clean archive were both
downloaded and verified in that run. All three assembled archive hashes match
the independent local builds; their four nonprompt files are identical.
The actual primary tasks are `requests_7309`, `rich_3486`, `httpx_3672`,
`requests_7315`, `rich_3067` and `requests_7502`. Six ordered reserves are fixed
in the selection receipt. The source inventory has Requests 13, Rich 48 and
HTTPX 1 eligible task; the primary sample therefore has three repository
clusters, not six independent repository samples. All 18 planned model slots
remain NOT RUN.

Teacher generation and its structural audit passed for 24 training and 24
evaluation questions from three families per partition. The Linux generator
reproduced all four local JSONL hashes exactly. The reference manifest preserves
posterior revision, duplicate evidence, contradiction, zero-support model
mismatch, logical entailment/refutation/unknown states, useful inspections,
uninformative or decision-irrelevant inspections, costs and stopping coverage.
These are exact teacher outputs, not measured student performance.

The input preparation receipt confirms zero provider operations, no model run,
no raw competition data publication and removal of its temporary input tree.
All 52 preexisting branch refs, including historical paid/watch/state branches,
were unchanged when checked after the implementation push; only the new
research branch was added. The PR remains a draft and Issue #1 remains open.

## Preserved earlier failures and amendment

The restricted local suite initially attempted 414 tests: 23 errors and three
skips reflected socket/process restrictions and a different bundled pip wheel.
All 48 focused new tests at that revision passed. The initial actual Linux
[run 40071820909](https://github.com/hynk-studio/backtrace/actions/runs/40071820909)
at `050091f680abc6cd4c4918661d33015c8a4166a7` then passed all 414 tests in
30.847 seconds, CPU preflight, source/prompt pins and teacher generation.

Original metadata acquisition passed its 1,984,455-byte SHA-256 pin and 129-row
inventory. It revealed only **three eligible repositories and 62 tasks** after
67 FastAPI tasks were excluded. The v1 selector correctly returned
`SELECTION_SHORTFALL`, not a completed six-task pilot. The
[initial receipt](research-preparation-initial-cpu-20261024.json) is preserved.
Before any task content or model outcome was inspected, v2 explicitly amended
selection to six tasks taken round-robin across the three eligible repositories.
It retains the original seed, ranking, exclusions, prompts and budgets; it does
not claim six independent repository clusters.

That same run separately failed while reacquiring the current competition's
eleven reference files (`DownloadError`; exact underlying file/cause not retained).
The original R0 ZIP had already been recovered and matched locally. The CPU
workflow was changed to read that same hash-pinned ZIP from the existing saved
Kaggle input notebook version 1, avoiding an assumption that the competition's
current reference files still reproduce the historical source. That revised
acquisition and v2 selection succeeded in run 40072228708.
Temporary raw inputs were removed even on the failed run.

An earlier run 40071765880 at `728fd3ca2ee9ab6f2c13e47f13851309a03f299c`
failed YAML parsing before any job ran. The pip command containing a colon was
changed to a block scalar and parsed locally before the successful Linux run.

The original reference bundle was recovered and all 11 files matched the
existing recorded hashes. Reconstructing the R0-clean derivative reproduced
its exact 6,230-byte archive with SHA-256
`2e24495826cb971053439a00d9ad8350471fc0efffa41a54b82082feedaa7358`.
This check reacquired reference/candidate bytes, not the large checkpoint.

Initial direct Kaggle download in this session returned HTTP 401. The local
Browser connection was unavailable. The existing repository's authorized CPU
input-resolution path then completed the required reads without exposing its
credential or requiring a new account/terms acceptance.

## Limits and next gate

No new real model task, R0/R1/R2 score comparison, adapter training, competition
submission or paid allocation has run. All historical paid/watch/state records
remain unchanged. New candidate archives still need actual official schema/
compiler and runner integration checks, including global model-request/token
accounting and clear work-versus-teardown timing. The original single-task driver
is not silently converted into a multi-task authorized runner.

The six-task comparison is a feasibility pilot. Synthetic teacher correctness
does not establish model learning or transfer to real code. R3's tiny training/
save/reload/attachment feasibility remains a separate next research task, with
a matched general-reasoning control required for learning-specific claims.
