# Issue #1 post-merge artifact and CPU-check checkpoint

2026-09-29 UTC. Current results below supersede the historical bootstrap access
blocker. The prior PR #2 report is retained further below; its Python 3.9.6 checks
and the reviewer's Python 3.13.5 checks are separate from this execution.

## Repository and authority

Started at clean `main` in `/Users/hynk/code/backtrace`, origin
`https://github.com/hynk-studio/backtrace.git`, main/base
`757b56f29ee8bcb6c9379b4d90525b10c0366a74`, tree
`db667aa37bea445c822748918adc91a5dded3906`. Read AGENTS.md, Issue #1 and its post-merge
checkpoint, owner access confirmation, PR #2 merge state and open PR inventory.
No open PRs or intervening tracked changes were present. New issue branch:
`bt-001-r0-artifacts`. The bootstrap exception was not reused. No main or merged-PR
changes, force push, issue closure or merge action occurred.

## Current verification levels

| Level | Observed result |
| --- | --- |
| Local tooling | PASS: 24 unittest tests on Python 3.9.6 (18 existing plus 6 authored artifact-pin regressions); preflight exit 0. |
| Official artifact acquisition/pinning | PASS for guide, complete ten-file starter and five relevant wheels (16 artifacts). Model/tokenizer and full hosted image are not acquired. |
| Candidate packaging/local archive inspection | NOT RUN: no-LoRA conflicts with adapter-equipped notebook v2; explicit variant decision pending. No archive produced. |
| Official CPU validation | PASS on **unchanged original starter**, Python 3.12.14: competition directory limits, single model, include resolution, both schemas, generation constraints and adapter discovery. Not a no-LoRA candidate result. |
| Compiler/tool binding | NOT RUN. |
| End-to-end model execution | NOT RUN. |
| Kaggle submission acceptance | NOT RUN. |
| Hosted scoring | NOT RUN. |

The selected reference is notebook v2, source SHA-256
`0c54c3bac3269e422b1d48ac8087ff26b49fe764231b7983c90ef842382f9a87`.
Its sampling literal equals the current sample's 120-byte configuration. The
original has two real adapters. No removal/variant substitution is authorized
by inference; the proposed no-LoRA deviation is recorded in [r0.md](r0.md).
All downloaded third-party bytes remain ignored. Public files are authored code,
notes and acquisition/environment manifests, without a license choice.

## Commands and observed outcomes

Repository inspection used `pwd`, `git remote -v`, `git status --short --branch`,
`git branch -avv`, `git worktree list --porcelain`, `git ls-remote --heads origin`,
`git rev-parse HEAD`, `git rev-parse HEAD^{tree}`, `gh issue view 1 --repo
hynk-studio/backtrace --comments`, and GitHub JSON issue/PR queries. Current
repository instructions and existing source documents were read before mutation.

```sh
git switch -c bt-001-r0-artifacts
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 tools/backtrace.py verify-artifacts .local/official
.local/cpu-checks/bin/python tools/official_check.py .local/official
python3 tools/backtrace.py baseline
git diff --check
git diff main...HEAD --check
```

Results respectively: branch created; **24 passed**; local READY (0); **16 pins,
10 starter files PASS** (0); official CPU checks **PASS on original starter** (0);
baseline expected **2**, no archive; both diff checks passed. A separate baseline
subprocess with an empty temporary cwd returned 2 and left zero files. Missing,
altered, extra, aliased and symlink input cases are synthetic local tests. Existing
ZIP duplicate/alias/traversal/collision/content checks remain unchanged and pass.
Preflight does not run or cache the separate official check, so its NOT RUN field
refers to that command's scope.

At acquisition, `kaggle competitions files gemma-4-developer-agent` returned
127 (CLI absent). Installed Kaggle 2.2.4 in an ignored, isolated CLI venv using
bundled Python 3.12.14. `.local/kaggle-cli/bin/kaggle --version` printed 2.2.4;
`.local/kaggle-cli/bin/kaggle competitions files gemma-4-developer-agent` returned
1 (API authentication required). Presence-only checks found no supported Kaggle
credential environment/file. No secret contents were printed or copied. Existing
Google sign-in in the dedicated Chrome tab restored Kaggle website access without
new credentials or terms. Per-file Download controls acquired the guide/starter
and five wheelhouse files; **Download all files was never used**. The browser's
download-event observer timed out once although HARNESS_README.md was successfully
saved; file size/hash and source contents confirmed acquisition. Notebook v2 Input
explorer supplied a second, byte-identical swegemma wheel. The temporary keep-awake
lease was stopped after browser acquisition.

CPU environment commands (from repository root):

```sh
/Users/hynk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m venv .local/cpu-checks
.local/cpu-checks/bin/python -m pip install --disable-pip-version-check --dry-run --only-binary=:all: --report .local/cpu-install-plan.json .local/official/wheels/adk_submission-0.2.11-py3-none-any.whl .local/official/wheels/google_adk-1.36.1-py3-none-any.whl .local/official/wheels/google_genai-2.11.0-py3-none-any.whl
.local/cpu-checks/bin/python -m pip install --disable-pip-version-check --only-binary=:all: --report .local/cpu-install-report.json .local/official/wheels/adk_submission-0.2.11-py3-none-any.whl .local/official/wheels/google_adk-1.36.1-py3-none-any.whl .local/official/wheels/google_genai-2.11.0-py3-none-any.whl
.local/cpu-checks/bin/python -m pip install --disable-pip-version-check --only-binary=:all: --report .local/cpu-extra-install-report.json .local/official/wheels/adk_eval_core-0.1.0-py3-none-any.whl 'litellm==1.83.14' networkx cachetools pandas
.local/cpu-checks/bin/python -m pip install --disable-pip-version-check --no-deps .local/official/wheels/swegemma-0.2.7-py3-none-any.whl
.local/cpu-checks/bin/python -m pip download --disable-pip-version-check --no-deps --only-binary=:all: --require-hashes -r .local/cpu-download-lock.txt -d .local/cpu-wheels
.local/cpu-checks/bin/python -m pip install --disable-pip-version-check --no-deps --require-hashes --only-binary=:all: -r docs/cpu-requirements.txt
.local/cpu-checks/bin/python -m pip check
```

Install/download commands exited 0; their stdout/stderr were retained in ignored
`.local/cpu-*.log` files. `pip check` exited 1 listing four deliberately omitted,
unused inference dependencies: accelerate, safetensors, torchvision, transformers.
This is a CPU-only import/check environment, not a complete inference installation.
The initial official checks were also invoked directly using sanitized `env -i`
Python heredocs before adding the reproducible script. They reported the same ten
files, model alias and two schema/adapter results. Only the final script additionally
checks installed official source bytes and generation constraints. No package
import result is being presented as model execution or hosted acceptance.

Python stdlib inspection used `zipfile` to check wheel member names/types and read
source/metadata without imports, `hashlib.sha256` on retained bytes, and `ast.parse`
to read the notebook's sampling string without executing cells. The later official
check imports only the inspected CPU validation path in its isolated environment.
There was one failed shell read from a nonmatching speculative validator filename;
actual package inventories were then used. No alternate generic schema was used.

Recommended next action: resolve the explicit no-LoRA variant choice in docs/r0.md
so the thin reproducible packager can be completed without silently changing R0.

---

# Historical PR #2 verification

2026-09-29 Asia/Seoul. Local execution: macOS, Python 3.9.6, standard library
only. No installed dependencies, model execution or paid services.

## Repository evidence

Initial cwd/root: `/Users/hynk/code/backtrace`; origin:
`https://github.com/hynk-studio/backtrace.git`. Local main was unborn, worktree had
no files, remote refs and GitHub branches were empty, and no existing PRs were
listed. Issue #1 was OPEN; no comments were returned. No repository/ancestor
AGENTS.md was found; the user-supplied global instructions applied.
GitHub reported `allow_auto_merge: false`.

The authorized exception created exactly one empty commit on main:
`2e0689eaf6fa23bb3de7d70832f3ee334b2e8180`. All substantive files belong to `bt-001-bootstrap`.
Final base/head/tree and Draft PR identity are reported in the PR/closeout rather
than embedded recursively in their own commit.

## Independent verification levels

| Level | Observed result |
| --- | --- |
| Local tooling tests | PASS: 18 unittest tests after the bounded allowlist correction, including adversarial synthetic ZIPs and mocked acquisition pin/overwrite checks. |
| Official requirements/starter acquired and pinned | PARTIAL: rendered primary pages inspected; complete notebook v2 source acquired/pinned and reacquired. Starter directory, harness guide/implementation and model bytes NOT ACQUIRED. |
| Candidate archive built and locally inspected | NOT RUN. Synthetic unit-test ZIPs are not candidates. |
| Official validator | NOT RUN: implementation/dependency bytes and starter missing. |
| Permitted end-to-end task | NOT RUN: no model/harness execution. |
| Kaggle submission accepted | NOT RUN: submission is not authorized. |
| Hosted scoring completed | NOT RUN. |

`preflight` reports local READY, official baseline BLOCKED. `baseline` returns
exit 2 with actionable missing-artifact instructions and no archive. Public
notebook acquisition returns version 2 and SHA-256
`0c54c3bac3269e422b1d48ac8087ff26b49fe764231b7983c90ef842382f9a87`;
reacquisition completed at `2026-09-28T19:56:09.575001+00:00`.

The first test run had one failed NUL-path fixture because Python's ZIP writer
truncates NUL filenames before serialization. The fixture was corrected by
mutating actual ZIP filename bytes; the inspector's truncation rejection then
passed. A subsequent metadata-rejection check raised the total from 14 to 15.
No official starter/validator test failures are claimed: those checks never ran.

## PR #2 bounded allowlist correction

Read the current instructions, Issue #1 and ChatGPT review before this repair.
The clean local branch and remote PR head matched reviewed commit
`c89bf82ef99e6596faa29e47c270e8f3c1f81a46`, tree
`285ce169d3e88a789556310782b5d32c0c027ef8`; there was no intervening work.

On local Python 3.9.6, new regressions reproduced the defect before the fix:
with either `notes.txt` or `Notes.txt` alone in a synthetic ZIP, the ambiguous
allowlist containing both names was accepted by the public function and the CLI
exited 0. The 18-test run reported four failing subtests. After rejecting distinct
allowlist names with the same canonical key and comparing exact member names for
completeness, both function cases raise `InspectionError` and both CLI cases exit
2. Ordinary exact allowlists still pass through both interfaces. Canonical keys
remain in use for archive aliases and file/directory collisions. Fixture bytes
remain unchanged, no files are extracted, and all existing safety tests pass.

Repair commands and observed results:

- `python3 -m unittest discover -s tests -v`: PASS, 18 tests after the fix.
- `python3 tools/backtrace.py preflight`: exit 0, local READY / official baseline BLOCKED.
- `python3 tools/backtrace.py baseline`: expected exit 2; no archive. A separate
  subprocess invocation in an empty temporary directory also left it empty.
- `git diff --check`: PASS.
- `git diff main...HEAD --check`: PASS.

These are Codex's Python 3.9.6 checks. The reviewer's independent Python 3.13.5
checks covered the original 15 tests and the reviewed source blobs, not this fix.
Notebook acquisition and Kaggle source inspection were not rerun during the
repair. All NOT RUN stages and missing-artifact limitations above remain intact.

## Exact inspection, acquisition and verification commands

Commands below were executed from the repository root (individual shell calls
sometimes batched commands with `&&`). File-authoring heredocs are not test or
execution evidence.

```sh
pwd
git remote -v
git status --short --branch
git branch -a
git ls-remote origin
rg --files -g AGENTS.md -g '!node_modules' -g '!vendor' .
git rev-parse --show-toplevel
git ls-remote --heads --tags origin
gh api repos/hynk-studio/backtrace --jq '{default_branch, size, allow_auto_merge}'
gh api repos/hynk-studio/backtrace/branches
ls -la
python3 --version
for p in /AGENTS.md /Users/AGENTS.md /Users/hynk/AGENTS.md /Users/hynk/code/AGENTS.md; do if test -f "$p"; then cat "$p"; fi; done
gh issue view 1 --repo hynk-studio/backtrace --json title,body,url,state
gh issue view 1 --repo hynk-studio/backtrace --comments
gh pr list --repo hynk-studio/backtrace --state all --json number,title,state,isDraft,url
git -c core.hooksPath=/dev/null commit --allow-empty -m 'chore: establish empty PR base'
git push origin main
git switch -c bt-001-bootstrap
python3 -m unittest discover -s tests -v
python3 tools/backtrace.py preflight
python3 tools/backtrace.py acquire-notebook .local/starter.ipynb
python3 tools/backtrace.py baseline
git diff --check
git status --short --ignored
git ls-tree main
git log --oneline --all
```

The initial `rg --files` returned exit 1 because there were no files, not because
an existing instruction was ignored. A focused memory lookup for Backtrace also
returned no matches; no project decisions were taken from another repository.

Source acquisition initially used Python `urllib.request.urlopen` with a
20-second timeout and a 2,000,001-byte bounded read for each URL in the manifest,
then `hashlib.sha256` on retained response bytes. HTML parsing exposed only page
titles. The public notebook API response was decoded with `json.loads`; the
`blob.source`/`sourceNullable` string was UTF-8 encoded unchanged and hashed.
The committed `acquire-notebook` command reproduces that source acquisition and
checks both version and source hash. It was executed successfully, independently
of mocked tests. No notebook cells were executed.

The web reader attempted all six Issue #1 URLs. Browser navigation then read the
rendered notebook, overview/model rules, rules, data description and welcome,
using accessibility snapshots or `#site-content` inner text. The data viewer
showed a sign-in/rules-agreement gate. No Join, agreement, submission or download
control for competition data was activated. The temporary browser tab was closed.
Browser-rendered content has no retained byte hash; downloaded HTML shell hashes
must not be used as hashes of that content. See the source manifest for exact
URLs, timestamps, identifiers and response-byte hashes.

## Limits and next action

ZIP checks are conservative local heuristics, not exhaustive secret detection or
official compliance. No binary adapter is permitted by this local inspector yet.
A caller allowlist needs independent provenance/content review; renaming or
encoding sensitive material can evade heuristic content checks. Source/terms
changes require reinspection. No claim of baseline performance, adapter
compatibility, synthetic competence or real-task transfer is supported.

Recommended next action: have the owner resolve Kaggle access/terms and obtain
`HARNESS_README.md`, `sample_submission/` and versioned harness packages for a
bounded contract-completion and R0 follow-up.
