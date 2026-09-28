# Backtrace

Does post-training logical/abductive inference, Bayesian belief revision, and
selection of useful inspections improve Gemma's software-engineering performance
under a matched inference budget?

Backtrace starts with [Issue #1](https://github.com/hynk-studio/backtrace/issues/1)
and the [Gemma 4 Developer Agent competition](https://www.kaggle.com/competitions/gemma-4-developer-agent).
This first slice provides CPU-only source acquisition and conservative artifact
inspection. **The official baseline is blocked, not reproduced.** The organizer
notebook v2 is acquired and pinned; the official starter directory and harness
implementation remain behind Kaggle's sign-in/rules gate.

## Local checks

Python 3.9+; standard library only, no installation or API credential needed.
Tested with Python 3.9.6. From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 tools/backtrace.py baseline
```

`preflight` reports local interpreter readiness, not competition readiness.
`baseline` deliberately exits **2**, with the missing artifacts and next steps.
There is no packaging, inference, training, or submission implementation yet.

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
