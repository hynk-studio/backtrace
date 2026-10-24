# Research preparation after the successful diagnostic

Scope: the owner's 24 October 2026 KST request to proceed with steps 1 and 2 of
the original research plan. This is free CPU work, stacked on Draft PR #20 at
`04ec3016c2631a2f0c08a004a2e1ecdbdb7b4fea`, referencing open Issue #1.

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
- A [small exact teacher](exact-teacher.md) with rational Bayesian/logic/decision
  labels, distinct train/evaluation structures and reproducible leakage audits.
- A separate free CPU workflow for the full Linux suite, teacher generation and
  authenticated original-input acquisition. It has read-only repository access,
  uses the existing Kaggle credential only to read the original metadata and
  saved R0-clean ZIP, has no RunPod secret and publishes only public receipts.
  Raw downloaded inputs are removed.

## Evidence in this preparation

Local focused checks and actual candidate/teacher artifacts have been exercised.
The restricted local suite attempted 414 tests: 23 errors and three skips
reflected socket/process restrictions and a different bundled pip wheel, not
new-feature failures. All 48 focused new tests passed. The actual Linux
[run 40071820909](https://github.com/hynk-studio/backtrace/actions/runs/40071820909)
at `050091f680abc6cd4c4918661d33015c8a4166a7` then passed all **414 tests in
30.847 seconds**, CPU preflight, source/prompt pins and teacher generation.

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
workflow therefore now reads that same hash-pinned ZIP from the existing saved
Kaggle input notebook version 1, avoiding an assumption that the competition's
current reference files still reproduce the historical source. Revised actual
selection/acquisition results will be added after the new workflow completes.
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
input-resolution path is used next; this neither extracts its credential nor
asks for a new account/terms acceptance.

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
