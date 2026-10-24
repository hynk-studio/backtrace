# Selected verifier and isolation preparation — 2026-10-24

Continues #1 and Draft #22 on `bt-001-research-verifier-prep-20261024`.
Final free CPU qualification is **BLOCKED by one original official verifier
conflict**. Linux 443 tests, all 18 isolated authored-response slots and every
isolation/deadline check pass. Five of six original baseline/reference pairs
qualify. All 18 real-model slots remain NOT RUN.

The six selected tasks, three archives, prompts and matched protocol stay fixed.
Each task receives two fresh official verifier executions: an unmodified baseline
and its original public reference patch. Only the root coordinator reads original
metadata; the reference patch enters only the positive control. Results require
actual JUnit, executed tests, matching pass/fail exit status and a verified import
from that sandbox's source checkout. Collection/setup errors remain infrastructure
failures, never unresolved model scores. The subprocess verifier skips package
installation; this wrapper performs an offline editable install as the evaluator
UID before the original test command. The separate evaluator dependency lock
adds no packages to the 143-package agent runtime.

Model-selected commands run as UID 65532, verifier commands as UID 65533. Trusted
coordinators, reference data and HTTP accounting remain root-owned. Every sandbox
has its own PID, network and proc-mount namespaces, dropped capabilities and
no-new-privileges. Local test servers may use sandbox loopback; a disconnected dummy device drops
outgoing packets so actual TCP connect-timeout tests retain their behavior; host gateway and
upstream loopback are unreachable from commands. File-copy tools refuse symlinks,
hardlinks and special files through descriptor-relative operations. These are
specific boundaries on a disposable Linux host, not a complete hostile-host
filesystem jail or a qualified GPU deployment image.

A timer begins at the official agent-session timestamp and terminates the PID
namespace when the 300-second allowance ends. Command timeouts cannot exceed the
remaining allowance. An independent 330-second child PID namespace bounds setup,
execution and cleanup, including detached descendants. Qualification uses actual
official command execution and deliberately shortened 0.5-second controls to
observe expiration without consuming five minutes per regression.

The CPU qualification loop has an independent 1,800-second deadline; exhausted
remaining cases are explicitly NOT_RUN. The 40-minute workflow bounds acquisition
and export as well. The new workflow records all six verifier pairs and all 18 isolated authored
runner fixtures. Public records contain counts, identities and checks; raw test
outputs and task material leave the host only encrypted to the existing owner
recipient. The original acquisition, runtime and runner evidence remains intact.

Initial actual run 40095255162 at e2c383470ee659974d1eb97a962e4f3acf1c7883
found three valid verifier pairs and three failures. Its full public receipt is
retained in `research-verifier-boundary-cpu-20261024.json`. The timeout probe
correctly rejected a command that never reached its marker; namespace entry had
changed the working directory. Explicitly restoring the workspace also corrects
the authored runner marker failures. The HTTPX editable backend needs the real
`editables` package. Four Requests timeout tests received network-unreachable
errors with loopback alone; the isolated sink uses genuine kernel TCP timeout
behavior without any external connection.

Rich `rich_3486` reveals a separate upstream verifier incompatibility. Its original
test patch adds complementary pre-3.11 and 3.11+ tests, each with its original
version skip. The official JUnit validator requires both added test names to pass.
On the frozen Python 3.12, actual pytest succeeds but the official verifier rejects
the intentionally skipped pre-3.11 test. Changing Python would skip the other
branch. Do not remove the skip, forge a passing test, weaken the original checker,
replace the selected task, or report this as a model failure. This selected slot
remains an explicit qualification blocker pending an agreed verifier/protocol
amendment. The original official verdict is preserved.

Earlier workflow parse failure 40094720185 ran no job. Run 40094763688 passed the
Linux suite but could not export root-owned receipts. Run 40094967033 retained
its failed dependency-acquisition evidence: the exact downloader required a
private directory. That directory and artifact ownership were corrected; the
minimal CPU runtime uses its pinned pip wheel for offline overlay installation.
Run 40096079939 at 87d449dbc2f3206f0a6d545b7883a5dd3ca2c863 passed all 18
isolated fixtures and all isolation/deadline controls. Its public receipt is
retained in `research-verifier-isolation-cpu-20261024.json`. An added negative-
control helper incorrectly inferred test identities from added `def` lines;
Rich's parameter-only test change demonstrates why that inference is invalid.
The final helper uses explicit F2P/P2P lists where provided, and the actual paired
original test-file contrast where these lists are absent. It never invents labels.
Two regressions cover parameter-only additions and failure-free negative controls.
The original official positive-control verdict is unchanged.

## Final observed execution

[CPU run 40096931090](https://github.com/hynk-studio/backtrace/actions/runs/40096931090)
executed source `5db450a8f22a991520f8d5ca3c98bad587a4f6ba`. Its overall workflow
conclusion remains **failure**, correctly keeping the six-task gate closed.
Linux passed **443 tests**; local focused tests passed **51**, plus CPU preflight
and the frozen protocol. The local full suite also encountered the already-known
host pip-wheel/procfs constraints; the native Linux run is the full-suite evidence.
The raw final report is `research-verifier-cpu-20261024.json`.

| Selected task | Baseline failures | Reference passes / skipped | Official reference verdict | Pair |
| --- | ---: | ---: | --- | --- |
| `requests_7309` | 5 | 207 / 13 | resolved | PASS |
| `rich_3486` | 1 | 20 / 1 | rejected version skip | FAIL |
| `httpx_3672` | 5 | 24 / 0 | resolved | PASS |
| `requests_7315` | 1 | 1 / 0 | resolved | PASS |
| `rich_3067` | 1 | 82 / 0 | resolved | PASS |
| `requests_7502` | 1 | 338 / 2 | resolved | PASS |

The 18 isolated fixtures used the same frozen candidate archives, six task asset
sets and 143-package CPU runtime. Every fixture completed and removed its sandbox;
108 HTTP attempts were authored CPU responses, not model inference. The separate
29-wheel evaluator overlay is byte-locked and retained. All 18 mechanism checks
passed, including actual official-command entry, deadline termination, detached
child cleanup, separate UIDs, host-loopback isolation and file-copy escape denial.
The 0.5-second active and outer controls returned in approximately 0.5 seconds;
these deliberately shortened controls exercise the fixed 300/330-second paths.

Owner-side independent inspection decrypted and checked all 242 private records,
12 JUnit hashes/counts, 18 patch hashes/sizes, 29 dependency wheels and all 11 final
operational source hashes. The 143 runtime wheel identities exactly match PR #22.
See `research-verifier-independent-check-20261024.json`. Public receipts and
owner-encrypted evidence from every retained stage are bundled separately.
The first export failure has only its original job log; no private archive was
exported in that failed run. The 53 unrelated historical branch heads and PR #22's
base e938c47af790585800921ef6cc66f792046f6651 are preserved.

Session termination destroys its command namespace. An already submitted patch
is retained; the official unsubmitted-diff fallback cannot execute afterward.
These fixtures cover completed submissions, not incomplete-patch recovery.
Full GPU image/model/cache identity and a finite 18-run lifecycle/cost proposal
remain separate gates. No GPU allocation, model run, training, merge, issue
closure or submission occurred. The version-skip amendment below remains inactive.


## Concrete amendment for review — not applied

The accompanying `research-verifier-skip-proposal-20261024.json` binds the original
test patch and the observed skipped function by SHA-256. A possible narrow
research-verifier amendment would permit only that original version-inapplicable
required node under Python 3.12.14. It must require all other applicable affected
tests to execute and pass, reject additional missing/error/skipped required nodes,
and retain the original official verdict separately. A baseline failure and
reference success for the applicable regression must be demonstrated again.

Before any model run, the owner would review this one exception and an explicit
new protocol revision applied equally to R0/R1/R2. No such exception or revision
is active in this PR. The six-task denominator and all 18 planned real-model slots
remain intact; reporting five tasks as the completed six-task experiment is not
permitted. This proposal changes neither source tests nor candidate prompts.

Owner evidence bundle: `backtrace-research-verifier-evidence-20261024.zip`, 13578990 bytes, SHA-256 `f98e75133720f480cdea5e9b0fcb0a4b38356faeb8e009e68c7747c2cbb68bca`.
