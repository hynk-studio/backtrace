# Issue #1 implementation verification

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
| Local tooling tests | PASS: 15 unittest tests, including adversarial synthetic ZIPs and mocked acquisition pin/overwrite checks. |
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
