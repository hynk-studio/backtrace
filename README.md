# Backtrace

Does post-training logical/abductive inference, Bayesian belief revision, and
selection of useful inspections improve Gemma's software-engineering performance
under a matched inference budget?

Backtrace starts with [Issue #1](https://github.com/hynk-studio/backtrace/issues/1)
and the [Gemma 4 Developer Agent competition](https://www.kaggle.com/competitions/gemma-4-developer-agent).
The official guide, ten-file starter, and five harness/schema wheels are now
acquired and pinned locally. **R0-clean is packaged reproducibly** as a six-file
no-LoRA derivative, preserving the ten-file official reference. Official CPU
directory, model, include, schema and generation checks pass separately on the
original and actual candidate archive. See [the exact delta and R0 recipe](docs/r0.md).
No model, task, or submission has run.

## Local checks

Python 3.9+; standard library only, no installation or API credential needed.
Tested with Python 3.9.6. From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
```

`preflight` reports local interpreter readiness, not competition readiness.
Packaging additionally requires the acquired pins and the separate official CPU
environment described below. There is no inference, training or submission implementation.

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
```

The build pins the original, removes only the two authorized adapter lines,
excludes four adapter files, and validates the staged archive before publishing
it. Existing outputs are never overwritten; failed checks remove staged output.
`baseline` with no arguments still exits **2**, names the required inputs and
creates no archive. Generated assets and receipts stay local and Git-ignored.

Acquire only the pinned public notebook source (network required; never executed):

```sh
python3 tools/backtrace.py acquire-notebook .local/starter.ipynb
```

This refuses overwrites and notebook version/hash drift. Preserve its JSON receipt.
The public API points to the current notebook, so a later revision will require
review and repinning, not silent acceptance. This is not a full historical mirror.

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

Non-goals: a central model, Augnes integration, full teacher, training pipeline,
RL campaign, multi-agent hierarchy, or formal prover. No GPU rental, paid API,
large model download, terms acceptance, training job, or Kaggle submission is
part of this slice. The human controls those decisions and merges. No repository
license has been selected. Third-party code, weights and data are not included.
